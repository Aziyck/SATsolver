"""
Solver registry.

Each SolverSpec declares its options as ParamFields (so the web UI can render
them) and knows how to call the underlying algorithm in solvers/. run_solver
is the single entry point used by jobs and benchmarks: it applies timeouts,
emits start/finish logs, turns solver exceptions into an ERROR status instead
of crashing the whole job, and strips bulky internals from the stats.
"""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Callable

from sat_core.models import (
    STATUS_CANCELLED,
    STATUS_ERROR,
    STATUS_SAT,
    STATUS_SKIPPED,
    STATUS_TIMEOUT,
    STATUS_UNKNOWN,
    STATUS_UNSAT,
    SolveResult,
)
from sat_core.params import Choice, ParamField, check_field_order, parse_params
from sat_core.runtime import EVENT_LOG, RunToken, cancellation_status, emit, stop_requested
from solvers.cdcl import cdcl
from solvers.dpll import dpll
from solvers.walksat import walksat


LOG_LEVELS = ("normal", "periodic", "debug")

Runner = Callable[[list[list[int]], dict[str, Any], dict[str, Any], Any, Any], tuple[Any, dict[str, Any]]]


@dataclass(frozen=True)
class SolverSpec:
    key: str
    title: str
    complete: bool
    summary: str
    description: str
    fields: tuple[ParamField, ...]
    runner: Runner
    progress_interval: int = 1000

    def parse_options(self, options: dict[str, Any] | None) -> dict[str, Any]:
        return parse_params(self.fields, options)

    def default_options(self) -> dict[str, Any]:
        return self.parse_options({})

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "complete": self.complete,
            "summary": self.summary,
            "description": self.description,
            "fields": [field.to_dict() for field in self.fields],
        }


# ---------------------------------------------------------------------------
# Option schemas
# ---------------------------------------------------------------------------

CDCL_BRANCHING = {
    "vsids": "VSIDS",
    "frequent": "Most frequent",
    "moms": "MOMS",
    "dlis": "DLIS",
    "random": "Random",
}
CDCL_PHASES = {
    "positive": "Positive first",
    "negative": "Negative first",
    "polarity": "Polarity based",
    "random": "Random",
}

CDCL_FIELDS = (
    ParamField(
        "branching",
        "Branching heuristic",
        "choice",
        default="vsids",
        choices=(
            Choice("vsids", "VSIDS", "Pick the most active variable; activity is bumped by conflicts."),
            Choice("frequent", "Most frequent", "Static: the variable with most occurrences."),
            Choice("moms", "MOMS", "Maximum occurrences in the shortest unresolved clauses."),
            Choice("dlis", "DLIS", "The literal that satisfies the most unresolved clauses."),
            Choice("random", "Random", "Uniform random unassigned variable (baseline)."),
        ),
        help="How CDCL chooses the next decision variable.",
    ),
    ParamField(
        "phase",
        "Initial phase",
        "choice",
        default="positive",
        choices=(
            Choice("positive", "Positive first", "Try True first (encoders use positive literals for choices)."),
            Choice("negative", "Negative first", "Try False first."),
            Choice("polarity", "Polarity based", "Use the more frequent polarity of each variable."),
            Choice("random", "Random", "Random value for every decision."),
        ),
        help="Value tried first for a decision; phase saving reuses the last value afterwards.",
    ),
    ParamField(
        "restarts",
        "Restarts",
        "bool",
        default=True,
        help="Now and then drop all decisions and start again, keeping learned clauses and scores.",
    ),
    ParamField(
        "restart_strategy",
        "Restart schedule",
        "choice",
        default="luby",
        choices=(
            Choice("luby", "Luby", "Restart after 1, 1, 2, 1, 1, 2, 4, ... times the interval: mostly short runs, a few long ones."),
            Choice("fixed", "Fixed", "Restart after the same number of conflicts every time."),
        ),
        show_if=(("restarts", (True,)),),
        advanced=True,
    ),
    ParamField(
        "restart_interval",
        "Restart interval",
        "int",
        default=100,
        minimum=1,
        unit="conflicts",
        help="Conflicts per restart (the unit of the Luby schedule).",
        show_if=(("restarts", (True,)),),
        advanced=True,
    ),
    ParamField(
        "clause_deletion",
        "Clean up learned clauses",
        "bool",
        default=True,
        help="Periodically delete half of the weak learned clauses (high LBD, long, unused) so propagation stays fast.",
        advanced=True,
    ),
    ParamField(
        "learned_limit",
        "Learned clause limit",
        "int",
        default=None,
        optional=True,
        minimum=1,
        placeholder="automatic",
        help="A fixed cap instead of the automatic cleanup: when exceeded, the weakest clauses are deleted down to half of it.",
        show_if=(("clause_deletion", (True,)),),
        advanced=True,
    ),
    ParamField(
        "random_seed",
        "Random seed",
        "seed",
        default=None,
        optional=True,
        placeholder="random",
        help="Makes Random branching and Random phase reproducible.",
        advanced=True,
    ),
)

