# Algorithmic analysis of the SAT solver application

> English, updated version of `legacy/docs_ro/analiza_algoritmica_aplicatie.md`.
> The original referred to the Tkinter app and to line numbers that have since
> changed; this version refers to functions and classes in the current code.

## Introduction

This document analyses the algorithmic side of the `SATsolver` project
(WizSAT) from the code itself, not from outside assumptions. It follows the
active modules: `solvers/`, `problems/`, `sat_core/` and, for the execution
model, `sat_web/`.

The application is a local web app for:

1. generating SAT instances, or problems reduced to SAT;
2. solving them with several solvers;
3. decoding solutions back into the original problem and checking them;
4. benchmarking algorithms and instances against each other.

From a theoretical point of view the project is relevant to *P vs NP*
because:

1. SAT is the central problem the application works on;
2. several classic problems are transformed into CNF formulas;
3. the application separates *search* (solving) from *verification*
   (checking a model) explicitly;
4. it implements both exact algorithms and heuristic, incomplete methods.

---

## 1. Summary of the application

### 1.1 What it does

The application accepts instances from these problem families:

1. Sudoku;
2. graph coloring;
3. N-Queens;
4. random 3-SAT;
5. Hamiltonian path;
6. independent set;
7. clique;
8. DIMACS/CNF entered directly.

Each instance is converted into a boolean formula in conjunctive normal form
and passed to one of the solvers:

1. `CDCL`;
2. `DPLL`;
3. `WalkSAT`;
4. `ProbSAT` (WalkSAT with probabilistic selection).

A satisfying assignment is then:

1. kept as a mapping `variable -> boolean`;
2. checked against every clause;
3. decoded into a solution of the original problem and checked against that
   problem's rules;
4. shown in the interface and recorded in benchmarks.

### 1.2 Main flow

```text
browser form
-> validated parameters (ParamField schema)
-> problems/* build a ProblemInstance
-> CNF formula (list[list[int]])
-> sat_core/solver_registry.run_solver
-> solvers/{cdcl,dpll,walksat}.py
-> SolveResult
-> ProblemSpec.decode and ProblemSpec.check, verify.check_assignment
-> display / benchmark / export
```

### 1.3 Where the logic lives

| Area | Role |
|---|---|
| `solvers/` | SAT algorithms and heuristics |
| `problems/` | reductions of problems to SAT, decoders and answer checks |
| `sat_core/solver_registry.py` | solver registry, option schemas, `run_solver` |
| `sat_core/benchmark.py` | benchmark plans, limit rules, comparative evaluation, CSV |
| `sat_core/params.py` | parameter schema: validation and parameter sweeps |
| `sat_core/verify.py` | checking a model against the clauses |
| `problems/encoding.py`, `problems/graph.py` | variable numbering, graph generation |
| `sat_web/` | job processes, persistence and the web API (no algorithmic content) |

---

## 2. Main algorithms

## 2.1 DPLL

- **Where**: `solvers/dpll.py`, function `dpll`; registered as `dpll` in
  `sat_core/solver_registry.py`.
- **Role**: exact SAT solver, the classic baseline.
- **Theory**: DPLL is a complete satisfiability algorithm for CNF. It
  combines:
  1. unit propagation;
  2. choosing a decision variable;
  3. branching on `True` / `False`;
  4. backtracking on conflict.

  If a model exists it finds one; otherwise it proves `UNSAT`.
- **Practice**: the solver is iterative. It
  1. propagates unit clauses, using two counters per clause (true and false
     literals) instead of copying the formula;
  2. chooses a variable with the small-clause rule;
  3. tries `True` first, then `False`;
  4. on a conflict, undoes the trail back to the most recent decision whose
     second value has not been tried (an explicit decision stack replaces
     recursion).
  The earlier recursive version, which copied the simplified formula at every
  branch, is archived in `legacy/dpll_recursive.py`; both make the same
  decisions.
- **Complexity**: exponential in the worst case, about `O(2^n)`; unit
  propagation adds a cost that depends on the number and length of clauses.
