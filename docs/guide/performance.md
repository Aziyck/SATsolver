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

CDCL and DPLL size their arrays by the largest variable number. The two
clauses `10000000 0` and `-5 0` took CDCL 20 s and 2.3 GB and DPLL 10 s and
1.5 GB, and variable 1,000,000,000 ran the process out of memory.
`run_solver()` now renumbers such formulas 1..n before CDCL or DPLL sees
them (largest number above 1,000,000 and more than twice the number of
variables); both cases take under a millisecond. The order of the variables
is kept, so decisions and conflicts do not change, and formulas below the
threshold are passed through untouched.

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

## Local search: why WalkSAT and ProbSAT used to lose

On satisfiable formulas you would expect local search to beat CDCL. In the
first version of the app it did not, for four reasons:

- **The problems.** Sudoku, N-Queens and the graph problems are structured,
  with many short "at most one" clauses. Unit propagation solves much of
  them for free, and CDCL has it while local search does not. Local search
  shines on large *random* formulas.
- **A slow implementation.** It recomputed make and break for every candidate
  by scanning its clauses: about 50,000 flips per second.
- **Non-standard strategies.** ProbSAT combined a noise step with a
  make/break weight, which is neither of the published algorithms.
- **A small budget.** 10 tries x 10,000 flips was too little for anything
  hard.

The rewrite (see [WalkSAT and ProbSAT](../algorithms/walksat.md)) uses the
textbook WalkSAT/SKC and ProbSAT. It keeps break counts incrementally with the
critical-variable trick, renumbers the variables compactly, and raises the
budget to 10 x 100,000 flips. Throughput is now 120,000 to 300,000 flips per
second.

Median over seeds, 20 s limit, before and after the rewrite (WalkSAT /
ProbSAT), with CDCL for reference:

| Instance | Before | After | CDCL |
|---|---|---|---|
| 3-SAT n=150, ratio 4.2, SAT | 0.81 / 2.64 s | 0.02 / 0.01 s | 0.32 s |
| Planted 3-SAT n=2000, ratio 4.0 | 0.13 / 0.26 s | 0.04 / 0.04 s | timeout |
| Planted 3-SAT n=5000, ratio 4.2 | 0.65 / 18.75 s | 0.17 / 0.14 s | timeout |
| 20-Queens | 0.04 / 12.36 s | 0.02 / 0.03 s | 0.06 s |
| Sudoku 9x9, 25% givens | 0.20 s / timeout | 0.05 / 0.05 s | 0.07 s |
| Hamiltonian path, G(20, 0.3) | timeouts | 0.12 / 0.73 s (one timeout) | 0.05 s |

What this shows:

- On large satisfiable random formulas local search now wins by a wide margin:
  CDCL cannot finish n=2000 in 20 s, while WalkSAT needs 0.04 s.
- On the structured problems they are now close to CDCL, but CDCL stays the
  safer choice, especially for path and ordering problems.
