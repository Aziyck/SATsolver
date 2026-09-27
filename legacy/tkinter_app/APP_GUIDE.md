# SAT Problem App Prototype

Run the desktop prototype with:

```powershell
python app.py
```

The app has two tabs.

## Solve

Choose one problem type:

- Sudoku: choose size `4`, `9`, `16`, or `25`, then fill the grid. Empty cells mean
  unknown values.
- Graph Coloring: choose manual edges like `1-2, 2-3`, or random graph
  generation with node count, color count, and optional seed. Random generation
  supports `G(n,p)` probability mode, `G(n,m)` exact-edge-count mode, and
  `G(n,d)` average-degree mode.
- N-Queens: choose board size `n`. The app asks whether `n` queens can be
  placed on an `n x n` board with no shared row, column, or diagonal.
- Random 3-SAT: choose variable count, clause count, optional seed, and formula
  mode. `Planted SAT` guarantees a satisfying assignment, `Forced UNSAT`
  inserts a small unsatisfiable 3-SAT core. In `Random`, leave `SAT target %`
  blank for pure unconstrained random formulas, or enter a percentage to mix
  planted SAT formulas with forced UNSAT formulas.
- Hamiltonian Path: choose manual or random undirected graph input. The app
  asks whether some path visits every node exactly once.
- Independent Set: choose manual or random undirected graph input plus target
  `k`. The app asks whether at least `k` nodes can be chosen with no edges
  between chosen nodes.
- Clique: choose manual or random undirected graph input plus target `k`. The
  app asks whether at least `k` nodes can be chosen so every chosen pair has an
  edge between them.
- DIMACS/CNF: paste or load raw DIMACS clauses.

Then choose `CDCL`, `DPLL`, or `WalkSAT`, generate the CNF preview, and solve.
The Solve tab is arranged as a workbench: the top toolbar keeps `Generate CNF`,
`Solve`, `Cancel`, `Save CNF`, `Load DIMACS`, solver choice, and timeout visible;
the left settings pane scrolls independently; the center panes hold CNF and
result text; the right pane holds problem details and graph previews. CNF files
can be saved under `input/generated/`. The compact Solver Guide in the controls
summarizes the solver families:

- `CDCL`: complete, learns clauses, backjumps, strongest default for hard
  formulas.
- `DPLL`: complete, recursive baseline, simpler and useful for comparison.
- `WalkSAT`: incomplete local search, fast on some SAT instances, supports
  Classic and ProbSAT flip strategies, and returns `UNKNOWN` if no model is
  found.

Advanced solver logs can be enabled for periodic progress messages or capped
verbose debug messages during a solve. The solve timeout defaults to 30
seconds; if a solver run exceeds it, the app stops that run and reports
`TIMEOUT`. WalkSAT progress logs include the active strategy, current noise,
adaptive-noise state, and recent make/break values; verbose debug logs also show
ProbSAT flip weights.

The CDCL advanced options let you experiment with search behavior:

- `CDCL branching`: `VSIDS`, `Most frequent`, `MOMS`, `DLIS`, or `Random`.
- `Initial phase`: `Positive first`, `Negative first`, `Polarity based`, or
  `Random`.
- `Restarts`: optionally restart CDCL every N conflicts while keeping learned
  clauses and activity scores.
- `Learned limit`: optionally cap the learned-clause database.
- `Random seed`: makes random branching and random phase choices repeatable.

These controls are grouped under `CDCL Options` because they apply only when
the selected solver is `CDCL`. `DPLL` ignores them and remains a fixed baseline
solver.

WalkSAT has its own `WalkSAT Options` group:

- `Max tries`: number of random restarts.
- `Max flips`: maximum flips per random try.
- `Noise`: probability of choosing a random variable from an unsatisfied clause
  instead of the best repair flip.
- `Strategy`: `Classic WalkSAT` keeps the random/greedy mix; `ProbSAT` chooses
  repair flips probabilistically, favoring low-break and high-make variables.
- `Adaptive noise`: raises randomness after stagnation and lowers it again when
  a new best assignment is found.
- `Random seed`: optional seed for reproducible local search.
Problem descriptions appear beside the controls, and irrelevant graph/log
settings are disabled as modes change.

CNF generation and solving run as background jobs, so the window stays
responsive even when the solver is CPU-heavy. The Solve tab has a compact
`Solve Jobs` panel. Pick a finished solve or generate job there to reload its
CNF, solver result, decoded response, problem input, and graph preview into the
main Solve view. `Cancel Selected` stops only the selected solve job, and
`Delete Selected` removes one finished solve job. `Clear Finished` removes all
finished solve jobs from that list.

For graph-like problems, use `Open Graph` to pop the current graph preview into
a resizable window. The popout can refresh the drawing, export the visible graph
as PNG, and copy or export only the current graph data.

The shared run feed at the bottom stays global and prefixes messages with the
job label, such as `J1` or `J2`.

## Benchmarks