- **Input / output**: a CNF `list[list[int]]`; a `dict[int, bool]` if
  satisfiable, otherwise `None`.
- **Example**: for `(x1) and (not x1 or x2)`, propagation forces `x1 = True`,
  the second clause becomes `(x2)`, so `x2 = True`; no clause is left, the
  formula is `SAT`.
- **Type**: exact algorithm.

Notes:

1. Unit propagation is implemented inside `solvers/dpll.py`, so the solver is
   self-contained.
2. The variable choice favours short clauses; there is no heuristic option in
   the interface.
3. The search depth is limited only by the number of variables (the recursive
   version stopped at Python's recursion limit, about 1,000 decisions).
4. Statistics: decisions, propagations, conflicts, maximum depth, time.

---

## 2.2 Unit propagation

- **Where**: `solvers/dpll.py`, `_unit_propagate`; CDCL has its own
  watched-literal propagation (`propagate` inside `cdcl`).
- **Role**: simplifies the formula and derives forced values before
  branching.
- **Theory**: if a clause has a single remaining literal, that literal must be
  true for the formula to stay satisfiable.
- **Practice**: the DPLL version looks for clauses of length 1, assigns the
  literal and
  1. removes satisfied clauses;
  2. removes the negated literal from the other clauses;
  3. reports a conflict when an empty clause appears.
- **Complexity**: the DPLL version rescans the formula, roughly
  `O(k * m * l)` for `k` propagations, `m` clauses and average length `l`.
  The CDCL version with watched literals only visits clauses watching the
  falsified literal.
- **Example**: `(x1) and (not x1 or x3) and (not x3 or x4)` gives `x1 = True`,
  then `x3 = True`, then `x4 = True`.
- **Type**: exact inference rule and optimisation.

---

## 2.3 CDCL

- **Where**: `solvers/cdcl.py`, function `cdcl`; registered as `cdcl`.
- **Role**: the main and most advanced solver of the project.
- **Theory**: CDCL extends DPLL with
  1. efficient propagation;
  2. conflict analysis;
  3. clause learning;
  4. non-chronological backjumping;
  5. variable activity;
  6. restarts.

  It is the dominant paradigm of modern complete SAT solvers.
- **Practice**: the implementation contains every essential block:
  1. normalisation of the formula;
  2. assignments stored with decision levels on a trail;
  3. watched literals for propagation;
  4. First-UIP conflict analysis;
  5. learned clauses scored by LBD;
  6. controlled deletion of learned clauses;
  7. several branching heuristics;
  8. phase selection and phase saving;
  9. Luby restarts (on by default).
  10. a binary heap that keeps the decision order (VSIDS).
- **Complexity**: still exponential in the worst case; in practice far more
  efficient than plain DPLL thanks to learning and cheap propagation.
- **Input / output**: CNF and solver options; a model, `None` for `UNSAT`, or
  `UNKNOWN` when a conflict limit (`max_conflicts`) is set and reached.
- **Example**: when a sequence of decisions leads to a conflict, the solver
  does not just undo the last decision; it derives a new clause that blocks
  the cause of the conflict and jumps back to the level where that clause
  becomes unit.
- **Type**: exact algorithm.

### Internal components of CDCL

**a) Formula normalisation** (`_normalise_formula`, `_dedupe_clause`):
removes duplicate literals, drops tautologies, detects the empty clause.
*Type*: preprocessing and logical check.

**b) Watched literals** (`add_clause`, `propagate`): each clause watches
two literals, kept at positions 0 and 1; when a value changes, only the
clauses watching the falsified literal are visited, not the whole formula.
`watches` maps a literal to the clauses watching it. *Type*: structural
optimisation; it changes practical cost, not worst-case complexity.

**c) First-UIP conflict analysis** (`analyse_conflict`): the conflict clause
is resolved with the reasons of propagated literals, walking the
implication graph backwards, until a single literal of the current decision
level remains (the first unique implication point). *Type*: exact internal
algorithm.

