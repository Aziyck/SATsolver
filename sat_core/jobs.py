"""
Job entry points, run inside worker processes.

The web server starts one process per job with run_job(). A job reports
everything through RunEvent objects put on a multiprocessing queue:
logs, progress, the encoded instance, the solver result or benchmark rows,
and finally done / cancelled / error. Payloads are plain JSON-friendly dicts.

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
from sat_core.benchmark import display_params, parse_request, run_benchmark
from sat_core.dimacs import app_header_comment, save_dimacs
from sat_core.models import STATUS_SAT, ProblemInstance
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
from sat_core.solver_registry import LOG_LEVELS, get_solver, options_summary, run_solver
from sat_core.verify import check_assignment


JOB_KINDS = ("solve", "generate", "benchmark")
DEFAULT_SOLVE_TIMEOUT = 60.0

Emit = Callable[[RunEvent], None]


def instance_payload(spec: ProblemSpec, instance: ProblemInstance, encode_seconds: float, cnf_file: str | None) -> dict[str, Any]:
    return {
        "name": instance.name,
        "problem": spec.key,
        "params": display_params(instance.params, spec),
        "variables": instance.variable_count,
        "clauses": instance.clause_count,
        "size_variables": instance.size_variables,
        "max_variable": instance.max_variable,
        "facts": spec.describe(instance),
        "visual": spec.visual(instance),
        "expected": spec.expected_status(instance),
        "encode_seconds": round(encode_seconds, 6),
        "cnf_file": cnf_file,
    }


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


def _build_instance(request: dict[str, Any], workdir: str | None, emit_event: Emit):
    spec = get_problem(request.get("problem", ""))
    params = spec.resolve_seed(spec.parse(request.get("params")))
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
    emit_event(RunEvent(EVENT_INSTANCE, payload=instance_payload(spec, instance, encode_seconds, cnf_file)))
    return spec, instance


def generate_job(request: dict[str, Any], workdir: str | None, emit_event: Emit, token: RunToken) -> None:
    emit_event(RunEvent(EVENT_PROGRESS, "Encoding", current=0, total=1))
    _build_instance(request, workdir, emit_event)
    emit_event(RunEvent(EVENT_PROGRESS, "Encoded", current=1, total=1))


def solve_job(request: dict[str, Any], workdir: str | None, emit_event: Emit, token: RunToken) -> None:
    solver = get_solver(request.get("solver", "cdcl"))
    try:
        options = solver.parse_options(request.get("options"))
    except ParamError as exc:
        raise ParamError({f"options.{name}": message for name, message in exc.errors.items()}) from None
    timeout = request.get("timeout", DEFAULT_SOLVE_TIMEOUT)
    timeout = None if timeout in (None, "") else float(timeout)
    log_level = request.get("log_level", "normal")
    if log_level not in LOG_LEVELS:
        raise ParamError({"log_level": f"must be one of {', '.join(LOG_LEVELS)}"})

    emit_event(RunEvent(EVENT_PROGRESS, "Encoding", current=0, total=2))
    spec, instance = _build_instance(request, workdir, emit_event)
    if token.is_cancelled():
        return
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

    decoded = None
    verified = None
    check_errors: list[str] = []
    model_file = None
    if result.status == STATUS_SAT and result.solution is not None:
        verified = check_assignment(instance.clauses, result.solution)
        if not verified:
            check_errors.append("the model does not satisfy every clause")
        try:
            decoded = spec.decode(instance, result.solution)
            if decoded is not None:
                check_errors.extend(spec.check(instance, decoded))
        except Exception as exc:  # noqa: BLE001
            check_errors.append(f"decoding failed: {exc}")
        verified = verified and not check_errors
        model_file = write_model(workdir, result.solution)
        emit_event(
            RunEvent(
                EVENT_LOG,
                "Verified: every clause is satisfied" if verified else "Verification FAILED: " + "; ".join(check_errors[:3]),
            )
        )

    expected = spec.expected_status(instance)
    if expected and result.status in ("SAT", "UNSAT") and result.status != expected:
        emit_event(RunEvent(EVENT_LOG, f"Warning: expected {expected} for this generator, solver said {result.status}"))

    emit_event(
        RunEvent(
            EVENT_RESULT,
            payload={
                "solver": solver.key,
                "solver_label": solver.title,
                "options": options,
                "options_summary": options_summary(solver, options),
                "status": result.status,
                "elapsed": result.elapsed,
                "stats": result.stats,
                "decoded": decoded,
                "verified": verified,
                "check_errors": check_errors,
                "expected": expected,
                "timeout": timeout,
                "error": result.error,
                "model_file": model_file,
            },
        )
    )
    emit_event(RunEvent(EVENT_PROGRESS, f"Finished: {result.status}", current=2, total=2))


def benchmark_job(request: dict[str, Any], workdir: str | None, emit_event: Emit, token: RunToken) -> None:
    plan = parse_request(request)
    run_benchmark(plan, event_callback=emit_event, cancel_token=token)


JOB_FUNCTIONS = {"solve": solve_job, "generate": generate_job, "benchmark": benchmark_job}


def execute_job(kind: str, request: dict[str, Any], workdir: str | None, emit_event: Emit, token: RunToken) -> None:
    """Run a job in the current process and always finish with done/cancelled/error."""

    try:
        if kind not in JOB_FUNCTIONS:
            raise ValueError(f"Unknown job kind: {kind}")
        JOB_FUNCTIONS[kind](request, workdir, emit_event, token)
    except ParamError as exc:
        emit_event(RunEvent(EVENT_ERROR, str(exc), payload={"errors": exc.errors}))
        return
    except Exception as exc:  # noqa: BLE001 - reported to the UI
        emit_event(RunEvent(EVENT_ERROR, f"{type(exc).__name__}: {exc}", payload={"traceback": traceback.format_exc()}))
        return
    if token.is_cancelled():
        emit_event(RunEvent(EVENT_CANCELLED, "Cancelled."))
    else:
        emit_event(RunEvent(EVENT_DONE, "Finished."))


def run_job(kind: str, request: dict[str, Any], workdir: str | None, event_queue, cancel_event, skip_event) -> None:
    """Process target: bridge execute_job to a multiprocessing queue."""

    token = RunToken(cancel_event, skip_event=skip_event)
    execute_job(kind, request, workdir, event_queue.put, token)
