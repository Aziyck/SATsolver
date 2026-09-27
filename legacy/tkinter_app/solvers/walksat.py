"""
WalkSAT and ProbSAT-style incomplete SAT solvers.

These algorithms perform local search over complete truth assignments. They
try to reduce the number of unsatisfied clauses by flipping variables chosen
from currently unsatisfied clauses. Finding an assignment with zero unsatisfied
clauses proves SAT, but exhausting the flip budget does not prove UNSAT.
"""

from __future__ import annotations

import random
import time

from sat_core.runtime import EVENT_LOG, cancellation_status, emit, stop_requested


def _normalise_formula(clauses):
    """
    Prepare a CNF formula for local search.

    Duplicate literals are removed and tautological clauses are skipped because
    they are already satisfied by every assignment. An empty clause is recorded
    because no complete assignment can satisfy it.
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
                clean.append(lit)
                seen.add(lit)
                variables.add(abs(lit))

        if tautology:
            continue
        if clean:
            clean_clauses.append(clean)
        else:
            has_empty_clause = True

    return clean_clauses, sorted(variables), has_empty_clause


class _UnsatisfiedTracker:
    """
    Incrementally track which clauses are unsatisfied by a complete assignment.

    Local search repeatedly flips one variable. Recomputing every clause after
    each flip would be expensive, so this tracker stores, for each clause, how
    many of its literals are currently true. A clause is unsatisfied exactly
    when that count is zero.
    """
    def __init__(self, clauses, variables, assignment):
        self.clauses = clauses
        self.assignment = assignment
        self.occurrences = {variable: [] for variable in variables}
        self.satisfied_counts = [0] * len(clauses)
        self.unsatisfied_list = []
        self.unsatisfied_positions = {}

        for clause_index, clause in enumerate(clauses):
            count = 0
            for lit in clause:
                variable = abs(lit)
                self.occurrences.setdefault(variable, []).append(clause_index)
                if self._literal_satisfied(lit):
                    count += 1

            self.satisfied_counts[clause_index] = count
            if count == 0:
                self._mark_unsatisfied(clause_index)

    def _literal_satisfied(self, lit):
        """Evaluate whether one signed literal is true in the current assignment."""
        value = self.assignment.get(abs(lit), False)
        return (lit > 0 and value) or (lit < 0 and not value)

    def _mark_unsatisfied(self, clause_index):
        """Add a clause to the unsatisfied set if it is not already present."""
        if clause_index in self.unsatisfied_positions:
            return
        self.unsatisfied_positions[clause_index] = len(self.unsatisfied_list)
        self.unsatisfied_list.append(clause_index)

    def _mark_satisfied(self, clause_index):
        """Remove a clause from the unsatisfied set in constant time."""
        position = self.unsatisfied_positions.pop(clause_index, None)
        if position is None:
            return

        last_clause = self.unsatisfied_list.pop()
        if position < len(self.unsatisfied_list):
            self.unsatisfied_list[position] = last_clause
            self.unsatisfied_positions[last_clause] = position

    def unsatisfied_count(self):
        """Return the objective value minimized by local search."""
        return len(self.unsatisfied_list)

    def random_unsatisfied_clause_index(self, rng):
        """Choose a currently false clause as the next repair target."""
        return rng.choice(self.unsatisfied_list)

    def random_unsatisfied_clause(self, rng):
        return self.clauses[self.random_unsatisfied_clause_index(rng)]

    def flip_score(self, variable):
        """Score a variable by the number of unsatisfied clauses after flipping it."""
        return self.flip_effect(variable)["unsatisfied_after"]

    def flip_effect(self, variable):
        """
        Compute the make/break effect of flipping one variable.

        make counts clauses that would become satisfied; break counts clauses
        that would become unsatisfied. The best flips have high make and low
        break.
        """
        unsatisfied_after = self.unsatisfied_count()
        make = 0
        break_count = 0
        current_value = self.assignment[variable]

        for clause_index in self.occurrences.get(variable, []):
            old_count = self.satisfied_counts[clause_index]
            delta = 0
            for lit in self.clauses[clause_index]:
                if abs(lit) != variable:
                    continue
                old_satisfied = (lit > 0 and current_value) or (lit < 0 and not current_value)
                delta += -1 if old_satisfied else 1

            new_count = old_count + delta
            if old_count == 0 and new_count > 0:
                unsatisfied_after -= 1
                make += 1
            elif old_count > 0 and new_count == 0:
                unsatisfied_after += 1
                break_count += 1

        return {
            "unsatisfied_after": unsatisfied_after,
            "make": make,
            "break": break_count,
            "delta": break_count - make,
        }

    def flip(self, variable):
        """
        Apply one local-search move and update all affected clause counts.

        Only clauses containing the flipped variable can change satisfaction
        status, so the update is local rather than a full formula scan.
        """
        current_value = self.assignment[variable]

        for clause_index in self.occurrences.get(variable, []):
            old_count = self.satisfied_counts[clause_index]
            delta = 0
            for lit in self.clauses[clause_index]:
                if abs(lit) != variable:
                    continue
                old_satisfied = (lit > 0 and current_value) or (lit < 0 and not current_value)
                delta += -1 if old_satisfied else 1

            new_count = old_count + delta
            self.satisfied_counts[clause_index] = new_count

            if old_count == 0 and new_count > 0:
                self._mark_satisfied(clause_index)
            elif old_count > 0 and new_count == 0:
                self._mark_unsatisfied(clause_index)

        self.assignment[variable] = not current_value


def walksat(
    clauses,
    max_tries=None,
    max_flips=None,
    noise=None,
    return_stats=False,
    event_callback=None,
    cancel_token=None,
    logging_options=None,
):
    """
    Incomplete WalkSAT-style local-search SAT solver.

    The solver repeatedly starts from a random complete assignment. During each
    try it selects an unsatisfied clause and flips one variable in that clause,
    either randomly or according to a make/break heuristic.

    Return:
    - dict {variable: True/False} if SAT
    - None when no solution is found within the search budget
    - (solution, stats) when return_stats=True

    A None result with status UNKNOWN is not an UNSAT proof.
    """
    started = time.perf_counter()
    logging_options = logging_options or {}

    def positive_int(value, default):
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return default

    def probability(value, default):
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return default
        return min(1.0, max(0.0, parsed))

    def bool_option(value, default=False):
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on", "enabled")
        return bool(value)

    def normalise_selection_mode(value):
        key = str(value or "walksat").strip().lower().replace(" ", "_").replace("-", "_")
        if key in ("probsat", "prob_sat", "probabilistic"):
            return "probsat"
        return "walksat"

    max_tries = positive_int(logging_options.get("max_tries", max_tries), 10)
    max_flips = positive_int(logging_options.get("max_flips", max_flips), 10000)
    noise = probability(logging_options.get("noise", noise), 0.5)
    selection_mode = normalise_selection_mode(logging_options.get("selection_mode"))
    adaptive_noise = bool_option(logging_options.get("adaptive_noise"), False)
    random_seed = logging_options.get("random_seed")
    rng = random.Random(random_seed) if random_seed not in (None, "") else random.Random()
    log_mode = logging_options.get("mode", "normal")
    if log_mode not in ("normal", "periodic", "debug"):
        log_mode = "normal"
    progress_interval = positive_int(logging_options.get("progress_interval"), 1000)
    verbose_limit = positive_int(logging_options.get("verbose_limit"), 120)
    current_noise = noise
    stagnation_limit = max(100, max_flips // 20)
    flips_since_global_best = 0

    stats = {
        "status": "UNKNOWN",
        "termination_reason": None,
        "selection_mode": selection_mode,
        "adaptive_noise": adaptive_noise,
        "stagnation_limit": stagnation_limit,
        "tries": 0,
        "flips": 0,
        "best_unsatisfied": None,
        "best_assignment": None,
        "restart_stats": [],
        "hard_clause_hits": {},
        "flip_make_total": 0,
        "flip_break_total": 0,
        "last_make": 0,
        "last_break": 0,
        "final_noise": noise,
        "elapsed": 0.0,
        "solver_options": (
            f"tries={max_tries}; flips={max_flips}; noise={noise:g}; "
            f"strategy={selection_mode}; adaptive_noise={'on' if adaptive_noise else 'off'}; "
            f"seed={random_seed if random_seed not in (None, '') else '-'}"
        ),
    }
    verbose_emitted = 0
    last_progress_work = 0

    def finish(solution, status):
        """Set final status fields and return the public result shape."""
        stats["status"] = status
        if status == "SAT":
            stats["termination_reason"] = "sat"
        elif status in ("TIMEOUT", "CANCELLED"):
            stats["termination_reason"] = status.lower()
        elif stats["termination_reason"] is None:
            stats["termination_reason"] = "budget_exhausted"
        stats["final_noise"] = current_noise
        stats["elapsed"] = time.perf_counter() - started
        if return_stats:
            return solution, stats
        return solution

    def log_option_summary():
        if log_mode not in ("periodic", "debug"):
            return
        emit(
            event_callback,
            EVENT_LOG,
            (
                "      WalkSAT options: "
                f"strategy={selection_mode}, "
                f"noise={noise:g}, "
                f"adaptive_noise={'on' if adaptive_noise else 'off'}, "
                f"stagnation_limit={stagnation_limit}"
            ),
        )

    def log_adaptive_noise(message):
        if log_mode not in ("periodic", "debug"):
            return
        emit(event_callback, EVENT_LOG, f"      WalkSAT adaptive noise: {message}")

    def choose_weighted(candidates):
        """
        Sample one candidate proportionally to its positive weight.

        ProbSAT uses this to prefer good flips while still allowing randomness,
        which helps escape local minima.
        """
        total = sum(weight for _variable, _effect, weight in candidates)
        if total <= 0:
            return rng.choice(candidates)
        target = rng.random() * total
        running = 0.0
        for candidate in candidates:
            running += candidate[2]
            if running >= target:
                return candidate
        return candidates[-1]

    def select_variable(clause):
        """
        Choose which variable to flip from an unsatisfied clause.

        With probability current_noise, WalkSAT makes a random repair move.
        Otherwise it uses either ProbSAT's weighted make/break rule or a greedy
        rule that minimizes the number of unsatisfied clauses after the flip.
        """
        if rng.random() < current_noise:
            variable = abs(rng.choice(clause))
            effect = tracker.flip_effect(variable)
            log_debug(f"random flip variable {variable}")
            return variable, effect

        effects = [(abs(lit), tracker.flip_effect(abs(lit))) for lit in clause]
        if selection_mode == "probsat":
            weighted = [
                (variable, effect, (effect["make"] + 1) / ((effect["break"] + 1) ** 2))
                for variable, effect in effects
            ]
            variable, effect, _weight = choose_weighted(weighted)
            log_debug(
                f"probsat flip variable {variable} "
                f"make={effect['make']} break={effect['break']} weight={_weight:.4g}"
            )
            return variable, effect

        best_score = min(effect["unsatisfied_after"] for _variable, effect in effects)
        best_candidates = [
            (variable, effect)
            for variable, effect in effects
            if effect["unsatisfied_after"] == best_score
        ]
        variable, effect = rng.choice(best_candidates)
        log_debug(f"greedy flip variable {variable} leaving {best_score} unsatisfied")
        return variable, effect

    def log_debug(message):
        nonlocal verbose_emitted
        if log_mode != "debug" or verbose_emitted >= verbose_limit:
            return
        verbose_emitted += 1
        emit(event_callback, EVENT_LOG, f"      WalkSAT debug: {message}")

    def log_progress(force=False):
        nonlocal last_progress_work
        if log_mode not in ("periodic", "debug"):
            return
        work = stats["flips"]
        if not force and work - last_progress_work < progress_interval:
            return
        last_progress_work = work
        emit(
            event_callback,
            EVENT_LOG,
            (
                "      WalkSAT progress: "
                f"tries={stats['tries']}, "
                f"flips={stats['flips']}, "
                f"best_unsatisfied={stats['best_unsatisfied']}, "
                f"strategy={selection_mode}, "
                f"noise={current_noise:.3g}, "
                f"adaptive_noise={'on' if adaptive_noise else 'off'}, "
                f"last_make={stats['last_make']}, "
                f"last_break={stats['last_break']}"
            ),
        )

    if stop_requested(cancel_token):
        return finish(None, cancellation_status(cancel_token))

    normalised, variables, has_empty_clause = _normalise_formula(clauses)
    if has_empty_clause:
        stats["best_unsatisfied"] = 1
        stats["termination_reason"] = "empty_clause"
        return finish(None, "UNKNOWN")
    if not normalised:
        stats["best_unsatisfied"] = 0
        stats["best_assignment"] = {variable: False for variable in variables}
        return finish({variable: False for variable in variables}, "SAT")

    # The optimization objective is the number of unsatisfied clauses. A value
    # of zero means the current complete assignment is a SAT model.
    best_unsatisfied = len(normalised)
    stats["best_unsatisfied"] = best_unsatisfied
    log_option_summary()

    for try_index in range(1, max_tries + 1):
        if stop_requested(cancel_token):
            return finish(None, cancellation_status(cancel_token))

        # Each try is a restart from a fresh complete assignment. This is not a
        # logical backtrack; it is a stochastic attempt to enter a better basin
        # of the search landscape.
        stats["tries"] = try_index
        assignment = {variable: rng.choice((False, True)) for variable in variables}
        tracker = _UnsatisfiedTracker(normalised, variables, assignment)
        try_best_unsatisfied = tracker.unsatisfied_count()
        try_flips_until_best = 0
        if stats["best_assignment"] is None and try_best_unsatisfied == best_unsatisfied:
            stats["best_assignment"] = assignment.copy()
        log_debug(f"try {try_index}: random assignment")

        for flip_index in range(max_flips):
            unsatisfied_count = tracker.unsatisfied_count()
            if unsatisfied_count < try_best_unsatisfied:
                try_best_unsatisfied = unsatisfied_count
                try_flips_until_best = flip_index
            if unsatisfied_count < best_unsatisfied:
                best_unsatisfied = unsatisfied_count
                stats["best_unsatisfied"] = best_unsatisfied
                stats["best_assignment"] = assignment.copy()
                flips_since_global_best = 0
                if adaptive_noise:
                    old_noise = current_noise
                    current_noise = max(noise, current_noise - 0.02)
                    if current_noise != old_noise:
                        log_adaptive_noise(f"reduced to {current_noise:.3g} after new best")
                log_progress()

            if unsatisfied_count == 0:
                # A complete assignment satisfying every clause is an explicit
                # certificate of satisfiability.
                stats["best_assignment"] = assignment.copy()
                stats["restart_stats"].append(
                    {
                        "try": try_index,
                        "best_unsatisfied": try_best_unsatisfied,
                        "flips_until_best": try_flips_until_best,
                        "final_unsatisfied": 0,
                    }
                )
                log_progress(force=True)
                return finish(assignment, "SAT")

            if stop_requested(cancel_token):
                stats["restart_stats"].append(
                    {
                        "try": try_index,
                        "best_unsatisfied": try_best_unsatisfied,
                        "flips_until_best": try_flips_until_best,
                        "final_unsatisfied": unsatisfied_count,
                    }
                )
                return finish(None, cancellation_status(cancel_token))

            clause_index = tracker.random_unsatisfied_clause_index(rng)
            stats["hard_clause_hits"][clause_index] = stats["hard_clause_hits"].get(clause_index, 0) + 1
            clause = tracker.clauses[clause_index]
            variable, effect = select_variable(clause)
            stats["last_make"] = effect["make"]
            stats["last_break"] = effect["break"]
            stats["flip_make_total"] += effect["make"]
            stats["flip_break_total"] += effect["break"]

            tracker.flip(variable)
            stats["flips"] += 1
            flips_since_global_best += 1
            if adaptive_noise and flips_since_global_best >= stagnation_limit:
                # When no new global best has appeared for a while, increase
                # randomness to help escape a local minimum.
                old_noise = current_noise
                current_noise = min(0.9, current_noise + 0.05)
                flips_since_global_best = 0
                if current_noise != old_noise:
                    log_adaptive_noise(f"increased to {current_noise:.3g} after stagnation")
            log_progress()

        stats["restart_stats"].append(
            {
                "try": try_index,
                "best_unsatisfied": try_best_unsatisfied,
                "flips_until_best": try_flips_until_best,
                "final_unsatisfied": tracker.unsatisfied_count(),
            }
        )

    log_progress(force=True)
    stats["termination_reason"] = "budget_exhausted"
    return finish(None, "UNKNOWN")