**d) Clause learning** (`add_clause`, `analyse_conflict`): the derived clause
is added to the formula so the same cause of conflict is never explored
again. *Type*: exact optimisation.

**e) Non-chronological backjumping** (`backtrack`): the solver returns to the
second-highest decision level in the learned clause, not necessarily to the
last decision. The literal with that level is stored second in the learned
clause, so it is the clause's second watch. *Type*: exact optimisation.

**f) Restarts** (`luby`): periodically return to level 0 while keeping the
learned clauses, activities and saved phases. By default after 1, 1, 2, 1, 1,
2, 4, ... times 100 conflicts (the Luby sequence); a fixed interval or no
restarts can be chosen. *Type*: heuristic.

**g) LBD of learned clauses** (`clause_lbd`): the Literal Block Distance is
the number of distinct decision levels among a clause's literals; clauses
with a low LBD tend to be more useful. *Type*: clause-quality heuristic.

**h) Deleting learned clauses** (`learned_clause_delete_key`,
`learned_clauses_to_delete`, `reduce_learned`): the learned-clause database
is cleaned periodically to keep propagation fast: after 2,000 conflicts, then
after 300 more each time, half of the weak learned clauses are deleted.
Binary clauses, glue clauses (LBD at most 2) and clauses that are currently
the reason of an assignment ("locked") are protected. Deleted clauses are
dropped from the watch lists lazily. *Type*: memory and performance
heuristic.

**i) Decision heap** (`heap_up`, `heap_down`, `heap_pop`): the unassigned
variables are kept in a binary max-heap ordered by VSIDS activity, so the
next decision costs O(log n) instead of a scan of all variables. *Type*:
data structure.

---

## 2.4 WalkSAT

- **Where**: `solvers/walksat.py`, function `walksat`; registered as
  `walksat`.
- **Role**: incomplete solver, used for experiments and comparison.
- **Theory**: local search for SAT. Start from a random assignment and flip
  variables of unsatisfied clauses, either at random or greedily. If no
  solution is found within the budget, nothing can be concluded about `UNSAT`.
- **Practice**: the solver
  1. normalises the formula;
  2. draws a random initial assignment;
  3. picks an unsatisfied clause;
  4. with probability `noise` flips a random variable of that clause;
  5. otherwise flips the variable with the best estimated effect;
  6. repeats; after `max_flips` flips it restarts (a new *try*).
- **Complexity**: no completeness guarantee; the work is bounded by
  `max_tries * max_flips`.
- **Input / output**: CNF and `max_tries`, `max_flips`, `noise`,
  `adaptive_noise`, seed; a model if found, otherwise `None` with status
  `UNKNOWN`.
- **Example**: if `(x1 or not x2 or x3)` is unsatisfied, one of its variables
  is flipped, which satisfies that clause and may break others.
- **Type**: incomplete local-search heuristic.

**Auxiliary structure** (`_UnsatisfiedTracker`): keeps, incrementally, the
number of true literals per clause, the occurrence lists and the set of
unsatisfied clauses, and computes the *make* and *break* counts of a flip.
After a flip only the clauses containing that variable are updated, instead
of re-evaluating the whole formula.

## 2.5 ProbSAT

- **Where**: `solvers/walksat.py` with `selection_mode="probsat"`;
  registered as its own solver `probsat`.
- **Theory**: instead of a greedy or uniformly random choice inside the
  selected clause, each variable is drawn with probability proportional to a
  weight that rewards repairs and penalises breaks:
  `weight = (make + 1) / ((break + 1) ^ 2)`.
- **Type**: incomplete stochastic local search.

---

## 2.6 Reductions to SAT

Each reduction is a `ProblemSpec` in `problems/`. The full description of
every encoding, with exact clause counts, is in
[docs/algorithms/encodings.md](../algorithms/encodings.md); this section keeps
the analysis format of the original document.

### Sudoku (`problems/sudoku.py`)

