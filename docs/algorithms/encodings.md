# Encodings: from problems to CNF

Every problem in WizSAT is solved the same way: it is **reduced** to a
boolean formula in conjunctive normal form (CNF), a SAT solver looks for a
satisfying assignment, and the assignment is **decoded** back into an answer
(a filled Sudoku, a coloring, a path). The formula is satisfiable exactly when
the original instance has a solution, and the reduction takes polynomial
time. These are concrete examples of the polynomial reductions behind
NP-completeness.

This page describes each encoding as implemented in `problems/`. Sizes are
the ones `estimate()` reports.

## CNF in a nutshell

A formula is a list of clauses; a clause is a list of literals; a literal is
a variable number, negative when negated. In Python and in DIMACS files:

```text
(x1 or not x2) and (x2 or x3) and (not x1)        [[1, -2], [2, 3], [-1]]

p cnf 3 3
1 -2 0
2 3 0
-1 0
```

A clause is satisfied when at least one of its literals is true; the formula
is satisfied when all clauses are. Checking an assignment takes one pass over
the clauses (`sat_core/verify.py`), but finding one is the hard part: that
gap between *verifying* and *searching* is the heart of P vs NP.

## Three reusable patterns

Almost every encoding below is built from the same constraints over a group
of variables `x1..xk`:

| Pattern | Clauses | Count |
|---|---|---|
| **at least one** | `x1 or x2 or ... or xk` | 1 |
| **at most one** (pairwise) | `not xi or not xj` for every pair i < j | k(k-1)/2 |
| **exactly one** | at least one + at most one | 1 + k(k-1)/2 |

The pairwise at-most-one is the simplest encoding and adds no helper
variables, at the cost of a quadratic number of binary clauses. Binary
clauses are cheap for unit propagation, so this is a good trade-off for the
sizes the app handles. (Larger solvers often use sequential-counter or
commander encodings with auxiliary variables instead.)

## Readable variable numbers

Variables are numbered so that a DIMACS file can be read by eye
(`problems/encoding.py`):

- `sudoku_var(r, c, v) = r*10000 + c*100 + v`: `10203` is "row 1, column 2
  holds 3";
- `readable_pair_var(a, b, max_b) = a*100 + b`, with more digits for b when
  `max_b >= 100`: `color_var(2, 3, 10) = 203` is "node 2 has color 3", and
  `readable_pair_var(2, 101, 101) = 2101`.

The numbers are sparse (a 9x9 Sudoku uses 729 variables with numbers up to
90909). The solvers do not care; the CNF header counts the largest number.

## Sudoku

`problems/sudoku.py`, n x n with n in {4, 9, 16, 25} and boxes of
sqrt(n) x sqrt(n).

- Variable `x(r, c, v)`: cell (r, c) holds value v.
- Each cell holds **exactly one** value.
- Each value appears **at most once** in every row, every column and every
  box. (Together with "every cell has a value" this forces each value to
  appear exactly once per unit.)
- Each given is a **unit clause** `x(r, c, v)`.

Size: n^3 variables; n^2 + 4 n^2 C(n,2) + givens clauses. For 9x9 that is 729
variables and 11,745 clauses plus the givens.

Decoding reads, for every cell, the value whose variable is true. The check
verifies the rows, columns, boxes and that the givens were kept.

Generated puzzles start from a random valid grid (a shuffled canonical
solution) and keep a chosen percentage of cells; they are always
satisfiable, though not necessarily with a unique solution.

## N-Queens

`problems/n_queens.py`, an n x n board.

- Variable `x(r, c)`: a queen stands on (r, c).
- Each row has **at least one** queen and **at most one** queen.
- Each column has **at most one** queen (n queens in n rows then fill every
  column exactly once).
- For every pair of cells on a common diagonal: `not x(r1,c1) or not
  x(r2,c2)`.

Size: n^2 variables; n + 2 n C(n,2) + (pairs of cells sharing a diagonal)
clauses, about 5n^3/3 for large n. The expected answer is UNSAT for n = 2 and
n = 3 and SAT otherwise, which benchmarks use as a correctness check.

## Graph coloring

`problems/graph_coloring.py`: can the nodes be colored with k colors so that
neighbours differ?

- Variable `x(v, c)`: node v has color c (`color_var(v, c, k)`).
- Each node has **exactly one** color.
- For every edge (u, v) and every color c: `not x(u,c) or not x(v,c)`.

Size: n k variables; n + n C(k,2) + |E| k clauses. The "at most one color"
clauses are not needed for correctness (a node with two colors could drop
one), but they make the decoded answer unambiguous.

