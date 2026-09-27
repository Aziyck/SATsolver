"""
Complete DPLL SAT solver.

The procedure searches the space of partial truth assignments for a CNF
formula. At each node it first applies unit propagation, then chooses an
unassigned variable and recursively explores the two possible truth values.
Unlike local-search solvers, DPLL can prove both SAT and UNSAT.
"""

from __future__ import annotations

import time

from sat_core.runtime import EVENT_LOG, cancellation_status, emit, stop_requested


def _unit_propagate(clauses, assignment):
    """
    Apply the unit-clause rule until no unit clause remains.

    Mathematically, if a clause has only one literal left, every satisfying
    extension of the current partial assignment must make that literal true.
    The function returns a simplified formula, or None when a contradiction is
    found.
    """
    changed = True

    while changed:
        changed = False

        for clause in clauses:
            if len(clause) != 1:
                continue

            lit = clause[0]
            var = abs(lit)
            value = lit > 0

            if var in assignment:
                if assignment[var] != value:
                    return None
                continue

            assignment[var] = value
            changed = True
            new_clauses = []

            # Simplify the CNF under the forced literal:
            # satisfied clauses disappear, and the opposite literal is removed
            # from clauses where it is now false.
            for current in clauses:
                if lit in current:
                    continue

                if -lit in current:
                    new_clause = [item for item in current if item != -lit]
                    if not new_clause:
                        return None
                    new_clauses.append(new_clause)
                else:
                    new_clauses.append(current)

            clauses = new_clauses
            break

    return clauses, assignment


def _choose_variable_small_clause(clauses, assignment):
    """
    Branch on an unassigned variable from a shortest remaining clause.

    Short clauses are closer to becoming unit or conflicting, so this simple
    heuristic often exposes contradictions earlier than an arbitrary choice.
    """
    for clause in sorted(clauses, key=len):
        for lit in clause:
            var = abs(lit)
            if var not in assignment:
                return var
    return None


def dpll(
    clauses,
    assignment=None,
    choose_var_fn=None,
    cancel_token=None,
    return_stats=False,
    event_callback=None,
    logging_options=None,
    _stats=None,
    _started=None,
    _level=0,
):
    """
    Recursive DPLL SAT solver.

    clauses is a CNF formula represented as a list of clauses, and assignment
    is the current partial model. The recursion corresponds to a binary search
    tree whose levels are decisions on variables.

    Return:
    - dict {variable: True/False} if SAT
    - None if UNSAT
    - (solution, stats) when return_stats=True
    """
    top_call = _stats is None
    if _stats is None:
        _stats = {
            "status": "UNKNOWN",
            "decisions": 0,
            "propagations": 0,
            "conflicts": 0,
            "elapsed": 0.0,
            "_verbose_emitted": 0,
            "_last_progress_work": 0,
        }
    if _started is None:
        _started = time.perf_counter()

    logging_options = logging_options or {}
    log_mode = logging_options.get("mode", "normal")
    if log_mode not in ("normal", "periodic", "debug"):
        log_mode = "normal"

    def positive_int(value, default):
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return default

    progress_interval = positive_int(logging_options.get("progress_interval"), 100)
    verbose_limit = positive_int(logging_options.get("verbose_limit"), 120)

    def public_stats():
        return {key: value for key, value in _stats.items() if not key.startswith("_")}

    def finish(solution, status):
        if status in ("CANCELLED", "TIMEOUT", "SKIPPED") or top_call:
            _stats["status"] = status
        if top_call:
            _stats["elapsed"] = time.perf_counter() - _started
            if return_stats:
                return solution, public_stats()
        return solution

    def log_debug(message):
        if log_mode != "debug" or _stats["_verbose_emitted"] >= verbose_limit:
            return
        _stats["_verbose_emitted"] += 1
        emit(event_callback, EVENT_LOG, f"      DPLL debug: level {_level}: {message}")

    def log_progress(force=False):
        if log_mode not in ("periodic", "debug"):
            return

        work = _stats["decisions"] + _stats["conflicts"] + _stats["propagations"]
        if not force and work - _stats["_last_progress_work"] < progress_interval:
            return

        _stats["_last_progress_work"] = work
        emit(
            event_callback,
            EVENT_LOG,
            (
                "      DPLL progress: "
                f"decisions={_stats['decisions']}, "
                f"conflicts={_stats['conflicts']}, "
                f"propagations={_stats['propagations']}"
            ),
        )

    if stop_requested(cancel_token):
        return finish(None, cancellation_status(cancel_token))

    if assignment is None:
        assignment = {}

    choose_var_fn = choose_var_fn or _choose_variable_small_clause

    # First close the current branch under all logically forced assignments.
    # A conflict here means the branch cannot be extended to a model.
    before_propagation = len(assignment)
    result = _unit_propagate(clauses, assignment.copy())

    if result is None:
        _stats["conflicts"] += 1
        log_debug("conflict during unit propagation")
        log_progress()
        return finish(None, "UNSAT")

    if stop_requested(cancel_token):
        return finish(None, cancellation_status(cancel_token))

    clauses, assignment = result
    propagated = max(0, len(assignment) - before_propagation)
    if propagated:
        _stats["propagations"] += propagated
        log_debug(f"unit propagation assigned {propagated} variable(s)")
        log_progress()

    if not clauses:
        return finish(assignment, "SAT")

    var = choose_var_fn(clauses, assignment)
    if var is None:
        return finish(assignment, "SAT")

    # No more forced moves are available, so DPLL makes a decision and tries
    # both truth values. Chronological backtracking happens through recursion:
    # if the first branch fails, control returns here and the second is tried.
    _stats["decisions"] += 1
    log_debug(f"choose variable {var}")
    log_progress()

    for value in (True, False):
        if stop_requested(cancel_token):
            return finish(None, cancellation_status(cancel_token))

        new_assignment = assignment.copy()
        new_assignment[var] = value
        log_debug(f"try {var}={value}")

        lit = var if value else -var
        new_clauses = []
        branch_conflict = False

        # Simplify the formula under the decision literal before recursing.
        # Producing an empty clause is exactly a falsified CNF constraint.
        for clause in clauses:
            if lit in clause:
                continue

            if -lit in clause:
                new_clause = [item for item in clause if item != -lit]

                if not new_clause:
                    branch_conflict = True
                    _stats["conflicts"] += 1
                    log_debug(f"empty clause after {var}={value}")
                    log_progress()
                    break

                new_clauses.append(new_clause)
            else:
                new_clauses.append(clause)

        if not branch_conflict:
            result = dpll(
                new_clauses,
                new_assignment,
                choose_var_fn,
                cancel_token=cancel_token,
                return_stats=False,
                event_callback=event_callback,
                logging_options=logging_options,
                _stats=_stats,
                _started=_started,
                _level=_level + 1,
            )

            if stop_requested(cancel_token):
                return finish(None, cancellation_status(cancel_token))

            if result is not None:
                return finish(result, "SAT")

        log_debug(f"backtrack on {var}={value}")

    return finish(None, "UNSAT")
