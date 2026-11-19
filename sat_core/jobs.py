"""
Job entry points, run inside worker processes.

The web server starts one process per job with run_job(). A job reports
everything through RunEvent objects put on a multiprocessing queue:
logs, progress, the encoded instance, the solver result or benchmark rows,
and finally done / cancelled / error. Payloads are plain JSON-friendly dicts;
the instance and result payloads are built as InstanceSummary and SolveOutcome
(sat_core/models.py) and sent through their to_dict().

Large artifacts are written to the job's work directory instead of being
sent through the queue: instance.cnf (DIMACS, with a "c wizsat" header so it
can be reopened) and model.txt (the satisfying assignment, if any).
"""

from __future__ import annotations

from pathlib import Path
import time
import traceback
from typing import Any, Callable

from problems import get_problem
from problems.base import ProblemSpec
from sat_core.answers import judge_answer
from sat_core.benchmark import display_params, parse_request, parse_timeout, run_benchmark
from sat_core.dimacs import app_header_comment, save_dimacs
from sat_core.models import STATUS_CANCELLED, InstanceSummary, ProblemInstance, SolveOutcome
from sat_core.params import ParamError
from sat_core.runtime import (
    EVENT_CANCELLED,
    EVENT_DONE,
    EVENT_ERROR,
    EVENT_INSTANCE,
    EVENT_LOG,
    EVENT_PROGRESS,
    EVENT_RESULT,
    RunEvent,
    RunToken,
)
from sat_core.solver_registry import LOG_LEVELS, SolverSpec, get_solver, options_summary, run_solver


JOB_KINDS = ("solve", "generate", "benchmark")
DEFAULT_SOLVE_TIMEOUT = 60.0

Emit = Callable[[RunEvent], None]


def lookup_problem(key: str | None) -> ProblemSpec:
    """The registered problem for a request, or a ParamError naming the "problem" field."""

    try:
        return get_problem(key or "")
    except ValueError as exc:
        raise ParamError({"problem": str(exc)}) from None


def visible_params(spec: ProblemSpec, params: dict[str, Any]) -> dict[str, Any]:
    """The parameters a problem actually uses; a hidden field is not stored with the job."""

    return {field.name: params[field.name] for field in spec.fields if field.visible(params) and field.name in params}


def parse_problem_request(raw: dict[str, Any]) -> tuple[ProblemSpec, dict[str, Any], dict[str, Any]]:
    """
    Check the problem half of a job request (encode and solve jobs).

    Returns the problem, its full parameters (a blank seed made concrete, so
    the instance can be rebuilt) and the normalized request: the problem key
    and the visible parameters.
    """

    spec = lookup_problem(raw.get("problem"))
    params = spec.resolve_seed(spec.parse(raw.get("params")))
    spec.check_size(params)
    return spec, params, {"problem": spec.key, "params": visible_params(spec, params)}


def _parse_solve(raw: dict[str, Any]) -> tuple[ProblemSpec, dict[str, Any], SolverSpec, dict[str, Any]]:
    spec, params, normalized = parse_problem_request(raw)
    try:
        solver = get_solver(raw.get("solver") or "cdcl")
    except ValueError as exc:
        raise ParamError({"solver": str(exc)}) from None
    try:
        options = solver.parse_options(raw.get("options"))
    except ParamError as exc:
        raise ParamError({f"options.{name}": message for name, message in exc.errors.items()}) from None
    log_level = raw.get("log_level") or "normal"
    if log_level not in LOG_LEVELS:
        raise ParamError({"log_level": f"must be one of {', '.join(LOG_LEVELS)}"})
    normalized.update(
        solver=solver.key,
        options=options,
        timeout=parse_timeout(raw.get("timeout", DEFAULT_SOLVE_TIMEOUT)),
        log_level=log_level,
    )
    return spec, params, solver, normalized


