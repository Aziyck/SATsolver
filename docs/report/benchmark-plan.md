# Benchmark plan

> English, updated version of `legacy/docs_ro/benchmark_plan.md`. How to run
> each experiment in the web app is described in the
> [benchmarking guide](../guide/benchmarking.md).

This document proposes a method for the experimental evaluation of the SAT
solver application. Numbers must only be filled in after real runs; the
tables use `TODO` for values still to be measured.

## Goals

1. Compare the complete solvers DPLL and CDCL.
2. Compare the local-search solvers WalkSAT and ProbSAT.
3. Observe the difference between satisfiable and unsatisfiable instances.
4. Measure the effect of parameters: size, graph density, number of clauses,
   seed, time limit and solver options.
5. Produce tables and charts for the report.

## General configuration

| Parameter | Recommended value | Notes |
|---|---|---|
| Repeats | TODO | at least 3 for fast instances (or several seeds per case) |
| Time limit per run | TODO | the same for every solver in a series |
| Limit rules | cap DPLL at 10 s from 200 variables (default) | state any change |
| Seed | TODO | needed for reproducibility; use seed ranges such as `1..20` |
| Complete solvers | CDCL, DPLL | can prove SAT and UNSAT |
| Incomplete solvers | WalkSAT, ProbSAT | may return UNKNOWN |
| Export | CSV from the results page | one format for every problem |

## Problem sets

### Sudoku

Implementation: `problems/sudoku.py`. Preset: *Sudoku sizes*.

| Size | Solvers | Repeats / seeds | Time limit | Notes |
|---:|---|---:|---:|---|
| 4x4 | CDCL, DPLL | TODO | TODO | small instance, quick check |
| 9x9 | CDCL, DPLL | TODO | TODO | representative instance |
| 16x16 | CDCL | TODO | TODO | optional, can take longer |
| 25x25 | CDCL | TODO | TODO | optional, expensive |

Use generated puzzles (source *Generate*) with a givens percentage such as
30% and 50% to control difficulty. WalkSAT and ProbSAT can be run on Sudoku
for comparison, but read their results carefully since they cannot prove
UNSAT.

### N-Queens

Implementation: `problems/n_queens.py`.

| n | Solvers | Repeats | Time limit | Notes |
|---:|---|---:|---:|---|
| TODO | CDCL, DPLL, WalkSAT, ProbSAT | TODO | TODO | grow the size gradually (for example `8..40:4`) |
| TODO | CDCL, DPLL, WalkSAT, ProbSAT | TODO | TODO | complete vs local search |

N-Queens has a known answer (UNSAT for n = 2, 3; SAT otherwise), which the
application checks automatically.

### Random 3-SAT

Implementation: `problems/random_3sat.py`. See the dedicated
[Random 3-SAT plan](random-3sat-benchmark-plan.md) and the presets A, B, C and
*phase transition*.

Recommended modes:

- *Planted SAT*, for satisfiable instances;
- *Forced UNSAT*, for UNSAT proofs with CDCL/DPLL;
- *Random*, for uncontrolled formulas (phase transition);
- *Mixed*, for a known mix of SAT and UNSAT formulas.

| Variables | Clauses per variable | Mode | Solvers | Repeats | Seeds | Time limit |
|---:|---:|---|---|---:|---:|---:|
| TODO | TODO | Planted SAT | CDCL, DPLL, WalkSAT, ProbSAT | TODO | TODO | TODO |
| TODO | TODO | Forced UNSAT | CDCL, DPLL | TODO | TODO | TODO |
| TODO | TODO | Random | CDCL, DPLL, WalkSAT, ProbSAT | TODO | TODO | TODO |

For WalkSAT and ProbSAT, `UNKNOWN` is not a proof of unsatisfiability.

### Graph coloring

Implementation: `problems/graph_coloring.py`, graphs from `problems/graph.py`.
Preset: *3-coloring threshold*.

| Nodes | Graph mode | Mode value | Colors | Solvers | Repeats | Time limit |
|---:|---|---:|---:|---|---:|---:|
| TODO | G(n,p) | TODO | TODO | CDCL, DPLL, WalkSAT, ProbSAT | TODO | TODO |
| TODO | G(n,m) | TODO | TODO | CDCL, DPLL, WalkSAT, ProbSAT | TODO | TODO |
| TODO | G(n,d) | TODO | TODO | CDCL, DPLL, WalkSAT, ProbSAT | TODO | TODO |

Each graph mode is a separate parameter grid in the builder (**Add another
parameter grid**).

### Hamiltonian path

Implementation: `problems/hamiltonian_path.py`.

| Nodes | Graph mode | Mode value | Solvers | Repeats | Time limit |
|---:|---|---:|---|---:|---:|
| TODO | G(n,p) | TODO | CDCL, DPLL | TODO | TODO |
| TODO | G(n,m) | TODO | CDCL, DPLL | TODO | TODO |

WalkSAT and ProbSAT can be included as incomplete methods, but their
`UNKNOWN` results must be reported separately. The CNF grows quickly with the
number of nodes (about n^4 clauses on sparse graphs); the plan panel shows
the largest formula before you start.

### Clique and independent set

Implementation: `problems/clique.py`, `problems/independent_set.py`.

| Problem | Nodes | Graph mode | Target k | Solvers | Repeats | Time limit |
|---|---:|---|---:|---|---:|---:|
| Clique | TODO | TODO | TODO | CDCL, DPLL, WalkSAT, ProbSAT | TODO | TODO |
| Independent set | TODO | TODO | TODO | CDCL, DPLL, WalkSAT, ProbSAT | TODO | TODO |

### Graph suite

Selecting several graph problems in one benchmark runs them all on **the same
generated graphs**, which makes the comparison between graph coloring,
Hamiltonian path, clique and independent set fair. Preset: *Graph suite:
Clique vs Independent Set*.

| Nodes | Graph mode | Problems | Solvers | Repeats | Seeds | Time limit |
|---:|---|---|---|---:|---:|---:|
| TODO | TODO | TODO | CDCL, DPLL, WalkSAT, ProbSAT | TODO | TODO | TODO |

## Rules for a fair comparison

1. Use the same time limit for every solver in a series, and report the
   limit rules that applied (the CSV has a `rule` column).
2. Keep the same seeds for randomly generated instances. The application
   runs every solver on the same CNF for each case.
3. For CDCL, record the branching heuristic, initial phase, restart schedule
   and learned-clause clean-up. Keep *Parallel cases* at 1 for timed runs.
4. For WalkSAT/ProbSAT, record max tries, max flips, noise, adaptive noise
   and seed.
5. Keep `UNSAT` and `UNKNOWN` apart.
6. Never compare a WalkSAT `UNKNOWN` with a CDCL `UNSAT` as if they meant the
   same thing.
7. Export the CSV right after the run and keep the exact configuration
   (**Edit as new** shows the request of any benchmark).
8. Check the *suspicious runs* filter: it must be empty, otherwise an
   answer failed verification or contradicts the expected result.

## Recommended final table

| Family | Instance | Solver | Options | Status | Median time | Conflicts | Decisions | Propagations | Notes |
|---|---|---|---|---|---:|---:|---:|---:|---|
| TODO | TODO | CDCL | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| TODO | TODO | DPLL | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| TODO | TODO | WalkSAT | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| TODO | TODO | ProbSAT | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
