# WalkSAT and ProbSAT: local search

WalkSAT and ProbSAT are local-search SAT solvers. They do not explore a
search tree like DPLL and CDCL. They hold one complete assignment (every
variable has a value) and keep changing it, one variable at a time, until
every clause is true.

| | DPLL / CDCL | WalkSAT / ProbSAT |
|---|---|---|
| State | a partial assignment plus a trail of decisions | a complete assignment |
| One step | decide, propagate, backtrack on a conflict | flip one variable |
| Can prove SAT | yes | yes: a model is a proof |
| Can prove UNSAT | yes | no: the answer is `UNKNOWN` |
| Strong on | structured formulas (Sudoku, graphs), UNSAT | large satisfiable random formulas |

Both solvers live in `solvers/walksat.py`. They share all the bookkeeping and
differ only in how they pick the variable to flip. The version that mixed the
two ideas (ProbSAT with a noise option and a make/break weight) is archived in
`legacy/walksat_original.py`.

## The loop

```text
for try in 1 .. max_tries:
    give every variable a random value
    repeat max_flips times:
        if no clause is false: return SAT (the assignment is the model)
        pick a false clause C at random
        pick a variable x of C          <- WalkSAT and ProbSAT differ here
        flip x
return UNKNOWN
```

Flipping any variable of a false clause makes that clause true. The catch is
that the flip can make other clauses false. Picking the variable well is the
whole algorithm.

Each try restarts from a fresh random assignment. That is a jump to another
part of the search space, not a backtrack: nothing is learned between tries.

## Make and break

Two numbers describe what a flip of `x` would do:

- **break(x)**: clauses that are true now and would become false. These are
  the clauses where `x` gives the only true literal.
- **make(x)**: clauses that are false now and would become true.

Classic WalkSAT and ProbSAT look only at break. Every variable of the chosen
false clause makes at least that clause, so make says little. Break says how
much damage the flip does.

## WalkSAT (SKC)

This is the variant of Selman, Kautz and Cohen (1994), the one the literature
calls WalkSAT:

1. If some variable of `C` has break 0, flip it. This is a **free move**: it
   fixes `C` and breaks nothing. With several, pick one at random.
2. Otherwise, with probability `noise`, flip a **random** variable of `C`.
3. Otherwise flip the variable with the **smallest break** (a greedy move;
   ties broken at random).

The noise is what gets the search out of local minima. A purely greedy search
keeps flipping the same few variables back and forth. The best noise on
random 3-SAT is about `0.567`, which is the default.

The stats count the three kinds of move: `free_flips`, `noise_flips` and
`greedy_flips`.

### Adaptive noise (optional)

With `adaptive_noise` on, WalkSAT starts from the configured noise and adjusts
it during the run:

- After `stagnation_limit` flips without a new best assignment (`max_flips / 20`,
  at least 100), it raises the noise by 0.05, up to 0.9.
- After each new best, it lowers the noise by 0.02, back toward the setting.

`final_noise` reports where the noise ended. This helps when you don't know a
good noise for a formula. On random 3-SAT, the fixed 0.567 is already good.

## ProbSAT

ProbSAT (Balint and Schoening, 2012) drops the rules and the noise. It picks
**every** variable of `C` at random, with probability proportional to a
weight that falls steeply as break grows:

```text
P(x) = f(break(x)) / sum of f(break(y)) over the variables y of C

f(b) = (0.9 + b) ^ -cb     for clauses of length <= 3, cb = 2.06
f(b) = cb ^ -b             for longer clauses, cb = 3.0 (k=4), 3.7 (k=5),
                           5.1 (k=6), 5.4 (k>=7)
```

`k` is the length of the longest clause in the formula. The constants are the
published defaults that the authors tuned on random k-SAT.

| break | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| f, 3-SAT (cb = 2.06) | 1.242 | 0.267 | 0.112 | 0.061 | 0.038 |
| f, 5-SAT (cb = 3.7) | 1.000 | 0.270 | 0.073 | 0.020 | 0.005 |

