# Plan: further solver optimisations (pure Python)

- **Status:** proposed, not started
- **Written:** 2026-10-19, against commit `9e11958`; tasks rewritten 2026-11-13
- **Related:** [PyPy solver runner](pypy-solver-runner.md),
  [memory measurement](memory-measurement.md),
  [2026-10-16 audit](../reviews/2026-10-16-audit.md) (A2, B6-B9),
  [Solver performance](../guide/performance.md)
- Item format, difficulty and closing rule: [README.md](README.md)

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
conflict analysis and the heap. So the tasks below target propagation first.

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

## Rules for every task

1. Measure before and after: `python scripts/solver_timings.py` (run nothing
   else heavy at the same time).
2. Correctness: `python -m unittest tests.test_solver_agreement tests.test_cdcl
   tests.test_walksat tests.test_runtime`.
3. Tasks marked "same search" must give identical decisions and conflicts:
   compare the conflicts column of `solver_timings.py` before and after. A
   different count means the task changed the search, which is a bug for
   those tasks.
4. One task per commit, with the measured gain in the commit message and a line
   in `docs/guide/performance.md`.
5. A task that brings no measurable gain is closed as dropped, with the
   numbers, and its code is not merged.

## Tasks

- [ ] **OPT-1. Blocker literals in the watch lists** (CDCL, same search)
  - **Difficulty:** hard (CDCL hot loop)
  - **Blocked by:** B6, B7, B8, B9 (the clean-up of the same code comes first)
  - **How:** each watch entry stores one other literal of the clause (the
    "blocker", as in MiniSat). When the blocker is already true, the clause is
    satisfied and `propagate()` skips it without opening the clause object.
    Watch lists become lists of `(clause, blocker)` pairs, or two parallel
    lists; `add_clause()` fills them. The blocker must be updated when the
    watch moves.
  - **Done when:** rules 1-3 hold with an unchanged conflicts column, and the
    large instances (3-SAT n=250, Sudoku 25x25) are measurably faster.
    Estimate, not measured: 1.2-1.4x on propagation.

- [ ] **OPT-2. Lighter clause objects** (CDCL, same search)
  - **Difficulty:** medium
  - **How:** `Clause` is a `@dataclass(eq=False)`; attribute access on a plain
    instance goes through a dict. Try `@dataclass(eq=False, slots=True)`
    (needs Python 3.10, which the repo requires). Measure plain lists only if
    slots is not enough; they are less readable.
  - **Done when:** rules 1-3 hold with an unchanged conflicts column and a
    measured gain; expect a few percent.

- [ ] **OPT-3. Fast path for two-literal clauses** (CDCL)
  - **Difficulty:** hard (CDCL hot loop; may change the search)
  - **Blocked by:** OPT-1
  - **Needs decision:** only if the conflicts column changes. The order in
    which implications are found can differ, which changes the search and
    makes earlier benchmark numbers no longer comparable. Options: accept and
    document it as a search change, or drop the task.
  - **How:** binary clauses are common in the encodings (all the "at most one"
    pairs). A separate watch list per literal holding just the other literal
    lets propagation handle them without the general replacement search.
    Conflict analysis still needs a reason clause for binary implications.
  - **Done when:** rules 1-2 hold and Sudoku, N-Queens and graph colouring are
    measurably faster (estimate, not measured: 1.2-1.5x on those). If the
    search changed, `docs/algorithms/cdcl.md` and `docs/guide/performance.md`
    say so.

- **OPT-4. Renumber huge variable numbers:** this is audit item A2; do it
  there.

- [ ] **OPT-5. Learned-clause minimisation** (CDCL, changes the search)
  - **Difficulty:** hard
  - **Needs decision:** on or off by default. It changes decisions and
    conflicts, so earlier benchmark results are no longer directly comparable.
    Recommendation: a solver option, off by default until the thesis numbers
    are final.
  - **How:** after first-UIP analysis, remove literals of the learned clause
    that are implied by the others (MiniSat's recursive minimisation), at the
    end of `analyse_conflict()`.
  - **Done when:** the agreement test passes with the option on and off; with
    it on, the hard instances need fewer conflicts and less time; the option
    is described in `docs/algorithms/cdcl.md`.

- [ ] **OPT-6. DPLL and WalkSAT: profile before touching**
  - **Difficulty:** easy (the result is a note, not code)
  - **How:** DPLL already uses counters and gains 8.6x under PyPy, so its
    CPython time is mostly interpreter overhead; WalkSAT/ProbSAT are close to
    a hand-tuned prototype. Profile one long run of each.
  - **Done when:** `docs/guide/performance.md` records where their time goes
    and either names a concrete next task (added to this plan) or says there
    is nothing worth doing.

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
