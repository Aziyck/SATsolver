# DPLL Solver

DPLL is the classic complete SAT search algorithm behind many modern SAT
solver ideas. It is simpler than CDCL, but it can still prove both SAT and
UNSAT.

## Core Idea

DPLL repeatedly simplifies the formula and branches on an unassigned variable:

1. Apply unit propagation.
2. If every clause is satisfied, return `SAT`.
3. If a clause becomes empty, backtrack.
4. Choose a variable.
5. Try one truth value, then the other if needed.

Because it systematically explores the search space, DPLL is complete. If the
formula is satisfiable, it can find a model. If the formula is unsatisfiable, it
can eventually prove that every branch fails.

## Unit Propagation

A unit clause has only one remaining literal:

```text
[3]
```

The solver must set variable `3` to true, because that is the only way to
satisfy the clause. Unit propagation repeats this forced assignment process
until no more unit clauses remain or a conflict appears.

## Backtracking

When DPLL guesses a value and later reaches a conflict, it returns to the most
recent guess and tries the opposite value. This is chronological backtracking:
it undoes one decision level at a time.

CDCL improves on this by learning a clause from the conflict and backjumping
over irrelevant decisions. DPLL keeps the simpler behavior, which makes it a
good baseline for teaching and benchmarking.

## This App's DPLL

The app uses DPLL as a fixed baseline solver:

- complete
- recursive
- uses unit propagation
- uses a small-clause variable heuristic
- ignores CDCL-specific options such as restarts and learned-clause limits

This makes DPLL easy to compare with CDCL and WalkSAT.

## Python Usage

```python
from solvers.dpll import dpll

clauses = [[1, 2], [-1, 2], [1, -2]]
solution = dpll(clauses)

print("SAT" if solution is not None else "UNSAT")
print(solution)
```