A variable with break 0 is about 4.6 times as likely as one with break 1
and 11 times as likely as one with break 2. Bad moves stay possible, which
is how ProbSAT escapes local minima without a separate noise parameter.

The advanced option **`cb`** overrides the constant. A higher cb is greedier,
because it punishes breaks harder. A lower cb is more random. Leave it blank
to use the defaults above. The stats report the `cb` actually used and the
`weight_function`.

### WalkSAT or ProbSAT?

On random 3-SAT the two are close; ProbSAT tends to win on very large random
instances near the threshold. On the structured encodings in this app
(Sudoku, N-Queens, graph problems) WalkSAT is usually a little faster and
more robust. Its free moves and greedy steps suit their many short "at most
one" clauses. See the numbers in `docs/guide/performance.md`.

## How a flip stays cheap

Recomputing break for every candidate on every flip would mean scanning
clauses again and again. The solver keeps it up to date instead. For every
clause `c`, `LocalSearchState` stores:

- `true_count[c]`: how many of its literals are true;
- `true_sum[c]`: the **sum of the variable numbers** of its true literals.

When `true_count[c] == 1`, `true_sum[c]` *is* the number of the one variable
that keeps `c` true. That variable is `c`'s **critical** variable: flipping it
would break `c`. So `breaks[v]` (the number of clauses where `v` is critical)
can be updated without looking at the other literals.

Flipping `x` touches only the clauses that contain `x`:

| Clause where `x`'s literal... | true_count goes | what changes |
|---|---|---|
| was true | 2 -> 1 | the remaining true variable (`true_sum`) becomes critical: its break +1 |
| was true | 1 -> 0 | `c` becomes false: add to the false list; `x` was critical: break(x) -1 |
| becomes true | 0 -> 1 | `c` becomes true: remove from the false list; `x` is now critical: break(x) +1 |
| becomes true | 1 -> 2 | the old critical variable (`true_sum - x`) is not alone any more: its break -1 |

Other counts (3 -> 2 and so on) change no break. The false clauses are kept
in a list with a position map, so picking a random false clause, adding one
and removing one are all O(1).

Two more details matter in Python:

