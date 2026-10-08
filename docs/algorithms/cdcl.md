# CDCL: Conflict-Driven Clause Learning

CDCL is the algorithm inside every modern complete SAT solver. It is
[DPLL](dpll.md) with three additions: when it hits a conflict it **learns a
clause** that explains it, it **backjumps** straight to the decision that
mattered, and it **chooses decisions** using what recent conflicts taught it.

This page follows `solvers/cdcl.py` from top to bottom. The section names
match the comments in the code.

Related notes: [DPLL](dpll.md), [WalkSAT](walksat.md),
[encodings](encodings.md), [solver performance](../guide/performance.md).

## CNF in one paragraph

A formula is a list of clauses; a clause is a list of literals; literal `x`
means "variable x is true" and `-x` means "x is false":

```python
[[1, -2], [2, 3], [-1]]      # (x1 or not x2) and (x2 or x3) and (not x1)
```

A clause is satisfied when one of its literals is true; the formula when all
clauses are.

## The main loop

```text
add every clause; assign the unit clauses
loop:
    conflict = propagate()                      # unit propagation
    if conflict:
        if no decision is open:  return UNSAT
        learned, level = analyse(conflict)      # First UIP
        add learned clause
        backjump to level; assign learned[0]    # the clause is unit there
        maybe clean up learned clauses
        maybe restart
    else:
        var = next decision variable            # VSIDS heap by default
        if none left:  return SAT
        open a new decision level; assign var = saved or preferred phase
```

Everything below explains one line of this loop.

## What the solver keeps in memory

| Name | Indexed by | Holds |
|---|---|---|
| `assignment` | variable | `True`, `False` or `None` |
| `val` | literal | `TRUE`, `FALSE` or `UNASSIGNED` for every literal, so "is this literal false?" is one list lookup |
| `levels` | variable | the decision level at which it was assigned |
| `reasons` | variable | the clause that forced it (`None` for a decision) |
| `trail` | time | every assigned literal, in order |
| `trail_lim` | level | where each decision level starts on the trail |
| `watches` | literal | the clauses currently watching that literal |
| `activity` | variable | VSIDS score |
| `heap` | rank | unassigned variables ordered by activity |
| `saved_phase` | variable | the last value the variable had |

Literals are stored at index `max_var + literal`, so one list covers
`-max_var .. max_var`.

**Decision levels.** Level 0 holds facts that follow from the formula alone
(unit clauses and what they force). Each decision opens a new level, and every
assignment it forces belongs to that level. The trail plus `trail_lim` let
the solver undo whole levels at once.

## Unit propagation with two watched literals

A clause is *unit* when every literal but one is false; the last one must
then be true. Checking every clause after every assignment would be far too
slow, so each clause **watches two of its literals**: `lits[0]` and
`lits[1]`. As long as both watched literals are not false, the clause cannot
be unit or conflicting, whatever happens to the others, so it can be ignored.

When literal `x` becomes true, `-x` becomes false, and `propagate()` visits
only the clauses in `watches[-x]`. For each one:

1. Swap so that the false literal is `lits[1]`.
2. If `lits[0]` is true, the clause is satisfied: keep watching, move on.
3. Look through `lits[2:]` for a literal that is not false. If there is one,
   swap it into position 1 and move the clause to that literal's watch list.
4. Otherwise every literal except `lits[0]` is false:
   - `lits[0]` unassigned: the clause is **unit**; assign `lits[0]` with this
     clause as its reason;
   - `lits[0]` false: **conflict**; return the clause.

Example: clause `(-1 or 2 or 3)` watches `-1` and `2`. Assigning `x1 = True`
makes `-1` false; the clause finds `3` not false and watches `3` instead.
If `x3` is also false, `2` is forced true.

Backtracking does not touch the watches at all: unassigning literals can
only make watched literals "not false" again, which keeps every clause
valid. This is why watched literals are much cheaper than DPLL's counters on
large formulas.

## Conflict analysis: the First UIP

