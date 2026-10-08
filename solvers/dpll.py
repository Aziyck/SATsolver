"""
Complete DPLL SAT solver (iterative).

DPLL searches the space of partial truth assignments for a CNF formula. It
repeatedly applies unit propagation, then chooses an unassigned variable,
tries True first and, if that branch fails, False. When both values of the
most recent decision have failed, it backtracks chronologically to the
decision before. Unlike local-search solvers, DPLL can prove both SAT and
UNSAT.

This version makes exactly the same decisions as the original recursive one
(kept in legacy/dpll_recursive.py) but works differently inside:

- an explicit decision stack replaces recursion, so deep searches cannot hit
  Python's recursion limit;
- the formula is never copied. Instead every clause keeps two counters (how
  many of its literals are true, how many are false), updated when a literal
  is assigned and restored when it is unassigned. A clause with no true
  literal and one free literal is unit; with no free literal it is a
  conflict.

docs/algorithms/dpll.md walks through an example.
"""

from __future__ import annotations

import time

from sat_core.runtime import EVENT_LOG, cancellation_status, emit, stop_requested


# Cancel/timeout checks happen every CHECK_EVERY clause updates (see cdcl.py).
CHECK_EVERY = 2048


def _normalise_formula(clauses):
    """Drop zeros, repeated literals and tautologies; collect the variables."""
    clean_clauses = []
    variables = set()
    has_empty_clause = False
    for clause in clauses:
        seen = set()
        clean = []
        tautology = False
        for lit in clause:
            lit = int(lit)
            if lit == 0:
                continue
            variables.add(abs(lit))
            if -lit in seen:
                tautology = True
                continue
            if lit not in seen:
                seen.add(lit)
                clean.append(lit)
        if tautology:
            continue
        if clean:
            clean_clauses.append(clean)
        else:
            has_empty_clause = True
    return clean_clauses, sorted(variables), has_empty_clause


