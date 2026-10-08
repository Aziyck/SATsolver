"""
Conflict-Driven Clause Learning (CDCL) SAT solver.

CDCL extends DPLL with an implication graph. Forced assignments remember the
clause that implied them, conflicts are analysed to derive learned clauses, and
the solver backjumps directly to the decision level where the learned clause
becomes useful. Watched literals make propagation cheap, VSIDS activity (kept
in a priority queue) picks decisions, Luby restarts and periodic learned-clause
cleanup keep long searches fast.

docs/algorithms/cdcl.md explains every part in prose; the comments here point
at the matching section.
"""

from collections import defaultdict
from dataclasses import dataclass
import random
import time

from sat_core.runtime import EVENT_LOG, cancellation_status, emit, stop_requested


# Asking the cancel token whether to stop is cheap but not free (it reads a
# multiprocessing Event and the clock). Doing it on every watch visit cost a
# third of the run time, so propagation only checks every CHECK_EVERY visits,
# which is still well under a millisecond between checks.
CHECK_EVERY = 2048

# Literal values, stored per literal (see "val" below).
TRUE = 1
FALSE = -1
UNASSIGNED = 0

# Automatic learned-clause cleanup, as in Glucose: the first cleanup happens
# after REDUCE_FIRST conflicts and each later one waits REDUCE_STEP longer.
REDUCE_FIRST = 2000
REDUCE_STEP = 300

# Learned clauses with LBD <= GLUE_LBD ("glue clauses") are never deleted by
# the automatic cleanup; they connect only a couple of decision levels and
# tend to stay useful for the whole search.
GLUE_LBD = 2


@dataclass(eq=False)
class Clause:
    """
    One CNF clause plus solver metadata.

    lits[0] and lits[1] are the two watched literals (see propagate). learnt
    marks a clause derived from conflict analysis. LBD counts how many decision
    levels the clause touched when it was learned; lower values often indicate
    stronger clauses. deleted marks a learned clause removed by cleanup; it is
    dropped from watch lists lazily, the next time propagation meets it.
    """
    lits: list[int]
    learnt: bool = False
    created: int = 0
    lbd: int | None = None
    last_used: int = 0
    deleted: bool = False


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
            # Every variable of the input gets a value in the model, even one
            # that only appears in a dropped tautology.
            variables.add(abs(lit))
            if -lit in seen:
                tautology = True
                continue
            if lit not in seen:
                seen.add(lit)
                clean.append(lit)

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

    Binary and low-LBD clauses are deliberately protected by lower key values;
    among equals, clauses used recently in propagation or conflict analysis
    are kept.
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
    Choose learned clauses to delete so that at most learned_clause_limit stay.

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