_BUDGET_FIELDS = (
    ParamField(
        "max_tries",
        "Max tries",
        "int",
        default=10,
        minimum=1,
        maximum=1_000_000,
        help="Random restarts: each try starts again from a fresh random assignment.",
    ),
    ParamField(
        "max_flips",
        "Max flips per try",
        "int",
        default=100_000,
        minimum=1,
        maximum=1_000_000_000,
        help="Flips before giving up on a try. Tries x flips is the whole budget; then the answer is UNKNOWN.",
    ),
)
_LOCAL_SEARCH_SEED = ParamField(
    "random_seed",
    "Random seed",
    "seed",
    default=None,
    optional=True,
    placeholder="random",
    help="Makes the local search reproducible.",
    advanced=True,
)

WALKSAT_FIELDS = _BUDGET_FIELDS + (
    ParamField(
        "noise",
        "Noise",
        "float",
        default=0.567,
        minimum=0.0,
        maximum=1.0,
        step=0.05,
        help=(
            "When no free move exists, the probability of flipping a random variable of the clause "
            "instead of the one that breaks the fewest clauses. 0.567 works best on random 3-SAT."
        ),
    ),
    ParamField(
        "adaptive_noise",
        "Adaptive noise",
        "bool",
        default=False,
        help="Raise noise after stagnation, lower it again after a new best assignment.",
        advanced=True,
    ),
    _LOCAL_SEARCH_SEED,
)

PROBSAT_FIELDS = _BUDGET_FIELDS + (
    ParamField(
        "cb",
        "Break exponent cb",
        "float",
        default=None,
        optional=True,
        minimum=0.1,
        maximum=20.0,
        step=0.1,
        placeholder="automatic",
        help=(
            "How strongly low-break variables are preferred. Blank uses the published values: "
            "(0.9 + break)^-2.06 for 3-SAT, cb^-break with cb = 3.0 to 5.4 for longer clauses."
        ),
        advanced=True,
    ),
    _LOCAL_SEARCH_SEED,
)

# Kept for code that imported the old shared schema.
LOCAL_SEARCH_FIELDS = WALKSAT_FIELDS

for _fields in (CDCL_FIELDS, WALKSAT_FIELDS, PROBSAT_FIELDS):
    check_field_order(_fields)


# ---------------------------------------------------------------------------
# Runners: translate typed options into the solvers' option dicts
# ---------------------------------------------------------------------------

def _run_cdcl(clauses, options, log_options, event_callback, token):
    solver_options = dict(log_options)
    solver_options.update(
        {
            "branching": CDCL_BRANCHING[options["branching"]],
            "initial_phase": CDCL_PHASES[options["phase"]],
            "restarts": options["restarts"],
            "restart_strategy": options["restart_strategy"],
            "restart_interval": options["restart_interval"],
            "clause_deletion": options["clause_deletion"],
            "learned_clause_limit": options["learned_limit"] if options["clause_deletion"] else None,
            "random_seed": options["random_seed"],
        }
    )
    return cdcl(
        clauses,
        return_stats=True,
        event_callback=event_callback,
        cancel_token=token,
        logging_options=solver_options,
    )


def _run_dpll(clauses, options, log_options, event_callback, token):
    return dpll(
        clauses,
        cancel_token=token,
        return_stats=True,
        event_callback=event_callback,
        logging_options=dict(log_options),
    )


def _local_search_runner(selection_mode: str) -> Runner:
    def run(clauses, options, log_options, event_callback, token):
        solver_options = dict(log_options)
        solver_options.update(options)
        solver_options["selection_mode"] = selection_mode
        return walksat(
            clauses,
            return_stats=True,
            event_callback=event_callback,
            cancel_token=token,
            logging_options=solver_options,
        )

    return run


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_SOLVERS: dict[str, SolverSpec] = {}


def register_solver(spec: SolverSpec) -> SolverSpec:
    if spec.key in _SOLVERS:
        raise ValueError(f"Solver {spec.key} is already registered")
    check_field_order(spec.fields)
    _SOLVERS[spec.key] = spec
    return spec


