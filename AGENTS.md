# WizSAT: guide for contributors and coding agents

WizSAT is a local web app for encoding NP problems as CNF, solving them with
several SAT solvers, and benchmarking the solvers. A Python backend (FastAPI)
serves a React frontend. Everything runs on the user's machine.

The original Tkinter app and the Romanian thesis documents are archived in
`legacy/`. Do not import from `legacy/` and do not edit it except to keep its
own tests passing.

Words such as *case*, *run*, *row*, *item* or *glue clause* have one meaning
each, pinned in [`GLOSSARY.md`](GLOSSARY.md). Use them that way.

## Commands

```bash
python -m sat_web                        # build the UI if stale, start, open the browser
python -m sat_web --dev --no-browser     # API with auto-reload on :8000
cd frontend && npm run dev               # UI with hot reload on :5173 (proxies /api)

python -m pip install -r requirements-dev.txt   # FastAPI, httpx (API tests), ruff
python -m ruff check .                   # lint (settings in pyproject.toml)
python -m unittest discover -s tests     # Python tests
python scripts/benchmark_cdcl.py         # smoke-run every solver
python scripts/solver_timings.py         # time the solvers on a fixed set (docs/guide/performance.md)

cd frontend
npm run typecheck                        # tsc
npm test                                 # vitest unit tests
npm run build                            # production build into frontend/dist
npm run test:e2e                         # Playwright against the real server (build first)
```

`tests/test_api.py` skips itself when FastAPI is missing, and a skip looks
like a pass. Set `WIZSAT_REQUIRE_API_TESTS=1` (CI and cloud sessions do) so a
missing dependency fails the run instead.

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
tests/           unittest suites
docs/            guide/, algorithms/, visualisations/ (standalone HTML),
                 plans/ (features to build), reviews/ (findings to fix),
                 adr/ (decisions), report/ (thesis material)
.claude/         skills/ (fix-item, do-plan-step, writing-for-agents), hooks/
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

## Parameters

A `ParamField` (`sat_core/params.py`) is the single description of a
parameter; forms, validation, sweeps, CSV columns, reset buttons and the
Settings/Setup tables all come from it. The frontend never hard-codes a field:
change it in Python. Options and rules:
`docs/guide/adding-a-problem.md#parameter-fields`.

## Problems and solvers

Follow the walkthrough in `docs/guide/adding-a-problem.md` for a new problem
or solver; it has the checklists and the tests to write. What it cannot show:

- Keep the `dpll()`, `cdcl()` and `walksat()` signatures backward compatible
  unless the registry, tests and docs change with them.
- Solver hot loops are performance-sensitive (`docs/guide/performance.md`):
  check the cancel token every few thousand steps, not on every step; avoid
  scanning all clauses or variables per conflict or decision; measure with
  `scripts/solver_timings.py` before and after. Its conflicts column must not
  move for a change that claims to keep the search.
- Encoders number variables sparsely on purpose (`sudoku_var(r, c, v) =
  r*10000 + c*100 + v`; `readable_pair_var(a, b, max_b)`, always with
  `max_b`, or large instances collide). A solver that keeps per-variable
  arrays renumbers 1..n internally and maps the model back (see
  `solvers/walksat.py`). For CDCL and DPLL, `run_solver` renumbers
  formulas whose largest number is above 1,000,000 and mostly unused; no
  encoder reaches that at the default clause limit. Numbering per problem: `docs/algorithms/encodings.md`.
- The order of the clauses an encoder produces is part of its behaviour: it
  changes the solvers' decisions and every benchmark number.
- Every solver is in `tests/test_solver_agreement.py`: complete solvers must
  agree with brute force; incomplete ones must find every model and never
  claim one for an UNSAT formula (give them a small budget there).
- Every new stat key gets a label and a one-line explanation in `STATS`
  (`frontend/src/lib/format.ts`).

## Statuses

`SAT`, `UNSAT`, `UNKNOWN` (incomplete solver gave up), `TIMEOUT`,
`CANCELLED`, `SKIPPED` (limit rule or user skip), `ERROR` (solver raised; the
message is in `error`). `run_solver` never raises for solver failures.
`UNKNOWN` is never `UNSAT`: keep them apart in code, tables and charts.

