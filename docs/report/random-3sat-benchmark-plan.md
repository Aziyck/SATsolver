# Random 3-SAT benchmark plan

> English, updated version of `legacy/docs_ro/random_3sat_benchmark_plan.md`.
> Presets A, B and C below are available in the app under **Benchmarks ->
> Start from a preset**; the exact definitions are in `sat_core/presets.py`.

This document describes the recommended method for evaluating the solvers on
random 3-SAT instances. The aim is not a single absolute time but a comparison
of how the solvers behave on controlled families of formulas, using the same
instances for every solver.

## Goals

The benchmark answers three practical questions:

- how the running time changes as the number of variables grows;
- how the clause/variable ratio affects the difficulty of the formulas;
- how the complete solvers (CDCL, DPLL) compare with local search (WalkSAT,
  ProbSAT).

Results are exported only after the experiments have actually run. Tables in
the report contain measured values, not estimates.

## Preset A: Planted SAT

Formulas that are satisfiable by construction.

| n | clause/variable ratio | seeds | solvers |
|---|---|---|---|
| 50 | 2.5, 3.5, 4.25, 5.5 | 1..20 | CDCL, DPLL, WalkSAT, ProbSAT |
| 100 | 2.5, 3.5, 4.25, 5.5 | 1..20 | CDCL, DPLL, WalkSAT, ProbSAT |
| 150 | 2.5, 3.5, 4.25, 5.5 | 1..20 | CDCL, DPLL, WalkSAT, ProbSAT |
| 200 | 2.5, 3.5, 4.25, 5.5 | 1..20 | CDCL, WalkSAT, ProbSAT; DPLL is SKIPPED |
| 300 | 3.5, 4.25, 5.5 | 1..10 | CDCL, WalkSAT, ProbSAT; DPLL is SKIPPED |

350 cases, 1,400 runs. This preset suits all solvers because every instance
has at least one satisfying assignment. WalkSAT and ProbSAT can confirm SAT by
finding an assignment even though they cannot prove UNSAT.

## Preset B: Forced UNSAT

A control test for the complete solvers.

| n | clause/variable ratio | seeds | solvers |
|---|---|---|---|
| 50 | 3.5, 4.25, 5.5 | 1..10 | CDCL, DPLL |
| 100 | 3.5, 4.25, 5.5 | 1..10 | CDCL, DPLL |
| 150 | 4.25, 5.5 | 1..10 | CDCL; DPLL capped at 10 s |
| 200 | 4.25, 5.5 | 1..10 | CDCL; DPLL is SKIPPED |

100 cases, 200 runs. WalkSAT and ProbSAT are not included because they are
incomplete: when they find no solution the correct result is `UNKNOWN`, not
`UNSAT`. Forced UNSAT instances are therefore mainly useful to check that CDCL
and DPLL reach a negative conclusion.

## Preset C: Mixed SAT/UNSAT

Ratio 4.25, with a varying share of satisfiable instances.

| Parameter | Values |
|---|---|
| variables | 100, 150, 200 |
| clause/variable ratio | 4.25 |
| SAT share | 30%, 50%, 70% |
| seeds | 1..30 |
| solvers | CDCL, DPLL, WalkSAT, ProbSAT |

270 cases, 1,080 runs. WalkSAT and ProbSAT are capped at 1 s (on UNSAT
formulas they would otherwise spend their whole budget), and DPLL at 10 s
from 200 variables. This preset suits a practical discussion of the hard
region of 3-SAT. WalkSAT and ProbSAT results must be read separately: `SAT`
means an assignment was found, `UNKNOWN` only means none was found within the
limits.

## Choosing the ratios

The clause/variable ratio controls the density of the formula. For random
3-SAT, small values such as 2.5 usually give loose formulas with many
satisfying assignments. Larger values such as 5.5 give tightly constrained
formulas that are more often unsatisfiable.

The ratio 4.25 matters because it is close to the known SAT/UNSAT transition
of random 3-SAT (about 4.26). In this region the probability that a formula
is satisfiable drops sharply and instances are often hardest for complete
solvers. That is why 4.25 appears in all three presets. The *Random 3-SAT
phase transition* preset (ratios 3 to 6 in steps of 0.25) shows the whole
curve.

## Comparison rules

For a fair comparison each parameter combination is generated once for a
given seed, and that same CNF is run with every selected solver. The
application does this automatically and stores, for each row, the case
parameters, the CNF size and the seed, so any row can be rebuilt (**Open in
Solve** or **Download CNF** in the row details).

The time limit is constant within an experiment, except for the explicit
limit rules of the presets:

- Preset A: DPLL is skipped for `n >= 200`;
- Preset B: DPLL is capped at 10 s for `n >= 150` and skipped for `n >= 200`;
- Preset C: WalkSAT and ProbSAT are capped at 1 s; DPLL at 10 s for
  `n >= 200`.

Skipped runs are exported with the status `SKIPPED` and the rule in the
`rule` column. All rules can be changed in the builder before starting.

## Why WalkSAT and ProbSAT are evaluated mainly on SAT instances

WalkSAT and ProbSAT are local-search methods. They look for an assignment
that satisfies all clauses but never build a proof of unsatisfiability.
Therefore:

- on SAT instances they can be compared by time, number of flips, number of
  tries and the quality of the best assignment found;
- on UNSAT instances an `UNKNOWN` result is not an error but a limit of the
  method;
- UNSAT correctness requires complete solvers such as CDCL and DPLL.

## Recommended metrics

The CSV export has one column per parameter (`variables`, `ratio`, `mode`,
`sat_percent`, `seed`) and the columns

```text
run, case, problem, case_label, repeat, solver, solver_label, status,
expected, verified, elapsed, cnf_variables, cnf_clauses, size_variables,
timeout, rule, decisions, conflicts, propagations, learned_clauses,
restarts, tries, flips, best_unsatisfied, error
```

Recommended analyses:

- mean and median time per combination of `variables`, `ratio`, `solver`
  (the results page charts the median by default);
- the share of `SAT`, `UNSAT`, `UNKNOWN` and `TIMEOUT` (the *Answers by*
  chart);
- decisions, conflicts, propagations and learned clauses for CDCL/DPLL;
- flips, tries and `best_unsatisfied` for WalkSAT/ProbSAT;
- a separate comparison at ratio 4.25;
- a separate discussion of UNSAT instances, where WalkSAT/ProbSAT cannot
  prove unsatisfiability;
- `expected` vs `status`: every planted formula must be SAT and every forced
  formula UNSAT when a complete solver answers.

## Interpreting UNKNOWN

`UNKNOWN` depends on the solver:

- for WalkSAT and ProbSAT it means no satisfying assignment was found within
  the tries, flips or time limit;
- a complete solver reports `TIMEOUT` when the time limit stops it, and
  `CANCELLED` or `SKIPPED` when the user or a rule stopped it; none of these
  is a conclusion about satisfiability.

`UNKNOWN` must never be counted as `UNSAT` in the final tables.

## Tables for the report

Fill in after running:

| Preset | Solver | n | ratio | Seeds | Dominant status | Median time | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | TODO | TODO | TODO |

| Solver | Runs | SAT | UNSAT | UNKNOWN | TIMEOUT | SKIPPED | Mean time | Median time |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CDCL | TODO | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| DPLL | TODO | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| WalkSAT | TODO | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| ProbSAT | TODO | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