- **Role**: turns a Sudoku puzzle into an equisatisfiable CNF.
- **Theory**: variable `X(r,c,v)` = "cell (r,c) holds v". Clauses: every
  cell has at least one and at most one value; every value at most once per
  row, column and box; givens as unit clauses.
- **Complexity**: `n^3` variables; `n^2 + 4 n^2 C(n,2)` clauses plus the
  givens, dominated by the `O(n^4)` pairwise exclusions.
- **Example**: a given 3 at (1,1) adds the unit clause `[X(1,1,3)]`.
- **Type**: exact reduction.

### Graph coloring (`problems/graph_coloring.py`)

- **Role**: decides whether a graph is k-colorable.
- **Theory**: `X(v,c)` = "node v has color c". Every node at least one and at
  most one color; adjacent nodes never share a color.
- **Complexity**: `O(|V| k)` variables, `O(|V| k^2 + |E| k)` clauses.
- **Example**: for edge (1,2) and color c: `not X(1,c) or not X(2,c)`.
- **Type**: exact reduction.

### N-Queens (`problems/n_queens.py`)

- **Role**: places n non-attacking queens.
- **Theory**: `X(r,c)` = "a queen on (r,c)". Exactly one queen per row, at
  most one per column, at most one per diagonal.
- **Complexity**: `n^2` variables, `O(n^3)` clauses.
- **Example**: on 4x4, `[X(1,1), X(1,2), X(1,3), X(1,4)]` puts a queen in
  row 1.
- **Type**: exact reduction.

### Hamiltonian path (`problems/hamiltonian_path.py`)

- **Role**: decides whether a path visits every node exactly once.
- **Theory**: `X(p,v)` = "node v at position p". Each position exactly one
  node; each node exactly one position; consecutive positions cannot hold
  non-adjacent nodes.
- **Complexity**: `n^2` variables, `O(n^3 + n * non_edges)` clauses, `O(n^4)`
  in the worst case.
- **Example**: if 2 and 4 are not adjacent, `not X(3,2) or not X(4,4)`.
- **Type**: exact reduction.

### Independent set (`problems/independent_set.py`)

- **Role**: decides whether an independent set of size k exists.
- **Theory**: `X(s,v)` = "node v fills slot s". Each slot exactly one node,
  a node in at most one slot, the ends of an edge never both chosen. The slots
  impose the exact cardinality k.
- **Complexity**: `k n` variables, `O(k n^2 + k^2 n + k^2 |E|)` clauses.
- **Example**: for edge (u,v): `not X(s1,u) or not X(s2,v)` for all slots.
- **Type**: exact reduction.

### Clique (`problems/clique.py`)

- **Role**: decides whether a clique of size k exists.
- **Theory**: the same slots as independent set with the opposite structural
  rule: two non-adjacent nodes can never both be chosen.
- **Complexity**: `k n` variables, `O(k n^2 + k^2 n + k^2 |non_edges|)`
  clauses.
- **Example**: if u and v are not adjacent: `not X(s1,u) or not X(s2,v)`.
- **Type**: exact reduction.

### Random 3-SAT generation (`problems/random_3sat.py`)

- **Role**: produces experimental SAT/UNSAT instances.
- **Theory**: clauses of exactly three literals. Modes: random, planted SAT,
  forced UNSAT, mixed.
- **Practice**: *planted*: draw a hidden assignment, keep only clauses it
  satisfies. *Forced UNSAT*: pick three variables and add all 8 sign
  combinations, which no assignment can satisfy.
- **Complexity**: linear in the number of clauses, with rejection sampling
  in planted mode (each random clause is kept with probability 7/8).
- **Type**: instance generator, not a solver.

---

## 3. Auxiliary algorithms

**3.1 Random graphs `G(n,p)`** (`problems/graph.py`, `build_graph`): each of
the `C(n,2)` pairs becomes an edge independently with probability p
(Erdos-Renyi). `O(n^2)`.

**3.2 Graphs with exactly m edges `G(n,m)`**: m distinct pairs are sampled by
index from the `C(n,2)` possible ones, without listing them all; requests above
`C(n,2)` are clamped to the complete graph and reported.

