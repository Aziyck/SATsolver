# Table templates for the report

> English, updated version of `legacy/docs_ro/tables_template.md`. `TODO`
> values are not results; fill them in after running the application.

## Table 1. Structure of the application

| Module | Role | Notes |
|---|---|---|
| `frontend/` | web interface: forms, previews, result views, charts, job list | TODO |
| `sat_web/` | local HTTP/WebSocket server, job processes, SQLite persistence | TODO |
| `problems/` | encoders from problems to SAT, decoders, answer checks | TODO |
| `sat_core/` | parameter schema, models, solver registry, benchmarks, jobs, runtime, DIMACS, verification | TODO |
| `solvers/` | DPLL, CDCL, WalkSAT/ProbSAT | TODO |
| `docs/visualisations/` | educational HTML visualisations | TODO |

## Table 2. Problems encoded in SAT

| Problem | Main file | SAT variable | Clause families | Decoded answer |
|---|---|---|---|---|
| Sudoku | `problems/sudoku.py` | `sudoku_var(r,c,v)` | cell, row, column, box, givens | the grid |
| N-Queens | `problems/n_queens.py` | `n_queens_var(row,col,n)` | rows, columns, diagonals | queen positions |
| Graph coloring | `problems/graph_coloring.py` | `color_var(node,color,k)` | one color per node, edges | node colors |
| Hamiltonian path | `problems/hamiltonian_path.py` | `readable_pair_var(position,node,n)` | positions, uniqueness, adjacency | the path |
| Clique | `problems/clique.py` | `slot_var(slot,node,n)` | slots, uniqueness, connections | selected nodes |
| Independent set | `problems/independent_set.py` | `slot_var(slot,node,n)` | slots, uniqueness, forbidden edges | selected nodes |
| Random 3-SAT | `problems/random_3sat.py` | variables 1..n | clauses of 3 literals | the assignment |
| DIMACS | `problems/dimacs_input.py` | as in the file | as in the file | the assignment |

## Table 3. Solvers and their properties

| Solver | File | Complete | Possible statuses | Main options |
|---|---|---|---|---|
| DPLL | `solvers/dpll.py` | yes | SAT, UNSAT, TIMEOUT, CANCELLED, ERROR | none (small-clause heuristic) |
| CDCL | `solvers/cdcl.py` | yes | SAT, UNSAT, TIMEOUT, CANCELLED | branching, phase, restarts, learned-clause limit, seed |
| WalkSAT | `solvers/walksat.py` | no | SAT, UNKNOWN, TIMEOUT, CANCELLED | tries, flips, noise, adaptive noise, seed |
| ProbSAT | `solvers/walksat.py` (`selection_mode="probsat"`) | no | SAT, UNKNOWN, TIMEOUT, CANCELLED | tries, flips, noise, adaptive noise, seed |

Any run in a benchmark can also be `SKIPPED` by a limit rule or by the user.

## Table 4. Experimental configuration

| Experiment | Problem family | Parameters | Solvers | Repeats | Time limit | Limit rules | Seed |
|---|---|---|---|---:|---:|---|---:|
| E1 | Sudoku | TODO | TODO | TODO | TODO | TODO | TODO |
| E2 | N-Queens | TODO | TODO | TODO | TODO | TODO | TODO |
| E3 | Random 3-SAT | TODO | TODO | TODO | TODO | TODO | TODO |
| E4 | Graph coloring | TODO | TODO | TODO | TODO | TODO | TODO |
| E5 | Graph suite | TODO | TODO | TODO | TODO | TODO | TODO |

## Table 5. Raw experimental results

| Experiment | Instance | Solver | Status | Time (s) | Conflicts | Decisions | Propagations | Learned clauses | Notes |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| TODO | TODO | CDCL | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| TODO | TODO | DPLL | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| TODO | TODO | WalkSAT | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| TODO | TODO | ProbSAT | TODO | TODO | TODO | TODO | TODO | TODO | TODO |

## Table 6. Aggregated results

| Family | Solver | Runs | SAT | UNSAT | UNKNOWN | TIMEOUT | Median time (s) | Min time (s) | Max time (s) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TODO | CDCL | TODO | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| TODO | DPLL | TODO | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| TODO | WalkSAT | TODO | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| TODO | ProbSAT | TODO | TODO | TODO | TODO | TODO | TODO | TODO | TODO |

The table view under each chart on the results page gives these numbers per
x value, and the CSV has every run.

## Table 7. Comparative interpretation

| Observation | Evidence from the benchmark | Interpretation |
|---|---|---|
| CDCL is faster than DPLL on instances with many conflicts | TODO | learned clauses prevent repeating the same conflicts |
| WalkSAT finds some SAT instances quickly | TODO | local search can be efficient without a complete proof |
| ProbSAT differs from classic WalkSAT on random formulas | TODO | probabilistic selection changes the search trajectory |
| Random 3-SAT is hardest near ratio 4.26 | TODO | the SAT/UNSAT phase transition |
| UNKNOWN is not equivalent to UNSAT | TODO | WalkSAT/ProbSAT build no proof of unsatisfiability |

## Table 8. Limitations and improvements

| Limitation | Impact | Direction |
|---|---|---|
| Benchmarks do not measure memory | the performance analysis is partial | add memory measurements |
| WalkSAT and ProbSAT are incomplete | they can return UNKNOWN | report separately from UNSAT |
| DPLL has no options in the interface | simpler but less flexible comparison | expose more heuristics |
| Pure Python solvers | absolute times are much higher than industrial solvers | compare relative behaviour, not absolute times |
| Pairwise at-most-one encoding | quadratic clause counts on large instances | sequential-counter encodings |