def luby(index):
    """
    The Luby sequence 1, 1, 2, 1, 1, 2, 4, 1, 1, 2, 1, 1, 2, 4, 8, ... (index from 0).

    Restart i happens after luby(i) * restart_interval conflicts: mostly short
    runs, with occasional long ones so hard instances can still be finished.
    """
    size, seq = 1, 0
    while size < index + 1:
        seq += 1
        size = 2 * size + 1
    while size - 1 != index:
        size = (size - 1) >> 1
        seq -= 1
        index %= size
    return 1 << seq


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

    Options (all optional) are read from logging_options:
    - branching: VSIDS (default), Most frequent, MOMS, DLIS, Random
    - initial_phase: Positive first (default), Negative first, Polarity based, Random
    - restarts: True (default) or False
    - restart_strategy: luby (default) or fixed
    - restart_interval: conflicts per restart unit (default 100)
    - clause_deletion: True (default) for the automatic learned-clause cleanup
    - learned_clause_limit: a fixed cap on learned clauses instead of the
      automatic schedule
    - random_seed, mode (normal/periodic/debug), progress_interval

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
        "reductions": 0,
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

    def flag(value, default):
        if value is None:
            return default
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)

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
    restarts_enabled = flag(logging_options.get("restarts"), True)
    restart_strategy = normalise_choice(logging_options.get("restart_strategy"), ("luby", "fixed"), "luby")
    restart_interval = positive_int(logging_options.get("restart_interval"), 100)
    learned_clause_limit = optional_positive_int(logging_options.get("learned_clause_limit"))
    # A fixed limit replaces the automatic schedule.
    auto_cleanup = flag(logging_options.get("clause_deletion"), True) and learned_clause_limit is None
    random_seed = logging_options.get("random_seed")
    rng = random.Random(random_seed) if random_seed not in (None, "") else random.Random()
    verbose_emitted = 0
    last_progress_work = 0
    learned_sequence = 0

    if restarts_enabled:
        restart_text = f"{restart_strategy}x{restart_interval}"
    else:
        restart_text = "off"
    if learned_clause_limit is not None:
        cleanup_text = f"limit {learned_clause_limit}"
    else:
        cleanup_text = "auto" if auto_cleanup else "off"
    stats["solver_options"] = (
        f"branch={branching_mode}; phase={initial_phase_mode}; restarts={restart_text}; "
        f"cleanup={cleanup_text}; seed={random_seed if random_seed not in (None, '') else '-'}"
    )

    # Learned-clause statistics are kept as running totals. (Recomputing them
    # by scanning every clause after each conflict used to take 40% of the
    # time on large formulas.)
    learned_count = 0
    learned_lbd_sum = 0

    def refresh_learned_stats():
        stats["active_learned_clauses"] = learned_count
        stats["avg_lbd"] = learned_lbd_sum / learned_count if learned_count else 0.0

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
        refresh_learned_stats()
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
                f"restarts={stats['restarts']} "
                f"avg_lbd={stats['avg_lbd']:.2f}"
            ),
        )

    def finish(solution, status):
        stats["status"] = status
        stats["elapsed"] = time.perf_counter() - started
        refresh_learned_stats()
        if return_stats:
            return solution, stats
        return solution

    if stop_requested(cancel_token):
        return finish(None, cancellation_status(cancel_token))

    normalised, variables, max_var, has_empty_clause = _normalise_formula(clauses)

    if has_empty_clause:
        return finish(None, "UNSAT")

    if not normalised:
        # Only tautologies (or nothing): any assignment works.
        return finish({var: True for var in variables}, "SAT")

    # Per-variable arrays, indexed by variable number. reasons[var] is the
    # clause that forced var; None means it was a decision (or is unassigned).
    assignment = [None] * (max_var + 1)   # None, True, or False
    levels = [0] * (max_var + 1)          # decision level of each assignment
    reasons = [None] * (max_var + 1)      # clause that forced each propagation
    saved_phase = [None] * (max_var + 1)  # last value used for each variable
    activity = [0.0] * (max_var + 1)      # VSIDS score
    preferred_phase = [True] * (max_var + 1)
    seen = [False] * (max_var + 1)        # scratch marks for conflict analysis

    # Per-literal arrays, indexed by offset + lit so that -max_var..max_var fit
    # in one list. val[offset + lit] is TRUE, FALSE or UNASSIGNED: checking a
    # literal is one list lookup instead of a function call.
    offset = max_var
    val = [UNASSIGNED] * (2 * max_var + 1)
    watches = [[] for _ in range(2 * max_var + 1)]  # clauses watching each literal

    original_clauses = []
    learned_db = []
    cancelled = object()
    countdown = CHECK_EVERY

    # The trail is the chronological assignment stack. Each item is a literal:
    # x means x=True, -x means x=False. trail_lim stores where each decision
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

    # -- Decision order heap --------------------------------------------------
    # VSIDS (and the static "most frequent" order) need "the unassigned
    # variable with the highest score" at every decision. Scanning all
    # variables each time is O(n); a binary max-heap makes it O(log n). The
    # heap is lazy, as in MiniSat: assigned variables may stay in it and are
    # skipped when popped, and backtracking puts unassigned variables back.
    use_heap = branching_mode in ("VSIDS", "Most frequent")
    heap_key = activity if branching_mode == "VSIDS" else occurrence_count
    heap = []
    heap_pos = [-1] * (max_var + 1)  # index of each variable in heap, -1 if absent

    def better(a, b):
        """Heap order: higher score first, smaller variable number on ties."""
        key_a, key_b = heap_key[a], heap_key[b]
        return key_a > key_b or (key_a == key_b and a < b)

    def heap_up(index):
        var = heap[index]
        while index > 0:
            parent_index = (index - 1) >> 1
            parent = heap[parent_index]
            if not better(var, parent):
                break
            heap[index] = parent
            heap_pos[parent] = index
            index = parent_index
        heap[index] = var
        heap_pos[var] = index

    def heap_down(index):
        var = heap[index]
        size = len(heap)
        while True:
            child = 2 * index + 1
            if child >= size:
                break
            right = child + 1
            if right < size and better(heap[right], heap[child]):
                child = right
            child_var = heap[child]
            if not better(child_var, var):
                break
            heap[index] = child_var
            heap_pos[child_var] = index
            index = child
        heap[index] = var
        heap_pos[var] = index

    def heap_insert(var):
        if heap_pos[var] >= 0:
            return
        heap_pos[var] = len(heap)
        heap.append(var)
        heap_up(len(heap) - 1)

    def heap_pop():
        top = heap[0]
        last = heap.pop()
        heap_pos[top] = -1
        if heap:
            heap[0] = last
            heap_pos[last] = 0
            heap_down(0)
        return top

    if use_heap:
        for var in variables:
            heap_insert(var)

    def current_level():
        return len(trail_lim)

    def enqueue(lit, reason):
        """
        Assign a literal.

        reason=None means this is a decision. Otherwise reason is the clause
        that became unit and forced the assignment.
        """
        var = abs(lit)
        current = assignment[var]

        if current is not None:
            return current == (lit > 0)

        value = lit > 0
        assignment[var] = value
        val[offset + lit] = TRUE
        val[offset - lit] = FALSE
        levels[var] = len(trail_lim)
        reasons[var] = reason
        saved_phase[var] = value
        trail.append(lit)

        if reason is not None:
            stats["propagations"] += 1

        return True

    def add_clause(lits, learnt=False, lbd=None):
        """
        Create a clause and watch its first two literals.

        During propagation we only revisit clauses watching the literal that
        just became false. That avoids scanning every clause after every
        assignment, which is the main practical speedup over simple DPLL.
        """
        nonlocal learned_sequence, learned_count, learned_lbd_sum
        if learnt:
            learned_sequence += 1
        clause = Clause(list(lits), learnt=learnt, created=learned_sequence if learnt else 0, lbd=lbd)
        watches[offset + clause.lits[0]].append(clause)
        if len(clause.lits) > 1:
            watches[offset + clause.lits[1]].append(clause)
        if learnt:
            learned_db.append(clause)
            learned_count += 1
            learned_lbd_sum += lbd or 0
        else:
            original_clauses.append(clause)
        return clause

    for index, lits in enumerate(normalised):
        if index % CHECK_EVERY == 0 and stop_requested(cancel_token):
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
        Boolean constraint propagation with two watched literals.

        Every clause watches lits[0] and lits[1]. When a watched literal
        becomes false the clause looks for another literal that is not false
        and watches that one instead. If there is none, the clause is unit
        (lits[0] is forced) or, if lits[0] is false too, conflicting.
        Returns the conflicting clause, None, or `cancelled`.
        """
        nonlocal qhead, countdown

        while qhead < len(trail):
            false_lit = -trail[qhead]
            qhead += 1

            watch_list = watches[offset + false_lit]
            i = 0
            # Track the length by hand: calling len() on every step showed up
            # in the profile.
            remaining = len(watch_list)

            while i < remaining:
                countdown -= 1
                if countdown <= 0:
                    countdown = CHECK_EVERY
                    if stop_requested(cancel_token):
                        return cancelled

                clause = watch_list[i]
                if clause.deleted:
                    # Lazy deletion: drop clauses removed by cleanup here.
                    watch_list[i] = watch_list[-1]
                    watch_list.pop()
                    remaining -= 1
                    continue

                lits = clause.lits
                size = len(lits)
                if size == 1:
                    # A unit clause whose only literal is false.
                    return clause

                # Keep the false literal in position 1.
                if lits[0] == false_lit:
                    lits[0], lits[1] = lits[1], false_lit
                first = lits[0]

                if val[offset + first] == TRUE:
                    # The clause is already satisfied; keep watching.
                    i += 1
                    continue

                # Look for a replacement watch among lits[2:].
                for k in range(2, size):
                    candidate = lits[k]
                    if val[offset + candidate] != FALSE:
                        lits[1], lits[k] = candidate, false_lit
                        watches[offset + candidate].append(clause)
                        watch_list[i] = watch_list[-1]
                        watch_list.pop()
                        remaining -= 1
                        break
                else:
                    # No replacement: every literal but lits[0] is false.
                    if val[offset + first] == FALSE:
                        return clause
                    enqueue(first, clause)
                    clause.last_used = stats["conflicts"]
                    i += 1

        return None

    def bump_var(var):
        """Increase a variable's VSIDS activity after a conflict."""
        nonlocal var_inc

        activity[var] += var_inc

        # Keep floating point values bounded during long runs. Scaling every
        # score by the same factor keeps the heap order intact.
        if activity[var] > 1e100:
            for v in variables:
                activity[v] *= 1e-100
            var_inc *= 1e-100

        if branching_mode == "VSIDS" and heap_pos[var] >= 0:
            heap_up(heap_pos[var])

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

        Returns (learned literals, backjump level). learnt[0] is the asserting
        literal and learnt[1] the literal with the highest remaining level, so
        those two are the right ones to watch after the backjump.
        """
        learnt = []
        touched = []
        path_count = 0
        scan = len(trail) - 1
        clause = conflict_clause
        skip_var = None
        decision_level = current_level()
        conflicts_now = stats["conflicts"]

        while True:
            if clause.learnt:
                clause.last_used = conflicts_now
            for lit in clause.lits:
                var = abs(lit)

                if var == skip_var or seen[var] or levels[var] == 0:
                    continue

                seen[var] = True
                touched.append(var)
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
                for var in touched:
                    seen[var] = False
                return _dedupe_clause(conflict_clause.lits), 0

            pivot_var = abs(pivot)
            seen[pivot_var] = False
            path_count -= 1

            reason = reasons[pivot_var]

            if path_count == 0 or reason is None:
                learnt.insert(0, -pivot)
                break

            clause = reason
            skip_var = pivot_var

        for var in touched:
            seen[var] = False

        learnt = _dedupe_clause(learnt)

        # All literals except learnt[0] are false at the backjump level.
        # Jump to the highest of those levels so learnt[0] becomes unit.
        backjump_level = 0
        best = 1
        for index in range(1, len(learnt)):
            level = levels[abs(learnt[index])]
            if level > backjump_level:
                backjump_level = level
                best = index
        if len(learnt) > 2:
            learnt[1], learnt[best] = learnt[best], learnt[1]

        return learnt, backjump_level

    def backtrack(level):
        """
        Remove all assignments above 'level'.

        This is the "non-chronological" part of CDCL: after learning, we jump
        directly to the useful level instead of undoing one decision at a time.
        """
        nonlocal qhead

        if current_level() <= level:
            return
        start = trail_lim[level]
        del trail_lim[level:]

        for lit in trail[start:]:
            var = abs(lit)
            assignment[var] = None
            val[offset + lit] = UNASSIGNED
            val[offset - lit] = UNASSIGNED
            reasons[var] = None
            if use_heap:
                heap_insert(var)

        del trail[start:]
        qhead = min(qhead, len(trail))

    def locked_clauses():
        """Learned clauses that currently justify an assignment on the trail."""
        locked = set()
        for lit in trail:
            reason = reasons[abs(lit)]
            if reason is not None and reason.learnt:
                locked.add(reason)
        return locked

    def reduce_learned(keep_target, protect_glue):
        """
        Delete weak learned clauses (high LBD, long, not used recently).

        protect_glue keeps binary and glue clauses whatever happens. Clauses
        that are the reason of a current assignment are never deleted.
        Deleted clauses are only flagged here; propagate drops them from the
        watch lists when it next meets them, so no watch list is rebuilt.
        """
        nonlocal learned_db, learned_count, learned_lbd_sum
        if protect_glue:
            candidates = [
                clause for clause in learned_db
                if len(clause.lits) > 2 and (clause.lbd is None or clause.lbd > GLUE_LBD)
            ]
            keep_target = len(candidates) // 2
        else:
            candidates = learned_db

        remove_set = learned_clauses_to_delete(candidates, locked_clauses(), keep_target)
        if not remove_set:
            return

        for clause in remove_set:
            clause.deleted = True
            learned_count -= 1
            learned_lbd_sum -= clause.lbd or 0
        learned_db = [clause for clause in learned_db if not clause.deleted]
        stats["deleted_learned_clauses"] += len(remove_set)
        stats["reductions"] += 1
        log_debug(f"cleanup removed {len(remove_set)} learned clauses, {learned_count} left")

    def unresolved_clause_lits():
        """Yield the still-unresolved literals of clauses not yet satisfied."""
        for clause_list in (original_clauses, learned_db):
            for clause in clause_list:
                unresolved = []
                for lit in clause.lits:
                    value = val[offset + lit]
                    if value == TRUE:
                        break
                    if value == UNASSIGNED:
                        unresolved.append(lit)
                else:
                    if unresolved:
                        yield unresolved

    def pick_heap_var():
        """VSIDS / most frequent: the unassigned variable with the best score."""
        while heap:
            var = heap_pop()
            if assignment[var] is None:
                return var
        return None

    def pick_moms_var():
        """
        MOMS heuristic: focus on variables in the shortest unresolved clauses.

        Such clauses are nearest to unit propagation or conflict. MOMS and
        DLIS look at every clause at every decision, which is what makes them
        expensive on large formulas.
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
                    scores[abs(lit)] += 1

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
        if use_heap:
            return pick_heap_var(), None
        if branching_mode == "MOMS":
            return pick_moms_var(), None
        if branching_mode == "DLIS":
            return pick_dlis_decision()
        return pick_random_var(), None

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

    restart_count = 0
    conflicts_since_restart = 0
    restart_limit = restart_interval * (luby(0) if restart_strategy == "luby" else 1)
    reduce_interval = REDUCE_FIRST
    next_reduce = REDUCE_FIRST

    while True:
        countdown -= 1
        if countdown <= 0:
            countdown = CHECK_EVERY
            if stop_requested(cancel_token):
                return finish(None, cancellation_status(cancel_token))

        conflict = propagate()

        if conflict is cancelled:
            return finish(None, cancellation_status(cancel_token))

        if conflict is not None:
            stats["conflicts"] += 1
            conflicts_since_restart += 1
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

            learnt_lbd = clause_lbd(learnt_lits, levels)
            learnt_clause = add_clause(learnt_lits, learnt=True, lbd=learnt_lbd)
            stats["learned_clauses"] += 1
            log_debug(f"learned clause LBD {learnt_lbd}")

            backtrack(backjump_level)

            # The learned clause is now unit. Enqueueing its first literal makes
            # the solver immediately avoid the same conflict pattern.
            if not enqueue(learnt_lits[0], learnt_clause):
                if current_level() == 0:
                    return finish(None, "UNSAT")
                continue

            # Learned-clause cleanup: either the automatic schedule or, with a
            # fixed limit, halve the database whenever it grows past the limit.
            if auto_cleanup and stats["conflicts"] >= next_reduce:
                reduce_learned(0, protect_glue=True)
                reduce_interval += REDUCE_STEP
                next_reduce = stats["conflicts"] + reduce_interval
            elif learned_clause_limit is not None and learned_count > learned_clause_limit:
                reduce_learned(learned_clause_limit // 2, protect_glue=False)

            if restarts_enabled and conflicts_since_restart >= restart_limit:
                # A restart discards the current decisions but keeps learned
                # clauses (and VSIDS scores and saved phases), so the search
                # starts again from a stronger formula.
                conflicts_since_restart = 0
                restart_count += 1
                if restart_strategy == "luby":
                    restart_limit = restart_interval * luby(restart_count)
                if current_level() > 0:
                    stats["restarts"] += 1
                    log_debug(f"restart {stats['restarts']} after {stats['conflicts']} conflicts")
                    backtrack(0)

            continue

        decision_var, branch_phase = pick_branch_decision()

        if decision_var is None:
            # No decision is needed: every clause is satisfied. (VSIDS stops
            # here once every variable has a value; MOMS and DLIS stop as soon
            # as no unresolved clause is left, and the variables that are
            # still free can take any value, so they get their preferred one.)
            solution = {
                var: assignment[var] if assignment[var] is not None else preferred_phase[var]
                for var in variables
            }
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
