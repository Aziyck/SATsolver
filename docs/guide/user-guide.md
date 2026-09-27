# User guide

WizSAT has four pages, listed in the left sidebar: **Solve**, **Benchmarks**,
**Jobs** and **Learn**. The **Jobs** button in the top bar opens a drawer with
the running and recent jobs from any page, and the moon/sun button switches
between light and dark mode. The green "Live" dot means the page is receiving
live updates from the server.

Start the app with `python -m sat_web` (see the [README](../../README.md)).

## Solve

### Choose a problem

The Solve page opens with one card per problem:

| Problem | Question it asks | Answer shown as |
|---|---|---|
| Sudoku | fill an n x n grid (n = 4, 9, 16, 25) | the completed board, givens in bold |
| N-Queens | place n non-attacking queens | the chessboard |
| Graph Coloring | color the nodes with k colors, neighbours differ | the colored graph |
| Hamiltonian Path | visit every node exactly once along edges | the graph with the path highlighted |
| Independent Set | find k nodes with no edge between them | the graph with the chosen nodes |
| Clique | find k nodes that are all connected | the graph with the chosen nodes and their edges |
| Random 3-SAT | a random formula with n variables and m = n x ratio clauses | the truth assignment |
| DIMACS / CNF | any CNF formula you paste or open | the truth assignment |

The small (i) next to a problem's title explains its encoding.

### Fill in the input

The **Input** card holds the problem's parameters. Hover or read the grey help
text under each field. A few special inputs:

- **Graphs** (graph coloring, Hamiltonian path, independent set, clique) come
  from one of four generators:
  - `G(n,p)`: every possible edge appears with probability p;
  - `G(n,m)`: exactly m edges, chosen at random;
  - `G(n,d)`: average degree d, which means m = round(n x d / 2) edges;
  - `Manual`: type edges as `1-2, 2-3, 3 4` (one per line also works), or
    click two nodes in the preview to add or remove the edge between them.
- **Seed**: the same parameters and seed always give the same graph, puzzle or
  formula. Leave it blank for a random one; the seed that was used is recorded
  with the job so the instance can be rebuilt. The dice button picks a seed.
- **Sudoku**: type into the grid (arrow keys move, Backspace clears), paste a
  whole puzzle as digits with `0` or `.` for empty cells, or switch the source
  to *Generated* to get a random puzzle with a chosen percentage of givens.
  Cells that break a rule turn red before you solve.
- **DIMACS / CNF**: paste the text or press **Open .cnf file**. Parse errors
  name the line. Files exported by WizSAT remember which problem they came
  from; after solving one, **Open as that problem** reloads its parameters.

The badge in the card header estimates the size of the CNF formula (variables
and clauses). Very large instances are refused before any work starts; the
limit is 2,000,000 clauses (`WIZSAT_MAX_CLAUSES`).

The **Input preview** tab on the right draws the graph, board or a sample of
the clauses as you type.

### Pick a solver

| Solver | Complete? | Good for |
|---|---|---|
| CDCL | yes, proves SAT and UNSAT | the default; learns from conflicts |
| DPLL | yes | the classic baseline; slower on hard formulas |
| WalkSAT | no, may answer UNKNOWN | fast on many satisfiable formulas |
| ProbSAT | no, may answer UNKNOWN | a probabilistic WalkSAT variant |

Each solver shows its own options: CDCL's branching heuristic (VSIDS, most
frequent, MOMS, DLIS, random), initial phase and restarts; WalkSAT's tries,
flips per try and noise. **Advanced options** holds the rest (random seeds,
CDCL's learned-clause limit, WalkSAT's adaptive noise).

**Time limit (s)** stops the solver after that many seconds (blank means no
limit). **Log detail** controls how much the solver writes to the log:
*Normal* (start and finish), *Progress* (periodic updates) or *Debug*
(every decision; slow on big formulas).

### Solve or encode

