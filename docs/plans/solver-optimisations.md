# Plan: further solver optimisations (pure Python)

- **Status:** proposed, not started
- **Written:** 2026-10-19, against commit `9e11958`
- **Related:** [PyPy runner and run metadata](pypy-solver-runner-and-run-metadata.md),
  [Memory measurement](memory-measurement.md),
  [2026-10-16 audit](../reviews/2026-10-16-audit.md) (A2, B6-B9),
  [Solver performance](../guide/performance.md)

## Goal

Make the solvers faster while they stay plain Python, so every user and every
interpreter (CPython and PyPy) benefits, without new dependencies or a build
step.

## Non-goals

- Compiling the solvers (mypyc, Cython, Numba): see "Considered and rejected".
- Changing the answers. SAT/UNSAT results must stay the same; a step that
  changes the search (decisions, conflicts) says so and is measured on its own.
- Running under PyPy: that is the other plan.

## Where things stand

What is already done (details in `docs/guide/performance.md` and
`docs/algorithms/cdcl.md`):

- CDCL: two watched literals at `lits[0]`/`lits[1]`, a VSIDS binary heap with
  lazy deletion, Luby restarts, Glucose-style learned-clause cleanup, literal
  values in one flat list (`val[offset + lit]`), cancel checks every 2048 watch
  visits, running totals for the learned-clause statistics.
- DPLL: iterative, with true/false counters per clause instead of copying the
  formula.
- WalkSAT/ProbSAT: incremental break counts with the true-count/true-sum
  trick, compact renumbering of variables 1..n, per-flip counters in local
  variables. About 120,000-300,000 flips per second.

Where CDCL spends its time now: propagation (`propagate()` in
`solvers/cdcl.py`) is about three quarters of the run time; the rest is
conflict analysis and the heap. So the steps below target propagation first.

Reference times (CPython 3.11, from `scripts/solver_timings.py` and the
2026-10-19 PyPy comparison):

| Instance | Solver | Time | Conflicts |
|---|---|---:|---:|
| 3-SAT n=200 r=4.26, seed 1 | CDCL | 4.05 s | 13,417 |
| 3-SAT n=250 r=4.26, seed 2 (UNSAT) | CDCL | 58.7 s | 101,834 |
| Sudoku 25x25, 40% givens, seed 1 | CDCL | 31.2 s | 40,804 |
| 25-Queens | DPLL | 2.76 s | 7,255 |
| 3-SAT n=60 r=6 (UNSAT), 10 x 100,000 flips | WalkSAT | 3.60 s | - |

Re-measure these on your own machine before starting; absolute times differ
between machines, ratios are what matter.

## Rules for every step

1. Measure before and after: `python scripts/solver_timings.py` (run nothing
   else heavy at the same time).
2. Correctness: `python -m unittest tests.test_solver_agreement tests.test_cdcl
   tests.test_walksat tests.test_runtime`.
3. Steps marked "same search" must give identical decisions and conflicts:
   compare the `conflicts` column of `solver_timings.py` before and after. A
   different count means the step changed the search, which is a bug for
   those steps.
4. One step per commit, with the measured gain in the commit message and a line
   in `docs/guide/performance.md`.

## Steps

Do the cleanup first: the CDCL items B6-B9 of the
[audit](../reviews/2026-10-16-audit.md) touch the same code (`_dedupe_clause`,
unreachable branches, the duplicated `assignment`/`val` state, the extra
counters). Doing them first makes the hot loop smaller and easier to change.

- [ ] **1. Blocker literals in the watch lists** (CDCL, same search)
  - **What:** each watch entry stores one other literal of the clause (the
    "blocker", as in MiniSat). When the blocker is already true, the clause is
    satisfied and propagation skips it without opening the clause object.
  - **Where:** `add_clause()` and `propagate()` in `solvers/cdcl.py`; watch
    lists become lists of `(clause, blocker)` pairs, or two parallel lists.
  - **Expected:** the biggest of the pure-Python wins on large formulas, since
    most watch visits find a satisfied clause. Estimate 1.2-1.4x on propagation;
    not measured.
  - **Risk:** the blocker must be updated when the watch moves; the agreement
    test covers it.

- [ ] **2. Lighter clause objects** (CDCL, same search)
  - **What:** `Clause` is a `@dataclass(eq=False)`; attribute access on a plain
    class instance goes through a dict. `@dataclass(eq=False, slots=True)`
    (Python 3.10+) makes `clause.lits`, `clause.deleted` faster. Measure plain
    lists (`[lits, learnt, lbd, ...]`) as an alternative only if slots is not
    enough; they are less readable.
  - **Where:** `Clause` near the top of `solvers/cdcl.py`.
  - **Expected:** a few percent; cheap to try.
  - **Risk:** none for correctness. `slots=True` needs Python 3.10, which the
    repo already requires.

