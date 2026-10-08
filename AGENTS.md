# WizSAT: guide for contributors and coding agents

WizSAT is a local web app for encoding NP problems as CNF, solving them with
several SAT solvers, and benchmarking the solvers. A Python backend (FastAPI)
serves a React frontend. Everything runs on the user's machine.

The original Tkinter app and the Romanian thesis documents are archived in
`legacy/`. Do not import from `legacy/` and do not edit it except to keep its
own tests passing.

## Commands

```bash
python -m sat_web                        # build the UI if stale, start, open the browser
python -m sat_web --dev --no-browser     # API with auto-reload on :8000
cd frontend && npm run dev               # UI with hot reload on :5173 (proxies /api)

python -m unittest discover -s tests     # Python tests (API tests need requirements-dev.txt)
python scripts/benchmark_cdcl.py         # smoke-run every solver
python scripts/solver_timings.py         # time the solvers on a fixed set (docs/guide/performance.md)

cd frontend
npm run typecheck                        # tsc
npm test                                 # vitest unit tests
npm run build                            # production build into frontend/dist
npm run test:e2e                         # Playwright against the real server (build first)
```

The e2e tests start `python -m sat_web --skip-build --strict-port --port 8799`
with a temporary `WIZSAT_DATA_DIR`. Set `WIZSAT_PYTHON` to pick the interpreter.

## Layout

```text
problems/        one module per problem, each a registered ProblemSpec
  base.py          ProblemSpec, register_problem, MAX_CLAUSES, RESULT_VIEWS
  encoding.py      variable numbering helpers (sudoku_var, readable_pair_var, ...)
  graph.py         shared graph fields (gnp/gnm/gnd/manual + seed) and GraphProblemSpec
solvers/         dpll.py (iterative), cdcl.py, walksat.py (WalkSAT and ProbSAT)
sat_core/
  params.py        ParamField schema: parsing, validation, sweeps ("1..30", "0.1..0.5:0.1")
  models.py        ProblemInstance, SolveResult, BenchmarkRow, STATUS_* constants
  solver_registry.py  SolverSpec registry and run_solver()
  benchmark.py     request parsing, plan expansion, limit rules, run_benchmark/run_case, CSV
  parallel.py      opt-in process pool for benchmarks ("workers" > 1), parent watchdog
  presets.py       benchmark presets (plain request dicts)
  jobs.py          job bodies run in worker processes (solve, generate, benchmark)
  runtime.py       RunEvent protocol, RunToken (cancel / skip / timeout)
  dimacs.py        DIMACS parser and writer (with line-numbered errors)
  verify.py        check a model against the clauses
  seeds.py         deterministic seeding helpers
sat_web/
  api.py           FastAPI app factory, REST endpoints, WebSocket, static files
  manager.py       JobManager: worker processes, queue, event fan-out, persistence
  store.py         SQLite store (jobs and benchmark rows)
  config.py        Settings from environment variables
  __main__.py      the launcher (build, free port, browser, uvicorn)
frontend/src/
  api/             types.ts (mirrors the JSON), client.ts, live.ts (WebSocket), queries.ts
  lib/             pure helpers (params, benchmark drafts, stats, formatting) + tests
  components/      forms (fields/ParamForm.tsx), result views (views/), charts (charts/)
  pages/           Solve, Benchmarks, BenchmarkBuilder, BenchmarkResults, Jobs, Learn
tests/           unittest suites; test_api.py is skipped when fastapi/httpx are missing
docs/            guide/, algorithms/, report/, visualisations/ (standalone HTML)
```

## How a request flows

```text
UI form -> POST /api/jobs {kind, request}
        -> api.validate_job: ProblemSpec.parse / benchmark.parse_request (422 on errors)
        -> JobManager.submit -> worker process (spawn) runs sat_core.jobs.run_job
        -> ProblemSpec.build -> ProblemInstance (clauses + decoder)
        -> run_solver -> solvers/* -> SolveResult
        -> ProblemSpec.decode / check, verify.check_assignment
        -> RunEvents on a multiprocessing queue -> JobManager -> SQLite + WebSocket
        -> frontend live.ts updates the React Query cache
```

Rules that keep this working:

- Problem modules never import `sat_web`, FastAPI or anything UI-related.
- Solvers know nothing about problems, files or the web. They take
  `list[list[int]]` clauses and return `(solution | None, stats)`.
- Worker processes talk to the server only through `RunEvent`s. They never
  touch the database or sockets.