def _normalise_key(name: str) -> str:
    return "".join(char for char in str(name).lower() if char.isalnum())


def get_solver(name: str) -> SolverSpec:
    key = _normalise_key(name)
    for spec in _SOLVERS.values():
        if key in (spec.key, _normalise_key(spec.title)):
            return spec
    raise ValueError(f"Unknown solver: {name}")


def all_solvers() -> list[SolverSpec]:
    return list(_SOLVERS.values())


register_solver(
    SolverSpec(
        key="cdcl",
        title="CDCL",
        complete=True,
        summary="Complete. Learns clauses from conflicts and backjumps; the strongest default.",
        description=(
            "Conflict-Driven Clause Learning: unit propagation with watched literals, First-UIP "
            "conflict analysis, learned clauses, non-chronological backjumping, VSIDS decisions, "
            "Luby restarts and periodic learned-clause cleanup. Proves both SAT and UNSAT."
        ),
        fields=CDCL_FIELDS,
        runner=_run_cdcl,
        progress_interval=2000,
    )
)
register_solver(
    SolverSpec(
        key="dpll",
        title="DPLL",
        complete=True,
        summary="Complete. The classic backtracking baseline, without learning.",
        description=(
            "Davis-Putnam-Logemann-Loveland: unit propagation plus branching on a variable from a "
            "shortest clause, with chronological backtracking (True first, then False). Proves "
            "SAT and UNSAT, but is much slower than CDCL on hard formulas because it never learns "
            "from a conflict."
        ),
        fields=(),
        runner=_run_dpll,
        progress_interval=2000,
    )
)
register_solver(
    SolverSpec(
        key="walksat",
        title="WalkSAT",
        complete=False,
        summary="Incomplete local search. Fast on large satisfiable formulas; UNKNOWN when no model is found.",
        description=(
            "WalkSAT/SKC: starts from a random assignment and repeatedly repairs a random unsatisfied "
            "clause. It flips a variable that breaks no other clause if there is one; otherwise a "
            "random variable of the clause (with probability noise) or the one that breaks the "
            "fewest clauses. Cannot prove UNSAT."
        ),
        fields=WALKSAT_FIELDS,
        runner=_local_search_runner("walksat"),
        progress_interval=5000,
    )
)
register_solver(
    SolverSpec(
        key="probsat",
        title="ProbSAT",
        complete=False,
        summary="Incomplete local search. Strong on random k-SAT; UNKNOWN when no model is found.",
        description=(
            "ProbSAT (Balint and Schoening): the same loop as WalkSAT, but the variable to flip is "
            "drawn at random with probability proportional to f(break), which falls steeply as "
            "break grows. No noise parameter. Cannot prove UNSAT."
        ),
        fields=PROBSAT_FIELDS,
        runner=_local_search_runner("probsat"),
        progress_interval=5000,
    )
)


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------

_STATS_SUMMARY_KEYS = (
    ("decisions", "decisions"),
    ("conflicts", "conflicts"),
    ("propagations", "propagations"),
    ("learned_clauses", "learned"),
    ("deleted_learned_clauses", "deleted learned"),
    ("avg_lbd", "avg LBD"),
    ("restarts", "restarts"),
    ("reductions", "cleanups"),
    ("max_depth", "max depth"),
    ("tries", "tries"),
    ("flips", "flips"),
    ("best_unsatisfied", "best unsatisfied"),
    ("termination_reason", "reason"),
    ("final_noise", "final noise"),
    ("free_flips", "free"),
    ("noise_flips", "noise"),
    ("greedy_flips", "greedy"),
)


def public_stats(stats: dict[str, Any]) -> dict[str, Any]:
    """Keep only small scalar statistics (drops best assignments, hit maps, ...)."""

    clean = {}
    for key, value in stats.items():
        if key.startswith("_") or key in ("status", "solver_options"):
            continue
        if isinstance(value, (bool, int, str)) or value is None:
            clean[key] = value
        elif isinstance(value, float):
            clean[key] = round(value, 6)
    return clean


def stats_summary(stats: dict[str, Any]) -> str:
    parts = []
    for key, label in _STATS_SUMMARY_KEYS:
        if key in stats and stats[key] is not None:
            value = stats[key]
            parts.append(f"{label}={value:.3g}" if isinstance(value, float) else f"{label}={value}")
    return ", ".join(parts)


