# WizSAT: guide for contributors and coding agents

WizSAT is a local web app for encoding NP problems as CNF, solving them with
several SAT solvers, and benchmarking the solvers. A Python backend (FastAPI)
serves a React frontend. Everything runs on the user's machine.

The original Tkinter app and the Romanian thesis documents are archived in
`legacy/`, a frozen archive: read it for reference, and keep imports and
edits outside it. Its tests are not run and may no longer pass
([ADR 0003](docs/adr/0003-legacy-is-a-frozen-archive.md)).

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
python scripts/child_cost.py [PYTHON]    # what the solver child process costs per run
WIZSAT_SOLVER_PYTHON=<pypy>              # run every solver in a child of that interpreter (README)
python scripts/mutation_sample.py <file.py ...>  # do the tests catch small bugs? (minutes; run alone)

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
  benchmark.py     request parsing, plan expansion, limit rules, run_benchmark/run_case
  export.py        CSV export of benchmark rows (rows_to_csv, one format for all problems)
  parallel.py      opt-in process pool for benchmarks ("workers" > 1), parent watchdog
  presets.py       benchmark presets (plain request dicts)
  jobs.py          job bodies run in worker processes (solve, generate, benchmark)
  runtime.py       RunEvent protocol, RunToken (cancel / skip / timeout)
  dimacs.py        DIMACS parser and writer (with line-numbered errors)
  solver_process.py  one solver run in a child process (JSON over pipes), used when WIZSAT_SOLVER_PYTHON is set
  verify.py        check a model against the clauses
  answers.py       judge_answer: the one rule for "verified" (model, decode, problem check)
  seeds.py         deterministic seeding helpers
sat_web/
  api.py           FastAPI app factory, REST endpoints, WebSocket, static files
  lifecycle.py     next_status(): the job status rule, pure (the manager's only source of job.status)
  manager.py       JobManager: worker processes, queue, event fan-out, persistence
  store.py         SQLite store (jobs and benchmark rows)
  config.py        Settings from environment variables
  __main__.py      the launcher (build, free port, browser, uvicorn)
frontend/src/
  api/             types.ts (mirrors the JSON), client.ts, live.ts (WebSocket), queries.ts
  lib/             pure helpers (params, benchmark drafts, stats, formatting) + tests
  components/      forms (fields/ParamForm.tsx), result views (views/), charts (charts/)
  pages/           Solve, Benchmarks, BenchmarkBuilder, BenchmarkResults, Jobs, Learn
  test/            renderWithApp() and field() fixtures for component tests, vitest setup
tests/           unittest suites
docs/            guide/, algorithms/, visualisations/ (standalone HTML),
                 plans/ (features to build), reviews/ (findings to fix),
                 adr/ (decisions), report/ (thesis material)
.claude/         skills/, agents/ (reviewer), hooks/, archive/
```

## Rules by area

The rules for one part of the code live in that folder's `AGENTS.md`. Claude
Code loads it (through the folder's `CLAUDE.md`) when it reads a file there;
if it is not in your context, read it before changing code in that folder.

| Working in | Read |
|---|---|
| `solvers/` | [`solvers/AGENTS.md`](solvers/AGENTS.md): signatures, hot loops, stats |
| `problems/` | [`problems/AGENTS.md`](problems/AGENTS.md): encoders, variable numbering |
| `sat_core/` | [`sat_core/AGENTS.md`](sat_core/AGENTS.md): benchmark invariants, workers |
| `sat_web/` | [`sat_web/AGENTS.md`](sat_web/AGENTS.md): processes, locks, security |
| `frontend/` | [`frontend/AGENTS.md`](frontend/AGENTS.md): data flow, types, charts |

How a request flows from the form to the solver and back:
[architecture](docs/guide/architecture.md#the-big-picture) and
[How it works](docs/guide/how-it-works.md#one-solve-start-to-finish).

Rules that hold everywhere:

- **Layers.** Code imports only what is below it
  ([architecture](docs/guide/architecture.md#layers));
  `tests/test_layers.py` checks it.
- **Parameters.** A `ParamField` (`sat_core/params.py`) is the single
  description of a parameter; forms, validation, sweeps, CSV columns and
  reset buttons all come from it. The frontend never hard-codes a field:
  change it in Python
  ([options](docs/guide/adding-a-problem.md#parameter-fields)).
- **Stopping.** Every long operation checks `stop_requested(token)`
  regularly, so cancel, skip and timeouts work.
- **Statuses.** A run's status is one of the seven in
  [`GLOSSARY.md`](GLOSSARY.md). `run_solver` never raises for solver
  failures (`ERROR` carries the message). `UNKNOWN` is never `UNSAT`: keep
  them apart in code, tables and charts.

## Working on items

Open work is a queue of **items**: findings in `docs/reviews/`, feature tasks
in `docs/plans/`. Read [`docs/plans/README.md`](docs/plans/README.md) before
taking one: it gives the order of work, the item format, the difficulty
levels and how to close an item. The skill `/do-item` walks through one
item (`/do-item-hard` for a hard one).

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
| benchmark engine, presets, CSV (`sat_core/benchmark.py`, `export.py`, `parallel.py`, `presets.py`) | `docs/guide/benchmarking.md` |
| server, jobs, storage, events (`sat_web/`, `sat_core/jobs.py`, `runtime.py`) | `docs/guide/architecture.md` when a part, layer, rule's home, status or database column changes; `docs/guide/how-it-works.md` for how it behaves; `docs/guide/api.md` for endpoints, JSON and events |
| a page or a component (`frontend/src/`) | `docs/guide/user-guide.md`; "Frontend" in `docs/guide/how-it-works.md` if the structure changed |
| launcher, settings, dependencies, CI | `README.md`, this file |
| a rule that holds only in one folder | that folder's `AGENTS.md` |
| a term's meaning, or a new term | `GLOSSARY.md` |
| the workflow or the item format | `docs/plans/README.md` |
| `docs/report/` | thesis material: edit only when the owner asks |
| `legacy/` | never (frozen archive, ADR 0003) |

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

- Replies, progress updates, commit messages and pull requests: shortest
  form that stays clear. Grammar may go for concision (fragments, no
  articles). Commits and pull requests are read later without the
  session's context: each claim names its file, test or term instead of
  leaning on the session. Docs: full sentences.
- **Skills.** A new skill must replace an existing one, or do a job already
  done by hand three times. A skill is refined only after three uses since
  its last change. Before writing or changing a skill, `AGENTS.md` or
  `CLAUDE.md`, read the `writing-for-agents` skill.
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
