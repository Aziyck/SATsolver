# WalkSAT Local Search

WalkSAT is a local-search SAT solver. It works very differently from DPLL and
CDCL because it does not build a proof tree and does not prove UNSAT.

In this app, WalkSAT is useful as a contrast solver:

- `CDCL`: complete, learns from conflicts, can prove SAT or UNSAT.
- `DPLL`: complete, simpler recursive baseline, can prove SAT or UNSAT.
- `WalkSAT`: incomplete, often fast on SAT instances, returns `UNKNOWN` when it
  does not find a model.

## Status Meaning

When WalkSAT returns `SAT`, the assignment satisfies every clause.

When WalkSAT returns `UNKNOWN`, it means the search budget ended before a
solution was found. The formula might still be SAT. WalkSAT does not report
`UNSAT` because failing to find a solution is not a proof that none exists.
The detailed stats include `termination_reason`; normal budget exhaustion is
reported there as `budget_exhausted`, while timeouts and cancellations still use
the public statuses `TIMEOUT` and `CANCELLED`.

## Search Loop

WalkSAT starts with a random assignment for every variable. Then it repeats:

1. Find all currently unsatisfied clauses.
2. If there are none, the formula is SAT.
3. Pick one unsatisfied clause.
4. Flip one variable from that clause.
5. Continue until solved or the flip limit is reached.

The app implementation uses multiple random tries. Each try starts from a new
random assignment.

## Incremental Tracking

The solver keeps occurrence lists:

```text
variable -> clauses containing that variable
```

It also keeps a satisfaction count for every clause. A clause with count `0` is
currently unsatisfied.

When WalkSAT flips one variable, only clauses containing that variable can
change. The solver updates just those clauses, instead of rescanning the whole
formula after every flip. This is important for larger encodings because a
single flip usually touches a small part of the CNF.

The greedy repair score uses the same occurrence lists. For a candidate
variable, the solver estimates how many clauses would be unsatisfied after the
flip by checking only clauses where that variable appears.

The same calculation also records make/break information:

- `make`: unsatisfied clauses that would become satisfied after the flip.
- `break`: satisfied clauses that would become unsatisfied after the flip.
- `unsatisfied_after`: total unsatisfied clauses predicted after the flip.

These values are exposed in aggregate stats as `flip_make_total`,
`flip_break_total`, `last_make`, and `last_break`.

## Best Assignment

WalkSAT now keeps `best_assignment` in its stats. This is the assignment that
achieved the lowest `best_unsatisfied` count during the run. It can differ from
the final assignment when the search later moves away from the best partial
state before the budget ends.

## Noise

When choosing a variable to flip, WalkSAT mixes two behaviors:

- Random walk: choose a random variable from the unsatisfied clause.
- Greedy repair: choose a variable whose flip leaves the fewest unsatisfied
  clauses.

The `noise` value controls how often the random choice is used. Randomness helps
the solver escape unlucky local minima where every obvious greedy move looks
bad.

## Strategy Modes

The default `Classic WalkSAT` strategy keeps the original random-vs-greedy
choice.

The `ProbSAT` strategy uses the same random-noise override, but its repair step
chooses probabilistically from the variables in the unsatisfied clause. Variables
with higher make and lower break receive more weight:

```text
weight = (make + 1) / ((break + 1) ^ 2)
```

This keeps the search stochastic while favoring flips that repair clauses
without damaging many already-satisfied clauses.

## Adaptive Noise

Adaptive noise is optional and off by default. When enabled, WalkSAT starts from
the configured `noise`. If it stagnates without improving `best_unsatisfied`, it
raises noise gradually up to `0.9`. When it finds a new best assignment, it
reduces noise back toward the original configured value. The final value is
reported as `final_noise`.

## Logging

With periodic or verbose solver logs enabled, WalkSAT prints its strategy,
current noise, adaptive-noise state, and last make/break values in progress
messages. Verbose debug mode also prints ProbSAT flip weights and adaptive noise
adjustments when they occur.

## App Controls

The app exposes WalkSAT controls in a compact `WalkSAT Options` group:

- `Max tries`: number of random restarts. Default: `10`.
- `Max flips`: maximum flips per try. Default: `10000`.
- `Noise`: probability of making a random flip instead of a greedy repair
  flip. Default: `0.5`.
- `Strategy`: `Classic WalkSAT` or `ProbSAT`.
- `Adaptive noise`: optional stagnation response that adjusts noise during the
  run.
- `Random seed`: optional seed for reproducible WalkSAT runs.

The solve timeout still applies. A timeout returns `TIMEOUT`, while a normal
budget exhaustion returns `UNKNOWN`.

## Python Usage

```python
from solvers.walksat import walksat

clauses = [[1, 2], [-1, 2], [1, -2]]
solution, stats = walksat(
    clauses,
    return_stats=True,
    logging_options={"random_seed": 7},
)

print(stats["status"])
print(stats["termination_reason"])
print(stats["best_unsatisfied"])
print(solution)
```

## When To Use It

WalkSAT is a good demonstration solver for random or large SAT-looking
instances where a satisfying assignment probably exists. The app's `Random
3-SAT` problem is especially useful for this: choose `Planted SAT` to generate
random-looking 3-literal clauses that are guaranteed to be SAT, then vary the
clause-to-variable ratio in benchmarks. Choose `Forced UNSAT` when you want to
see CDCL/DPLL prove UNSAT; WalkSAT will return `UNKNOWN` unless it times out,
because local search cannot prove unsatisfiability.
