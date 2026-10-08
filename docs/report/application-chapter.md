# Chapter 2. Design and implementation of the SAT solver application

> English, updated version of `legacy/docs_ro/partea_aplicativa_baza.md`.
> The original described the Tkinter desktop app; this version describes the
> current web application (WizSAT 2.0). Figure placeholders are in square
> brackets; the matching screenshot list is in
> [screenshot-checklist.md](screenshot-checklist.md).

This chapter describes the practical part of the project: an application for
generating, solving and comparing SAT instances. It follows the current
structure of the repository: the web server in `sat_web/`, the shared core in
`sat_core/`, the problem encoders in `problems/`, the solvers in `solvers/`,
the browser interface in `frontend/` and the visualisations in
`docs/visualisations/`.

The theoretical part of the thesis presents P vs NP, SAT, 3-SAT, polynomial
reductions and the families of SAT algorithms. Here the focus is on how those
concepts become a concrete program: problems are encoded in CNF, the formulas
are passed to solvers, and the results are decoded and shown to the user.

## 2.1 Purpose and functional requirements

The application is an experimental environment for working with SAT formulas
and with classic problems reduced to SAT. The user can build problem
instances, inspect the generated CNF formula, choose a solver, and compare
the behaviour of the algorithms on the same family of instances.

Main features:

1. building SAT instances for Sudoku, N-Queens, graph coloring, Hamiltonian
   path, clique, independent set and random 3-SAT;
2. entering or opening formulas in DIMACS/CNF format;
3. solving formulas with DPLL, CDCL, WalkSAT or ProbSAT;
4. showing the raw SAT result and the decoded solution of the original
   problem, drawn on the problem itself;
5. verifying every answer twice: against the clauses and against the rules
   of the original problem;
6. generating and downloading CNF files and models;
7. running benchmarks over parameter sweeps, with repeats, time limits,
   seeds, solver options and per-solver limit rules;
8. charting benchmark results and exporting them as CSV;
9. previewing graphs, boards and formulas before solving;
10. interactive visualisations of DPLL, CDCL and WalkSAT.

[Figure 1: The main page of the application]

The application has four areas:

- **Solve**, for a single instance;
- **Benchmarks**, for systematic runs of many instances and solvers;
- **Jobs**, the history of everything that ran;
- **Learn**, the interactive visualisations (`docs/visualisations/dpll/`,
  `cdcl/`, `walksat/`) and notes on the algorithms.

## 2.2 General architecture

The application runs locally: a Python server does the computation and a
browser page provides the interface. The layers are separated so that the
interface contains no reduction or solver logic.

| Area | Role |
|---|---|
| `frontend/` | React interface: forms, previews, result views, charts, job list |
| `sat_web/api.py` | HTTP API and WebSocket used by the interface |
| `sat_web/manager.py` | runs each job in its own process, relays live events, stores results |
| `sat_web/store.py` | SQLite persistence of jobs and benchmark rows |
| `problems/` | one encoder per problem, registered as a `ProblemSpec` |
| `sat_core/params.py` | the declarative parameter schema shared by forms, validation and benchmarks |
| `sat_core/models.py` | the shared models `ProblemInstance`, `SolveResult`, `BenchmarkRow` |
| `sat_core/solver_registry.py` | the solver registry and the common entry point `run_solver` |
| `sat_core/jobs.py` | the solve, encode and benchmark jobs executed in worker processes |
| `sat_core/runtime.py` | run events, progress, cancellation, timeout and skip |
| `sat_core/benchmark.py` | benchmark plans, limit rules, execution and CSV export |
| `sat_core/dimacs.py` | DIMACS parsing and writing |
| `sat_core/verify.py` | checking an assignment against the clauses |
| `solvers/` | the DPLL, CDCL and WalkSAT/ProbSAT implementations |

The overall flow:

```text
browser form
-> HTTP request to the local server
-> problem encoder (problems/*)
-> ProblemInstance (CNF clauses + decoder)
-> run_solver (sat_core/solver_registry.py)
-> solver (solvers/*)
-> SolveResult
-> decoder and checks of the problem
-> live events to the browser: display, benchmark table, export
```

