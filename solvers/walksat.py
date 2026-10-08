"""
WalkSAT and ProbSAT: incomplete local-search SAT solvers.

Both start from a random complete assignment and repeatedly flip one variable
of a randomly chosen unsatisfied clause. They differ only in which variable
of that clause they flip:

- WalkSAT (the SKC variant of Selman, Kautz and Cohen): if a variable can be
  flipped without breaking any satisfied clause, flip it (a "free" move).
  Otherwise, with probability `noise` flip a random variable of the clause,
  else the one that breaks the fewest clauses.
- ProbSAT (Balint and Schoening, 2012): pick a variable of the clause at
  random, with probability proportional to f(break), a function that falls
  steeply as break grows. No noise parameter: the randomness is in f.

"break" of a variable = number of currently satisfied clauses that would
become unsatisfied if it were flipped. It is kept up to date incrementally
(see LocalSearchState), so choosing a variable costs a few lookups.

Finding an assignment with no unsatisfied clause proves SAT. Running out of
tries and flips proves nothing: the result is UNKNOWN, never UNSAT.

docs/algorithms/walksat.md walks through an example.
"""

from __future__ import annotations

import random
import time

from sat_core.runtime import EVENT_LOG, cancellation_status, emit, stop_requested


# Cancel/timeout checks happen every CHECK_EVERY flips (see cdcl.py).
CHECK_EVERY = 1024

# WalkSAT/SKC noise that works best on random 3-SAT in the literature.
DEFAULT_NOISE = 0.567

# ProbSAT's published defaults: for 3-SAT f(b) = (EPS + b) ** -cb with
# cb = 2.06; for longer clauses f(b) = cb ** -b with cb growing with the
# clause length k.
PROBSAT_EPS = 0.9
PROBSAT_POLY_CB = 2.06
PROBSAT_EXP_CB = {4: 3.0, 5: 3.7, 6: 5.1}
PROBSAT_EXP_CB_LONG = 5.4


