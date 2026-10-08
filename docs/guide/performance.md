# Solver performance

The solvers are plain Python, so they are hundreds of times slower than C
solvers such as MiniSat. Within that limit, a few implementation choices make
a large difference. This page describes how the solvers were measured, what
was slow, what changed, and how to measure them yourself.

## How to measure

```bash
python scripts/solver_timings.py        # fixed set of instances, 60 s limit each
python scripts/solver_timings.py 10     # 10 s limit
```

The script prints the status, the time, the number of conflicts and
**conflicts per second** for each instance. Conflicts per second measures
how fast the solver works, independently of how lucky its search was. Total
time on satisfiable instances depends a lot on luck: a different restart or
decision can find a model ten times sooner or later.

To find out *where* the time goes, profile one run:

```python
import cProfile, pstats
from problems import build_problem
from sat_core.solver_registry import run_solver

instance = build_problem("random_3sat", {"variables": 250, "ratio": 4.26, "mode": "random", "seed": 2})
profiler = cProfile.Profile()
profiler.enable()
run_solver(instance.clauses, "cdcl", timeout=15)
profiler.disable()
pstats.Stats(profiler).sort_stats("tottime").print_stats(12)
```

`tottime` is the time spent inside a function itself; the functions at the
top are the ones worth optimising.

## What was slow in CDCL, and the fixes

Profiling the earlier CDCL on a 25x25 Sudoku and on random 3-SAT showed four
problems. None of them was in the algorithm itself; they were in its
bookkeeping.

| Problem | Share of run time | Fix |
|---|---|---|
| After every conflict, the statistics "active learned clauses" and "average LBD" were recomputed by scanning every clause, twice | 40% (Sudoku 25x25, 750k clauses), 16% (3-SAT) | keep running totals, updated when a clause is learned or deleted |
| The cancel/timeout check ran on every clause visited during propagation, 2.7 million times in 20 s; each check reads a shared event and the clock | 36% (3-SAT) | check every 2,048 steps |
| VSIDS scanned all variables to find the most active one at every decision | grows with variables x decisions | a binary heap: O(log n) per decision |
| Conflict analysis allocated a fresh array the size of the largest variable number at every conflict (252,525 entries for a 25x25 Sudoku) | about 1 ms per conflict there | one array, reset after use |

Two search changes then made long runs much faster:

- **Learned-clause clean-up.** Learned clauses were never deleted by
  default, so propagation slowed down the longer the search ran. Now half of
  the weak learned clauses are removed periodically (Glucose-style, see
  [CDCL](../algorithms/cdcl.md#cleaning-up-learned-clauses)).
- **Restarts** are on by default, with the Luby schedule.

Smaller changes: literal values in one list indexed by literal (a lookup
instead of a function call), watch lists in a list instead of a dictionary,
and the watched literals kept at positions 0 and 1 of each clause.

One correctness detail was fixed along the way: the second watched literal
of a learned clause is now the one with the highest decision level (as in
MiniSat). Before, a propagation could be noticed late after certain
backjumps.

Every change was checked with a randomised test that compares the solvers
with brute force on thousands of small formulas
(`tests/test_solver_agreement.py` runs 400 of them on every test run).

## Results

Same machine, same instances, 60 s limit per run, before and after the
changes:

| Instance | Before | After | Conflicts per second |
|---|---|---|---|
| 3-SAT n=150, ratio 4.26 | SAT, 0.03 s | SAT, 0.02 s | 4,800 -> 7,900 |
| 3-SAT n=200, ratio 4.26 | SAT, 3.3 s | SAT, 3.8 s | 1,400 -> 3,500 |
| 3-SAT n=250, ratio 4.26 | **timeout** | **UNSAT, 48.5 s** | 400 -> 2,100 |
| 3-SAT n=120, ratio 5.5 | UNSAT, 0.05 s | UNSAT, 0.02 s | 5,100 -> 8,400 |
| Sudoku 25x25, 40% givens | **timeout** | **SAT, 25 s** | 32 -> 1,600 |
| 40-Queens | **timeout** | **SAT, 0.3 s** | |
| 60-Queens | **timeout** | **SAT, 1.4 s** | |
| DPLL, 3-SAT n=100, ratio 4.26 | SAT, 1.19 s | SAT, 0.11 s | |
| DPLL, 25-Queens | SAT, 5.0 s | SAT, 2.1 s | |

The 3-SAT n=200 run is the example of luck: the new solver handles conflicts
2.5 times faster, but with restarts it took a different path that needed
13,400 conflicts instead of 4,600. Over many instances the faster solver
wins; on any single satisfiable instance it may not.

DPLL's numbers come from rewriting it iteratively with clause counters (see
[DPLL](../algorithms/dpll.md#how-this-implementation-works)); it makes
exactly the same decisions as before.

## Where the time goes now

In CDCL, propagation is now about three quarters of the run time, which is
the normal profile of a CDCL solver: the remaining cost is the Python
interpreter executing the watch-list loop. Going much further would need a
compiled language or a different runtime (for example running the solvers
with PyPy), not a different algorithm.

MOMS and DLIS remain slow on large formulas by design: they look at every
clause at every decision. That cost is part of what comparing them with
VSIDS shows.

## Benchmarks: running cases in parallel

A benchmark normally solves its cases one after another on one CPU core. The
builder's **Parallel cases** setting (the `workers` field of a benchmark
request) solves several cases at the same time in separate processes:

| Workers | 24 cases of 3-SAT (n=120 and 150), CDCL and DPLL, 4-core machine |
|---|---|
| 1 | 16.7 s |
| 2 | 9.4 s |
| 4 | 6.9 s |

The rows were identical in all three runs; only the timings changed. Two
things limit the speed-up: starting the worker processes takes a moment, and
the last few cases can leave some workers idle.

When the timings are the result you report, keep it at 1: parallel runs
compete for the CPU, caches and memory bandwidth, so individual times get
noisier (and turbo clock speeds drop when every core is busy). See
[Benchmarking](benchmarking.md#parallel-runs) and
[Architecture](architecture.md#parallel-benchmark-runs).

## Ideas for later

- Run the solvers under PyPy, which typically speeds up this kind of
  pure-Python loop several times.
- Compact cardinality encodings (sequential counters) to shrink the formulas
  of large Sudoku and N-Queens instances (see
  [encodings](../algorithms/encodings.md#three-reusable-patterns)).
- Learned-clause minimisation (removing redundant literals from learned
  clauses), as MiniSat does.
