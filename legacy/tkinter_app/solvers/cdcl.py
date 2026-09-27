"""
Conflict-Driven Clause Learning (CDCL) SAT solver.

CDCL extends DPLL with an implication graph. Forced assignments remember the
clause that implied them, conflicts are analysed to derive learned clauses, and
the solver backjumps directly to the decision level where the learned clause
becomes useful. Watched literals make propagation efficient, while VSIDS-style
activity scores, optional restarts, and learned-clause pruning improve search.
"""

from collections import defaultdict
from dataclasses import dataclass
import random
import time

from sat_core.runtime import EVENT_LOG, cancellation_status, emit, stop_requested


@dataclass(eq=False)
class Clause:
    """
    One CNF clause plus solver metadata.

    lits is the disjunction of signed literals. watch1 and watch2 identify the
    two watched literals used by Boolean constraint propagation. learnt marks a
    clause derived from conflict analysis rather than from the input formula.
    LBD counts how many decision levels the clause touches; lower values often
    indicate stronger learned clauses.
    """
    lits: list[int]
    learnt: bool = False
    watch1: int = 0
    watch2: int = 0
    created: int = 0
    lbd: int | None = None
    last_used: int = 0


def _normalise_formula(clauses):
    """
    Remove duplicate literals and skip tautologies like (x OR not x).

    A tautological clause is always true, so it does not constrain the solver.
    If an empty clause remains, the formula is immediately UNSAT.
    """
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
            if -lit in seen:
                tautology = True
                break
            if lit not in seen:
                seen.add(lit)
                clean.append(lit)
                variables.add(abs(lit))

        if tautology:
            continue
        if not clean:
            has_empty_clause = True
        else:
            clean_clauses.append(clean)

    max_var = max(variables) if variables else 0
    return clean_clauses, sorted(variables), max_var, has_empty_clause


def _dedupe_clause(lits):
    """Remove repeated literals while preserving the clause order."""
    clean = []
    seen = set()

    for lit in lits:
        if lit not in seen:
            clean.append(lit)
            seen.add(lit)

    return clean


def clause_lbd(lits, levels):
    """Return the number of distinct decision levels touched by clause lits."""
    return len({levels[abs(lit)] for lit in lits})


def learned_clause_delete_key(clause):
    """
    Sort key for learned-clause deletion. Larger keys are worse clauses.

    Binary and low-LBD clauses are deliberately protected by lower key values.
    """
    lbd = clause.lbd if clause.lbd is not None else len(clause.lits) + 1000
    binary_penalty = 0 if len(clause.lits) <= 2 else 1
    return (
        binary_penalty,
        lbd,
        len(clause.lits),
        -clause.last_used,
        -clause.created,
    )


def learned_clauses_to_delete(learned, locked, learned_clause_limit):
    """
    Choose learned clauses to delete when the learned database is too large.

    Clauses currently used as implication reasons are locked: deleting them
    would break the implication graph needed for later conflict analysis.
    """
    remove_count = len(learned) - learned_clause_limit
    if remove_count <= 0:
        return set()

    unlocked = [clause for clause in learned if clause not in locked]
    if not unlocked:
        return set()

    removable = sorted(unlocked, key=learned_clause_delete_key, reverse=True)
    return set(removable[:remove_count])