def _normalise_formula(clauses):
    """
    Prepare a CNF formula for local search.

    Duplicate literals are removed and tautological clauses are skipped because
    they are already satisfied by every assignment. An empty clause is recorded
    because no complete assignment can satisfy it. Every variable of the input
    is collected, so the model gives each one a value.
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
            variables.add(abs(lit))
            if -lit in seen:
                tautology = True
            elif lit not in seen:
                clean.append(lit)
                seen.add(lit)

        if tautology:
            continue
        if clean:
            clean_clauses.append(clean)
        else:
            has_empty_clause = True

    return clean_clauses, sorted(variables), has_empty_clause


def probsat_weights(max_clause_length, max_break, cb=None):
    """
    ProbSAT's f(break) for break = 0 .. max_break, as a lookup table.

    3-SAT (and shorter clauses) uses the polynomial (0.9 + b) ** -cb; longer
    clauses use the exponential cb ** -b. cb=None picks the published default
    for the clause length.
    """
    if max_clause_length <= 3:
        exponent = PROBSAT_POLY_CB if cb is None else cb
        return [(PROBSAT_EPS + b) ** -exponent for b in range(max_break + 1)], "poly", exponent
    base = cb if cb is not None else PROBSAT_EXP_CB.get(max_clause_length, PROBSAT_EXP_CB_LONG)
    return [base ** -b for b in range(max_break + 1)], "exp", base


class LocalSearchState:
    """
    A complete assignment plus the bookkeeping that makes one flip cheap.

    For every clause c:
      true_count[c]  how many of its literals are true;
      true_sum[c]    the sum of the variable numbers of its true literals.
    When true_count[c] == 1, true_sum[c] *is* the one true variable: the
    clause's "critical" variable, the one whose flip would break it.

    For every variable v:
      breaks[v]      number of clauses for which v is critical, i.e. its break.

    The unsatisfied clauses are kept in a list with an index map, so picking a
    random one, adding and removing are all O(1).

    Flipping v only touches the clauses that contain v (see flip()).
    """

    def __init__(self, clauses, variables, values):
        self.clauses = clauses
        max_var = max(variables) if variables else 0
        self.offset = max_var
        self.values = values  # list indexed by variable: True / False
        self.occurs = [[] for _ in range(2 * max_var + 1)]
        for index, clause in enumerate(clauses):
            for lit in clause:
                self.occurs[max_var + lit].append(index)
        count = len(clauses)
        self.true_count = [0] * count
        self.true_sum = [0] * count
        self.breaks = [0] * (max_var + 1)
        self.unsat = []
        self.unsat_pos = [-1] * count
        self.reset(values)

    def reset(self, values):
        """Recompute everything for a new assignment (used at each try)."""
        self.values = values
        breaks = self.breaks
        breaks[:] = [0] * len(breaks)
        self.unsat.clear()
        for index, clause in enumerate(self.clauses):
            true = 0
            total = 0
            for lit in clause:
                if values[abs(lit)] == (lit > 0):
                    true += 1
                    total += abs(lit)
            self.true_count[index] = true
            self.true_sum[index] = total
            self.unsat_pos[index] = -1
            if true == 0:
                self.unsat_pos[index] = len(self.unsat)
                self.unsat.append(index)
            elif true == 1:
                breaks[total] += 1

    def make_of(self, variable):
        """Unsatisfied clauses that flipping variable would satisfy (for logs and tests)."""
        false_lit = -variable if self.values[variable] else variable
        return sum(1 for c in self.occurs[self.offset + false_lit] if self.true_count[c] == 0)

    def flip(self, variable):
        """
        Flip one variable and update the counters of the clauses containing it.

        The literal of `variable` that was true becomes false: its clauses lose
        a true literal. The opposite literal becomes true: its clauses gain one.
        Each change may make a clause unsatisfied or satisfied, or change which
        variable is its critical one.
        """
        offset = self.offset
        true_count = self.true_count
        true_sum = self.true_sum
        breaks = self.breaks
        unsat = self.unsat
        unsat_pos = self.unsat_pos
        was_true = variable if self.values[variable] else -variable

        for c in self.occurs[offset + was_true]:
            count = true_count[c] - 1
            true_count[c] = count
            true_sum[c] -= variable
            if count == 0:
                # Was critical for c; now c is unsatisfied.
                breaks[variable] -= 1
                unsat_pos[c] = len(unsat)
                unsat.append(c)
            elif count == 1:
                # The one remaining true variable becomes critical.
                breaks[true_sum[c]] += 1

        for c in self.occurs[offset - was_true]:
            count = true_count[c] + 1
            true_count[c] = count
            true_sum[c] += variable
            if count == 1:
                # c becomes satisfied, with `variable` as its critical one.
                breaks[variable] += 1
                position = unsat_pos[c]
                last = unsat.pop()
                if last != c:
                    unsat[position] = last
                    unsat_pos[last] = position
                unsat_pos[c] = -1
            elif count == 2:
                # The previously critical variable is no longer alone.
                breaks[true_sum[c] - variable] -= 1

        self.values[variable] = not self.values[variable]


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
    WalkSAT / ProbSAT local search.

    Options (keyword arguments or logging_options keys):
    - selection_mode: "walksat" (default) or "probsat"
    - max_tries: random restarts (default 10)
    - max_flips: flips per try (default 100,000)
    - noise: WalkSAT's random-move probability (default 0.567)
    - adaptive_noise: WalkSAT only; raise noise when stuck (default off)
    - cb: ProbSAT's break exponent/base (default: by clause length)
    - random_seed, mode (normal/periodic/debug), progress_interval

    Return:
    - dict {variable: True/False} if SAT
    - None when no solution is found within the budget (status UNKNOWN,
      which is not an UNSAT proof)
    - (solution, stats) when return_stats=True
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

    def positive_float_or_none(value):
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

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
    max_flips = positive_int(logging_options.get("max_flips", max_flips), 100_000)
    noise = probability(logging_options.get("noise", noise), DEFAULT_NOISE)
    selection_mode = normalise_selection_mode(logging_options.get("selection_mode"))
    probsat = selection_mode == "probsat"
    adaptive_noise = bool_option(logging_options.get("adaptive_noise"), False) and not probsat
    cb_option = positive_float_or_none(logging_options.get("cb"))
    random_seed = logging_options.get("random_seed")
    rng = random.Random(random_seed) if random_seed not in (None, "") else random.Random()
    log_mode = logging_options.get("mode", "normal")
    if log_mode not in ("normal", "periodic", "debug"):
        log_mode = "normal"
    progress_interval = positive_int(logging_options.get("progress_interval"), 10_000)
    verbose_limit = positive_int(logging_options.get("verbose_limit"), 120)
    current_noise = noise
    stagnation_limit = max(100, max_flips // 20)
    flips_since_global_best = 0

    stats = {
        "status": "UNKNOWN",
        "termination_reason": None,
        "selection_mode": selection_mode,
        "tries": 0,
        "flips": 0,
        "best_unsatisfied": None,
        "best_assignment": None,
        "restart_stats": [],
        "hard_clause_hits": {},
        "flip_break_total": 0,
        "last_break": 0,
        "elapsed": 0.0,
    }
    if probsat:
        stats["cb"] = cb_option
    else:
        stats.update(
            {
                "adaptive_noise": adaptive_noise,
                "stagnation_limit": stagnation_limit,
                "free_flips": 0,
                "noise_flips": 0,
                "greedy_flips": 0,
                "final_noise": noise,
            }
        )
    verbose_emitted = 0
    last_progress_flips = 0

    def strategy_text():
        if probsat:
            return f"strategy=probsat, f={stats.get('weight_function', '?')}, cb={stats.get('cb')}"
        return f"strategy=walksat, noise={current_noise:.3g}, adaptive_noise={'on' if adaptive_noise else 'off'}"

    # Per-flip counters live in local variables (updating the stats dict on
    # every flip was a visible cost); sync_counters() copies them into stats.
    flips = 0
    break_total = 0
    last_break = 0
    free_flips = noise_flips = greedy_flips = 0

    def sync_counters():
        stats["flips"] = flips
        stats["flip_break_total"] = break_total
        stats["last_break"] = last_break
        if not probsat:
            stats["free_flips"] = free_flips
            stats["noise_flips"] = noise_flips
            stats["greedy_flips"] = greedy_flips

    def finish(solution, status):
        """Set final status fields and return the public result shape."""
        sync_counters()
        stats["status"] = status
        if status == "SAT":
            stats["termination_reason"] = "sat"
        elif status in ("TIMEOUT", "CANCELLED", "SKIPPED"):
            stats["termination_reason"] = status.lower()
        elif stats["termination_reason"] is None:
            stats["termination_reason"] = "budget_exhausted"
        if not probsat:
            stats["final_noise"] = current_noise
        stats["elapsed"] = time.perf_counter() - started
        if return_stats:
            return solution, stats
        return solution

    def log_debug(message):
        nonlocal verbose_emitted
        if log_mode != "debug" or verbose_emitted >= verbose_limit:
            return
        verbose_emitted += 1
        emit(event_callback, EVENT_LOG, f"      WalkSAT debug: {message}")

    def log_progress(force=False):
        nonlocal last_progress_flips
        if log_mode not in ("periodic", "debug"):
            return
        if not force and flips - last_progress_flips < progress_interval:
            return
        sync_counters()
        last_progress_flips = flips
        emit(
            event_callback,
            EVENT_LOG,
            (
                "      WalkSAT progress: "
                f"tries={stats['tries']}, flips={stats['flips']}, "
                f"unsatisfied={len(state.unsat) if state else '-'}, "
                f"best_unsatisfied={stats['best_unsatisfied']}, "
                f"{strategy_text()}, last_break={stats['last_break']}"
            ),
        )

    state = None
    if stop_requested(cancel_token):
        return finish(None, cancellation_status(cancel_token))

    formula, variables, has_empty_clause = _normalise_formula(clauses)
    if has_empty_clause:
        stats["best_unsatisfied"] = 1
        stats["termination_reason"] = "empty_clause"
        return finish(None, "UNKNOWN")
    if not formula:
        model = {variable: False for variable in variables}
        stats["best_unsatisfied"] = 0
        stats["best_assignment"] = dict(model)
        return finish(model, "SAT")

    # Work on compact variable numbers 1..n. The app's encoders use sparse,
    # readable numbers (a 9x9 Sudoku goes up to 90909 for 729 variables), and
    # every per-variable array would otherwise be that long.
    original = variables                      # compact v -> original variable
    compact_of = {var: index + 1 for index, var in enumerate(original)}
    formula = [[compact_of[lit] if lit > 0 else -compact_of[-lit] for lit in clause] for clause in formula]
    variables = list(range(1, len(original) + 1))
    values = [False] * (len(original) + 1)
    state = LocalSearchState(formula, variables, values)
    hits = [0] * len(formula)
    breaks = state.breaks
    unsat = state.unsat

    if probsat:
        max_break = max(len(occ) for occ in state.occurs)
        weights, family, parameter = probsat_weights(max(len(c) for c in formula), max_break, cb_option)
        stats["cb"] = parameter
        stats["weight_function"] = "(0.9 + break)^-cb" if family == "poly" else "cb^-break"

    if log_mode in ("periodic", "debug"):
        extra = "" if probsat else f", stagnation_limit={stagnation_limit}"
        emit(event_callback, EVENT_LOG, f"      WalkSAT options: {strategy_text()}{extra}")

    best_unsatisfied = len(formula) + 1
    best_values = None
    countdown = CHECK_EVERY

    for try_index in range(1, max_tries + 1):
        if stop_requested(cancel_token):
            return finish(None, cancellation_status(cancel_token))

        # Each try restarts from a fresh random assignment: a jump to another
        # region of the search space, not a logical backtrack.
        stats["tries"] = try_index
        for variable in variables:
            values[variable] = rng.random() < 0.5
        state.reset(values)
        try_best = len(unsat)
        try_flips_until_best = 0
        log_debug(f"try {try_index}: random assignment with {len(unsat)} unsatisfied clauses")

        for flip_index in range(max_flips):
            unsatisfied = len(unsat)
            if unsatisfied < try_best:
                try_best = unsatisfied
                try_flips_until_best = flip_index
            if unsatisfied < best_unsatisfied:
                best_unsatisfied = unsatisfied
                stats["best_unsatisfied"] = unsatisfied
                best_values = values[:]  # n + 1 entries thanks to compact numbering
                flips_since_global_best = 0
                if adaptive_noise and current_noise > noise:
                    current_noise = max(noise, current_noise - 0.02)
                    log_debug(f"adaptive noise reduced to {current_noise:.3g} after a new best")

            if unsatisfied == 0:
                # A complete assignment satisfying every clause is a
                # certificate of satisfiability.
                stats["restart_stats"].append(
                    {"try": try_index, "best_unsatisfied": 0, "flips_until_best": flip_index, "final_unsatisfied": 0}
                )
                stats["hard_clause_hits"] = {index: count for index, count in enumerate(hits) if count}
                model = {original[variable - 1]: values[variable] for variable in variables}
                stats["best_assignment"] = dict(model)
                log_progress(force=True)
                return finish(model, "SAT")

            countdown -= 1
            if countdown <= 0:
                countdown = CHECK_EVERY
                if stop_requested(cancel_token):
                    stats["restart_stats"].append(
                        {"try": try_index, "best_unsatisfied": try_best, "flips_until_best": try_flips_until_best, "final_unsatisfied": unsatisfied}
                    )
                    stats["hard_clause_hits"] = {index: count for index, count in enumerate(hits) if count}
                    stats["best_assignment"] = {original[v - 1]: best_values[v] for v in variables} if best_values else None
                    return finish(None, cancellation_status(cancel_token))

            clause_index = unsat[rng.randrange(unsatisfied)]
            hits[clause_index] += 1
            clause = formula[clause_index]

            if probsat:
                # Sample a variable with probability proportional to f(break).
                clause_weights = [weights[breaks[abs(lit)]] for lit in clause]
                target = rng.random() * sum(clause_weights)
                variable = abs(clause[-1])
                running = 0.0
                for lit, weight in zip(clause, clause_weights):
                    running += weight
                    if running >= target:
                        variable = abs(lit)
                        break
                if log_mode == "debug" and verbose_emitted < verbose_limit:
                    log_debug(
                        f"probsat flip variable {original[variable - 1]} break={breaks[variable]} "
                        f"weight={weights[breaks[variable]]:.4g} of {sum(clause_weights):.4g}"
                    )
            else:
                # WalkSAT/SKC: a free move if there is one, else noise or greedy.
                best_break = None
                candidates = []
                for lit in clause:
                    b = breaks[abs(lit)]
                    if best_break is None or b < best_break:
                        best_break = b
                        candidates = [lit]
                    elif b == best_break:
                        candidates.append(lit)
                if best_break == 0:
                    variable = abs(candidates[rng.randrange(len(candidates))])
                    free_flips += 1
                    kind = "free"
                elif rng.random() < current_noise:
                    variable = abs(clause[rng.randrange(len(clause))])
                    noise_flips += 1
                    kind = "noise"
                else:
                    variable = abs(candidates[rng.randrange(len(candidates))])
                    greedy_flips += 1
                    kind = "greedy"
                if log_mode == "debug" and verbose_emitted < verbose_limit:
                    log_debug(f"{kind} flip variable {original[variable - 1]} break={breaks[variable]}")

            last_break = breaks[variable]
            break_total += last_break
            state.flip(variable)
            flips += 1

            if adaptive_noise:
                flips_since_global_best += 1
                if flips_since_global_best >= stagnation_limit:
                    # No new global best for a while: more randomness to
                    # escape the current local minimum.
                    flips_since_global_best = 0
                    if current_noise < 0.9:
                        current_noise = min(0.9, current_noise + 0.05)
                        log_debug(f"adaptive noise increased to {current_noise:.3g} after stagnation")
            if log_mode != "normal":
                log_progress()

        stats["restart_stats"].append(
            {"try": try_index, "best_unsatisfied": try_best, "flips_until_best": try_flips_until_best, "final_unsatisfied": len(unsat)}
        )

    stats["hard_clause_hits"] = {index: count for index, count in enumerate(hits) if count}
    stats["best_assignment"] = {original[v - 1]: best_values[v] for v in variables} if best_values else None
    log_progress(force=True)
    stats["termination_reason"] = "budget_exhausted"
    return finish(None, "UNKNOWN")