The central model is `ProblemInstance` in `sat_core/models.py`. It holds the
instance name, the problem type, the list of CNF clauses, metadata and a
decoding function. Through this model Sudoku, N-Queens and Clique are handled
uniformly by the SAT solvers.

`SolveResult` normalises what a solver returns: status, time, solution,
statistics, number of clauses and variables, and an error message when the
solver failed. For benchmarks, `BenchmarkRow` also records the case and its
parameters, the repeat, the solver label, the expected answer, whether the
answer was verified, the solver statistics and the limit rule that applied.

Longer computations never run inside the web server's request handling.
Every solve, encoding and benchmark is a *job* executed in a separate
process: the solvers are CPU-bound pure Python, so processes use several
cores and can be stopped safely. The worker reports progress through events
that the server stores and forwards to the browser over a WebSocket, so the
page updates live and stays responsive. Cancellation is cooperative (the
solver stops at its next checkpoint), with a forced stop as a fallback.

[Figure 2: Architecture of the application]

## 2.3 Representing CNF formulas

A CNF formula is a list of clauses and each clause is a list of integer
literals:

```python
[[1, -2], [2, 3], [-1]]
```

The interpretation is the standard one:

- a positive literal `x` means variable `x` appears positively;
- a negative literal `-x` means the negation of `x`;
- a clause is satisfied when at least one literal is true;
- the formula is satisfied when every clause is satisfied.

DIMACS parsing and formatting live in `sat_core/dimacs.py`: `parse_dimacs`
reads text (with line-numbered errors and warnings for inaccurate headers),
`clauses_to_dimacs` produces text, and `save_dimacs` / `load_dimacs` work
with files. Files written by the application start with a
`c wizsat {...}` comment that records the problem and its parameters, so they
can be reopened as the original problem.

Example:

```text
c minimal example
p cnf 3 2
1 -2 0
2 3 0
```

The generated CNF of every job can be viewed in the **CNF** tab of the
result and downloaded as a `.cnf` file.

## 2.4 Encoding the problems in SAT

Each problem is a `ProblemSpec` subclass registered in `problems/`. It
declares its parameters, encodes validated parameters into a
`ProblemInstance`, decodes a model into an answer, and checks that answer
against the original problem. Encoders do not know about the interface or
the solvers. A detailed description of each encoding, with clause counts, is
in [docs/algorithms/encodings.md](../algorithms/encodings.md).

### 2.4.1 Sudoku

`problems/sudoku.py`. The variable `sudoku_var(r, c, v) = r*10000 + c*100 + v`
means "row r, column c holds value v".

Clauses:

1. each cell has at least one value;
2. each cell has at most one value;
3. no value appears twice in the same row;
4. no value appears twice in the same column;
5. no value appears twice in the same box;
6. the givens are unit clauses.

The decoder turns the model into a grid of numbers. Sizes 4, 9, 16 and 25 are
supported. Puzzles are typed into an editable grid (conflicting cells are
highlighted) or generated from a random valid grid with a chosen percentage
of givens.

[Figure 3: Sudoku input and the generated CNF]

### 2.4.2 N-Queens

`problems/n_queens.py`. The variable `readable_pair_var(row, col, n)` means
"a queen stands on (row, col)", for example `101` for (1, 1) on a 4x4 board.

Clauses:

1. at least one queen in every row;
2. at most one queen in every row;
3. at most one queen in every column;
4. no two queens on a common diagonal.

The decoder returns the queen positions, drawn on a chessboard.

### 2.4.3 Graph coloring

`problems/graph_coloring.py`, with the graph inputs shared by all graph
problems in `problems/graph.py`. Graphs can be:

- typed as a list of edges (or edited by clicking in the preview);
- random `G(n,p)`, each edge with probability p;
- random `G(n,m)`, exactly m edges;
- random `G(n,d)`, average degree d, converted to `m = round(n*d/2)`.

The variable `color_var(node, color, colors)` means "node has color", for
example `color_var(2, 3, 10) = 203`. When the second part exceeds 99 the
width grows automatically: `color_var(2, 101, 101) = 2101`.

Clauses:

1. each node has at least one color;
2. each node has at most one color;
3. adjacent nodes do not share a color.

