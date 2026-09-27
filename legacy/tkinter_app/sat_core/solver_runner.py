from __future__ import annotations

import time

from solvers.cdcl import cdcl
from solvers.dpll import dpll
from solvers.walksat import walksat
from sat_core.models import ProblemInstance, SolveResult
from sat_core.runtime import EVENT_LOG, RunToken, cancellation_status, emit, stop_requested


SOLVERS = ("CDCL", "DPLL", "WalkSAT", "ProbSAT")


def _canonical_solver_name(solver_name: str) -> str:
    key = solver_name.strip().upper()
    if key in ("PROBSAT", "PROB SAT"):
        return "ProbSAT"
    if key == "WALKSAT":
        return "WalkSAT"
    if key in ("CDCL", "DPLL"):
        return key
    return key


def _options_for_solver(solver_name: str, options: dict) -> dict:
    solver_options = dict(options)
    if solver_name == "CDCL":
        solver_options["random_seed"] = options.get("cdcl_random_seed", options.get("random_seed"))
    elif solver_name == "WalkSAT":
        for key in ("max_tries", "max_flips", "noise", "random_seed", "selection_mode", "adaptive_noise"):
            solver_key = f"walksat_{key}"
            if solver_key in options:
                solver_options[key] = options[solver_key]
    elif solver_name == "ProbSAT":
        for key in ("max_tries", "max_flips", "noise", "random_seed", "adaptive_noise"):
            probsat_key = f"probsat_{key}"
            walksat_key = f"walksat_{key}"
            if probsat_key in options:
                solver_options[key] = options[probsat_key]
            elif walksat_key in options:
                solver_options[key] = options[walksat_key]
        solver_options["selection_mode"] = "probsat"
    return solver_options


def solve_clauses(
    clauses: list[list[int]],
    solver_name: str,
    event_callback=None,
    cancel_token: RunToken | None = None,
    logging_options: dict | None = None,
    timeout_seconds: float | None = None,
) -> SolveResult:
    solver_name = _canonical_solver_name(solver_name)
    logging_options = logging_options or {}
    solver_logging_options = _options_for_solver(solver_name, logging_options)
    if timeout_seconds is not None:
        cancel_token = RunToken(timeout_seconds=timeout_seconds, parent=cancel_token)
    started = time.perf_counter()
    variables = {abs(lit) for clause in clauses for lit in clause}

    if stop_requested(cancel_token):
        status = cancellation_status(cancel_token)
        if status == "TIMEOUT":
            emit(event_callback, EVENT_LOG, f"{solver_name} timed out before starting.")
        elif status == "SKIPPED":
            emit(event_callback, EVENT_LOG, f"{solver_name} skipped before starting.")
        else:
            emit(event_callback, EVENT_LOG, f"{solver_name} cancelled before starting.")
        return SolveResult(
            solver=solver_name,
            status=status,
            elapsed=0.0,
            solution=None,
            stats={"elapsed": 0.0, "status": status},
            clauses=len(clauses),
            variables=len(variables),
        )

    emit(event_callback, EVENT_LOG, f"Solving with {solver_name}...")

    if solver_name == "CDCL":
        solution, stats = cdcl(
            clauses,
            return_stats=True,
            event_callback=event_callback,
            cancel_token=cancel_token,
            logging_options=solver_logging_options,
        )
        elapsed = stats.get("elapsed", time.perf_counter() - started)
        status = stats.get("status", "SAT" if solution is not None else "UNSAT")
    elif solver_name == "DPLL":
        solution, stats = dpll(
            clauses,
            cancel_token=cancel_token,
            return_stats=True,
            event_callback=event_callback,
            logging_options=solver_logging_options,
        )
        elapsed = stats.get("elapsed", time.perf_counter() - started)
        status = stats.get("status", "SAT" if solution is not None else "UNSAT")
    elif solver_name in ("WalkSAT", "ProbSAT"):
        solution, stats = walksat(
            clauses,
            return_stats=True,
            event_callback=event_callback,
            cancel_token=cancel_token,
            logging_options=solver_logging_options,
        )
        elapsed = stats.get("elapsed", time.perf_counter() - started)
        status = stats.get("status", "SAT" if solution is not None else "UNKNOWN")
    else:
        raise ValueError(f"Unknown solver: {solver_name}")

    stats.setdefault("timeout", timeout_seconds if timeout_seconds is not None else "-")
    stats.setdefault("solver_options", _solver_options_summary(solver_name, solver_logging_options))

    if status == "CANCELLED":
        emit(event_callback, EVENT_LOG, f"{solver_name} cancelled after {elapsed:.4f}s.")
    elif status == "TIMEOUT":
        emit(event_callback, EVENT_LOG, f"{solver_name} timed out after {elapsed:.4f}s.")
        stats_summary = _stats_summary(stats)
        if stats_summary:
            emit(event_callback, EVENT_LOG, f"{solver_name} stats: {stats_summary}")
    elif status == "SKIPPED":
        emit(event_callback, EVENT_LOG, f"{solver_name} skipped after {elapsed:.4f}s.")
        stats_summary = _stats_summary(stats)
        if stats_summary:
            emit(event_callback, EVENT_LOG, f"{solver_name} stats: {stats_summary}")
    else:
        emit(event_callback, EVENT_LOG, f"{solver_name} finished: {status} in {elapsed:.4f}s.")
        stats_summary = _stats_summary(stats)
        if stats_summary:
            emit(event_callback, EVENT_LOG, f"{solver_name} stats: {stats_summary}")

    return SolveResult(
        solver=solver_name,
        status=status,
        elapsed=elapsed,
        solution=solution,
        stats=stats,
        clauses=len(clauses),
        variables=len(variables),
    )