Example: for edge (1, 2) and color 3 the clause is `-103 -203 0`.

## Hamiltonian path

`problems/hamiltonian_path.py`: is there a path that visits every node
exactly once?

- Variable `x(i, v)`: position i of the path holds node v.
- Each position holds **exactly one** node.
- Each node appears at **exactly one** position.
- For every position i < n and every ordered pair (u, v) of distinct,
  **non-adjacent** nodes: `not x(i,u) or not x(i+1,v)`.

Size: n^2 variables; 2 (n + n C(n,2)) + (n-1)(n(n-1) - 2|E|) clauses. Sparse
graphs have many non-edges, so this grows like n^4 in the worst case; the
size guard refuses instances that would be too large.

## Independent set

`problems/independent_set.py`: are there k nodes with no edge between any
two of them?

- Variable `x(s, v)`: slot s (1..k) of the set holds node v.
- Each slot holds **exactly one** node; each node fills **at most one** slot.
  The slots turn "at least k nodes" into "exactly k distinct nodes", which is
  equivalent for this decision problem.
- For every edge (u, v) and every pair of slots (s, t): `not x(s,u) or not
  x(t,v)`.

Size: n k variables; k + k C(n,2) + n C(k,2) + |E| k^2 clauses.

## Clique

`problems/clique.py`: are there k nodes that are all pairwise adjacent?

Same slots as Independent Set, with the edge rule reversed: for every pair of
**non-adjacent** nodes (u, v) and every pair of distinct slots (s, t):
`not x(s,u) or not x(t,v)`.

Size: n k variables; k + k C(n,2) + n C(k,2) + |non-edges| k(k-1) clauses.

Clique in G and independent set in the complement of G are the same
question, which the graph suite preset makes visible: dense graphs have
k-cliques and no independent k-sets, sparse ones the reverse.

## Random 3-SAT

`problems/random_3sat.py`: n variables, m = round(n x ratio) clauses, each
over three distinct variables with random signs.

| Mode | How it is built | Answer |
|---|---|---|
| Random | clauses drawn uniformly | unknown in advance |
| Planted SAT | draw a hidden assignment, keep only clauses it satisfies | SAT |
| Forced UNSAT | add the 8 sign patterns over 3 random variables, then random clauses | UNSAT |
| Mixed | planted with probability "SAT share", forced UNSAT otherwise | known per formula |

The eight clauses `(+-a or +-b or +-c)` forbid every assignment of a, b, c,
so a forced formula is unsatisfiable whatever the other clauses are.

For plain random formulas the **ratio** decides the difficulty. Below about
4.26 clauses per variable almost all formulas are satisfiable and easy;
above it almost all are unsatisfiable and, far enough above, easy to refute;
near 4.26 the probability of satisfiability drops sharply and solvers work
hardest. The *phase transition* preset shows both effects.

Generation is deterministic for a given (n, m, mode, SAT share, seed).

## DIMACS input

`problems/dimacs_input.py` takes any CNF in DIMACS format and solves it as
is; the answer is the assignment. The parser (`sat_core/dimacs.py`) accepts
comments anywhere, clauses spread over several lines, a missing header, and
a header whose counts are wrong (with a warning), and reports errors with line
numbers.

Files written by WizSAT start with

```text
c wizsat {"problem": "graph_coloring", "params": {...}}
```

so the app can reopen them as the problem they came from. Other SAT tools
ignore comment lines.

## Graphs for the graph problems

The four graph problems share their inputs (`problems/graph.py`):

| Mode | Graph | Parameters |
|---|---|---|
| `G(n,p)` | each of the C(n,2) possible edges independently with probability p (Erdos-Renyi) | n, p |
| `G(n,m)` | exactly m edges chosen uniformly (capped at C(n,2), the complete graph) | n, m |
| `G(n,d)` | `G(n,m)` with m = round(n d / 2), since the degrees of a graph sum to 2m | n, average degree d |
| Manual | the edges you type, such as `1-2, 2-3` | n, edges |

Random graphs depend only on the graph fields and the seed, so in a graph
suite every problem sees the same graph.

## Verification

After a solver answers SAT, two independent checks run:

1. `sat_core/verify.check_assignment` evaluates every clause under the model;
2. the problem's `check()` validates the decoded answer against the original
   instance (for example "no two queens attack", "adjacent nodes have
   different colors").

The first catches solver bugs, the second catches encoding bugs. A result is
shown as **Verified** only when both pass.