The decoder produces a mapping node -> color, drawn as a colored graph.

[Figure 4: Graph preview for graph coloring]

### 2.4.4 Hamiltonian path

`problems/hamiltonian_path.py`. The variable `readable_pair_var(position,
node, n)` means "node is at this position of the path".

Clauses:

1. every position holds at least one node;
2. no position holds two nodes;
3. every node appears at least once;
4. no node appears at two positions;
5. consecutive positions cannot hold nodes without an edge between them.

The decoder returns the nodes in path order, highlighted on the graph.

### 2.4.5 Clique and independent set

`problems/clique.py` and `problems/independent_set.py` look for a selection
of k nodes represented by k slots. The variable `readable_pair_var(slot,
node, n)` means "node fills this slot".

In both cases the clauses require:

1. each slot holds a node;
2. no slot holds two nodes;
3. no node is used in two slots;
4. the problem's own condition:
   - for clique, every two selected nodes are adjacent;
   - for independent set, no two selected nodes are adjacent.

Both run on typed or random graphs. In a benchmark they can be run together
on exactly the same graphs (a graph suite).

### 2.4.6 Random 3-SAT

`problems/random_3sat.py` generates formulas with n variables and
`m = round(n * ratio)` clauses of three distinct variables:

- **Random**: plain random clauses; the answer is not known in advance;
- **Planted SAT**: a hidden assignment is drawn first and only clauses it
  satisfies are kept, so the formula is satisfiable;
- **Forced UNSAT**: all 8 sign combinations over three variables are added,
  an unsatisfiable core, so the formula is unsatisfiable;
- **Mixed**: planted with a chosen probability, forced otherwise.

The metadata records the number of variables and clauses, the ratio, the
seed and the mode. The generator is useful for experiments because it gives
unstructured formulas and, through the ratio, direct control over
difficulty.

## 2.5 The solvers

Solvers are registered in `sat_core/solver_registry.py` with typed options:

| Key | Solver | Complete |
|---|---|---|
| `cdcl` | CDCL | yes |
| `dpll` | DPLL | yes |
| `walksat` | WalkSAT | no |
| `probsat` | ProbSAT | no |

All of them take a list of clauses and return a solution `dict[int, bool]` or
`None`, plus statistics. `run_solver` applies the time limit, turns solver
failures into an `ERROR` status with a readable message, and normalises the
result.

### 2.5.1 DPLL

`solvers/dpll.py`. A complete solver: if the formula is satisfiable it finds
a model, otherwise it proves unsatisfiability by exhausting the search tree.

Main steps:

1. unit propagation, with two counters per clause (true and false literals);
2. detection of conflicts (clauses with every literal false);
3. choice of an unassigned variable;
4. trying `True` and `False`;
5. chronological backtracking when a branch fails, with an explicit decision
   stack.

The variable is chosen with a small-clause heuristic (`choose_variable`):
variables from the shortest clauses are preferred, because short clauses are
the most constrained.

The solver is iterative and never copies the formula, so it is not limited by
Python's recursion depth. An earlier recursive version, which made the same
decisions, is kept in `legacy/dpll_recursive.py`.

Statistics: decisions, propagations, conflicts, maximum depth and time. DPLL
has no options in the interface.

### 2.5.2 CDCL

`solvers/cdcl.py`. Extends DPLL with clause learning and non-chronological
backjumping:

- the `Clause` class, with metadata for learned clauses;
- watched literals for fast propagation;
- a trail with decision levels;
- First-UIP conflict analysis;
- learned clauses scored by LBD;
- periodic deletion of weak learned clauses;
- a binary heap for VSIDS decisions;
- phase saving and Luby restarts.

Options exposed in the interface:

- branching heuristic: VSIDS, most frequent, MOMS, DLIS, random;
- initial phase: positive first, negative first, polarity based, random;
- restarts (Luby schedule or a fixed interval, on by default);
- automatic learned-clause clean-up, or a fixed limit;
- a seed for reproducible random choices.

The options are declared as typed fields in the solver registry and passed to
`cdcl()` by its runner.

### 2.5.3 WalkSAT