The benchmark tab runs graph-coloring sweeps over node counts, either
probabilities, exact edge counts, or average degrees, color counts, repeats,
and solvers. The benchmark controls group the solver checkboxes with the same
Solver Guide used on the Solve tab, so the complete solvers and incomplete
local-search solver are easy to compare. It also runs Sudoku benchmarks over
built-in deterministic
`4x4`, `9x9`, `16x16`, and `25x25` cases. Sudoku defaults to `4x4` and `9x9`;
larger sizes are opt-in because they can take much longer. N-Queens benchmarks
sweep board sizes. Random 3-SAT benchmarks sweep variable counts and
clause-to-variable ratios; use `Planted SAT` for satisfiable WalkSAT targets,
`Forced UNSAT` for complete-solver UNSAT proofs, `Random` with blank
`SAT target %` for pure random formulas, or `Random` plus `SAT target %` for a
controlled SAT/UNSAT mix across repeats. Hamiltonian Path, Independent Set, and
Clique benchmarks reuse the same random graph modes as graph coloring;
Independent Set and Clique also sweep target `k` values. `Graph Suite` generates
one shared graph per graph setting and repeat, then runs the selected graph
problems on those exact same edges; it defaults to comparing Clique and
Independent Set. Benchmark solver logs can use the same normal, periodic
progress,
or capped verbose modes as Solve. The benchmark tab also has the same CDCL
heuristic controls as the Solve tab. The compact option summary is stored in
each benchmark row, exported in CSV files, shown in the selected-case details,
and included as a comment when saving a selected benchmark CNF. Each benchmark
solver run also has a timeout, defaulting to 30 seconds. Timed-out runs are kept
as `TIMEOUT` rows and shown as distinct chart bars before the benchmark
continues. The Benchmark tab keeps run, cancel, skip, export, metric, view, and
`Refresh Chart` controls in the fixed top toolbar. Settings and job controls
scroll on the left; the table and chart share the center workspace; selected
case details and graph preview stay on the right. The chart title shows the
active problem type, so bar labels stay compact. Results appear in a shared
table and Matplotlib chart and can be exported to:

```text
output/benchmarks/
```

Benchmark rows appear as each solver run finishes. When multiple benchmarks are
running at once, the table and CSV export include a `Run`/`run` label so rows
from different jobs are easy to distinguish. `Export CSV` writes the rows
currently shown in the benchmark table, so filtered views export only that
filtered subset. The Benchmark tab also has a `Benchmark Jobs` panel:

- `Show Selected Runs` filters the shared table and chart to the selected job
  rows; select multiple jobs to compare or export only those runs.
- `Show All Runs` restores the combined benchmark table and chart.
- `Hide Results` clears the current job selection and shows an empty table
  without deleting saved benchmark rows.
- `Delete Selected Jobs` removes the selected finished benchmark jobs and their
  rows; multi-select is supported.
- `Clear Table` empties the benchmark result table.
- `Clear Finished Jobs` removes finished benchmark jobs from the job list, but
  does not delete their rows unless you clear results.

Select any benchmark row to inspect that exact case's solver response, decoded
output, input data, saved CNF, and graph preview. Graph Coloring, Hamiltonian
Path, Independent Set, and Clique rows also support `Open Graph`, which opens a
resizable graph window with refresh, PNG export, and current-row graph-data copy
or export actions. The feed logs each case, repeat, CNF generation step, solver
start, and solver finish, similar to the old console output in
`legacy/genearate_graph_coloring.py`. Large benchmark charts are not
auto-rendered at the end because drawing hundreds of bars can make Tkinter feel
stuck; use `Refresh Chart` when you want to draw them. Filtering between
benchmark jobs refreshes the table first and then redraws the chart so job
switching stays responsive.

Use benchmark heuristic comparisons carefully. Changing branching, phase,
restarts, learned-clause limits, or CDCL random seed changes the CDCL search
path. Changing WalkSAT tries, flips, noise, strategy, adaptive noise, or WalkSAT
random seed changes the local-search path. Compare runs with the same timeout,
problem sweep, solver set, and repeat count. Random modes should use a seed when
you want reproducible results.

WalkSAT result stats also include the best partial assignment found,
make/break flip totals, restart summaries, and hard-clause hit counts. The
public status remains `UNKNOWN` when the normal search budget ends without a
model; the detailed reason appears as `termination_reason=budget_exhausted`.

Use probability mode for quick Erdos-Renyi style experiments. Use exact-edge
mode when you want fixed edge counts. Use average-degree mode for fairer
benchmarks across different node counts; it converts `d` into
`m = round(n * d / 2)` and then reuses exact-edge generation. If the requested
edge count is larger than a simple graph can contain, the app generates the
complete graph instead and shows both the requested and actual edge counts in
the feed.

Use `Cancel Selected` in the relevant job panel to request cooperative
cancellation for that selected job. Small runs may finish before the click is
processed, but longer CDCL, DPLL, WalkSAT, and benchmark runs check the cancel
token during their work and stop with status `CANCELLED`.

Use `Skip Selected Case` during a benchmark to mark the selected benchmark
job's current case as `SKIPPED` and continue with the next case. This is useful
when one generated graph or puzzle is taking much longer than the surrounding
sweep.

Use `Ctrl+W` to close the desktop app window.

## Adding More NP Problems

Add a new encoder in `problems/` that returns a `ProblemInstance`:

```python
from sat_core.models import ProblemInstance

def my_problem(...) -> ProblemInstance:
    return ProblemInstance(
        name="My Problem",
        problem_type="My Problem",
        clauses=clauses,
        metadata={},
        decoder=optional_decoder,
    )
```

The UI and benchmark code use the same `ProblemInstance` shape, so new problems
can be added without changing the solvers.