**3.3 Average degree to edges `G(n,d)`**: `m = round(n*d/2)`, because in an
undirected graph the degrees sum to `2m`.

**3.4 DIMACS parsing and writing** (`sat_core/dimacs.py`): converts between
`list[list[int]]` and the standard text format, with line-numbered errors and
warnings. Infrastructure, not search.

**3.5 Deterministic seeding** (`sat_core/seeds.py`): every random choice is
made by a `random.Random` seeded from a string of the relevant parameters, so
the same parameters and seed always give the same instance, independently of
process or platform.

**3.6 Sudoku generation** (`problems/sudoku.py`): a valid solution is built
by shuffling a canonical grid (permuting digits, rows within bands, bands,
columns within stacks, stacks), then a chosen share of cells is kept as
givens.

---

## 4. Heuristics and strategies

| Heuristic | Where | Idea | Type |
|---|---|---|---|
| Small-clause preference | `dpll`, `choose_variable` | branch on variables of the shortest clauses; they are the most constrained and reveal conflicts early | heuristic |
| VSIDS-like activity | `cdcl`, `bump_var`, `decay_activity` | variables involved in recent conflicts get higher scores and are chosen first | main CDCL branching heuristic |
| Most frequent | `cdcl`, `pick_heap_var` with occurrence counts | the variable occurring most often in the formula | heuristic |
| MOMS | `cdcl`, `pick_moms_var` | Maximum Occurrences in clauses of Minimum Size | heuristic |
| DLIS | `cdcl`, `pick_dlis_decision` | Dynamic Largest Individual Sum: the literal satisfying the most unresolved clauses | heuristic |
| Random branching | `cdcl`, `pick_random_var` | a baseline for comparisons | stochastic heuristic |
| Initial phase | `cdcl`, `choose_phase` | positive first, negative first, polarity based, random | heuristic |
| Phase saving | `cdcl`, `saved_phase` | retry the last value a variable had | search-continuity heuristic |
| Restarts | `cdcl`, `luby` | return to level 0 after a Luby-sequence number of conflicts, keeping learned clauses | heuristic |
| Noise | `walksat` | with probability `noise` flip at random, otherwise greedily | exploration vs exploitation |
| Adaptive noise | `walksat` | raise the noise when the search stagnates, lower it on progress | adaptive heuristic |
| Greedy flip score | `walksat`, `_UnsatisfiedTracker.flip_effect` | estimate make/break of each candidate flip | local optimisation |
| ProbSAT weights | `walksat` with `probsat` | probabilistic choice by `(make+1)/(break+1)^2` | stochastic heuristic |
| Planted assignment | `random_3sat` | keep only clauses satisfied by a hidden assignment | constructive generation |
| Forced UNSAT core | `random_3sat`, `unsat_core` | all 8 sign patterns over 3 variables | exact logical construction |

The choice of phase can change performance dramatically without affecting
correctness.

---

## 5. Important data structures

| Structure | Where | Role |
|---|---|---|
| `list[list[int]]` | everywhere | a CNF formula |
| `dict[int, bool]` | solver results | a boolean assignment |
| `Clause` | `solvers/cdcl.py` | a clause with metadata (learned flag, watched literals, LBD, last use) |
| `watches` | `cdcl` | literal -> clauses watching it |
| `trail`, `trail_lim` | `cdcl` | chronological stack of assignments and level boundaries |
| `levels`, `reasons` | `cdcl` | decision level and reason clause of each variable |
| `activity` | `cdcl` | VSIDS-like scores |
| `_UnsatisfiedTracker` | `solvers/walksat.py` | incremental unsatisfied-clause bookkeeping |
| `Graph` | `problems/graph.py` | node count and edge list, with adjacency |
| `ParamField` | `sat_core/params.py` | declarative parameter: kind, range, sweeps, visibility |
| `ProblemInstance` | `sat_core/models.py` | CNF, metadata, decoder |
| `SolveResult` | `sat_core/models.py` | normalised solver result |
| `BenchmarkRow` | `sat_core/models.py` | one measurement of a benchmark |
| `RunToken` | `sat_core/runtime.py` | cooperative cancellation, skip and timeout |