## Benchmarks

Request format, limit rules, presets and CSV: `docs/guide/benchmarking.md`.
The invariants code must keep:

- Every solver entry of a case runs on the same CNF.
- Row index = `case.index * len(solvers) + position`, so parallel
  (`"workers" > 1`, `sat_core/parallel.py`) and sequential runs give identical
  rows. The frontend relies on the same formula (`entryForRow` in
  `components/BenchmarkSetup.tsx`).
- Code inside `run_case` must work in a worker process (no globals set by the
  job process).
- Workers are `spawn` processes, which re-import the main module: a script
  that runs a parallel benchmark must be a file with an
  `if __name__ == "__main__":` guard (piping it into `python -` fails).
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

## Working on items

Open work is a queue of **items**: findings in `docs/reviews/`, feature tasks
in `docs/plans/`. Read [`docs/plans/README.md`](docs/plans/README.md) before
taking one: it gives the order of work, the item format, the difficulty
levels and how to close an item. The skills `/fix-item` and `/do-plan-step`
walk through one item each.

- **Test first.** Turn the item's "done when" into a failing test before
  changing code.
- **Stop at `Needs decision`** and at anything the item does not settle that
  the owner would want a say in; ask instead of choosing silently.
- **Branches.** A change that touches code, tests, CI or dependencies is made
  on a branch (in a Claude Code cloud session: the branch the session was
  given), one item or a few small related items per branch, and reaches
  `main` through a pull request so CI runs first. Open the pull request when
  the work is verified; merging is the owner's call. Documentation-only
  changes may go straight to `main`.
- **One thing per change.** A new problem noticed along the way becomes a new
  item, not an extra edit.
- **Decisions** that are hard to reverse or were chosen over a real
  alternative get an ADR ([`docs/adr/`](docs/adr/README.md)).

## Which docs go with which code

Update the docs of the area you changed, in the same change. Nothing else
needs a routine edit.

| You changed | Update |
|---|---|
| a solver (`solvers/`, `sat_core/solver_registry.py`) | `docs/algorithms/<solver>.md`; `docs/guide/performance.md` when speed or the search changed; solver options in `docs/guide/user-guide.md` |
| a problem or an encoding (`problems/`) | `docs/algorithms/encodings.md`; `docs/guide/user-guide.md` |
| how problems or solvers are added | `docs/guide/adding-a-problem.md` |
| benchmark engine, presets, CSV (`sat_core/benchmark.py`, `parallel.py`, `presets.py`) | `docs/guide/benchmarking.md` |
| server, jobs, storage, events (`sat_web/`, `sat_core/jobs.py`, `runtime.py`) | `docs/guide/architecture.md`; `docs/guide/api.md` for endpoints, JSON and events |
| a page or a component (`frontend/src/`) | `docs/guide/user-guide.md`; "Frontend" in `docs/guide/architecture.md` if the structure changed |
| launcher, settings, dependencies, CI | `README.md`, this file |
| a term's meaning, or a new term | `GLOSSARY.md` |
| the workflow or the item format | `docs/plans/README.md` |
| `docs/report/` | thesis material: edit only when the owner asks |
| `legacy/` | never, except to keep its own tests passing |

## Before you finish

1. `python -m ruff check .` is clean.
2. `python -m unittest discover -s tests` passes with the API tests really
   running: the summary line must not say `skipped` for `test_api`
   (`WIZSAT_REQUIRE_API_TESTS=1` enforces it).
3. For solver, DIMACS or example changes: `python scripts/benchmark_cdcl.py`,
   and `python scripts/solver_timings.py` when speed may have changed.
4. For frontend changes: `npm run typecheck`, `npm test`, `npm run build`,
   and `npm run test:e2e` when a user flow changed.
5. The docs for the area are updated (table above).
6. The item is closed in its file as `docs/plans/README.md` describes, and
   the commit subject starts with its ID.

State a result only from output you have just seen: "tests pass" means the
command ran in this session after the last edit.

CI (`.github/workflows/ci.yml`) runs the same checks on every push to `main`
and on pull requests: lint and Python tests on Ubuntu (3.10, 3.13) and Windows
(3.12), the frontend checks, then the end-to-end tests.

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