def dpll(
    clauses,
    assignment=None,
    choose_var_fn=None,
    cancel_token=None,
    return_stats=False,
    event_callback=None,
    logging_options=None,
):
    """
    Iterative DPLL SAT solver.

    clauses is a CNF formula (a list of lists of non-zero ints). assignment
    may fix some variables up front. choose_var_fn(remaining_clauses,
    assignment) can replace the built-in branching rule; it receives the
    simplified formula (satisfied clauses removed, false literals dropped).

    Return:
    - dict {variable: True/False} if SAT
    - None if UNSAT
    - (solution, stats) when return_stats=True
    """
    started = time.perf_counter()
    stats = {
        "status": "UNKNOWN",
        "decisions": 0,
        "propagations": 0,
        "conflicts": 0,
        "max_depth": 0,
        "elapsed": 0.0,
    }

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
    verbose_emitted = 0
    last_progress_work = 0

    def finish(solution, status):
        stats["status"] = status
        stats["elapsed"] = time.perf_counter() - started
        if return_stats:
            return solution, stats
        return solution

    def log_debug(message):
        nonlocal verbose_emitted
        if log_mode != "debug" or verbose_emitted >= verbose_limit:
            return
        verbose_emitted += 1
        emit(event_callback, EVENT_LOG, f"      DPLL debug: level {len(decisions)}: {message}")

    def log_progress():
        nonlocal last_progress_work
        if log_mode not in ("periodic", "debug"):
            return
        work = stats["decisions"] + stats["conflicts"] + stats["propagations"]
        if work - last_progress_work < progress_interval:
            return
        last_progress_work = work
        emit(
            event_callback,
            EVENT_LOG,
            (
                "      DPLL progress: "
                f"decisions={stats['decisions']}, "
                f"conflicts={stats['conflicts']}, "
                f"propagations={stats['propagations']}, "
                f"depth={len(decisions)}"
            ),
        )

    if stop_requested(cancel_token):
        return finish(None, cancellation_status(cancel_token))

    formula, variables, has_empty_clause = _normalise_formula(clauses)
    if has_empty_clause:
        return finish(None, "UNSAT")

    max_var = max(variables, default=0)
    for var in (assignment or {}):
        max_var = max(max_var, abs(int(var)))

    # values[var]: None (free), True or False.
    values = [None] * (max_var + 1)
    # Occurrence lists: occurs[offset + lit] = indices of clauses containing lit.
    offset = max_var
    occurs = [[] for _ in range(2 * max_var + 1)]
    for index, clause in enumerate(formula):
        for lit in clause:
            occurs[offset + lit].append(index)
    lengths = [len(clause) for clause in formula]
    true_count = [0] * len(formula)
    false_count = [0] * len(formula)

    # The trail lists assigned literals in order. Literals before qhead have
    # had their effect on the clause counters applied.
    trail = []
    qhead = 0
    # One entry per open decision: [variable, value tried, trail position,
    # whether the second value is being tried].
    decisions = []
    countdown = CHECK_EVERY

    def assign(lit, forced):
        var = abs(lit)
        values[var] = lit > 0
        trail.append(lit)
        if forced:
            stats["propagations"] += 1

    def propagate():
        """
        Apply every pending assignment to the clause counters.

        Each new true literal satisfies the clauses containing it; each new
        false literal shrinks the clauses containing its negation. A shrunk
        clause with nothing true and one free literal forces that literal
        (unit propagation); with nothing free it is a conflict.
        Returns "conflict", "cancelled" or None.
        """
        nonlocal qhead, countdown
        while qhead < len(trail):
            lit = trail[qhead]
            qhead += 1
            for index in occurs[offset + lit]:
                true_count[index] += 1
            conflict = False
            for index in occurs[offset - lit]:
                false_count[index] += 1
                countdown -= 1
                if countdown <= 0:
                    countdown = CHECK_EVERY
                    if stop_requested(cancel_token):
                        return "cancelled"
                if conflict or true_count[index]:
                    continue
                free = lengths[index] - false_count[index]
                if free == 0:
                    # Keep updating the counters of this literal so that
                    # undo() can reverse them uniformly, then report.
                    conflict = True
                elif free == 1:
                    for other in formula[index]:
                        if values[abs(other)] is None:
                            assign(other, forced=True)
                            break
            if conflict:
                return "conflict"
        return None

    def undo(position):
        """Unassign every literal from trail[position:] and restore the counters."""
        nonlocal qhead
        for index in range(len(trail) - 1, position - 1, -1):
            lit = trail[index]
            if index < qhead:
                for clause_index in occurs[offset + lit]:
                    true_count[clause_index] -= 1
                for clause_index in occurs[offset - lit]:
                    false_count[clause_index] -= 1
            values[abs(lit)] = None
        del trail[position:]
        qhead = min(qhead, position)

    def choose_variable():
        """
        Small-clause rule: a free variable from a shortest remaining clause.

        Short clauses are closest to becoming unit or conflicting, so branching
        on them tends to expose contradictions early. Ties go to the earliest
        clause and, inside it, the earliest free literal, exactly like the
        recursive version.
        """
        if choose_var_fn is not None:
            return choose_var_fn(remaining_clauses(), current_assignment())
        best = None
        best_length = None
        for index, clause in enumerate(formula):
            if true_count[index]:
                continue
            length = lengths[index] - false_count[index]
            if best_length is None or length < best_length:
                best, best_length = index, length
                if length <= 2:
                    break  # nothing shorter can remain after propagation
        if best is None:
            return None
        for lit in formula[best]:
            if values[abs(lit)] is None:
                return abs(lit)
        return None

    def remaining_clauses():
        return [
            [lit for lit in clause if values[abs(lit)] is None]
            for index, clause in enumerate(formula)
            if not true_count[index]
        ]

    def current_assignment():
        return {var: values[var] for var in range(1, max_var + 1) if values[var] is not None}

    # Variables fixed by the caller are facts before the first decision.
    for var, value in (assignment or {}).items():
        var = abs(int(var))
        if values[var] is None:
            assign(var if value else -var, forced=False)
        elif values[var] != bool(value):
            return finish(None, "UNSAT")
    # Input unit clauses are forced from the start.
    for clause in formula:
        if len(clause) == 1:
            lit = clause[0]
            if values[abs(lit)] is None:
                assign(lit, forced=True)
            elif values[abs(lit)] != (lit > 0):
                stats["conflicts"] += 1
                return finish(None, "UNSAT")

    while True:
        outcome = propagate()
        if outcome == "cancelled":
            return finish(None, cancellation_status(cancel_token))

        if outcome == "conflict":
            stats["conflicts"] += 1
            log_debug("conflict")
            log_progress()
            # Chronological backtracking: undo the most recent decision whose
            # second value has not been tried yet, and try it.
            while decisions:
                var, value, position, flipped = decisions.pop()
                undo(position)
                if not flipped:
                    log_debug(f"backtrack: try {var}={not value}")
                    decisions.append([var, not value, position, True])
                    assign(var if not value else -var, forced=False)
                    break
                log_debug(f"both values of {var} failed")
            else:
                # Every decision has been tried both ways.
                return finish(None, "UNSAT")
            continue

        var = choose_variable()
        if var is None:
            # No clause is left unsatisfied. Variables that are still free can
            # take any value; they get True, like CDCL's default phase.
            solution = {v: values[v] if values[v] is not None else True for v in variables}
            for v in (assignment or {}):
                solution[abs(int(v))] = values[abs(int(v))]
            return finish(solution, "SAT")

        stats["decisions"] += 1
        decisions.append([var, True, len(trail), False])
        stats["max_depth"] = max(stats["max_depth"], len(decisions))
        log_debug(f"choose variable {var}, try {var}=True")
        log_progress()
        assign(var, forced=False)