---

## 6. Logical rules and checks

These are not always algorithms in the strict sense, but they are useful for
the theoretical part.

### 6.1 Input validation

- **Parameters** (`sat_core/params.py`): every value is checked against its
  declared kind and range; all errors are collected and reported per field.
- **Sudoku**: the size is one of 4, 9, 16, 25, the grid must match it and
  values must be in range. Conflicting givens are highlighted in the editor
  and recorded with the instance, which is then expected to be UNSAT.
- **Graphs** (`problems/graph.py`): no self-loops, nodes in range, duplicate
  edges merged.
- **Size guard** (`ProblemSpec.check_size`): instances whose estimated clause
  count exceeds the limit are refused before encoding.

### 6.2 Structural CNF rules

- tautology elimination (`solvers/cdcl.py`, `solvers/walksat.py`);
- duplicate literal elimination;
- empty clause detection: a direct criterion for `UNSAT`.

### 6.3 Standard constraint patterns

- **At least one**: one clause over the group. Used in Sudoku, graph
  coloring, N-Queens, Hamiltonian path, independent set, clique.
- **At most one**: binary clauses over all pairs.
- **Exactly one**: at least one plus at most one.

This is one of the most important concepts to explain in the report: it
appears in every reduction and unifies them.

### 6.4 Answer verification

- `sat_core/verify.check_assignment`: every clause is evaluated under the
  model (a polynomial check).
- `ProblemSpec.check`: the decoded answer is validated against the original
  instance (rows and boxes of a Sudoku, attacks between queens, colors of
  adjacent nodes, adjacency along a path, the size and edges of a clique or
  independent set).
- `ProblemSpec.expected_status`: generators that know the answer by
  construction (planted SAT, forced UNSAT, N-Queens with n = 2, 3) record it,
  and benchmarks flag answers that contradict it.

### 6.5 Cooperative cancellation, timeout and skip

`sat_core/runtime.py`: solvers poll a `RunToken` and stop cleanly with
`CANCELLED`, `TIMEOUT` or `SKIPPED`. Not SAT theory, but an important control
strategy of the application.

---

## 7. Connection with the theoretical part

### 7.1 P vs NP

The application shows the difference between

1. *searching* for a solution, and
2. *verifying* a solution.

For SAT, checking a given assignment is polynomial (it is exactly what
`check_assignment` does after every solve), while finding one is, in
general, the hard problem. This is the conceptual gap at the centre of the
P vs NP question.

### 7.2 SAT and 3-SAT

The application has general SAT solvers, an explicit 3-SAT generator, direct
DIMACS input, and reductions from other problems to SAT. This supports
explaining that SAT is NP-complete and that 3-SAT, a well-known restriction,
is NP-complete too. The phase-transition experiment adds the empirical side:
random 3-SAT is hardest near 4.26 clauses per variable.

### 7.3 Polynomial reductions

The modules in `problems/` are concrete polynomial reductions:

1. graph coloring -> SAT;
2. Hamiltonian path -> SAT;
3. independent set -> SAT;
4. clique -> SAT;
5. Sudoku -> SAT;
6. N-Queens -> SAT.

Each reduction produces a formula whose size is polynomial in the input
(the clause counts are given above), and each comes with a decoder that maps
models back to solutions. The application does not just "solve SAT"; it
demonstrates how combinatorial problems are transformed into SAT.

### 7.4 Combinatorial search

The project contains several paradigms:

1. systematic search with backtracking (DPLL);
2. conflict-driven learning (CDCL);
3. stochastic local search (WalkSAT, ProbSAT).

This allows comparing exact and incomplete algorithms, systematic and
stochastic methods, and logical deduction and heuristic exploration.

---

## 8. What to write in the report

### 8.1 Suggested structure for the theoretical part