- Every long operation checks `stop_requested(token)` regularly so cancel,
  skip and timeouts work.

## Parameters are declared once

`ParamField` (in `sat_core/params.py`) is the single description of a
parameter. It drives server-side validation, benchmark sweeps, CSV columns,
case labels and the web forms. Kinds: `int`, `float`, `bool`, `choice`,
`text`, `seed`, `edges`, `sudoku_grid`, `cnf`.

- `sweepable=True` lets benchmarks pass a list or range for that field.
- `show_if={"graph_mode": ["manual"]}` hides a field unless another field has
  one of the listed values. A field may only depend on fields declared before
  it (`check_field_order` enforces this).
- `short="n"` makes the field part of the case label (`n=50 r=4.26 ...`).
- `advanced=True` tucks the field under "Advanced options" in the UI.
- Errors are raised as `ParamError({field_name: message})`; the API returns
  them as `422 {"message", "errors"}` and the forms show them per field.

The frontend never hard-codes a problem's fields. Adding or changing a field
in Python is enough for the form, the preview and the benchmark builder.

## Adding a problem

Full walkthrough: `docs/guide/adding-a-problem.md`. Checklist:

1. Create `problems/<name>.py` with a `@register_problem` `ProblemSpec`
   subclass: `key`, `title`, `summary`, `description`, `fields`,
   `result_view`, and `encode(params) -> ProblemInstance`.
2. Implement `estimate()` (CNF size without building it; used for the size
   guard and the UI badge), `decode()` via the instance decoder, and
   `check()` (validate the decoded answer independently of the CNF).
3. Optional: `expected_status()` when the answer is known by construction,
   `describe()` (facts), `visual()` / `preview()` (data for the drawing),
   `validate()` (cross-field checks).
4. Graph problems subclass `GraphProblemSpec` from `problems/graph.py` and
   implement `encode_graph(graph, params)`; they get the four graph modes, the
   seed and graph drawing for free, and can share graphs in a benchmark suite.
5. Import the module in `problems/__init__.py` (order = order in the UI) and
   add a picture under `assets/` if you want a card image.
6. Pick an existing `result_view` (`sudoku`, `queens`, `graph`,
   `assignment`). A new kind of picture needs a component in
   `frontend/src/components/views/` and a case in `ProblemViews.tsx`.
7. Tests in `tests/test_problems.py`: clause shape on a tiny instance,
   `estimate()` matches the real counts, SAT and UNSAT cases, `check()`
   catches a broken answer.

## Adding a solver

1. Implement it in `solvers/` with the same shape as the others:
   `solve(clauses, *, return_stats, event_callback, cancel_token,
   logging_options)` returning `(dict[int, bool] | None, stats)`. Put
   `status` in stats when it is not simply SAT/UNSAT (`TIMEOUT`,
   `CANCELLED`, `UNKNOWN`), and poll `stop_requested(cancel_token)`.
2. Register a `SolverSpec` in `sat_core/solver_registry.py` with typed option
   fields and a runner that maps the options to your solver's arguments.
   `complete=False` for solvers that cannot prove UNSAT (they report
   `UNKNOWN`).
3. Add tests (`tests/test_<solver>.py`), add complete solvers to
   `tests/test_solver_agreement.py` (checks against brute force), and make
   sure `python scripts/benchmark_cdcl.py` runs it.

Keep the `dpll()`, `cdcl()` and `walksat()` signatures backward compatible
unless the registry, tests and docs change with them. The recursive DPLL
that `solvers/dpll.py` replaced is archived in `legacy/dpll_recursive.py`.

Solver hot loops are performance-sensitive (`docs/guide/performance.md`):
check the cancel token every few thousand steps, not on every step; avoid
scanning all clauses or variables per conflict or decision; measure with
`scripts/solver_timings.py` before and after.

## Statuses

`SAT`, `UNSAT`, `UNKNOWN` (incomplete solver gave up), `TIMEOUT`,
`CANCELLED`, `SKIPPED` (limit rule or user skip), `ERROR` (solver raised; the
message is in `error`). `run_solver` never raises for solver failures.
`UNKNOWN` is never `UNSAT`: keep them apart in code, tables and charts.

## Variable numbering

Encoders use readable numbers so a DIMACS file can be read by eye:

- Sudoku: `sudoku_var(r, c, v) = r*10000 + c*100 + v`.
- Pairs: `readable_pair_var(a, b, max_b)` gives `a*100 + b`, widening to
  `a*1000 + b` and so on when `max_b >= 100`. Always pass `max_b`, or large
  instances collide. Graph coloring uses `color_var(node, color, colors)`.

