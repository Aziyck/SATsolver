<p align="center">
  <img src="assets/logo.png" alt="WizSAT logo" width="120">
</p>

<h1 align="center">WizSAT</h1>

<p align="center">
  A local SAT-solving workbench: encode classic NP problems as CNF, solve them
  with DPLL, CDCL, WalkSAT or ProbSAT, and benchmark the solvers against each
  other, all from a web page on your own machine.
</p>

---

## What it does

- **Solve** Sudoku, N-Queens, graph coloring, Hamiltonian path, clique,
  independent set, random 3-SAT, or any DIMACS `.cnf` file. The answer is drawn
  on the problem itself (a filled board, a colored graph, a highlighted path)
  and is checked twice: the model must satisfy every clause, and the decoded
  answer must pass the problem's own rules.
- **Look inside the encoding**: the generated CNF, its size, what each variable
  means, the solver statistics and the full solver log, live, on a page of
  its own for each job.
- **Benchmark** solvers on parameter sweeps (`n = 50..200`, ratios
  `3, 3.5, 4.26`, seeds `1..30`, ...), with repeats, time limits and per-solver
  limit rules such as "cap DPLL at 10 s once formulas reach 200 variables".
  Results stream in live and can be charted, filtered, compared across runs
  and exported as CSV. Optionally several cases run at once, one per CPU
  core.
- **Presets** reproduce the report experiments (Random 3-SAT A/B/C) and a few
  classic ones (the 3-SAT phase transition, the 3-coloring threshold, CDCL
  branching heuristics).
- **Learn** how DPLL, CDCL and WalkSAT work with step-by-step interactive
  visualisations and notes.

Everything runs locally. The server listens on `127.0.0.1` only, and jobs and
results are kept in a small SQLite database under `output/`.

## Screenshots

> [Screenshot placeholder: `docs/images/solve.png` - the Solve page with a
> 3-colored random graph and the "Verified" badge]

> [Screenshot placeholder: `docs/images/benchmark-results.png` - results of the
> "Random 3-SAT phase transition" preset: median time and SAT/UNSAT share by
> ratio]

> [Screenshot placeholder: `docs/images/benchmark-builder.png` - the benchmark
> builder with a parameter grid, two solvers and the DPLL limit rule]

To add them, save the images under `docs/images/` (see
[docs/images/README.md](docs/images/README.md)) and replace each placeholder
with `![Description](docs/images/<name>.png)`.

## Requirements

| Tool | Version | Why |
|---|---|---|
| Python | 3.10 or newer | server, encoders and solvers |
| Node.js | 20 or newer (includes `npm`) | builds the web interface once |

The solvers and encoders are pure Python; the only Python dependencies are
FastAPI and Uvicorn (`requirements.txt`).

## Quick start

Clone the repository, create a virtual environment, install the two Python
dependencies and start the app. The first start installs the web-UI packages
and builds the interface (about a minute); later starts take a second.

**Windows (PowerShell)**

```powershell
git clone https://github.com/Aziyck/SATsolver.git
cd SATsolver
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m sat_web
```

**macOS / Linux**

```bash
git clone https://github.com/Aziyck/SATsolver.git
cd SATsolver
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m sat_web
```

The browser opens at `http://localhost:8000` (or the next free port). Stop the
server with `Ctrl+C`. Next time, activate the environment and run
`python -m sat_web` again.

### Launcher options

```text
python -m sat_web                 build the UI if it changed, start, open the browser
python -m sat_web --no-browser    do not open a browser window
python -m sat_web --port 8080     use another port (moves to the next free one if busy)
python -m sat_web --strict-port   exit instead of moving when the port is busy
python -m sat_web --build         force a rebuild of the web UI
python -m sat_web --skip-build    never build (serve whatever is in frontend/dist)
python -m sat_web --dev           auto-reload the Python server while you edit it
```

Environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `WIZSAT_DATA_DIR` | `output/` | where the job database and job files are stored |
| `WIZSAT_MAX_JOBS` | CPU cores - 1 | jobs that may run at the same time; the rest wait in a queue |
| `WIZSAT_MAX_CLAUSES` | `2000000` | instances larger than this are refused before encoding |
| `WIZSAT_FRONTEND_DIST` | `frontend/dist/` | the built web UI to serve |