`solvers/walksat.py`. Incomplete: it can quickly find a solution of a
satisfiable formula, but it cannot prove unsatisfiability. When the search
budget is exhausted the status is `UNKNOWN`.

Starting from a random complete assignment, it repeats:

1. pick an unsatisfied clause at random;
2. pick a variable from that clause: one with break 0 if there is one (a
   free move), otherwise a random one with probability `noise`, otherwise one
   with the smallest break (the SKC variant of Selman, Kautz and Cohen);
3. flip it;
4. update the unsatisfied clauses and the break counts incrementally;
5. stop at SAT, timeout, cancellation, or when the budget runs out.

The break of a variable is the number of true clauses that would become false
if it were flipped. `LocalSearchState` keeps it up to date: for every clause
it stores the number of true literals and the sum of their variable numbers,
and when only one literal is true that sum names the variable that keeps the
clause true. A flip only touches the clauses that contain the flipped
variable.

Options: `max_tries` (random restarts, default 10), `max_flips` (per try,
default 100,000), `noise` (default 0.567), `adaptive_noise` (raise the noise
when the search stagnates) and a seed.

Statistics: tries, flips, best number of unsatisfied clauses, the number of
free, random and greedy flips, final noise and the reason for stopping.

### 2.5.4 ProbSAT

ProbSAT (Balint and Schoening, 2012) is registered as its own solver; it
shares the implementation and the incremental break counts with WalkSAT
(`selection_mode="probsat"`). It has no noise parameter: every variable of
the chosen clause is drawn with probability proportional to a weight that
falls steeply with its break:

```text
f(break) = (0.9 + break) ^ -2.06      3-SAT
f(break) = cb ^ -break                longer clauses, cb = 3.0 .. 5.4
```

The search stays stochastic: bad moves remain possible, which is how ProbSAT
escapes local minima. An advanced option overrides `cb`.

### Technical notes

- All four solvers are available in the Solve page, in benchmarks and in the
  API.
- WalkSAT and ProbSAT never prove unsatisfiability; `UNKNOWN` only means no
  model was found within the budget.
- Every SAT answer is checked: the model against all clauses
  (`sat_core/verify.py`) and the decoded answer against the problem's own
  rules.

## 2.6 The interface and how it is used

The interface is a web page served by the local Python server. The **Solve**
page handles one instance:

1. the user chooses a problem from a gallery;
2. fills in the parameters (the preview shows the graph, board or clauses and
   the estimated size of the CNF);
3. chooses a solver and its options, a time limit and the log detail;
4. presses **Solve** (or **Encode only** to just build the CNF);
5. inspects the answer drawn on the problem, the verification badge, the
   CNF, the statistics and the log.

[Figure 5: The Solve flow]

For graph problems the graph is drawn before and after solving; nodes can be
dragged, and in manual mode edges can be added or removed by clicking.
DIMACS formulas can be pasted or opened from a file.

The **Benchmarks** page runs series of experiments. The user selects a
problem (or several graph problems), gives lists or ranges for the parameters
(`50, 100`, `1..30`, `3..6:0.25`), adds solvers (the same solver can be added
several times with different options), and sets repeats, the time limit, the
seed and limit rules. A live plan shows the number of runs before starting.
Results stream in; they are shown as line charts with a chosen x axis and
optional panels per parameter, a chart of SAT/UNSAT/UNKNOWN shares, table
views, and a sortable table of runs. The CSV export has the same format for
every problem.

[Figure 6: Benchmark results with charts and the run table]

Every solve, encoding and benchmark is a job with its own entry on the
**Jobs** page. Jobs can be cancelled, rerun, edited as new, or deleted, and
they survive restarts of the application.

## 2.7 Benchmarks and test methodology

Benchmarks are implemented in `sat_core/benchmark.py` and are generic: any
registered problem can be swept over any of its sweepable parameters, and
several graph problems can share the same graphs. Presets
(`sat_core/presets.py`) reproduce the experiments of the report:

- Random 3-SAT A: planted SAT;
- Random 3-SAT B: forced UNSAT;
- Random 3-SAT C: mixed SAT/UNSAT;
- the random 3-SAT phase transition;
- CDCL branching heuristics;
- a graph suite (clique vs independent set);
- the 3-coloring threshold;
- Sudoku sizes.

