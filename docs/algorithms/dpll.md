# DPLL

DPLL (Davis-Putnam-Logemann-Loveland, 1962) is the classic complete SAT
algorithm: it can prove both SAT and UNSAT. Modern CDCL solvers are DPLL plus
learning, so DPLL is the natural baseline to compare them with.

Related notes: [CDCL](cdcl.md), [WalkSAT](walksat.md),
[encodings](encodings.md).

## The idea

1. **Unit propagation.** If a clause has no true literal and only one literal
   left that is not false, that literal must be true. Repeat until nothing is
   forced.
2. If a clause has every literal false, that is a **conflict**: the current
   choices cannot lead to a model.
3. If every clause is satisfied, the formula is **SAT**.
4. Otherwise make a **decision**: pick a variable, try `True`.
5. On a conflict, **backtrack**: undo everything since the most recent
   decision whose other value has not been tried, and try that value. If both
   values of every decision failed, the formula is **UNSAT**.

Step 5 is *chronological* backtracking: DPLL always goes back to the most
recent open decision, even if that decision had nothing to do with the
conflict. That, and the fact that it forgets every conflict, is what
[CDCL](cdcl.md) improves.

## A worked example

```text
F = (x1 or x2) and (not x1 or x3) and (not x1 or not x3)
    and (not x2 or x4) and (not x2 or not x4 or x5) and (not x5 or not x4)
```

| Step | What happens |
|---|---|
| 1 | No clause is unit. The shortest clauses have 2 literals; the first is `(x1 or x2)`, so **decide x1 = True** (decision 1). |
| 2 | `(not x1 or x3)` is now unit: **x3 = True** is forced. `(not x1 or not x3)` now has both literals false: **conflict**. |
| 3 | Backtrack: undo x3 and x1, **try x1 = False**. |
| 4 | `(x1 or x2)` forces **x2 = True**, then `(not x2 or x4)` forces **x4 = True**, then `(not x2 or not x4 or x5)` forces **x5 = True**. `(not x5 or not x4)` is all false: **conflict**. |
| 5 | Both values of x1 failed and there is no earlier decision: **UNSAT**. |

Statistics: 1 decision, 2 conflicts, 4 propagations, depth 1. You can watch
this in the app: solve the formula as DIMACS with DPLL and set *Log detail*
to *Debug*.

## How this implementation works

`solvers/dpll.py` is iterative. Its behaviour is the same as the original
recursive version (archived in `legacy/dpll_recursive.py`): on clean formulas,
which is everything the app's encoders produce, both make exactly the same
decisions and reach the same conflicts. The inside is different.

### Clause counters instead of copying the formula

The recursive version built a new, simplified formula for every branch:
satisfied clauses removed, false literals deleted. That is easy to read but
copies the whole formula at every node of the search tree.

The iterative version never changes the formula. For every clause it keeps
two numbers:

```text
true_count[c]   how many literals of clause c are true
false_count[c]  how many literals of clause c are false
```

and, for every literal, the list of clauses that contain it (`occurs`).

Assigning a literal `x` updates only the clauses that mention it:

- every clause containing `x` gets `true_count += 1` (it is satisfied now);
- every clause containing `not x` gets `false_count += 1`. If such a clause
  has `true_count == 0` and then
  - `length - false_count == 1`: it is **unit**, so its one free literal is
    assigned;
  - `length - false_count == 0`: it is a **conflict**.

Undoing an assignment subtracts the same numbers again, so backtracking costs
only as much as the assignments it undoes.

### The trail and the decision stack

- **trail**: every assigned literal, in order. `qhead` marks how far the
  counters have been updated; literals after it are waiting to be propagated.
- **decision stack**: one entry per open decision: the variable, the value
  being tried, where on the trail the decision started, and whether this is
  already the second value.

On a conflict the solver pops decisions until it finds one whose second
value has not been tried, undoes the trail back to that decision, and assigns
the other value. If the stack runs empty, the formula is UNSAT. Because the
stack is a plain list, the search can be as deep as there are variables;
the recursive version stopped with Python's recursion limit at about 1,000
nested decisions.

### Choosing the decision variable

The *small-clause rule*: among the clauses that are not yet satisfied, take
the one with the fewest free literals, and branch on its first free
variable. Short clauses are the closest to becoming unit or conflicting, so
deciding there exposes contradictions early. The scan stops as soon as it
finds a clause with 2 free literals, since nothing shorter can remain after
propagation.

The value tried first is always `True`, then `False`. DPLL has no options in
the app.

### Cancel and timeouts

Every 2048 counter updates the solver asks the cancel token whether to stop
(Stop button, Skip in a benchmark, or the time limit). That keeps the cost of
checking negligible while still reacting within a fraction of a second.

## Statistics

| Name | Meaning |
|---|---|
| decisions | variables chosen by the small-clause rule (each counts once, even when both values are tried) |
| conflicts | branches that ended with an all-false clause |
| propagations | literals forced by unit clauses |
| max_depth | the largest number of open decisions at once |

## Cost

Unit propagation with counters costs, per assigned literal, the number of
clauses that literal appears in. The small-clause rule scans the clauses at
every decision. The search tree itself can have up to 2^n leaves, and DPLL
never learns: the same conflict can be rediscovered in many different
branches. On hard random 3-SAT formulas that is what makes it slow compared
with CDCL, and why benchmarks cap it at 10 s from 200 variables by default.

| Instance | Recursive (old) | Iterative (now) |
|---|---|---|
| Random 3-SAT, n=100, ratio 4.26 | 1.19 s | 0.11 s |
| 25-Queens | 4.99 s | 2.13 s |
| 1,500 independent 2-clauses | recursion-limit error | 0.03 s |

Both versions made the same decisions in each case. Measured on the same
machine; see [Solver performance](../guide/performance.md).

## Python usage

```python
from solvers.dpll import dpll

clauses = [[1, 2], [-1, 2], [1, -2]]
solution, stats = dpll(clauses, return_stats=True)

print(stats["status"], solution)   # SAT {1: True, 2: True}
```

The archived recursive version can be run for comparison from the
repository root:

```python
from legacy.dpll_recursive import dpll as recursive_dpll
```