def parse_solve_request(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Check a solve request and return it normalized: problem, visible
    parameters, solver, parsed options, timeout and log level.

    The API calls this before it stores a job and solve_job parses the stored
    request again when the job runs, so a script that runs a job directly is
    refused the same things. A normalized request parses to itself. Raises
    ParamError with the field names the UI shows: options.<name>, timeout,
    log_level, solver, problem and the problem's own parameters.
    """

    return _parse_solve(raw)[3]


def instance_summary(spec: ProblemSpec, instance: ProblemInstance, encode_seconds: float, cnf_file: str | None) -> InstanceSummary:
    return InstanceSummary(
        name=instance.name,
        problem=spec.key,
        params=display_params(instance.params, spec),
        variables=instance.variable_count,
        clauses=instance.clause_count,
        size_variables=instance.size_variables,
        max_variable=instance.max_variable,
        facts=spec.describe(instance),
        visual=spec.visual(instance),
        expected=spec.expected_status(instance),
        encode_seconds=round(encode_seconds, 6),
        cnf_file=cnf_file,
    )


def write_cnf(workdir: str | None, spec: ProblemSpec, instance: ProblemInstance) -> str | None:
    if not workdir:
        return None
    comments = [instance.name, f"{instance.variable_count} variables, {instance.clause_count} clauses"]
    if spec.key != "dimacs":
        # Lets the UI reopen this file as the problem it was generated from.
        comments.append(app_header_comment(spec.key, display_params(instance.params, spec)))
    path = Path(workdir) / "instance.cnf"
    save_dimacs(path, instance.clauses, comments)
    return path.name


def write_model(workdir: str | None, solution: dict[int, bool]) -> str | None:
    if not workdir:
        return None
    path = Path(workdir) / "model.txt"
    literals = [variable if value else -variable for variable, value in sorted(solution.items())]
    lines = ["s SATISFIABLE"]
    for start in range(0, len(literals), 20):
        lines.append("v " + " ".join(str(lit) for lit in literals[start:start + 20]))
    lines.append("v 0")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path.name


def _build_instance(spec: ProblemSpec, params: dict[str, Any], workdir: str | None, emit_event: Emit) -> ProblemInstance:
    emit_event(RunEvent(EVENT_LOG, f"Encoding {spec.title}: {spec.case_label(params) or 'default parameters'}"))
    started = time.perf_counter()
    instance = spec.build(params)
    encode_seconds = time.perf_counter() - started
    emit_event(
        RunEvent(
            EVENT_LOG,
            f"Encoded {instance.variable_count} variables and {instance.clause_count} clauses in {encode_seconds:.3f}s",
        )
    )
    cnf_file = write_cnf(workdir, spec, instance)
    emit_event(RunEvent(EVENT_INSTANCE, payload=instance_summary(spec, instance, encode_seconds, cnf_file).to_dict()))
    return instance


def generate_job(request: dict[str, Any], workdir: str | None, emit_event: Emit, token: RunToken) -> bool:
    spec, params, _ = parse_problem_request(request)
    emit_event(RunEvent(EVENT_PROGRESS, "Encoding", current=0, total=1))
    _build_instance(spec, params, workdir, emit_event)
    emit_event(RunEvent(EVENT_PROGRESS, "Encoded", current=1, total=1))
    return True


def solve_job(request: dict[str, Any], workdir: str | None, emit_event: Emit, token: RunToken) -> bool:
    spec, params, solver, parsed = _parse_solve(request)
    options, timeout, log_level = parsed["options"], parsed["timeout"], parsed["log_level"]

    emit_event(RunEvent(EVENT_PROGRESS, "Encoding", current=0, total=2))
    instance = _build_instance(spec, params, workdir, emit_event)
    if token.is_cancelled():
        return False
    emit_event(RunEvent(EVENT_PROGRESS, f"Solving with {solver.title}", current=1, total=2))

    result = run_solver(
        instance.clauses,
        solver.key,
        options,
        timeout=timeout,
        log_level=log_level,
        event_callback=emit_event,
        cancel_token=token,
    )

    verdict = judge_answer(spec, instance, result)
    model_file = None
    if verdict.verified is not None:
        model_file = write_model(workdir, result.solution)
        emit_event(
            RunEvent(
                EVENT_LOG,
                "Verified: every clause is satisfied"
                if verdict.verified
                else "Verification FAILED: " + "; ".join(verdict.errors[:3]),
            )
        )

    expected = spec.expected_status(instance)
    if expected and result.status in ("SAT", "UNSAT") and result.status != expected:
        emit_event(RunEvent(EVENT_LOG, f"Warning: expected {expected} for this generator, solver said {result.status}"))

    emit_event(
        RunEvent(
            EVENT_RESULT,
            payload=SolveOutcome(
                solver=solver.key,
                solver_label=solver.title,
                options=options,
                options_summary=options_summary(solver, options),
                status=result.status,
                elapsed=result.elapsed,
                stats=result.stats,
                decoded=verdict.decoded,
                verified=verdict.verified,
                check_errors=verdict.errors,
                expected=expected,
                timeout=timeout,
                error=result.error,
                model_file=model_file,
            ).to_dict(),
        )
    )
    emit_event(RunEvent(EVENT_PROGRESS, f"Finished: {result.status}", current=2, total=2))
    # The solver reports a Stop during the search as a CANCELLED result.
    return result.status != STATUS_CANCELLED


def benchmark_job(request: dict[str, Any], workdir: str | None, emit_event: Emit, token: RunToken) -> bool:
    plan = parse_request(request)
    # run_benchmark returns normally after a Stop, with the rows it finished.
    return len(run_benchmark(plan, event_callback=emit_event, cancel_token=token)) == plan.total_runs


JOB_FUNCTIONS = {"solve": solve_job, "generate": generate_job, "benchmark": benchmark_job}


def execute_job(kind: str, request: dict[str, Any], workdir: str | None, emit_event: Emit, token: RunToken) -> None:
    """Run a job in the current process and always finish with done/cancelled/error.

    A job body returns True when it did all its work, and the job then ends
    done even if a Stop arrived after the work was finished (audit item A18).
    """

    try:
        if kind not in JOB_FUNCTIONS:
            raise ValueError(f"Unknown job kind: {kind}")
        completed = JOB_FUNCTIONS[kind](request, workdir, emit_event, token)
    except ParamError as exc:
        emit_event(RunEvent(EVENT_ERROR, str(exc), payload={"errors": exc.errors}))
        return
    except Exception as exc:  # noqa: BLE001 - reported to the UI
        emit_event(RunEvent(EVENT_ERROR, f"{type(exc).__name__}: {exc}", payload={"traceback": traceback.format_exc()}))
        return
    if completed:
        emit_event(RunEvent(EVENT_DONE, "Finished."))
    else:
        emit_event(RunEvent(EVENT_CANCELLED, "Cancelled."))


def run_job(kind: str, request: dict[str, Any], workdir: str | None, event_queue, cancel_event, skip_event) -> None:
    """Process target: bridge execute_job to a multiprocessing queue."""

    from sat_core.parallel import exit_when_parent_dies

    exit_when_parent_dies()
    token = RunToken(cancel_event, skip_event=skip_event)
    execute_job(kind, request, workdir, event_queue.put, token)