Details for every problem: `docs/algorithms/encodings.md`.

## Benchmarks

A benchmark request is plain JSON (the same shape the presets use):

```json
{
  "problems": ["random_3sat"],
  "segments": [{"variables": "50, 100", "ratio": "3..6:0.5", "mode": "random", "seed": "1..10"}],
  "solvers": [{"solver": "cdcl"}, {"solver": "dpll"}],
  "repeats": 1,
  "timeout": 30,
  "rules": [{"solver": "dpll", "action": "cap", "min_variables": 200, "seconds": 10}],
  "seed": 1
}
```

- Each segment is a grid; the plan is the union of all segment grids, times
  repeats, times solvers. Several graph problems in one request run on the
  same graphs.
- Every solver runs on the same CNF for a given case.
- Limit rules match by solver and `ProblemInstance.size_variables`: n for
  Random 3-SAT, the header count for DIMACS, otherwise the number of distinct
  CNF variables. `skip` wins over `cap`, and the smallest cap applies.
- `sat_core.benchmark.DPLL_FALLBACK_RULE` (cap DPLL at 10 s from 200
  variables) is the default rule in the builder and in presets.
- `"workers": N` (default 1, at most the CPU count) solves N cases at once
  in a process pool (`sat_core/parallel.py`). A case is the unit of work and
  row indices are `case.index * len(solvers) + position`, so parallel and
  sequential runs give identical rows. Code inside `run_case` must therefore
  work in a worker process too (no globals set by the job process).
- One CSV format for all problems: base columns, one column per parameter,
  solver statistics.

## Web server rules

- Jobs run in `spawn` worker processes, at most `WIZSAT_MAX_JOBS` at once.
  They are not daemons (a benchmark may start its own pool); they exit with
  the server through `shutdown()` and a parent watchdog.
- The reader thread applies events under `JobManager.lock` and publishes to
  the event loop with `call_soon_threadsafe`. Take snapshots for HTTP replies
  under the lock (`manager.summary(job)`, `manager.detail(job)`).
- Every published job summary carries a `rev` that increases by one each time.
  The frontend drops copies older than the one it has, and merges events that
  arrive while a fetch is in flight (`frontend/src/api/live.ts`).
- Logs are throttled per job; row and summary events are batched.
- Only `instance.cnf` and `model.txt` can be downloaded from a job folder.
- The server binds to `127.0.0.1` by default. Keep it that way.

## Frontend rules

- Server data goes through React Query (`api/queries.ts`); live updates patch
  the cache in `api/live.ts`. Per-browser preferences go through
  `lib/storage.ts` (localStorage, wrapped in try/catch).
- Keep `api/types.ts` in sync with the JSON the API returns.
- Charts follow the dataviz rules already in `lib/palette.ts` and
  `components/charts/`: fixed categorical order, one y-axis (use facets
  instead of a second axis), a table view next to every chart, status colors
  only for statuses, text never in series colors.
- Pure logic lives in `lib/` with vitest tests; components stay thin.

## Before you finish

1. `python -m unittest discover -s tests` passes (install
   `requirements-dev.txt` so the API tests run too).
2. For solver, DIMACS or example changes: `python scripts/benchmark_cdcl.py`,
   and `python scripts/solver_timings.py` when speed may have changed.
3. For frontend changes: `npm run typecheck`, `npm test`, `npm run build`,
   and `npm run test:e2e` when a user flow changed.
4. Update the docs that describe what you changed (README, `docs/guide/`,
   this file).

CI (`.github/workflows/ci.yml`) runs the same checks on every push to `main`
and on pull requests: Python on Ubuntu (3.10, 3.13) and Windows (3.12), the
frontend checks, then the end-to-end tests.

## Conventions

- Python 3.10+, standard library `unittest`, no new runtime dependencies
  without a good reason (the solvers are pure Python on purpose).
- Use ASCII in Python source and docs. The UI may use typographic symbols
  where it helps (for example `µs`).
- Comments explain why, especially around SAT and CDCL logic.
- Never commit `__pycache__/`, `output/`, `input/generated/`,
  `frontend/node_modules/`, `frontend/dist/` or test reports (`.gitignore`
  covers them).
- Small stable examples live in `input/examples/`; tests and
  `scripts/benchmark_cdcl.py` use `input/examples/sudoku_4x4.cnf` and
  `input/examples/graph_coloring/gc_n10_p10_k2.cnf`.