- **Solve** builds the CNF and runs the solver.
- **Encode only** builds the CNF without solving, so you can inspect or
  download it.

Both run in the background as a *job* (labelled J1, J2, ...). You can keep
working, start other jobs or leave the page; up to one job per CPU core runs
at a time and the rest queue.

### Read the result

The **Result** tab shows:

- the **answer** (SAT, UNSAT, UNKNOWN, TIMEOUT, ...), the solver time and the
  solver;
- **Verified** when the model satisfies every clause *and* the decoded answer
  passes the problem's own checks (for example, no two queens attack). A red
  alert appears if a check fails or if the answer contradicts a known expected
  result (planted SAT formulas, forced UNSAT formulas, N-Queens for n = 2, 3);
- four tabs:
  - **Answer**: the solution drawn on the problem, plus facts about the
    instance (sizes, density, seed, encoding time);
  - **CNF**: the DIMACS text, paged, with a download button;
  - **Statistics**: decisions, conflicts, propagations, learned clauses,
    restarts (CDCL/DPLL) or tries, flips, best number of unsatisfied clauses
    (WalkSAT/ProbSAT);
  - **Log**: the solver log.

Buttons on the result: **Edit** loads the job's parameters back into the
form, **Rerun** runs exactly the same job again, the bin deletes it.
**Download the model** saves the assignment as DIMACS `v` lines.

What the statuses mean:

| Status | Meaning |
|---|---|
| SAT | a satisfying assignment was found (and checked) |
| UNSAT | a complete solver proved that no assignment exists |
| UNKNOWN | an incomplete solver (WalkSAT, ProbSAT) gave up; this is **not** a proof of UNSAT |
| TIMEOUT | the time limit was reached |
| CANCELLED | you cancelled the job |
| SKIPPED | a benchmark rule or you skipped this run |
| ERROR | the solver failed; the message says why (for example, DPLL running out of recursion depth on a huge formula) |

**Recent runs** below the result lists earlier jobs for the same problem.

## Benchmarks

A benchmark runs many cases (parameter combinations) with one or more solvers
and collects one row per solver run.

### Start from a preset

The Benchmarks page lists presets with their size. Opening one fills the
builder, where you can change anything before starting.

| Preset | What it shows |
|---|---|
| Random 3-SAT A: Planted SAT | all solvers on satisfiable formulas, n = 50..300, four densities (350 cases) |
| Random 3-SAT B: Forced UNSAT | CDCL vs DPLL proving UNSAT (100 cases) |
| Random 3-SAT C: Mixed SAT/UNSAT | ratio 4.25, 30%/50%/70% satisfiable, seeds 1..30 (270 cases) |
| Random 3-SAT phase transition | SAT share and time against the ratio, 3 to 6 |
| CDCL branching heuristics | VSIDS, most frequent, MOMS and DLIS on the same formulas |
| Graph suite: Clique vs Independent Set | both problems on the same random graphs |
| 3-coloring threshold | 3-colorability of G(n,d) graphs as the average degree grows |
| Sudoku sizes | generated puzzles of growing size, CDCL vs DPLL |

The [benchmarking guide](benchmarking.md) describes each preset exactly.

### Build your own

1. **Name** (optional) and **Problem**. Select several graph problems to run
   them on exactly the same graphs (a graph suite).
2. **Parameters**: every field that can vary accepts a list or a range:
   - `10, 20, 30` (commas, semicolons or spaces);
   - `1..20` (whole numbers from 1 to 20);
   - `0.1..0.5:0.1` or `3..6:0.25` (start..stop:step);
   - choices (such as the 3-SAT formula mode) are multi-selects.

   The cases are all combinations of the values. **Add another parameter
   grid** adds a second, independent grid (for example small n with many
   seeds and large n with few); the plan is the union of the grids.
3. **Solvers**: add one or more. Every case runs with every solver on the same
   CNF. Add the same solver twice with different options (for example CDCL
   with VSIDS and with DLIS) and give each a label to compare settings.