def log_options_for(level: str, progress_interval: int) -> dict[str, Any]:
    if level not in LOG_LEVELS:
        raise ValueError(f"Unknown log level {level!r}; use one of {', '.join(LOG_LEVELS)}")
    if level == "normal":
        return {"mode": "normal"}
    return {
        "mode": level,
        "progress_interval": progress_interval,
        "verbose_limit": 300 if level == "debug" else 200,
    }


def options_summary(spec: SolverSpec, options: dict[str, Any]) -> str:
    """Compact description of the non-default options, e.g. "branching=MOMS; noise=0.3"."""

    defaults = spec.default_options()
    parts = []
    for field in spec.fields:
        value = options.get(field.name)
        if value == defaults.get(field.name) or not field.visible(options):
            continue
        if field.kind == "choice":
            value = next((choice.label for choice in field.choices if choice.value == value), value)
        elif isinstance(value, bool):
            value = "on" if value else "off"
        parts.append(f"{field.name}={value}")
    return "; ".join(parts) or "defaults"


def _error_message(solver: SolverSpec, exc: BaseException) -> str:
    if isinstance(exc, RecursionError):
        return (
            f"{solver.title} exceeded Python's recursion limit: this formula needs a deeper search "
            "tree than the recursive implementation supports. Try CDCL."
        )
    if isinstance(exc, MemoryError):
        return f"{solver.title} ran out of memory."
    return f"{solver.title} failed: {type(exc).__name__}: {exc}"


def run_solver(
    clauses: list[list[int]],
    solver: str,
    options: dict[str, Any] | None = None,
    *,
    timeout: float | None = None,
    log_level: str = "normal",
    progress_interval: int | None = None,
    event_callback=None,
    cancel_token: RunToken | None = None,
    label: str | None = None,
) -> SolveResult:
    """
    Run one solver on a CNF formula.

    timeout is in seconds (None means no limit, 0 times out immediately).
    The returned SolveResult never raises for solver-side failures; they come
    back as status ERROR with a readable message.
    """

    spec = get_solver(solver)
    parsed = spec.parse_options(options)
    name = label or spec.title
    token = RunToken(timeout_seconds=timeout, parent=cancel_token) if timeout is not None else cancel_token
    variables = len({abs(lit) for clause in clauses for lit in clause})

    def result(status, elapsed=0.0, solution=None, stats=None, error=None):
        return SolveResult(
            solver=spec.key,
            status=status,
            elapsed=elapsed,
            solution=solution,
            stats=stats or {},
            clauses=len(clauses),
            variables=variables,
            error=error,
        )

    if stop_requested(token):
        status = cancellation_status(token)
        emit(event_callback, EVENT_LOG, f"{name} {_status_phrase(status)} before starting.")
        return result(status)

    emit(event_callback, EVENT_LOG, f"Solving with {name}...")
    log_options = log_options_for(log_level, progress_interval or spec.progress_interval)
    started = time.perf_counter()
    try:
        solution, raw_stats = spec.runner(clauses, parsed, log_options, event_callback, token)
    except Exception as exc:  # noqa: BLE001 - reported as an ERROR status
        elapsed = time.perf_counter() - started
        message = _error_message(spec, exc)
        emit(event_callback, EVENT_LOG, f"{name} error after {elapsed:.4f}s: {message}")
        return result(STATUS_ERROR, elapsed, error=message)

    elapsed = raw_stats.get("elapsed", time.perf_counter() - started)
    default_status = STATUS_SAT if solution is not None else (STATUS_UNSAT if spec.complete else STATUS_UNKNOWN)
    status = raw_stats.get("status") or default_status
    stats = public_stats(raw_stats)

    if status in (STATUS_CANCELLED, STATUS_TIMEOUT, STATUS_SKIPPED):
        emit(event_callback, EVENT_LOG, f"{name} {_status_phrase(status)} after {elapsed:.4f}s.")
    else:
        emit(event_callback, EVENT_LOG, f"{name} finished: {status} in {elapsed:.4f}s.")
    summary = stats_summary(stats)
    if summary and status != STATUS_CANCELLED:
        emit(event_callback, EVENT_LOG, f"{name} stats: {summary}")

    if status != STATUS_SAT:
        solution = None
    return result(status, elapsed, solution, stats)


def _status_phrase(status: str) -> str:
    return {
        STATUS_TIMEOUT: "timed out",
        STATUS_SKIPPED: "skipped",
        STATUS_CANCELLED: "cancelled",
    }.get(status, status.lower())