If Node.js is missing, the server still starts and the page explains how to
build the interface.

## Using the app

A short tour; the [user guide](docs/guide/user-guide.md) has the details.

1. **Solve**: pick a problem, fill in the form (a live preview shows the
   graph, board or clauses and the CNF size), choose a solver and press
   **Solve**. **Encode only** builds the CNF without solving it, so you can
   download the `.cnf` file.
2. **Benchmarks**: start from a preset or a blank form. Every sweepable field
   accepts a list or a range: `10, 20, 30`, `1..30`, `3..6:0.25`. The plan panel
   shows how many cases and solver runs you are about to start.
3. **Jobs**: every solve, encoding and benchmark, with status, duration and
   links back to the result.
4. **Learn**: interactive DPLL, CDCL and WalkSAT visualisations, also online:
   [DPLL](https://aziyck.github.io/SATsolver/docs/visualisations/dpll/),
   [CDCL](https://aziyck.github.io/SATsolver/docs/visualisations/cdcl/),
   [WalkSAT](https://aziyck.github.io/SATsolver/docs/visualisations/walksat/).

## Development

Run the Python server with auto-reload in one terminal and the Vite dev server
(hot reload for the UI) in another:

```bash
python -m sat_web --dev --no-browser     # API on http://127.0.0.1:8000
cd frontend
npm install
npm run dev                              # UI on http://localhost:5173, proxies /api to :8000
```

### Tests

```bash
# Python: core, encoders, solvers, and the web API
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests

# Frontend: type check, unit tests, production build
cd frontend
npm run typecheck
npm test
npm run build

# End to end: drives the real server in Chromium (build first)
npx playwright install chromium          # once
npm run test:e2e
```

The end-to-end tests start `python -m sat_web` themselves with a throwaway data
directory; set `WIZSAT_PYTHON` if your interpreter is not called `python`.

A quick command-line check of every solver (no server needed):

```bash
python scripts/benchmark_cdcl.py
```

## Project layout

```text
sat_web/        FastAPI server: REST API, WebSocket events, job manager, launcher
sat_core/       parameter schema, solver registry, benchmark engine, presets,
                DIMACS, verification, job runner
problems/       one module per problem: parameters, CNF encoding, decoding, checks
solvers/        DPLL, CDCL and WalkSAT/ProbSAT implementations
frontend/       React + TypeScript web interface (Vite, Mantine, ECharts, Cytoscape)
tests/          Python unit and API tests (standard-library unittest)
docs/           guides, algorithm notes, interactive visualisations, report material
scripts/        command-line helpers
input/examples/ small DIMACS examples
assets/         logo and problem pictures
legacy/         the original Tkinter app and Romanian documents, kept for reference
```

## Documentation

| Document | What it covers |
|---|---|
| [User guide](docs/guide/user-guide.md) | every page of the app, input formats, reading results |
| [Benchmarking](docs/guide/benchmarking.md) | sweeps, limit rules, presets, parallel runs, CSV columns, fair comparisons |
| [Solver performance](docs/guide/performance.md) | how fast the solvers are, what made them faster, how to measure |
| [Architecture](docs/guide/architecture.md) | how the pieces fit together, job lifecycle, live events |
| [HTTP API](docs/guide/api.md) | endpoints and WebSocket messages |
| [Adding a problem or solver](docs/guide/adding-a-problem.md) | step-by-step extension guide |
| [Encodings](docs/algorithms/encodings.md) | how each problem becomes CNF, with sizes |
| [DPLL](docs/algorithms/dpll.md), [CDCL](docs/algorithms/cdcl.md), [WalkSAT](docs/algorithms/walksat.md) | the solver algorithms |
| [Report material](docs/report/README.md) | English, updated versions of the thesis documents |
| [AGENTS.md](AGENTS.md) | conventions for contributors and coding agents |

## Legacy

The original Tkinter desktop app (with its own copy of the backend and tests),
the early console scripts and the Romanian thesis documents are archived in
[`legacy/`](legacy/README.md). They are not used by the web app.
