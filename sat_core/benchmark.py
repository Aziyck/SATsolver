"""
Generic benchmark engine.

A benchmark request says which problem(s) to generate, over which parameter
grid, and which solvers to run on every generated instance:

    {
      "problems": ["graph_coloring"],
      "segments": [{"graph_mode": "gnp", "nodes": "10,20", "probability": [0.1, 0.3], "colors": 3}],
      "solvers": [{"solver": "cdcl"}, {"solver": "walksat", "options": {"noise": 0.4}}],
      "repeats": 3,
      "timeout": 30,
      "rules": [{"solver": "dpll", "action": "cap", "min_variables": 200, "seconds": 10}],
      "seed": 1
    }

- A segment is one parameter grid. Sweepable fields may hold lists or range
  strings ("1..20", "0.1..0.5:0.1"); the cases are their cartesian product.
  Several segments let one benchmark cover grids that are not rectangular.
- Several graph problems may be listed together (a "graph suite"): they share
  the graph fields, so every problem sees exactly the same graphs.
- repeats re-run each case; repeat r > 1 derives a fresh seed from the case
  seed, so repeats are independent samples. Repeat 1 keeps the typed seed, so
  any row can be reproduced on the Solve page.
- The same solver may appear several times with different options (to
  compare heuristics); each entry gets its own label.
- rules cap the timeout of, or skip, a solver once the formula has at least
  min_variables variables (see ProblemInstance.size_variables).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
import io
import json
import time
from typing import Any, Iterable

from problems import get_problem
from problems.base import ProblemSpec
from sat_core.models import (
    STATUS_CANCELLED,
    STATUS_ERROR,
    STATUS_SAT,
    STATUS_SKIPPED,
    BenchmarkRow,
)
from sat_core.params import ParamError
from sat_core.runtime import (
    EVENT_CANCELLED,
    EVENT_LOG,
    EVENT_PLAN,
    EVENT_PROGRESS,
    EVENT_ROW,
    RunToken,
    cancel_requested,
    emit,
    skip_requested,
)
from sat_core.seeds import fresh_seed, repeat_seed
from sat_core.solver_registry import LOG_LEVELS, get_solver, options_summary, run_solver
from sat_core.verify import check_assignment


MAX_BENCHMARK_RUNS = 200_000
MAX_ROW_DECODED_CHARS = 16_000
DEFAULT_TIMEOUT = 30.0

# Default safety net for the recursive DPLL baseline on larger formulas.
# Presets and new benchmarks start with it; it can be edited or removed.
DPLL_FALLBACK_RULE = {"solver": "dpll", "action": "cap", "min_variables": 200, "seconds": 10.0}


@dataclass
class SolverRun:
    solver: str
    options: dict[str, Any]
    label: str

    def to_dict(self) -> dict[str, Any]:
        return {"solver": self.solver, "options": self.options, "label": self.label}


@dataclass
class LimitRule:
    solver: str
    action: str
    min_variables: int = 0
    seconds: float | None = None

    def matches(self, solver: str, size_variables: int) -> bool:
        return self.solver in ("*", solver) and size_variables >= self.min_variables

    def describe(self) -> str:
        who = "every solver" if self.solver == "*" else get_solver(self.solver).title
        when = f" when variables >= {self.min_variables}" if self.min_variables else ""
        if self.action == "skip":
            return f"skip {who}{when}"
        return f"cap {who} at {self.seconds:g} s{when}"

    def to_dict(self) -> dict[str, Any]:
        return {"solver": self.solver, "action": self.action, "min_variables": self.min_variables, "seconds": self.seconds}


@dataclass
class BenchmarkCase:
    index: int
    problem: str
    params: dict[str, Any]
    repeat: int
    segment: int
    label: str


@dataclass
class BenchmarkPlan:
    problems: list[str]
    cases: list[BenchmarkCase]
    solvers: list[SolverRun]
    rules: list[LimitRule]
    timeout: float | None
    repeats: int
    log_level: str
    seed: int
    title: str = ""
    normalized: dict[str, Any] = field(default_factory=dict)

    @property
    def total_runs(self) -> int:
        return len(self.cases) * len(self.solvers)

    def summary(self, sample: int = 20) -> dict[str, Any]:
        estimates = [estimate_case(case) for case in self.cases]
        known = [estimate for estimate in estimates if estimate]
        largest = max(known, key=lambda estimate: estimate["clauses"], default=None)
        return {
            "cases": len(self.cases),
            "runs": self.total_runs,
            "solvers": [solver.label for solver in self.solvers],
            "rules": [rule.describe() for rule in self.rules],
            "largest": largest,
            "total_clauses": sum(estimate["clauses"] for estimate in known) if known else None,
            "sample": [
                {"problem": case.problem, "label": case.label, "repeat": case.repeat, "estimate": estimates[index]}
                for index, case in enumerate(self.cases[:sample])
            ],
            "seed": self.seed,
        }


def estimate_case(case: BenchmarkCase) -> dict[str, int] | None:
    try:
        return get_problem(case.problem).estimate(case.params)
    except Exception:  # noqa: BLE001 - estimates are best effort
        return None


# ---------------------------------------------------------------------------
# Request parsing
# ---------------------------------------------------------------------------

def _prefixed(prefix: str, error: ParamError) -> ParamError:
    return ParamError({f"{prefix}.{name}": message for name, message in error.errors.items()})


def _parse_solvers(raw_solvers: Any) -> list[SolverRun]:
    if not isinstance(raw_solvers, list) or not raw_solvers:
        raise ParamError({"solvers": "select at least one solver"})
    runs = []
    for index, raw in enumerate(raw_solvers):
        if isinstance(raw, str):
            raw = {"solver": raw}
        if not isinstance(raw, dict) or "solver" not in raw:
            raise ParamError({f"solvers.{index}": "needs a solver key"})
        try:
            spec = get_solver(raw["solver"])
        except ValueError as exc:
            raise ParamError({f"solvers.{index}.solver": str(exc)}) from None
        try:
            options = spec.parse_options(raw.get("options"))
        except ParamError as exc:
            raise _prefixed(f"solvers.{index}.options", exc) from None
        runs.append(SolverRun(spec.key, options, str(raw.get("label") or "").strip()))

    # Give every entry a distinct label: "CDCL", or "CDCL (branching=MOMS)"
    # when the same solver appears more than once.
    counts: dict[str, int] = {}
    for run in runs:
        counts[run.solver] = counts.get(run.solver, 0) + 1
    seen: set[str] = set()
    for run in runs:
        spec = get_solver(run.solver)
        if not run.label:
            run.label = spec.title
            if counts[run.solver] > 1:
                run.label = f"{spec.title} ({options_summary(spec, run.options)})"
        base, suffix = run.label, 2
        while run.label in seen:
            run.label = f"{base} #{suffix}"
            suffix += 1
        seen.add(run.label)
    return runs


def _parse_rules(raw_rules: Any) -> list[LimitRule]:
    if raw_rules is None:
        return []
    if not isinstance(raw_rules, list):
        raise ParamError({"rules": "must be a list"})
    rules = []
    for index, raw in enumerate(raw_rules):
        prefix = f"rules.{index}"
        if not isinstance(raw, dict):
            raise ParamError({prefix: "must be an object"})
        solver = str(raw.get("solver", "*"))
        if solver != "*":
            try:
                solver = get_solver(solver).key
            except ValueError as exc:
                raise ParamError({f"{prefix}.solver": str(exc)}) from None
        action = raw.get("action", "cap")
        if action not in ("cap", "skip"):
            raise ParamError({f"{prefix}.action": "must be cap or skip"})
        try:
            min_variables = int(raw.get("min_variables") or 0)
        except (TypeError, ValueError):
            raise ParamError({f"{prefix}.min_variables": "must be a whole number"}) from None
        if min_variables < 0:
            raise ParamError({f"{prefix}.min_variables": "must not be negative"})
        seconds = raw.get("seconds")
        if action == "cap":
            try:
                seconds = float(seconds)
            except (TypeError, ValueError):
                raise ParamError({f"{prefix}.seconds": "a cap needs a time in seconds"}) from None
            if seconds < 0:
                raise ParamError({f"{prefix}.seconds": "must not be negative"})
        else:
            seconds = None
        rules.append(LimitRule(solver, action, min_variables, seconds))
    return rules


def _parse_timeout(raw: Any) -> float | None:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    try:
        timeout = float(raw)
    except (TypeError, ValueError):
        raise ParamError({"timeout": "must be a number of seconds"}) from None
    if timeout < 0:
        raise ParamError({"timeout": "must not be negative"})
    return timeout


def _graph_signature(spec: ProblemSpec, params: dict[str, Any]) -> str:
    graph_values = {field.name: params.get(field.name) for field in spec.fields if field.group == "graph"}
    return json.dumps(graph_values, sort_keys=True, default=str)


def parse_request(raw: dict[str, Any]) -> BenchmarkPlan:
    if not isinstance(raw, dict):
        raise ParamError({"_": "the benchmark request must be an object"})

    problem_keys = raw.get("problems") or ([raw["problem"]] if raw.get("problem") else [])
    if not isinstance(problem_keys, list) or not problem_keys:
        raise ParamError({"problems": "select a problem"})
    specs = []
    for key in problem_keys:
        try:
            specs.append(get_problem(key))
        except ValueError as exc:
            raise ParamError({"problems": str(exc)}) from None
    if len(specs) != len({spec.key for spec in specs}):
        raise ParamError({"problems": "each problem can be selected once"})
    if len(specs) > 1 and not all(spec.graph_based for spec in specs):
        raise ParamError({"problems": "only graph problems can be benchmarked together"})

    segments = raw.get("segments")
    if segments is None:
        segments = [raw.get("params") or {}]
    if not isinstance(segments, list) or not segments:
        raise ParamError({"segments": "add at least one parameter grid"})

    try:
        repeats = int(raw.get("repeats", 1))
    except (TypeError, ValueError):
        raise ParamError({"repeats": "must be a whole number"}) from None
    if repeats < 1 or repeats > 1000:
        raise ParamError({"repeats": "must be between 1 and 1000"})

    log_level = raw.get("log_level", "normal")
    if log_level not in LOG_LEVELS:
        raise ParamError({"log_level": f"must be one of {', '.join(LOG_LEVELS)}"})

    base_seed = raw.get("seed")
    if base_seed is None or (isinstance(base_seed, str) and not base_seed.strip()):
        base_seed = fresh_seed()
    try:
        base_seed = int(base_seed)
    except (TypeError, ValueError):
        raise ParamError({"seed": "must be a whole number"}) from None

    solvers = _parse_solvers(raw.get("solvers"))
    rules = _parse_rules(raw.get("rules"))
    timeout = _parse_timeout(raw.get("timeout", DEFAULT_TIMEOUT))

    cases: list[BenchmarkCase] = []
    for segment_index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            raise ParamError({f"segments.{segment_index}": "must be an object"})
        field_names = {field.name for spec in specs for field in spec.fields}
        unknown = [name for name in segment if name not in field_names]
        if unknown:
            raise ParamError({f"segments.{segment_index}.{name}": "unknown parameter" for name in unknown})

        # expanded[problem_index] = list of parameter dicts for that problem
        expanded = []
        for spec in specs:
            own = {name: value for name, value in segment.items() if any(f.name == name for f in spec.fields)}
            try:
                expanded.append(spec.expand(own))
            except ParamError as exc:
                raise _prefixed(f"segments.{segment_index}", exc) from None

        def with_seed(spec: ProblemSpec, params: dict[str, Any], repeat: int) -> dict[str, Any]:
            if not spec.has_visible_seed(params):
                return params
            seed = params.get("seed")
            seed = base_seed if seed is None else seed
            return {**params, "seed": repeat_seed(seed, repeat)}

        if len(specs) == 1:
            spec = specs[0]
            for params in expanded[0]:
                for repeat in range(1, repeats + 1):
                    case_params = with_seed(spec, params, repeat)
                    cases.append(BenchmarkCase(0, spec.key, case_params, repeat, segment_index, spec.case_label(case_params)))
        else:
            # Group by graph so every problem runs on a graph before moving on.
            groups: dict[str, list[tuple[int, dict[str, Any]]]] = {}
            for problem_index, spec in enumerate(specs):
                for params in expanded[problem_index]:
                    groups.setdefault(_graph_signature(spec, params), []).append((problem_index, params))
            for members in groups.values():
                for repeat in range(1, repeats + 1):
                    for problem_index, params in members:
                        spec = specs[problem_index]
                        case_params = with_seed(spec, params, repeat)
                        cases.append(BenchmarkCase(0, spec.key, case_params, repeat, segment_index, spec.case_label(case_params)))

        if len(cases) * len(solvers) > MAX_BENCHMARK_RUNS:
            raise ParamError({"_": f"more than {MAX_BENCHMARK_RUNS:,} solver runs; narrow the grid"})

    for index, case in enumerate(cases):
        case.index = index

    normalized = {
        "problems": [spec.key for spec in specs],
        "segments": segments,
        "solvers": [solver.to_dict() for solver in solvers],
        "repeats": repeats,
        "timeout": timeout,
        "rules": [rule.to_dict() for rule in rules],
        "log_level": log_level,
        "seed": base_seed,
        "title": str(raw.get("title") or ""),
    }
    return BenchmarkPlan(
        problems=[spec.key for spec in specs],
        cases=cases,
        solvers=solvers,
        rules=rules,
        timeout=timeout,
        repeats=repeats,
        log_level=log_level,
        seed=base_seed,
        title=str(raw.get("title") or ""),
        normalized=normalized,
    )


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------

def display_params(params: dict[str, Any], spec: ProblemSpec | None = None) -> dict[str, Any]:
    """
    Parameters for rows and exports: only fields visible for these values
    (no G(n,p) probability on a manual graph), without bulky payloads such as
    CNF text.
    """

    if spec is not None:
        visible = {field.name for field in spec.fields if field.visible(params)}
        params = {name: value for name, value in params.items() if name in visible}
    clean = {}
    for name, value in params.items():
        if isinstance(value, dict) and "text" in value:
            clean[name] = value.get("name") or f"{len(value['text'])} chars"
        else:
            clean[name] = value
    return clean


def _small(value: Any) -> Any:
    if value is None:
        return None
    try:
        text = json.dumps(value)
    except (TypeError, ValueError):
        return None
    return value if len(text) <= MAX_ROW_DECODED_CHARS else None


def limits_for(plan: BenchmarkPlan, solver: str, size_variables: int) -> tuple[bool, float | None, str | None]:
    """Return (skip, timeout, rule description) for one solver run."""

    timeout = plan.timeout
    applied = []
    for rule in plan.rules:
        if not rule.matches(solver, size_variables):
            continue
        if rule.action == "skip":
            return True, timeout, rule.describe()
        if timeout is None or rule.seconds < timeout:
            timeout = rule.seconds
            applied.append(rule.describe())
    return False, timeout, (applied[-1] if applied else None)


def _row(case, instance, spec, solver, index, **values) -> BenchmarkRow:
    defaults = dict(
        index=index,
        case_index=case.index,
        problem=case.problem,
        case_label=case.label,
        params=display_params(case.params, spec),
        repeat=case.repeat,
        solver=solver.solver,
        solver_label=solver.label,
        elapsed=0.0,
        variables=instance.variable_count if instance else 0,
        clauses=instance.clause_count if instance else 0,
        size_variables=instance.size_variables if instance else 0,
        expected=spec.expected_status(instance) if instance else None,
    )
    defaults.update(values)
    return BenchmarkRow(**defaults)


def run_benchmark(
    plan: BenchmarkPlan,
    event_callback=None,
    cancel_token: RunToken | None = None,
) -> list[BenchmarkRow]:
    rows: list[BenchmarkRow] = []
    total = plan.total_runs
    emit(
        event_callback,
        EVENT_PLAN,
        f"Benchmark: {len(plan.cases)} cases x {len(plan.solvers)} solvers = {total} runs",
        payload={"cases": len(plan.cases), "runs": total, "solvers": [solver.label for solver in plan.solvers]},
        current=0,
        total=total,
    )
    for rule in plan.rules:
        emit(event_callback, EVENT_LOG, f"Rule: {rule.describe()}")

    def add(row: BenchmarkRow) -> None:
        rows.append(row)
        emit(event_callback, EVENT_ROW, payload={"row": row.to_dict()}, current=len(rows), total=total)
        emit(event_callback, EVENT_PROGRESS, f"{len(rows)}/{total} runs", current=len(rows), total=total)

    for case in plan.cases:
        if cancel_requested(cancel_token):
            emit(event_callback, EVENT_CANCELLED, "Benchmark cancelled.", current=len(rows), total=total)
            return rows

        spec = get_problem(case.problem)
        prefix = f"[{case.index + 1}/{len(plan.cases)}]"
        repeat_text = f" repeat {case.repeat}" if plan.repeats > 1 else ""
        emit(event_callback, EVENT_LOG, f"{prefix} {spec.title}: {case.label}{repeat_text}")

        try:
            started = time.perf_counter()
            instance = spec.build(case.params)
            encode_seconds = time.perf_counter() - started
        except Exception as exc:  # noqa: BLE001 - one bad case must not stop the sweep
            message = str(exc) if isinstance(exc, ParamError) else f"{type(exc).__name__}: {exc}"
            emit(event_callback, EVENT_LOG, f"   encoding failed: {message}")
            for solver in plan.solvers:
                add(_row(case, None, spec, solver, len(rows), status=STATUS_ERROR, error=f"Encoding failed: {message}"))
            continue

        emit(
            event_callback,
            EVENT_LOG,
            f"   {instance.variable_count} variables, {instance.clause_count} clauses (encoded in {encode_seconds:.3f}s)",
        )

        for position, solver in enumerate(plan.solvers):
            if cancel_requested(cancel_token):
                emit(event_callback, EVENT_CANCELLED, "Benchmark cancelled.", current=len(rows), total=total)
                return rows

            if skip_requested(cancel_token):
                emit(event_callback, EVENT_LOG, "   skip requested: remaining runs of this case are SKIPPED")
                for skipped in plan.solvers[position:]:
                    add(_row(case, instance, spec, skipped, len(rows), status=STATUS_SKIPPED, rule="skipped by user"))
                cancel_token.clear_skip()
                break

            skip, timeout, rule_text = limits_for(plan, solver.solver, instance.size_variables)
            if skip:
                emit(event_callback, EVENT_LOG, f"   {solver.label}: skipped ({rule_text})")
                add(_row(case, instance, spec, solver, len(rows), status=STATUS_SKIPPED, rule=rule_text, timeout=timeout))
                continue

            result = run_solver(
                instance.clauses,
                solver.solver,
                solver.options,
                timeout=timeout,
                log_level=plan.log_level,
                event_callback=event_callback,
                cancel_token=cancel_token,
                label=solver.label,
            )
            if result.status == STATUS_CANCELLED:
                emit(event_callback, EVENT_CANCELLED, "Benchmark cancelled during a solver run.", current=len(rows), total=total)
                return rows

            verified = None
            check_errors: list[str] = []
            decoded = None
            if result.status == STATUS_SAT:
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

            add(
                _row(
                    case,
                    instance,
                    spec,
                    solver,
                    len(rows),
                    status=result.status,
                    elapsed=result.elapsed,
                    verified=verified,
                    check_errors=check_errors,
                    stats=result.stats,
                    timeout=timeout,
                    rule=rule_text,
                    error=result.error,
                    decoded=_small(decoded),
                )
            )

            if result.status == STATUS_SKIPPED:
                remaining = plan.solvers[position + 1:]
                if remaining:
                    emit(event_callback, EVENT_LOG, "   skip requested: remaining runs of this case are SKIPPED")
                for skipped in remaining:
                    add(_row(case, instance, spec, skipped, len(rows), status=STATUS_SKIPPED, rule="skipped by user"))
                if cancel_token is not None:
                    cancel_token.clear_skip()
                break

    return rows


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

STAT_COLUMNS = (
    "decisions",
    "conflicts",
    "propagations",
    "learned_clauses",
    "restarts",
    "tries",
    "flips",
    "best_unsatisfied",
)
BASE_COLUMNS = (
    "run",
    "case",
    "problem",
    "case_label",
    "repeat",
    "solver",
    "solver_label",
    "status",
    "expected",
    "verified",
    "elapsed",
    "variables",
    "clauses",
    "size_variables",
    "timeout",
    "rule",
)


def csv_columns(rows: Iterable[BenchmarkRow | dict[str, Any]]) -> tuple[list[str], list[str]]:
    """Parameter columns (in first-seen order) and all columns."""

    param_names: list[str] = []
    for row in rows:
        params = row.params if isinstance(row, BenchmarkRow) else row.get("params", {})
        for name in params:
            if name not in param_names:
                param_names.append(name)
    columns = list(BASE_COLUMNS[:4]) + param_names + list(BASE_COLUMNS[4:]) + list(STAT_COLUMNS) + ["error"]
    return param_names, columns


def rows_to_csv(rows: list[BenchmarkRow | dict[str, Any]], run_label: str = "") -> str:
    """One CSV format for every problem: base columns, one column per parameter, stats."""

    param_names, columns = csv_columns(rows)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        data = row.to_dict() if isinstance(row, BenchmarkRow) else row
        label = data.get("run_label", run_label)
        params = data.get("params", {})
        stats = data.get("stats", {})
        values = [label, data["case_index"] + 1, data["problem"], data["case_label"]]
        values += [_csv_value(params.get(name, "")) for name in param_names]
        values += [
            data["repeat"],
            data["solver"],
            data["solver_label"],
            data["status"],
            data.get("expected") or "",
            "" if data.get("verified") is None else data["verified"],
            f"{data['elapsed']:.6f}",
            data["variables"],
            data["clauses"],
            data.get("size_variables", ""),
            "" if data.get("timeout") is None else data["timeout"],
            data.get("rule") or "",
        ]
        values += [stats.get(name, "") for name in STAT_COLUMNS]
        values.append(data.get("error") or "")
        writer.writerow(values)
    return buffer.getvalue()


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, separators=(",", ":"))
    if value is None:
        return ""
    return value