- **Compact numbering.** The encoders use readable variable numbers
  (Sudoku's `10203` is "row 1, column 2, value 3"), so the highest number can be
  far above the variable count. The solver renumbers the variables 1..n for its
  arrays and maps the model back. Without this, saving a best assignment would
  copy a list sized by the highest number (over 90,000 entries for Sudoku)
  each time.
- **Cancel checks** every 1024 flips, not on every flip (see
  `docs/guide/performance.md`).

The result is about 120,000 to 300,000 flips per second, depending on clause
length and how many clauses each variable appears in.

## A worked example

Five clauses over four variables, starting from all variables false:

```text
C1 = (x1 or x2)        C4 = (not x2 or not x3)
C2 = (not x1 or x3)    C5 = (x3 or x4 or not x1)
C3 = (not x2 or not x4)
```

| Clause | true literals | true_count | true_sum | critical |
|---|---|---|---|---|
| C1 | none | 0 | 0 | false clause |
| C2 | not x1 | 1 | 1 | x1 |
| C3 | not x2, not x4 | 2 | 6 | - |
| C4 | not x2, not x3 | 2 | 5 | - |
| C5 | not x1 | 1 | 1 | x1 |

So break(x1) = 2 (C2 and C5), and break(x2) = break(x3) = break(x4) = 0. C1
is the only false clause, and its variables are x1 (break 2) and x2 (break 0).

- **WalkSAT**: x2 has break 0, a free move, so it flips x2 without looking at
  the noise.
- **ProbSAT**: weights f(2) = 0.112 and f(0) = 1.242, so it flips x2 with
  probability 1.242 / 1.354 = 92% and x1 with probability 8%.

Flipping x2 to true:

- C1: `x2` becomes true, count 0 -> 1. C1 is fixed and x2 is its critical
  variable: break(x2) = 1.
- C3: `not x2` becomes false, count 2 -> 1. `true_sum` drops from 6 to 4, so x4
  becomes critical: break(x4) = 1.
- C4: count 2 -> 1, `true_sum` 5 -> 3, so x3 becomes critical: break(x3) = 1.

No clause is false any more, so the assignment x1 = false, x2 = true,
x3 = false, x4 = false is a model. Only the three clauses that contain x2
were touched.

## Statuses and stopping

| Status | When |
|---|---|
| `SAT` | an assignment made every clause true (checked again by the app) |
| `UNKNOWN` | every try used all its flips (`termination_reason = budget_exhausted`) |
| `TIMEOUT` / `CANCELLED` | the time limit or the user stopped it |

`UNKNOWN` is never `UNSAT`. The default budget is 10 tries x 100,000 flips.
On an unsatisfiable formula, the solver spends the whole budget before it
says `UNKNOWN`: about 1 to 10 seconds, depending on the formula. In
benchmarks with UNSAT cases, a limit rule such as "cap WalkSAT at 1 s"
avoids that wait.

## Options

| Option | Solver | Default | Meaning |
|---|---|---|---|
| Max tries | both | 10 | random restarts |
| Max flips per try | both | 100,000 | flips before a try gives up |
| Noise | WalkSAT | 0.567 | probability of a random move when there is no free move |
| Adaptive noise (advanced) | WalkSAT | off | tune the noise during the run |
| Break exponent cb (advanced) | ProbSAT | automatic | override the published cb |
| Random seed (advanced) | both | random | makes the run reproducible |

Every option has a reset button in the form once you change it. A job's
**Settings** tab shows the value each option had, its default, and what it
means.

## Statistics

| Stat | Meaning |
|---|---|
| `tries`, `flips` | tries started, flips over all tries |
| `best_unsatisfied` | fewest false clauses seen (0 when SAT) |
| `termination_reason` | `sat`, `budget_exhausted`, `timeout`, `cancelled`, `empty_clause` |
| `free_flips`, `noise_flips`, `greedy_flips` | WalkSAT's three kinds of move |
| `adaptive_noise`, `final_noise`, `stagnation_limit` | WalkSAT's noise control |
| `cb`, `weight_function` | ProbSAT's weight function as used |
| `flip_break_total`, `last_break` | sum of the break of every flip, and the last one |

The Python result also has `best_assignment` (the assignment with the fewest
false clauses), `restart_stats` (per try: best count, the flip where it was
reached, the final count) and `hard_clause_hits` (how often each clause was
picked). They are too large for the web stats table.

## Logs

- **Progress**: every `progress_interval` flips, a line with the try, the
  flips, the false clauses now and at best, the noise and the last break.
- **Debug**: every flip with its kind (`free`, `noise`, `greedy`, or the
  ProbSAT weight and its share of the clause total), capped at a few hundred
  lines. Debug output slows the solver down a lot.

## Python usage

```python
from solvers.walksat import walksat

clauses = [[1, 2], [-1, 3], [-2, -4], [-2, -3], [3, 4, -1]]
model, stats = walksat(
    clauses,
    return_stats=True,
    logging_options={"selection_mode": "probsat", "random_seed": 7},
)
print(stats["status"], stats["flips"], model)
```

`logging_options` takes `selection_mode` (`walksat` or `probsat`),
`max_tries`, `max_flips`, `noise`, `adaptive_noise`, `cb`, `random_seed`,
`mode` (`normal`, `periodic`, `debug`) and `progress_interval`. Through the app,
`sat_core.solver_registry.run_solver(clauses, "walksat", {...})` validates the
options first. It rejects options a solver does not have, such as `noise` for
ProbSAT.

## When to use them

- Large satisfiable random formulas: **Random 3-SAT** with **Planted SAT**
  and a few thousand variables. CDCL times out there, while WalkSAT and ProbSAT
  answer in well under a second.
- As a contrast in benchmarks: put them next to CDCL on the same cases and
  look at where each one wins.
- Not for UNSAT: with **Forced UNSAT** they can only return `UNKNOWN`.

## References

- B. Selman, H. Kautz, B. Cohen. *Noise strategies for improving local
  search.* AAAI 1994.
- A. Balint, U. Schoening. *Choosing probability distributions for stochastic
  local search and the role of make versus break.* SAT 2012.