4. **Run settings**:
   - **Repeats**: runs per case. Repeat 1 uses the case's own seed, so any row
     can be reproduced on the Solve page; later repeats derive new seeds.
   - **Time limit (s)**: per run; blank means none.
   - **Seed**: used for cases whose grid has no seed.
   - **Log detail**: as on the Solve page.
5. **Limit rules** cap the time of a solver, or skip it, once formulas reach a
   size:
   *cap DPLL at 10 s when variables >= 200* is there by default, because DPLL
   gets very slow on large formulas. Change the solver (or *Any solver*), the
   action, the variable threshold and the seconds, or remove the rule.

The **Plan** panel on the right updates as you type: the number of solver
runs, cases x solvers, the largest formula, the limits that apply and the
first cases. Fields with errors turn red. Press **Start benchmark**. Big plans
are fine: results stream in, and you can leave the page.

### While it runs

The results page fills in live. **Skip case** marks the run in progress as
SKIPPED and moves on (useful when one hard case hangs); **Stop** cancels the
whole benchmark and keeps the rows so far.

### Results

- **Tiles**: runs done, SAT, UNSAT, no answer (UNKNOWN + TIMEOUT), skipped and
  errors, total solver time.
- **Suspicious runs** alert: rows whose answer failed verification or
  contradicts the known expected answer. The Runs tab can filter to them.
- **Compare with other benchmarks**: pick earlier benchmarks to show their
  rows next to these ones, in the charts and the table (each run is labelled
  by its job, such as J4).
- **Charts** tab:
  - **X axis**: any parameter that varies (or the case number);
  - **Split into panels by**: a second parameter, one small chart per value;
  - **Measure**: time, decisions, conflicts, propagations, learned clauses or
    flips;
  - **Summary**: median, mean, minimum or maximum over the runs that share an
    x value;
  - **Log scale** for measures that span orders of magnitude.

  Below the line chart, **Answers by ...** shows the share of each status per
  x value for one solver (the phase transition is easy to see here). Every
  chart has a **Table view** with the same numbers and a download button for
  the image.
- **Runs** tab: every run, sortable by any column, with search, status and
  solver filters. Click a row (or press Enter on it) for details: parameters,
  statistics, checks, and buttons to **Open in Solve** (rebuilds that exact
  instance on the Solve page) or **Download CNF**.
- **Log** tab: the benchmark log.

Header buttons: **Rerun** (same request again), **Edit as new** (open the
request in the builder), **CSV** (download all rows; with comparisons it
includes the compared benchmarks too), and delete.

## Jobs

Every solve, encoding and benchmark, newest first, with status, result,
duration and start time. Filter by kind or search by title; click a row to
open its result. **Delete finished** removes all finished jobs and their
files. Running jobs can be cancelled from the Jobs drawer.

Jobs and benchmark rows are stored in `output/wizsat.db` (SQLite) and job
files (the CNF and the model) in `output/jobs/<id>/`. They survive restarts;
jobs that were running when the server stopped are marked *interrupted*.

## Learn

- **Interactive**: step-by-step visualisations of DPLL, CDCL (implication
  graph, conflict analysis, learned clauses) and WalkSAT, on small formulas.
- **Notes**: the DPLL, CDCL and WalkSAT/ProbSAT documents from
  `docs/algorithms/`.

## Files you can import and export

| File | Where |
|---|---|
| `.cnf` (DIMACS) | open on DIMACS / CNF; download from any job's CNF tab or a benchmark row |
| model (`v` lines) | download from a SAT result |
| CSV | benchmark results, one row per solver run ([columns](benchmarking.md#csv-columns)) |
| PNG | download button on each chart |

DIMACS files exported by WizSAT start with a `c wizsat {...}` comment that
records the problem and its parameters. Other tools ignore comments, so the
files stay standard.