1. **SAT and its role in complexity**: what a CNF formula is, what
   satisfiability is, why verification is easy once a solution is given, and
   why search is hard in general.
2. **Reductions to SAT**: Sudoku, graph coloring, Hamiltonian path,
   independent set, clique, N-Queens, with the emphasis on the boolean
   variables introduced and the clause patterns.
3. **Solving algorithms**: DPLL, CDCL, WalkSAT/ProbSAT: completeness, use of
   propagation, role of heuristics, practical impact.
4. **Heuristics**: variable choice, phase choice, restarts, clause learning,
   VSIDS, MOMS, DLIS, noise in WalkSAT.
5. **Experimental evaluation**: link the benchmarks to graph density,
   formula size, the clause/variable ratio of 3-SAT, and the influence of
   heuristics on performance.

### 8.2 Academic phrasings ready to adapt

> The application uses SAT as a universal modelling language for
> combinatorial problems. Each instance is transformed into a CNF formula,
> and the satisfiability of the formula is equivalent to the existence of a
> solution of the original problem.

> The DPLL solver represents classic systematic search by branching and
> backtracking, while the CDCL solver extends this model with learning from
> conflicts, non-chronological backjumping and modern selection heuristics.

> WalkSAT illustrates a different paradigm, based on local search and
> stochastic moves; it is efficient on many satisfiable instances but cannot
> prove unsatisfiability.

> The reductions implemented for graph coloring, Hamiltonian path,
> independent set and clique show in practice the idea of polynomial
> reduction that is central to the theory of NP-completeness.

---

## 9. Possible improvements

These are extensions, not existing behaviour. (Several suggestions of the
original document are now implemented: formal checks of decoded answers,
visual explanations of CDCL's implication graph in the Learn section, and
phase-transition experiments for random 3-SAT.)

1. An explicit `3-SAT -> Clique` or `3-SAT -> Independent Set` reduction, to
   connect the code with NP-completeness proofs.
2. Additional preprocessing: pure literal elimination, subsumption, clause
   strengthening.
3. Compact cardinality encodings (sequential counters) as an alternative to
   pairwise at-most-one.
4. Memory measurements in benchmarks, not just time.
5. DPLL heuristic options, for a fairer comparison with CDCL's heuristics.

---

## 10. Conclusion

The application is more than an interface to a SAT solver. It is a small
educational and experimental platform for

1. modelling combinatorial problems;
2. reducing them to SAT;
3. comparing several algorithmic paradigms;
4. observing in practice the difference between exact and heuristic
   solving.

The analysis of the code shows that its theoretical core consists of

1. exact reductions to SAT;
2. the exact algorithms DPLL and CDCL;
3. the incomplete heuristic algorithms WalkSAT and ProbSAT;
4. modern heuristics for branching, phase selection, learning and restarts;
5. specialised data structures for propagation and conflict analysis.

For a thesis on P vs NP the project fits well, because it directly connects
SAT theory and NP-completeness, the transformation of classic problems into
CNF, the difference between verification and search, and the real impact of
heuristics on theoretically hard problems.

---

## Appendix: quick map of the algorithms

| Category | Elements |
|---|---|
| Main algorithms | DPLL, CDCL, WalkSAT, ProbSAT |
| Auxiliary algorithms | unit propagation, `G(n,p)` / `G(n,m)` / `G(n,d)` graph generation, Sudoku generation, deterministic seeding |
| Reductions to SAT | Sudoku, graph coloring, N-Queens, Hamiltonian path, independent set, clique |
| Heuristics | small-clause, most frequent, VSIDS-like, MOMS, DLIS, random, saved phase, polarity based, random phase, restarts, greedy flip, noise, adaptive noise, ProbSAT weights |
| Optimisations | watched literals, clause learning, non-chronological backjumping, learned-clause deletion, incremental unsatisfied-clause tracking |
| Checks | parameter validation, tautology elimination, empty-clause detection, exactly-one constraints, model verification, answer checks, expected-status checks, size guard |