Recommended method:

1. fix the set of problems and parameters;
2. run the same instances with several solvers (the application guarantees
   this: each case is encoded once);
3. use seeds so that generation is reproducible;
4. use the same time limit for all solvers, and state the limit rules;
5. repeat each configuration several times;
6. export the results as CSV;
7. report the status as well as the time and the internal statistics.

WalkSAT and ProbSAT must be interpreted differently from DPLL and CDCL:
DPLL and CDCL are complete, WalkSAT and ProbSAT are not, so `UNKNOWN` is not
the same as `UNSAT`. By default DPLL is capped at 10 seconds on formulas with
200 variables or more, because without clause learning it can take far
longer than the other solvers; the cap can be changed or removed in the
interface.

Details: [benchmark-plan.md](benchmark-plan.md),
[random-3sat-benchmark-plan.md](random-3sat-benchmark-plan.md) and the
[benchmarking guide](../guide/benchmarking.md).

| Family | Parameters | Solvers | Repeats | Time limit | Seed |
|---|---|---|---:|---:|---:|
| Sudoku | TODO | CDCL, DPLL | TODO | TODO | TODO |
| Random 3-SAT | TODO | CDCL, DPLL, WalkSAT, ProbSAT | TODO | TODO | TODO |
| Graph coloring | TODO | CDCL, DPLL, WalkSAT, ProbSAT | TODO | TODO | TODO |

## 2.8 Experimental results

The experimental results must be filled in after running the benchmarks in
the application. No numbers are entered without real runs.

| Instance | Solver | Status | Mean time (s) | Conflicts | Decisions | Propagations | Notes |
|---|---|---|---:|---:|---:|---:|---|
| TODO | CDCL | TODO | TODO | TODO | TODO | TODO | TODO |
| TODO | DPLL | TODO | TODO | TODO | TODO | TODO | TODO |
| TODO | WalkSAT | TODO | TODO | TODO | TODO | TODO | TODO |
| TODO | ProbSAT | TODO | TODO | TODO | TODO | TODO | TODO |

[Figure 7: Comparison chart of solver times]

Points to discuss when interpreting the results:

- the difference between complete and incomplete solvers;
- the effect of learned clauses in CDCL;
- cases where DPLL slows down because of plain backtracking;
- the influence of the seed on WalkSAT and ProbSAT;
- satisfiable versus unsatisfiable instances;
- the influence of graph density or of the clause/variable ratio.

## 2.9 Limitations and future work

Current limitations:

1. the application is meant for education and experiments, not for the
   performance of an industrial solver (the solvers are pure Python);
2. DPLL uses a fixed heuristic and has no options in the interface;
3. WalkSAT and ProbSAT cannot prove `UNSAT`;
4. benchmarks measure time and solver statistics, not memory;
5. results on random formulas depend on the seed and must be read
   statistically;
6. the at-most-one constraints use the pairwise encoding, which grows
   quadratically.

Since the first version, several earlier directions have been implemented:
formal checks of decoded answers, dedicated phase-transition experiments,
integration of the visualisations in the application, more detailed solver
statistics in the export, and a web interface that stays responsive on large
benchmarks.

Future work:

1. measuring memory in benchmarks;
2. SAT preprocessing such as pure literal elimination or subsumption;
3. more compact cardinality encodings (sequential counters) for large
   instances;
4. an explicit `3-SAT -> Clique` reduction to connect the code with
   NP-completeness proofs;
5. DPLL heuristics exposed as options.

## 2.10 Conclusions

The application turns the theory of SAT and polynomial reductions into a
practical tool. Different problems are expressed in the common CNF
representation and solved by solvers from different paradigms: DPLL as the
classic complete algorithm, CDCL as the modern variant with conflict-driven
learning, and WalkSAT/ProbSAT as incomplete local search.

Because the interface, encoders, shared models, solvers and benchmarks are
separated, and problems and solvers are declared in registries, the project
both demonstrates reductions to SAT and supports experimental comparison of
the algorithms, and new problems or solvers can be added without touching the
rest. The benchmark numbers must be filled in after real runs.