- On UNSAT formulas local search spends its whole budget and says `UNKNOWN`.
  It cannot do better. Use a limit rule in benchmarks that mix SAT and UNSAT
  cases.

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
[How it works](how-it-works.md#parallel-benchmark-runs).

## Running the solvers under PyPy

PyPy is an alternative Python with a just-in-time compiler. The solvers are
pure Python, so it runs them unchanged. Set `WIZSAT_SOLVER_PYTHON` to its
path ([README](../../README.md#running-the-solvers-under-pypy)) and every
solve and benchmark run happens in a child process of that interpreter; the
server stays on CPython. The work counts (conflicts, flips) are identical
under both, so the comparison is like for like.

```bash
python scripts/pypy_timings.py /path/to/pypy3 --limit 300 --repeat 3
```

The script sends every case through `run_solver`, the path of solve jobs and
benchmarks: once with the setting unset (CPython runs the solver in its own
process) and once with it set to PyPy (a child process). "Solver" is the run
time the result reports, without the child's start-up; "with start-up" is
the whole `run_solver` call. The conflicts and flips matched on every case.

Measured on 2026-11-23 (RUNNER-10): Windows 11, AMD Ryzen 7 4800H (8 cores,
16 logical CPUs), 16 GB, CPython 3.13.14 as the server side, PyPy 8.0.1
(Python 3.12.15) as the child, median of 3 runs, one run at a time with
nothing else running:

| Instance | CPython | PyPy solver | Speed-up | PyPy with start-up | Speed-up |
|---|---:|---:|---:|---:|---:|
| CDCL, 3-SAT n=250 r=4.26 seed 2 (UNSAT) | 78.81 s | 26.34 s | 3.0x | 26.63 s | 3.0x |
| CDCL, Sudoku 25x25 40% seed 1 | 47.83 s | 11.31 s | 4.2x | 12.53 s | 3.9x |
| CDCL, 3-SAT n=200 r=4.26 seed 1 | 7.38 s | 3.23 s | 2.3x | 3.65 s | 2.0x |
| DPLL, 25-Queens | 3.52 s | 0.44 s | 8.0x | 0.90 s | 3.9x |
| WalkSAT, 3-SAT n=60 r=6 (UNSAT), 10 x 100,000 flips | 5.76 s | 1.91 s | 3.0x | 2.32 s | 2.5x |
| WalkSAT, planted n=5000 r=4.2 | 0.35 s | 0.55 s | 0.6x | 0.96 s | 0.4x |
| ProbSAT, planted n=5000 r=4.2 | 0.37 s | 0.34 s | 1.1x | 0.73 s | 0.5x |
| CDCL, 3-SAT n=150 r=4.26 seed 3 | 0.04 s | 0.16 s | 0.25x | 0.50 s | 0.1x |
| CDCL, Sudoku 16x16 40% seed 1 | 0.56 s | 0.41 s | 1.4x | 0.86 s | 0.8x |
| CDCL, 40-Queens | 0.49 s | 0.48 s | 1.0x | 0.88 s | 0.6x |
| DPLL, 3-SAT n=100 r=4.26 seed 1 | 0.17 s | 0.14 s | 1.2x | 0.45 s | 0.4x |

The CPython column includes the in-process overhead of `run_solver` (under
0.1 s, more for the larger Sudoku formulas). The first table, measured on
2026-10-19 in a Linux container with PyPy 7.3.15 (Python 3.9) and CPython
3.11.15 running the solvers directly, gave the same picture: 2.9x, 3.4x,
1.8x and 8.6x on the four longest runs, slower on the short ones.

**The warm-up caveat.** Every run is a fresh process, so PyPy pays its JIT
warm-up on every run, and with the setting also about 0.3 to 0.5 s to start
the child and send it the formula. Runs that take seconds gain 2 to 4 times
(up to 8 times in the solver for DPLL); runs under about a second get
slower once the start-up is counted, up to 10 times slower for the very
short ones. In a benchmark that mixes both, PyPy can change the ranking of
the solvers on the small instances. Use PyPy for long runs and big formulas,
and CPython for sweeps of many small cases.

What to report, and why a PyPy result must say so:
[Benchmarking](benchmarking.md#checklist-for-report-quality-experiments).

## The solver child process

With `WIZSAT_SOLVER_PYTHON` set, every run starts a child interpreter and
sends it the formula as one line of JSON (`sat_core/solver_process.py`). That
costs time on every run, before the solver starts:

```bash
python scripts/child_cost.py                    # this interpreter as the child
python scripts/child_cost.py /path/to/pypy3     # other interpreters as the child
```

The script times a 4x4 Sudoku solved with CDCL 20 times (the solve itself
takes about a millisecond, so the difference is the child's start-up), and a
random formula of 2,000,000 clauses, the clause limit, cancelled at its first
log line (so the solver does no work and only the cost of getting the formula
to it is left). "Window" is the time from starting the child to its first log
line. For a run with a time limit, the parent counts the limit from that
line, and until it arrives it allows `START_UP_SECONDS` on top of the limit
before it kills a silent child as hung; the window is what that allowance
must cover.

Measured on 2026-11-23: Windows 11, AMD Ryzen 7 4800H (8 cores, 16 logical
CPUs), 16 GB, CPython 3.13.14 as the parent and the child. The PyPy rows
(PyPy 8.0.1, Python 3.12.15, as the child) come from a second run on the same
machine and day ([RUNNER-10](../plans/pypy-solver-runner.md)); their "without
the setting" column is that run's own.

| Run | Without the setting | With the setting | Window |
|---|---:|---:|---:|
| 4x4 Sudoku, CPython child, median of 20 (max) | 0.03 s (0.06 s) | 0.32 s (0.45 s) | 0.29 s (0.40 s) |
| 4x4 Sudoku, PyPy child, median of 20 (max) | 0.02 s (0.03 s) | 0.35 s (0.46 s) | 0.33 s (0.43 s) |
| 2,000,000 clauses of 3 literals (53.6 MB of JSON), CPython child, median of 3 (max) | 2.6 s (2.8 s) | 7.6 s (7.8 s) | 4.2 s (4.5 s) |
| 2,000,000 clauses of 3 literals, PyPy child, median of 3 (max) | 2.4 s (2.5 s) | 6.7 s (6.9 s) | 3.0 s (3.3 s) |
| 2,000,000 clauses of 5 literals (86.6 MB), CPython child, median of 2 (max) | 4.6 s (5.3 s) | 13.5 s (14.6 s) | 7.4 s (8.3 s) |

What the numbers say:

- **About 0.3 s per run**, almost all of it starting the interpreter:
  `python -c pass` alone takes 0.3 s on this machine. A benchmark of many
  small cases pays it on every run, so on runs under a second the setting
  makes the total slower, before PyPy's own warm-up is counted.
- **About 5 s more per run at the clause limit.** Without the setting,
  `run_solver` spends its 2.6 s counting the variables. With it, the parent
  counts them too, then encodes the request (`json.dumps`, 0.9 s), and the
  child parses it (`json.loads`, 1.4 s) and counts the variables again
  (2.5 s); the 54 MB through the pipe and the interpreter start add little
  on top. Each of these grows with the number of literals: 0.7 to 0.83 s of
  window per million literals.
- **`START_UP_SECONDS` stays at 60 s.** It is more than ten times the worst
  window at the clause limit, and the limit counts clauses, not literals: a
  DIMACS file with long clauses can carry many more. At the worst measured
  rate, 60 s covers about 70 million literals, 35 per clause at the limit. A
  value too low would end a healthy run as `TIMEOUT`; a high one only keeps
  a child that hangs before its first line, and that nobody cancels, that
  much longer. A PyPy child is no slower to reach its first line: its
  window at the limit is 3.0 s (3.3 s at most), shorter than CPython's,
  because PyPy parses the JSON and counts the variables faster. Slower
  machines and busy cores (`workers` above 1) were not measured.

Two follow-ups would remove most of the cost at the limit: a binary request
format instead of JSON ([RUNNER-12](../plans/pypy-solver-runner.md)), and
counting the variables once instead of twice
([F6](../reviews/findings.md)).

## Ideas for later

- Compact cardinality encodings (sequential counters) to shrink the formulas
  of large Sudoku and N-Queens instances (see
  [encodings](../algorithms/encodings.md#three-reusable-patterns)).
- Learned-clause minimisation (removing redundant literals from learned
  clauses), as MiniSat does.
- Clause weighting for local search (as in SAPS or PAWS), which helps on
  structured formulas.