A conflict is a clause whose literals are all false. Some of those
assignments were decisions, most were forced. CDCL walks the **implication
graph** backwards: it replaces a forced literal by the reason clause that
forced it (a resolution step), and stops as soon as exactly one literal of
the current decision level remains. That literal is the **first unique
implication point** (UIP): one assignment at this level that by itself,
together with older assignments, leads to the conflict.

Example. Clauses:

```text
c1 = (-1 or 2)       c2 = (-1 or 3)      c3 = (-2 or -3 or 4)
c4 = (-4 or 5)       c5 = (-4 or -5 or -6)
```

Suppose the solver decided `x6 = True` at level 1 and `x1 = True` at level 2.
Propagation at level 2 gives `x2` (from c1), `x3` (c2), `x4` (c3), `x5` (c4),
and then c5 has every literal false: a conflict.

| Step | Clause | Level-2 literals in it |
|---|---|---|
| start | c5 = `(-4 or -5 or -6)` | `-4`, `-5` (two) |
| resolve with c4, the reason for `x5` | `(-4 or -6)` | `-4` (one: stop) |

The learned clause is `(-4 or -6)`: "x4 and x6 cannot both be true". Its
only level-2 literal is `-4`, the asserting literal.

## Backjumping

The learned clause is stored as `[asserting literal, highest-level other
literal, the rest...]`, here `[-4, -6]`. The solver jumps back to the highest
level among the *other* literals (level 1, where `x6` was decided). There,
`-6` is still false and `x4` is unassigned, so the learned clause is unit and
forces `x4 = False` immediately.

Two details make this work:

- Level 2 is skipped entirely, even though the conflict happened there. With
  more levels in between, all of them would be skipped too. This is
  *non-chronological* backtracking.
- The other watched literal is the one with the **highest level**. Then the
  clause keeps a correct watch if the solver later backtracks between the
  levels of its literals; with any other choice a later propagation could be
  missed.

The learned clause is permanent (unless clean-up removes it), so this
particular mistake is never made again in any part of the search.

## Choosing decisions: VSIDS and the heap

Every variable has an **activity** score, starting at its number of
occurrences. Each variable that takes part in a conflict analysis gets
`activity += increment`, and after every conflict the increment grows by
5% (`var_decay = 0.95`). Recent conflicts therefore weigh more than old ones
(this is VSIDS, from the Chaff solver). The next decision is the unassigned
variable with the highest activity.

Finding that variable by scanning all variables costs O(n) per decision. The
solver keeps the variables in a **binary max-heap** ordered by activity
instead (`heap_up`, `heap_down`, `heap_pop`): a decision pops the top
(O(log n)), a bump moves one variable up (O(log n)), and backtracking puts
unassigned variables back. The heap is lazy, as in MiniSat: assigned
variables may stay inside and are skipped when popped. When scores grow past
1e100 they are all scaled down by the same factor, which keeps the order.

Other branching options (for comparisons):

| Option | Rule | Cost per decision |
|---|---|---|
| VSIDS (default) | highest activity | O(log n), heap |
| Most frequent | most occurrences in the input (static) | O(log n), same heap with a fixed score |
| MOMS | most occurrences in the shortest unresolved clauses | scans every clause |
| DLIS | the literal that satisfies most unresolved clauses (also picks the value) | scans every clause |
| Random | a random unassigned variable (reproducible with a seed) | scans the variables |

MOMS and DLIS are classic DPLL-era heuristics. They look at the whole formula
at every decision, which is why they become slow on large instances; that
cost is part of what a comparison with VSIDS shows.

## Phases and phase saving

The value tried for a decision:

1. if the heuristic chose one (DLIS), that one;
2. otherwise the **saved phase**: the value the variable had the last time
   it was assigned;
3. for a variable never assigned, the **initial phase** option: *Positive
   first* (default), *Negative first*, *Polarity based* (the sign it has
   most often in the formula) or *Random*.

*Positive first* suits the app's encoders, where a positive literal is a
constructive choice (place a queen, give node v color c). Phase saving makes
the solver return to the part of the search space it was in before a
backjump or restart, instead of starting over.

## Restarts (Luby schedule)