- [ ] **3. Fast path for two-literal clauses** (CDCL, same search if done
  carefully)
  - **What:** binary clauses are common in the encodings (all the "at most one"
    pairs). A separate watch list per literal holding just the other literal
    lets propagation handle them without the general replacement search.
  - **Where:** `add_clause()`, `propagate()`, and conflict analysis (which
    needs a reason clause for binary implications).
  - **Expected:** large on Sudoku, N-Queens and graph colouring, where most
    clauses are binary. Estimate 1.2-1.5x on those; not measured.
  - **Risk:** medium. The order in which implications are found can change,
    which changes the search. If the conflicts column moves, document it as a
    search change rather than reverting blindly.

- [ ] **4. Renumber huge variable numbers** (CDCL and DPLL, same search)
  - **What:** audit item A2. CDCL and DPLL size their arrays by the largest
    variable number, so two clauses using variable 10,000,000 cost 20 s and
    2.3 GB. Move WalkSAT's compact renumbering (`solvers/walksat.py`,
    "Work on compact variable numbers") into `run_solver` in
    `sat_core/solver_registry.py`, used when the largest variable is above
    1,000,000 and far above the number of distinct variables.
  - **Expected:** fixes the memory blow-up; no change for normal encodings
    (they stay below the threshold and keep readable numbers in the logs).
  - **Risk:** low. Renumbering keeps the order of the variables, so every
    heuristic (heap ties, DLIS, MOMS) makes the same decisions.

- [ ] **5. Learned-clause minimisation** (CDCL, changes the search)
  - **What:** after first-UIP analysis, remove literals of the learned clause
    that are implied by the others (MiniSat's recursive minimisation). Shorter
    learned clauses propagate more and usually cut the number of conflicts.
  - **Where:** end of `analyse_conflict()` in `solvers/cdcl.py`.
  - **Expected:** fewer conflicts on hard instances; often a clear net win.
  - **Risk:** it changes decisions and conflicts, so earlier benchmark results
    are no longer directly comparable. Make it an option (default on or off is
    your call), mention it in `docs/algorithms/cdcl.md`, and note it in the
    thesis if results before and after are mixed.

- [ ] **6. DPLL and WalkSAT: profile before touching**
  - DPLL already uses counters and gains 8.6x under PyPy, so its CPython time
    is dominated by interpreter overhead; look for allocations in
    `propagate()`/`undo()` only if a profile shows them.
  - WalkSAT/ProbSAT are close to the speed of a hand-tuned prototype; the hot
    loop is already lean. Leave them unless a profile says otherwise.

How to profile one instance:

```bash
python - <<'EOF'
import cProfile, pstats
from problems import build_problem
from sat_core.solver_registry import run_solver
inst = build_problem("random_3sat", {"variables": 200, "ratio": 4.26, "mode": "random", "seed": 1})
cProfile.run("run_solver(inst.clauses, 'cdcl', {}, timeout=60)", "cdcl.prof")
pstats.Stats("cdcl.prof").sort_stats("tottime").print_stats(15)
EOF
```

The solver runs in the same process here, so the profile shows the solver's
own functions (`propagate`, `analyse_conflict`, `enqueue`, ...). The profiler
slows everything down, so use it to compare shares of time, not absolute
times.

## Done when

- Each step above is either done (with its measured gain in
  `docs/guide/performance.md`) or explicitly dropped with the reason.
- `tests/test_solver_agreement.py` and the solver tests pass; the
  `conflicts` column of `scripts/solver_timings.py` is unchanged for the
  "same search" steps.

## Considered and rejected

These came up on 2026-10-19 and were set aside; reopen only with a new reason.

- **mypyc:** compiles type-annotated Python to C. The solvers are written as one
  big function with nested functions on purpose (fast in CPython), and mypyc
  gains little on that style; it would need a rewrite into typed classes. It
  also needs a C compiler or prebuilt wheels on every platform.
- **Cython:** large gains are possible with C types in the hot loops, but the
  solvers would become a second dialect to maintain, and Windows users would
  need a compiler. Conflicts with "the solvers are pure Python on purpose"
  (AGENTS.md).
- **Numba:** built for NumPy arrays and numeric loops; it does not handle lists
  of clauses, dicts, closures or classes well.
- **Moving the heap or propagation into classes:** attribute lookups in the hot
  path would make CPython slower; the closures are the speed trick.
