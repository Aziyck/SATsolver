# Benchmarking

This guide explains how WizSAT benchmarks work, what each preset measures,
how to read the results and the CSV, and how to keep comparisons fair. For
the buttons and screens, see the [user guide](user-guide.md#benchmarks).

## Vocabulary

| Term | Meaning |
|---|---|
| **case** | one parameter combination, such as `n=100 r=4.25 Planted SAT seed=7` |
| **grid** (segment) | a set of parameter values; its cases are all combinations of them |
| **run** | one solver on one case (one row in the results and the CSV) |
| **repeat** | running every case again; repeat 1 uses the case's own seed, later repeats derive new seeds |
| **limit rule** | "cap solver X at S seconds" or "skip solver X" once a formula reaches N variables |

The number of runs is `cases x repeats x solvers`. The plan panel shows it
before you start; a single benchmark is limited to 200,000 runs.

## Writing parameter values

Every field marked as sweepable accepts several values:

| You type | Values |
|---|---|
| `50` | 50 |
| `50, 100, 150` or `50; 100; 150` or `50 100 150` | 50, 100, 150 |
| `1..10` | 1, 2, ..., 10 |
| `3..6:0.25` | 3, 3.25, 3.5, ..., 6 |
| `1..5, 10, 20` | 1, 2, 3, 4, 5, 10, 20 |

The Random 3-SAT formula mode is a multi-select. Fields that depend on a
choice only apply to the cases where that choice is active: with the modes
*Planted SAT* and *Mixed* selected, the SAT share is swept for the mixed cases
only. The graph generator and the Sudoku source are one per grid.

Several grids in one benchmark are combined as a union. Use them to mix graph
generators, or to run many seeds on small formulas and fewer on large ones, as
the presets do.

## Fair comparisons by construction

- **Same formula for every solver.** Each case is encoded once and every
  solver runs on that exact CNF.
- **Same graphs across problems.** Selecting several graph problems (a graph
  suite) builds each graph once from the graph fields and encodes every
  problem on it. Clique and Independent Set, for example, are compared on
  identical graphs.
- **Reproducible cases.** Every generated case has a seed. A grid whose seed
  is left blank uses the benchmark seed. Repeat 1 uses the case's seed as is,
  so **Open in Solve** on any row rebuilds exactly the instance that was
  measured; later repeats derive their seeds from it, so rerunning the
  benchmark gives the same cases again.
- **Checked answers.** Every SAT model is checked against the clauses, the
  decoded answer is checked by the problem's own rules, and generators that
  know the answer (planted SAT, forced UNSAT, N-Queens) record the expected
  status. Mismatches are flagged as suspicious.

## Limit rules

A rule has a solver (or *any solver*), an action, a variable threshold and,
for caps, seconds:

```text
cap  DPLL    at 10 s  when variables >= 200
skip DPLL             when variables >= 200
cap  WalkSAT at 1 s   when variables >= 0
```

- The variable count is the instance's *size*: n for Random 3-SAT, the header
  count for DIMACS files, otherwise the number of distinct CNF variables.
- `skip` wins over `cap`; when several caps match, the smallest one applies.
  A cap never raises the benchmark's own time limit.
- Skipped runs appear as `SKIPPED` rows with the rule in the `rule` column, so
  the table stays rectangular.

**The DPLL fallback.** New benchmarks and all presets start with *cap DPLL at
10 s when variables >= 200*. DPLL has no clause learning and can take
minutes or hours on formulas that CDCL solves in milliseconds; the cap keeps
it in the comparison without stalling the run. Edit or remove it in **Limit
rules**. To change the default for everyone, edit
`DPLL_FALLBACK_RULE` in `sat_core/benchmark.py`.

## Presets

Presets are plain benchmark requests (see `sat_core/presets.py`). Opening one
fills the builder, so you can change anything before starting. All presets
use a 30 s time limit per run and benchmark seed 1.

### Random 3-SAT A: Planted SAT (350 cases, 1,400 runs)

Formulas satisfiable by construction, so every correct answer is SAT.

| n | ratio m/n | seeds | solvers |
|---|---|---|---|
| 50, 100, 150, 200 | 2.5, 3.5, 4.25, 5.5 | 1..20 | CDCL, DPLL, WalkSAT, ProbSAT |
| 300 | 3.5, 4.25, 5.5 | 1..10 | CDCL, DPLL, WalkSAT, ProbSAT |

DPLL is skipped from n = 200 (rows marked SKIPPED). This preset suits all four
solvers because every instance has a solution that local search can find.

### Random 3-SAT B: Forced UNSAT (100 cases, 200 runs)

Formulas with a small unsatisfiable core (all 8 sign patterns over three
variables), so every correct answer is UNSAT.

| n | ratio | seeds | solvers |
|---|---|---|---|
| 50, 100 | 3.5, 4.25, 5.5 | 1..10 | CDCL, DPLL |
| 150, 200 | 4.25, 5.5 | 1..10 | CDCL, DPLL |

DPLL is capped at 10 s from n = 150 and skipped from n = 200. WalkSAT and
ProbSAT are left out: they can never prove UNSAT, so on these formulas they
could only answer UNKNOWN.

### Random 3-SAT C: Mixed SAT/UNSAT (270 cases, 1,080 runs)

Ratio 4.25, near the satisfiability threshold. Each formula is planted SAT
with probability 30%, 50% or 70% and forced UNSAT otherwise.

| n | ratio | SAT share | seeds | solvers |
|---|---|---|---|---|
| 100, 150, 200 | 4.25 | 30, 50, 70 % | 1..30 | CDCL, DPLL, WalkSAT, ProbSAT |

WalkSAT and ProbSAT are capped at 1 s: on the UNSAT formulas they would
otherwise use their whole budget before answering UNKNOWN. DPLL is capped at
10 s from n = 200.

### Random 3-SAT phase transition (260 cases)

Plain random formulas (the answer is not known in advance), n = 30 and 50,
ratio 3 to 6 in steps of 0.25, seeds 1..10, solved by CDCL. Plot **Answers by
ratio** to see the SAT share fall from almost 100% to almost 0% around 4.26,
and the median time (or conflicts) to see the easy-hard-easy peak at the same
place.

### CDCL branching heuristics (10 cases, 40 runs)

Ten random formulas with n = 60 at ratio 4.26, each solved by CDCL with VSIDS,
MOMS, DLIS and random branching, labelled `CDCL VSIDS`, `CDCL MOMS`, ... so
charts show one line per heuristic. (Entries without a label are named after
their options, such as `CDCL (branching=DLIS)`.)

### Graph suite: Clique vs Independent Set (120 cases)

Both problems on the same `G(n,p)` graphs: n = 10, 20, 30, p = 0.3 and 0.5,
k = 3 and 4, seeds 1..5, solved by CDCL. Dense graphs tend to contain
k-cliques and no independent k-sets, sparse graphs the reverse.

### 3-coloring threshold (90 cases)

Graph 3-coloring on `G(n,d)` graphs with n = 20 and 40 and average degree
2 to 6 in steps of 0.5, seeds 1..5. Random graphs stop being 3-colorable
around d = 4.7; the SAT share chart shows the drop.

### Sudoku sizes (18 cases, 36 runs)

Generated puzzles of size 4, 9 and 16 with 30% and 50% givens, seeds 1..3,
CDCL against DPLL.

## Reading results

- **Status first, time second.** A fast `UNKNOWN` is not a fast answer.
  Compare times only between runs that answered, and report the status counts
  next to the times (the status share chart and the tiles do this).
- **UNKNOWN is not UNSAT.** WalkSAT and ProbSAT answer `UNKNOWN` when they
  run out of tries and flips. That says nothing about satisfiability. Only
  CDCL and DPLL can prove `UNSAT`. Keep the two apart in tables.
- **TIMEOUT and capped runs** are censored measurements: the true time is at
  least the cap. Medians are more robust than means when some runs time out.
- **Use facets, not a second axis.** To compare two parameters (for example
  n and ratio), put one on the x axis and split into panels by the other.
- **Watch the suspicious filter.** A verified-false or unexpected answer
  means a bug in an encoder or solver, not a slow run.

Measures available in the charts:

| Measure | Solvers | Meaning |
|---|---|---|
| Time | all | wall-clock solver time, excluding encoding |
| Decisions | CDCL, DPLL | branching decisions |
| Conflicts | CDCL, DPLL | dead ends reached |
| Propagations | CDCL, DPLL | literals forced by unit propagation |
| Learned clauses | CDCL | clauses learned from conflicts |
| Flips | WalkSAT, ProbSAT | variable flips over all tries |

## CSV columns

Every benchmark exports the same format, whatever the problem:

| Column | Meaning |
|---|---|
| `run` | the job label (J12); useful when several benchmarks are exported together |
| `case` | case number, starting at 1 |
| `problem` | problem key (`random_3sat`, `graph_coloring`, ...) |
| `case_label` | readable case description |
| *one column per parameter* | the case's parameter values (`variables`, `ratio`, `mode`, `seed`, `nodes`, ...). A parameter whose name collides with a base column gets a `param_` prefix |
| `repeat` | repeat number |
| `solver`, `solver_label` | solver key and its label in this benchmark (`CDCL (VSIDS)`) |
| `status` | SAT, UNSAT, UNKNOWN, TIMEOUT, CANCELLED, SKIPPED or ERROR |
| `expected` | SAT/UNSAT when known by construction, else empty |
| `verified` | whether a SAT answer passed the checks |
| `elapsed` | solver time in seconds |
| `cnf_variables`, `cnf_clauses` | size of the CNF |
| `size_variables` | the size used by limit rules |
| `timeout` | the time limit that applied to this run |
| `rule` | the limit rule that applied, if any |
| `decisions`, `conflicts`, `propagations`, `learned_clauses`, `restarts` | CDCL/DPLL statistics |
| `tries`, `flips`, `best_unsatisfied` | WalkSAT/ProbSAT statistics |
| `error` | the error message for ERROR rows |

Download a single benchmark with **CSV** on its results page, or several at
once by comparing them first; the API also offers
`GET /api/export.csv?jobs=3,4,5`.

## Running a benchmark from a script

The web UI sends a JSON request that you can also post yourself (the server
must be running):

```bash
curl -X POST http://127.0.0.1:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "kind": "benchmark",
    "title": "3-SAT, n=50",
    "request": {
      "problems": ["random_3sat"],
      "segments": [{"variables": 50, "ratio": "3..6:0.5", "mode": "random", "seed": "1..10"}],
      "solvers": [{"solver": "cdcl"}, {"solver": "dpll"}],
      "repeats": 1,
      "timeout": 30,
      "rules": [{"solver": "dpll", "action": "cap", "min_variables": 200, "seconds": 10}],
      "seed": 1
    }
  }'
```

Then fetch `GET /api/jobs/<id>/export.csv` when it is done. Invalid requests
come back as `422` with one message per field. The [API reference](api.md)
lists every endpoint.

Without the server, the same engine is available in Python:

```python
from sat_core.benchmark import parse_request, run_benchmark, rows_to_csv

plan = parse_request({...})            # the "request" object above
rows = run_benchmark(plan)
print(rows_to_csv(rows))
```

## Checklist for report-quality experiments

1. Use the same time limit for every solver in a series, and write down the
   limit rules that applied.
2. Fix the benchmark seed (and use seed ranges in the grids) so the formulas
   can be regenerated.
3. Record solver options: for CDCL the branching heuristic, phase, restarts
   and learned-clause limit; for WalkSAT/ProbSAT the tries, flips, noise and
   seed. Solver labels (named after the options unless you set one) carry
   them into the CSV.
4. Report SAT, UNSAT, UNKNOWN and TIMEOUT counts separately.
5. Prefer medians, and show how many runs each point summarises (the table
   view shows `n=`).
6. Export the CSV right after the run and keep it with the request (use
   **Edit as new** to see it).