A restart undoes every decision (back to level 0) but keeps the learned
clauses, the activities and the saved phases. It lets the solver abandon a
bad early decision that backjumping would never revisit. With phase saving
it costs little, because the solver quickly rebuilds most of the old
assignment.

By default restarts follow the **Luby sequence** times 100 conflicts:

```text
restart after 100, 100, 200, 100, 100, 200, 400, 100, 100, 200, ... conflicts
```

Mostly short runs, with longer ones mixed in so hard proofs can still finish.
Options: turn restarts off, use a *Fixed* interval instead, or change the
unit (`restart_interval`).

## Cleaning up learned clauses

Every conflict adds a clause. Without clean-up the database grows
without bound, and every clause has to be visited by propagation, so the
solver gets slower and slower. The solver therefore deletes weak learned
clauses periodically, as Glucose does:

- **When**: after 2,000 conflicts, then after 2,300 more, 2,600 more, ...
  (each wait is 300 longer).
- **What is kept**: clauses that are currently the reason of an assignment
  (deleting those would break the implication graph), binary clauses, and
  **glue clauses** with LBD at most 2.
- **What is deleted**: half of the others, worst first: highest LBD, then
  longest, then least recently used.

**LBD** (literal block distance) is the number of different decision levels
among a clause's literals when it was learned. Low LBD means the clause
links few levels, and such clauses tend to keep propagating.

```text
literal levels 8, 8, 5, 2   ->   LBD 3
```

Deleted clauses are only flagged. `propagate()` drops a flagged clause from
a watch list the next time it meets it, so no watch list is ever rebuilt.

Options: switch the clean-up off, or set a *learned clause limit*; when the
learned database grows past it, it is cut to half of the limit.

## Stopping: cancel, skip and timeouts

The solver asks the cancel token whether to stop every 2,048 propagation
steps (`CHECK_EVERY`). Asking on every step used to cost about a third of the
run time; every 2,048 steps still means well under a millisecond between
checks. The answer can be `CANCELLED` (Stop), `SKIPPED` (Skip in a
benchmark) or `TIMEOUT`.

## Statistics

| Name | Meaning |
|---|---|
| decisions | variables chosen by the branching heuristic |
| conflicts | all-false clauses found (each produces one learned clause) |
| propagations | literals forced by unit clauses |
| learned_clauses | clauses learned in total |
| active_learned_clauses | learned clauses still in the database at the end |
| deleted_learned_clauses | learned clauses removed by clean-up |
| reductions | number of clean-ups |
| avg_lbd | average LBD of the learned clauses still kept |
| restarts | restarts performed |

## Options

| In the app | `logging_options` key | Default |
|---|---|---|
| Branching heuristic | `branching` | `VSIDS` |
| Initial phase | `initial_phase` | `Positive first` |
| Restarts | `restarts` | on |
| Restart schedule (advanced) | `restart_strategy` | `luby` |
| Restart interval (advanced) | `restart_interval` | 100 conflicts |
| Clean up learned clauses (advanced) | `clause_deletion` | on |
| Learned clause limit (advanced) | `learned_clause_limit` | automatic |
| Random seed (advanced) | `random_seed` | random |

The registry (`sat_core/solver_registry.py`) turns the app's options into
these keys.

## How to run it from Python

```python
from solvers.cdcl import cdcl
from sat_core.dimacs import load_dimacs

clauses = load_dimacs("input/examples/graph_coloring/gc_n10_p10_k2.cnf")
solution, stats = cdcl(clauses, return_stats=True)
print(stats["status"], stats["conflicts"])

# The same solver without restarts or clean-up, for comparison:
cdcl(clauses, return_stats=True, logging_options={"restarts": False, "clause_deletion": False})
```

To see a solver work step by step in the app, solve a small formula with
*Log detail* set to *Debug*, open the job's full page, and read the log; the
[interactive CDCL visualisation](../visualisations/cdcl/index.html) shows the
implication graph on a small example.

Checks: `python -m unittest tests.test_cdcl tests.test_solver_agreement`
(the second compares eight CDCL configurations and DPLL with brute force on
400 random formulas), and `python scripts/benchmark_cdcl.py` for a quick run
of every solver.