def solve_problem(
    problem: ProblemInstance,
    solver_name: str,
    event_callback=None,
    cancel_token: RunToken | None = None,
    logging_options: dict | None = None,
    timeout_seconds: float | None = None,
) -> SolveResult:
    result = solve_clauses(
        problem.clauses,
        solver_name,
        event_callback=event_callback,
        cancel_token=cancel_token,
        logging_options=logging_options,
        timeout_seconds=timeout_seconds,
    )
    result.decoded = problem.decode_solution(result.solution)
    return result


def _stats_summary(stats: dict) -> str:
    labels = [
        ("decisions", "decisions"),
        ("conflicts", "conflicts"),
        ("propagations", "propagations"),
        ("learned_clauses", "learned"),
        ("deleted_learned_clauses", "deleted learned"),
        ("avg_lbd", "avg LBD"),
        ("restarts", "restarts"),
        ("tries", "tries"),
        ("flips", "flips"),
        ("best_unsatisfied", "best unsatisfied"),
        ("selection_mode", "strategy"),
        ("adaptive_noise", "adaptive noise"),
        ("termination_reason", "reason"),
        ("final_noise", "final noise"),
        ("flip_make_total", "make"),
        ("flip_break_total", "break"),
    ]
    parts = [f"{label}={stats[key]}" for key, label in labels if key in stats]
    return ", ".join(parts)


def _solver_options_summary(solver_name: str, options: dict) -> str:
    if solver_name == "CDCL":
        return (
            f"branch={options.get('branching', 'VSIDS')}; "
            f"phase={options.get('initial_phase', 'Positive first')}; "
            f"restart={options.get('restart_interval') or '-'}; "
            f"learned_limit={options.get('learned_clause_limit') or '-'}; "
            f"seed={options.get('random_seed') or '-'}"
        )
    if solver_name in ("WalkSAT", "ProbSAT"):
        return (
            f"tries={options.get('max_tries', 10)}; "
            f"flips={options.get('max_flips', 10000)}; "
            f"noise={options.get('noise', 0.5)}; "
            f"strategy={options.get('selection_mode', 'probsat' if solver_name == 'ProbSAT' else 'walksat')}; "
            f"adaptive_noise={'on' if options.get('adaptive_noise') else 'off'}; "
            f"seed={options.get('random_seed') or '-'}"
        )
    return "DPLL small-clause"