def cdcl(
    clauses,
    max_conflicts=None,
    return_stats=False,
    event_callback=None,
    cancel_token=None,
    logging_options=None,
):
    """
    Conflict-Driven Clause Learning SAT solver.

    The solver maintains a partial assignment, a trail ordered by time, and
    reason clauses for propagated literals. A conflict triggers First-UIP
    analysis, which produces a learned clause and a non-chronological
    backjump level.

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
        "learned_clauses": 0,
        "active_learned_clauses": 0,
        "deleted_learned_clauses": 0,
        "avg_lbd": 0.0,
        "restarts": 0,
        "elapsed": 0.0,
    }
    logging_options = logging_options or {}
    log_mode = logging_options.get("mode", "normal")
    if log_mode not in ("normal", "periodic", "debug"):
        log_mode = "normal"

    def normalise_choice(value, allowed, default):
        if value is None:
            return default
        canonical = str(value).strip().lower().replace("_", " ").replace("-", " ")
        for option in allowed:
            if canonical == option.lower():
                return option
        return default

    def positive_int(value, default):
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return default

    def optional_positive_int(value):
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    progress_interval = positive_int(logging_options.get("progress_interval"), 100)
    verbose_limit = positive_int(logging_options.get("verbose_limit"), 120)
    branching_mode = normalise_choice(
        logging_options.get("branching"),
        ("VSIDS", "Most frequent", "MOMS", "DLIS", "Random"),
        "VSIDS",
    )
    initial_phase_mode = normalise_choice(
        logging_options.get("initial_phase"),
        ("Positive first", "Negative first", "Polarity based", "Random"),
        "Positive first",
    )
    restart_interval = optional_positive_int(logging_options.get("restart_interval"))
    learned_clause_limit = optional_positive_int(logging_options.get("learned_clause_limit"))
    random_seed = logging_options.get("random_seed")
    rng = random.Random(random_seed) if random_seed not in (None, "") else random.Random()
    verbose_emitted = 0
    last_progress_work = 0
    learned_sequence = 0
    conflicts_at_last_restart = 0
    stats["solver_options"] = (
        f"branch={branching_mode}; phase={initial_phase_mode}; "
        f"restart={restart_interval or '-'}; learned_limit={learned_clause_limit or '-'}; "
        f"seed={random_seed if random_seed not in (None, '') else '-'}"
    )

    def log_debug(message):
        nonlocal verbose_emitted
        if log_mode != "debug" or verbose_emitted >= verbose_limit:
            return
        verbose_emitted += 1
        emit(event_callback, EVENT_LOG, f"      CDCL debug: {message}")

    def log_progress(force=False):
        nonlocal last_progress_work
        if log_mode not in ("periodic", "debug"):
            return

        work = stats["decisions"] + stats["conflicts"] + stats["propagations"]
        if not force and work - last_progress_work < progress_interval:
            return

        last_progress_work = work
        emit(
            event_callback,
            EVENT_LOG,
            (
                "      CDCL progress: "
                f"decisions={stats['decisions']}, "
                f"conflicts={stats['conflicts']}, "
                f"propagations={stats['propagations']}, "
                f"learned={stats['learned_clauses']} "
                f"active learned={stats['active_learned_clauses']} "
                f"deleted learned={stats['deleted_learned_clauses']} "
                f"avg_lbd={stats['avg_lbd']:.2f}"
            ),
        )

    def finish(solution, status):
        stats["status"] = status
        stats["elapsed"] = time.perf_counter() - started
        if return_stats:
            return solution, stats
        return solution

    if stop_requested(cancel_token):
        return finish(None, cancellation_status(cancel_token))

    normalised, variables, max_var, has_empty_clause = _normalise_formula(clauses)

    if has_empty_clause:
        return finish(None, "UNSAT")

    if not normalised:
        return finish({}, "SAT")

    # These arrays represent the current partial assignment and the implication
    # graph. For each variable, reasons[var] is the clause that forced it; a
    # None reason means the assignment was a decision.
    assignment = [None] * (max_var + 1)   # None, True, or False
    levels = [0] * (max_var + 1)          # decision level of each assignment
    reasons = [None] * (max_var + 1)      # clause that forced each propagation
    saved_phase = [None] * (max_var + 1)  # last value used for each variable
    activity = [0.0] * (max_var + 1)      # VSIDS-like score
    preferred_phase = [True] * (max_var + 1)

    clauses_db = []
    watches = defaultdict(list)
    cancelled = object()

    # The trail is the chronological assignment stack. Each item is a literal:
    #  x means x=True, -x means x=False. trail_lim stores where each decision
    # level begins, so backjumping can erase whole levels at once.
    trail = []
    trail_lim = []
    qhead = 0

    var_inc = 1.0
    var_decay = 0.95

    # Initial scores approximate which variables are syntactically important
    # before any conflicts have been seen. Later, conflict analysis bumps the
    # activity of variables involved in learned clauses.
    polarity_score = [0] * (max_var + 1)
    occurrence_count = [0] * (max_var + 1)
    for clause in normalised:
        for lit in clause:
            var = abs(lit)
            activity[var] += 1.0
            occurrence_count[var] += 1
            polarity_score[var] += 1 if lit > 0 else -1

    for var in variables:
        if initial_phase_mode == "Negative first":
            preferred_phase[var] = False
        elif initial_phase_mode == "Polarity based":
            preferred_phase[var] = polarity_score[var] >= 0
        elif initial_phase_mode == "Random":
            preferred_phase[var] = bool(rng.getrandbits(1))
        else:
            # The app's encoders use positive literals as constructive choices
            # (place a queen, choose a color, select a node). Counting literal
            # polarity heavily favours False on pairwise "at most one" clauses.
            preferred_phase[var] = True

    def current_level():
        return len(trail_lim)

    def lit_value(lit):
        """Evaluate a signed literal under the current partial assignment."""
        value = assignment[abs(lit)]
        if value is None:
            return None
        return value if lit > 0 else not value

    def enqueue(lit, reason):
        """
        Assign a literal.

        reason=None means this is a decision. Otherwise reason is the clause
        that became unit and forced the assignment.
        """
        var = abs(lit)
        value = lit > 0
        current = assignment[var]

        if current is not None:
            return current == value

        assignment[var] = value
        levels[var] = current_level()
        reasons[var] = reason
        saved_phase[var] = value
        trail.append(lit)

        if reason is not None:
            stats["propagations"] += 1

        return True

    def watch_clause(clause):
        """
        Register the initial watched literals for a clause.

        A unit clause watches its only literal twice conceptually; here one
        stored watch is enough because the clause immediately forces that
        literal.
        """
        if len(clause.lits) == 1:
            clause.watch1 = 0
            clause.watch2 = 0
            watches[clause.lits[0]].append(clause)
            return

        clause.watch1 = 0
        clause.watch2 = 1
        watches[clause.lits[clause.watch1]].append(clause)
        watches[clause.lits[clause.watch2]].append(clause)

    def update_active_learned_count():
        """Refresh statistics for the current learned-clause database."""
        learned = [clause for clause in clauses_db if clause.learnt]
        stats["active_learned_clauses"] = len(learned)
        lbd_values = [clause.lbd for clause in learned if clause.lbd is not None]
        stats["avg_lbd"] = sum(lbd_values) / len(lbd_values) if lbd_values else 0.0

    def attach_clause(clause):
        """
        Watch two literals in the clause.

        During propagation we only revisit clauses watching the literal that
        just became false. That avoids scanning every clause after every
        assignment, which is the main practical speedup over simple DPLL.
        """
        clauses_db.append(clause)
        watch_clause(clause)

    def add_clause(lits, learnt=False, lbd=None):
        """Create a clause object, attach its watches, and store it."""
        nonlocal learned_sequence
        if learnt:
            learned_sequence += 1
        clause = Clause(list(lits), learnt=learnt, created=learned_sequence if learnt else 0, lbd=lbd)
        attach_clause(clause)
        return clause

    for lits in normalised:
        if stop_requested(cancel_token):
            return finish(None, cancellation_status(cancel_token))

        # Input unit clauses are facts at decision level 0. If two such facts
        # contradict each other, the formula is UNSAT without any search.
        clause = add_clause(lits)
        if len(lits) == 1:
            log_debug(f"unit clause forces {lits[0]}")
            if not enqueue(lits[0], clause):
                return finish(None, "UNSAT")

    def propagate():
        """
        Boolean constraint propagation using watched literals.

        If a watched literal becomes false, the clause tries to watch another
        non-false literal. If it cannot, either the clause is conflicting or it
        has become unit and forces the other watched literal.
        """
        nonlocal qhead

        while qhead < len(trail):
            if stop_requested(cancel_token):
                return cancelled

            false_lit = -trail[qhead]
            qhead += 1

            watch_list = watches[false_lit]
            i = 0

            while i < len(watch_list):
                if stop_requested(cancel_token):
                    return cancelled

                clause = watch_list[i]

                if clause.lits[clause.watch1] == false_lit:
                    false_watch = clause.watch1
                    other_watch = clause.watch2
                elif clause.lits[clause.watch2] == false_lit:
                    false_watch = clause.watch2
                    other_watch = clause.watch1
                else:
                    # Defensive guard for stale watches; normally not reached.
                    i += 1
                    continue

                other_lit = clause.lits[other_watch]

                if lit_value(other_lit) is True:
                    i += 1
                    continue

                # Try to preserve the invariant that every unresolved clause
                # has at least one watched literal not known to be false.
                moved_watch = False
                for new_watch, new_lit in enumerate(clause.lits):
                    if new_watch == clause.watch1 or new_watch == clause.watch2:
                        continue

                    if lit_value(new_lit) is not False:
                        if false_watch == clause.watch1:
                            clause.watch1 = new_watch
                        else:
                            clause.watch2 = new_watch

                        watches[new_lit].append(clause)
                        watch_list[i] = watch_list[-1]
                        watch_list.pop()
                        moved_watch = True
                        break

                if moved_watch:
                    continue

                # If the other watched literal is false too, every literal in
                # the clause is false: this is a conflict. Otherwise the clause
                # is unit and forces the other watched literal.
                if lit_value(other_lit) is False:
                    return clause

                if not enqueue(other_lit, clause):
                    return clause
                clause.last_used = stats["conflicts"]

                i += 1

        return None

    def bump_var(var):
        """Increase a variable's VSIDS-style activity after a conflict."""
        nonlocal var_inc

        activity[var] += var_inc

        # Keep floating point values bounded during long runs.
        if activity[var] > 1e100:
            for v in variables:
                activity[v] *= 1e-100
            var_inc *= 1e-100

    def decay_activity():
        """Make future conflict bumps relatively more important."""
        nonlocal var_inc
        var_inc /= var_decay

    def analyse_conflict(conflict_clause):
        """
        First-UIP conflict analysis.

        The learned clause is built by resolving the conflict clause with the
        reasons of current-level assignments until only one current-level
        literal remains. That literal is the first UIP, and the learned clause
        becomes asserting after we backjump.
        """
        seen = [False] * (max_var + 1)
        learnt = []
        path_count = 0
        scan = len(trail) - 1
        clause = conflict_clause
        skip_var = None
        decision_level = current_level()

        while True:
            for lit in clause.lits:
                var = abs(lit)

                if var == skip_var or seen[var] or levels[var] == 0:
                    continue

                seen[var] = True
                bump_var(var)

                if levels[var] == decision_level:
                    path_count += 1
                else:
                    learnt.append(lit)

            while scan >= 0:
                pivot = trail[scan]
                scan -= 1
                if seen[abs(pivot)]:
                    break
            else:
                # This should not happen for a normal implication graph, but
                # returning a learned clause is better than hiding the failure.
                return _dedupe_clause(conflict_clause.lits), 0

            pivot_var = abs(pivot)
            seen[pivot_var] = False
            path_count -= 1

            reason = reasons[pivot_var]

            if path_count == 0:
                learnt.insert(0, -pivot)
                break

            if reason is None:
                learnt.insert(0, -pivot)
                break

            clause = reason
            skip_var = pivot_var

        learnt = _dedupe_clause(learnt)

        # All literals except learnt[0] are false at the backjump level.
        # Jump to the highest of those levels so learnt[0] becomes unit.
        backjump_level = 0
        for lit in learnt[1:]:
            backjump_level = max(backjump_level, levels[abs(lit)])

        return learnt, backjump_level

    def backtrack(level):
        """
        Remove all assignments above 'level'.

        This is the "non-chronological" part of CDCL: after learning, we jump
        directly to the useful level instead of undoing one decision at a time.
        """
        nonlocal qhead

        while current_level() > level:
            start = trail_lim.pop()

            for lit in reversed(trail[start:]):
                var = abs(lit)
                assignment[var] = None
                levels[var] = 0
                reasons[var] = None

            del trail[start:]

        qhead = min(qhead, len(trail))

    def active_reason_clauses():
        """Return learned clauses that currently justify propagated literals."""
        locked = set()
        for var in variables:
            reason = reasons[var]
            if reason is not None:
                locked.add(reason)
        return locked

    def prune_learned_clauses():
        """
        Delete weak learned clauses when a limit is configured.

        The solver keeps clauses that are active reasons in the implication
        graph and prefers to keep short or low-LBD clauses.
        """
        if learned_clause_limit is None:
            return

        learned = [clause for clause in clauses_db if clause.learnt]
        if len(learned) <= learned_clause_limit:
            return

        locked = active_reason_clauses()
        remove_set = learned_clauses_to_delete(learned, locked, learned_clause_limit)
        if not remove_set:
            return

        clauses_db[:] = [clause for clause in clauses_db if clause not in remove_set]

        # Important: do not rebuild all watches during an active search.
        # Only remove deleted clauses from existing watch lists.
        for lit in list(watches.keys()):
            watches[lit] = [
                clause for clause in watches[lit]
                if clause not in remove_set
            ]

            if not watches[lit]:
                del watches[lit]

        stats["deleted_learned_clauses"] += len(remove_set)
        update_active_learned_count()

    def unresolved_clause_lits():
        """Yield the still-unresolved literals of clauses not yet satisfied."""
        for clause in clauses_db:
            unresolved = []
            satisfied = False
            for lit in clause.lits:
                value = lit_value(lit)
                if value is True:
                    satisfied = True
                    break
                if value is None:
                    unresolved.append(lit)
            if not satisfied and unresolved:
                yield unresolved

    def pick_branch_var():
        """VSIDS branch choice: pick the unassigned variable with max activity."""
        best_var = None
        best_score = -1.0

        for var in variables:
            if assignment[var] is None and activity[var] > best_score:
                best_var = var
                best_score = activity[var]

        return best_var

    def pick_most_frequent_var():
        """Static heuristic: pick the unassigned variable with most occurrences."""
        best_var = None
        best_score = -1
        for var in variables:
            if assignment[var] is None and occurrence_count[var] > best_score:
                best_var = var
                best_score = occurrence_count[var]
        return best_var

    def pick_moms_var():
        """
        MOMS heuristic: focus on variables in the shortest unresolved clauses.

        Such clauses are nearest to unit propagation or conflict.
        """
        shortest = None
        scores = defaultdict(int)
        for unresolved in unresolved_clause_lits():
            length = len(unresolved)
            if shortest is None or length < shortest:
                shortest = length
                scores.clear()
            if length == shortest:
                for lit in unresolved:
                    var = abs(lit)
                    if assignment[var] is None:
                        scores[var] += 1

        if not scores:
            return None
        return max(scores, key=lambda var: (scores[var], occurrence_count[var], -var))

    def pick_dlis_decision():
        """
        DLIS heuristic: choose the literal satisfying the most unresolved clauses.

        Unlike variable-only heuristics, DLIS also suggests the branch phase.
        """
        literal_scores = defaultdict(int)
        for unresolved in unresolved_clause_lits():
            for lit in unresolved:
                if assignment[abs(lit)] is None:
                    literal_scores[lit] += 1

        if not literal_scores:
            return None, None

        best_lit = max(literal_scores, key=lambda lit: (literal_scores[lit], occurrence_count[abs(lit)], abs(lit)))
        return abs(best_lit), best_lit > 0

    def pick_random_var():
        """Random branch choice, useful as a baseline heuristic."""
        candidates = [var for var in variables if assignment[var] is None]
        return rng.choice(candidates) if candidates else None

    def pick_branch_decision():
        """Dispatch to the configured branching heuristic."""
        if branching_mode == "Most frequent":
            return pick_most_frequent_var(), None
        if branching_mode == "MOMS":
            return pick_moms_var(), None
        if branching_mode == "DLIS":
            return pick_dlis_decision()
        if branching_mode == "Random":
            return pick_random_var(), None
        return pick_branch_var(), None

    def choose_phase(var, branch_phase=None):
        """
        Choose the truth value for a decision variable.

        saved_phase implements phase saving: after a variable was useful with a
        truth value, later decisions try that value again.
        """
        if branch_phase is not None:
            return branch_phase
        if initial_phase_mode == "Random":
            return bool(rng.getrandbits(1))
        if saved_phase[var] is not None:
            return saved_phase[var]
        return preferred_phase[var]

    while True:
        if stop_requested(cancel_token):
            return finish(None, cancellation_status(cancel_token))

        conflict = propagate()

        if conflict is cancelled:
            return finish(None, cancellation_status(cancel_token))

        if conflict is not None:
            stats["conflicts"] += 1
            log_debug(f"conflict {stats['conflicts']} at level {current_level()}")
            log_progress()

            # A level-0 conflict means the original formula itself is
            # contradictory under all mandatory propagations.
            if current_level() == 0:
                return finish(None, "UNSAT")

            if max_conflicts is not None and stats["conflicts"] >= max_conflicts:
                return finish(None, "UNKNOWN")

            # Resolve the conflict through the implication graph, learn a new
            # clause, and jump to the level where that clause becomes asserting.
            learnt_lits, backjump_level = analyse_conflict(conflict)
            decay_activity()
            log_debug(f"learned clause size {len(learnt_lits)}; backjump to level {backjump_level}")

            if not learnt_lits:
                return finish(None, "UNSAT")

            learnt_lits = _dedupe_clause(learnt_lits)
            learnt_lbd = clause_lbd(learnt_lits, levels)
            learnt_clause = add_clause(learnt_lits, learnt=True, lbd=learnt_lbd)
            stats["learned_clauses"] += 1
            update_active_learned_count()
            log_debug(f"learned clause LBD {learnt_lbd}")

            backtrack(backjump_level)

            # The learned clause is now unit. Enqueueing its first literal makes
            # the solver immediately avoid the same conflict pattern.
            if not enqueue(learnt_lits[0], learnt_clause):
                if current_level() == 0:
                    return finish(None, "UNSAT")
                continue

            prune_learned_clauses()
            update_active_learned_count()

            if (
                restart_interval is not None
                and stats["conflicts"] - conflicts_at_last_restart >= restart_interval
                and current_level() > 0
            ):
                # A restart discards the current decisions but keeps learned
                # clauses, so future search starts from a stronger formula.
                conflicts_at_last_restart = stats["conflicts"]
                stats["restarts"] += 1
                log_debug(f"restart {stats['restarts']} after {stats['conflicts']} conflicts")
                backtrack(0)

            continue

        decision_var, branch_phase = pick_branch_decision()

        if decision_var is None:
            # Every variable appearing in the formula has a value and no clause
            # is conflicting, so the current assignment is a satisfying model.
            solution = {var: assignment[var] for var in variables if assignment[var] is not None}
            return finish(solution, "SAT")

        # Start a new decision level. Subsequent propagations record this level
        # and can later be erased together by backtracking/backjumping.
        trail_lim.append(len(trail))
        stats["decisions"] += 1

        value = choose_phase(decision_var, branch_phase)

        log_debug(f"decision {stats['decisions']} at level {current_level()}: {decision_var}={value}")
        log_progress()
        enqueue(decision_var if value else -decision_var, reason=None)


def cdcl_debug(clauses, max_steps=5000):
    """
    Compatibility wrapper for older experiments.

    max_steps maps to max_conflicts because the new solver is conflict-driven.
    """
    return cdcl(clauses, max_conflicts=max_steps)
