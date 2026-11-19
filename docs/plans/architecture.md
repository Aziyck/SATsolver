# Plan: deepen the modules the next features will change

- **Status:** in progress (ARCH-1 to ARCH-4, ARCH-7 to ARCH-9, ARCH-11 and ARCH-12 done)
- **Written:** 2026-11-16, from the architecture review of commit `8b567ef`
- **Related:** [run metadata](run-metadata.md), [PyPy solver runner](pypy-solver-runner.md),
  [memory measurement](memory-measurement.md) (all three add fields and
  statistics to the code below), [architecture guide](../guide/architecture.md),
  [audit](../reviews/2026-10-16-audit.md) A7, A10, A15, A16, A22
- Item format, difficulty and closing rule: [README.md](README.md)

## Goal

Each rule that decides what the app shows or stores lives in one module, with
an interface a test can reach without starting the server or a worker process.
Today several of those rules are written in two to five places, and the three
planned features would each have to edit every copy.

The review found the large-scale shape sound: the layers hold
(`tests/test_layers.py`), a problem is one file, and `ParamField`,
`ProblemSpec`, `run_solver`, `execute_job` and `RunToken` are deep modules.
This plan leaves them alone.

## Non-goals

- Splitting `cdcl()`: audit B12 owns it.
- Speed: every task here must leave solver behaviour and benchmark numbers
  unchanged.
- New features. A task that would change what the user sees says so in its
  "done when".

## Vocabulary

Used as in the `codebase-design` skill. A **module** is anything with an
interface and an implementation. Its **interface** is everything a caller must
know: signature, invariants, error modes. A module is **deep** when much
behaviour sits behind a small interface. A **seam** is where an interface
lives. **Locality** means a change or a bug lands in one place.

## Order inside this plan

The parts are independent unless a task says `Blocked by`. Parts 1 to 4 come
before the features ([README.md](README.md), order of work). Parts 5 to 7 are
worth doing when the code is touched anyway.

| Part | Tasks | Strength | Why now |
|---|---|---|---|
| 1. One place that judges a SAT answer | ARCH-1 | strong | the PyPy runner adds a third path through this rule |
| 2. One catalog of statistics | ARCH-2, ARCH-3 | strong | the memory plan adds three statistics |
| 3. One owner of a solve request | ARCH-4 | strong | small; closes A10 on the way |
| 4. The job lifecycle as its own module | ARCH-5, ARCH-6 | strong | run metadata adds an event; memory adds a status |
| 5. Job, result and row shapes declared once | ARCH-7, ARCH-8 | worth exploring | all three features add fields |
| 6. Benchmark cases without the solvers | ARCH-9, ARCH-10 | worth exploring | |
| 7. Benchmark results logic out of the page | ARCH-11, ARCH-12 | worth exploring | |

## Considered and rejected

- **Splitting `JobManager` into several classes** (spawning, reading,
  publishing). They share one lock, and splitting would spread it across
  classes. Only the status rule moves out (Part 4); it needs no lock because
  it is pure.
- **The lifecycle also returns what to persist and publish.** A wider
  interface for the first step. The manager keeps those calls; they can move
  later if the table test shows a pattern.
- **Statistics declared in TypeScript and sent to Python.** The solvers
  produce the statistics and the CSV is written in Python, so Python owns the
  list, as it owns parameter fields.
- **A dataclass for the stored solve request.** The request is stored and
  sent as JSON and rerun from JSON; ARCH-4 keeps it a plain dict and gives
  it one parser instead.

## Part 1: one place that judges a SAT answer

Two callers decide whether a SAT answer is correct: `solve_job`
(`sat_core/jobs.py`) and the benchmark runner (`run_case` in
`sat_core/benchmark.py`). Each checks the model against the clauses, decodes
it, runs the problem's own `check`, and combines the result into `verified`.
The two copies already differ: the solve job also requires
`result.solution is not None`, the benchmark does not.

- [x] **ARCH-1. One function judges a SAT answer** - Done 2026-11-16.
  - **Difficulty:** medium (it defines what "verified" means in every result)
  - **How:** a new engine module `sat_core/answers.py` (add it to `ENGINE`
    in `tests/test_layers.py`):

    ```python
    @dataclass(frozen=True)
    class Verdict:
        verified: bool | None    # None when there is no model to check
        decoded: Any
        errors: list[str]

    def judge_answer(spec: ProblemSpec, instance: ProblemInstance, result: SolveResult) -> Verdict
    ```

    `solve_job` and `run_case` call it and keep only what is theirs (writing
    `model.txt`, building the row). The guard is the stricter one: a model is
    judged only when the status is SAT and a solution is present.
  - **Done when:** tests on `judge_answer` cover a satisfying model, a model
    that violates a clause, a decoder that raises, a failing problem check,
    an UNSAT result and a SAT result without a solution (verdict `None`, no
    exception); `check_assignment` is called only from `sat_core/answers.py`
    (a repo search); the existing tests pass.

## Part 2: one catalog of statistics

The keys of the statistics solvers report are listed five times, each a
different subset:

| List | Where | Used for |
|---|---|---|
| `STAT_COLUMNS` | `sat_core/benchmark.py` | CSV columns |
| `_STATS_SUMMARY_KEYS` | `sat_core/solver_registry.py` | the one-line run summary in the log |
| `STATS` | `frontend/src/lib/format.ts` | labels and explanations |
| `METRICS` | `frontend/src/lib/stats.ts` | chart measures |
| `SortKey` | `frontend/src/pages/BenchmarkResults.tsx` | sortable table columns |

`AGENTS.md` asks only for the `STATS` entry, so a new statistic that follows
the rule is still missing from the CSV, the charts and the sort, and nothing
fails. Parameter fields solved the same problem by being declared once in
Python and sent with `GET /api/catalog`; statistics should travel the same
way.

- [x] **ARCH-2. Every statistic is declared once, in Python** - Done 2026-11-16.
  - **Difficulty:** medium
  - **How:** a `StatSpec` per statistic in `sat_core/solver_registry.py`,
    next to `public_stats`:

    ```python
    @dataclass(frozen=True)
    class StatSpec:
        key: str
        label: str          # "Learned clauses"
        short: str          # "learned", for the log summary
        help: str           # one line, moved from STATS in format.ts
        unit: str = ""
        csv: bool = False   # a column in the benchmark CSV
        chart: bool = False # a measure in the charts and a sortable column
    ```

    `STAT_COLUMNS` and `_STATS_SUMMARY_KEYS` are derived from the list, in
    its order. `GET /api/catalog` returns it as `"stats"`. Mirror the shape in
    `frontend/src/api/types.ts`.

    Built as written, with details the plan left open. A statistic the log
    summary leaves out has `short=""`. `elapsed` is in the catalog because
    solvers report it (the frontend keeps it a built-in measure, as ARCH-3
    says). The catalog order is the log-summary order, and the CSV entries
    are a subset in that same order, so both outputs are unchanged.
    `chart=True` is set on the five measures `METRICS` lists today
    (decisions, conflicts, propagations, learned clauses, flips). The sort
    columns of `BenchmarkResults.tsx` are only three of them, so ARCH-3
    changes what the table can sort by when it derives both from `chart`.
    `STATS` in `format.ts` also has `timeout`, which no solver reports;
    ARCH-3 decides where it goes.
  - **Done when:** a test runs every registered solver on a small SAT and a
    small UNSAT formula and finds every key of its `public_stats` in the
    catalog; the CSV of a fixed benchmark is byte-identical before and after
    (record it first, as a test); `/api/catalog` includes `stats`.

- [x] **ARCH-3. The frontend reads statistics from the catalog** - Done 2026-11-19.
  - **Difficulty:** medium
  - **Blocked by:** ARCH-2
  - **How:** `STATS` in `format.ts`, `METRICS` in `stats.ts` and `SortKey`
    in `BenchmarkResults.tsx` are built from `catalog.stats` (`elapsed` stays
    a built-in measure, it is not a solver statistic). An unknown key still
    falls back to its own name. Update the rule in `AGENTS.md` ("Every new
    stat key gets a label...") to name the catalog, and the "Where the
    numbers live" part of [memory-measurement.md](memory-measurement.md).

    Built as written, with details the plan left open. `statLabel` and
    `statHelp` take the catalog's list as a second argument; components get it
    from `useStatSpecs()` (`api/queries.ts`). The measures are `chartMetrics`
    and `metricOption` in `lib/stats.ts`, time being the built-in
    `TIME_METRIC`, and the picker is its own component,
    `components/charts/MeasureSelect.tsx`, so a test can reach it without the
    page. The Runs table gets one sortable column per `chart` statistic, so it
    now has five (decisions, conflicts, propagations, learned clauses, flips)
    instead of three, each shrinking from 90 px to 72 px on a narrow window.
    `timeout` is gone from the labels: no solver reports it, and the fallback
    label "Timeout" is the same text. Test fixtures `statSpec()` and
    `catalog()` are in `frontend/src/test/catalog.ts`.
  - **Done when:** the frontend has no hard-coded list of statistic keys (a
    repo search for `"conflicts"` in `frontend/src` finds only tests and
    fixtures); a component test with a seeded catalog that adds a made-up
    `chart: true` statistic shows it in the chart measure picker; the
    end-to-end tests pass.

## Part 3: one owner of a solve request

A benchmark request has `parse_request` in `sat_core/benchmark.py`. A solve
request has no such module: `validate_job` in `sat_web/api.py` checks the
problem, solver, options, timeout and log level, and `solve_job` in
`sat_core/jobs.py` parses solver, options, timeout and log level again, with
weaker checks. A script that calls `execute_job` directly gets the weaker
ones. A10 covers the timeout part of this.

- [x] **ARCH-4. A solve request is parsed in one place** - Done 2026-11-19.
  - **Difficulty:** medium
  - **Blocked by:** A10 (it leaves one `parse_timeout`)
  - **How:** `parse_solve_request(raw: dict) -> dict` in `sat_core/jobs.py`
    returns the normalized request that `validate_job` returns today
    (problem, visible params, solver, options, timeout, log level) and raises
    `ParamError` with the same field names (`options.<name>`, `timeout`,
    `log_level`). `validate_job` and `solve_job` both call it; the encode
    job uses its problem half.

    Built as written, with details the plan left open. The problem half is
    `parse_problem_request(raw)` in `sat_core/jobs.py`; it returns the spec,
    the full parameters and the normalized `{"problem", "params"}`, and
    `generate_job` calls it. `parse_solve_request` is a thin wrapper over an
    internal `_parse_solve` that `solve_job` calls itself, so a job parses its
    problem once. `lookup_problem` (the "problem" `ParamError`) and
    `visible_params` moved from `sat_web/api.py` to `sat_core/jobs.py`, and the
    API imports them. `validate_job` still looks up the problem and solver once
    more to build the default title.
  - **Done when:** `validate_job` contains no solver, option, timeout or
    log-level parsing of its own; a test calls `solve_job` directly with a bad
    option, a negative timeout and an unknown log level and gets the same
    `ParamError` fields the API returns; the API tests pass.

## Part 4: the job lifecycle as its own module

A job's status is assigned in twelve places in `sat_web/manager.py`, across
`submit`, `_start`, `_apply`, `_finalize`, `cancel`, `shutdown` and `_load`.
The same class spawns processes, runs the reader threads, persists, throttles
logs and fans events out. No test constructs a `JobManager`: every lifecycle
test goes through the HTTP client, a real worker process and polling sleeps.
The state diagram in the architecture guide has no single piece of code that
matches it.

Separate the rule from the machinery. The manager keeps processes, threads
and the lock, and asks a small pure module what the next status is.

- [ ] **ARCH-5. The status rule is a pure function with a table test**
  - **Difficulty:** hard (job statuses, cancellation)
  - **How:** a new module `sat_web/lifecycle.py`, imported by nothing but
    the manager:

    ```python
    Status = Literal["queued", "running", "cancelling", "done", "failed", "cancelled", "interrupted"]

    def next_status(status: Status, happening: str, *, terminal_seen: bool = True) -> Status
    ```

    The happenings are the arrows of the state diagram: `slot_free`,
    `start_failed`, `stop`, `done_event`, `error_event`, `cancelled_event`,
    `process_exited`, `server_stopping`, `found_at_startup`. A happening that
    has no arrow from the current status leaves it unchanged (for example a
    Stop on a finished job).
  - **Done when:** a table-driven test covers every arrow of the diagram in
    `docs/guide/architecture.md` ("Statuses") and every final status ignores
    every happening; the guide's diagram and the test table list the same
    arrows.

- [ ] **ARCH-6. The manager takes every status from the lifecycle**
  - **Difficulty:** hard (processes, threads, cancellation)
  - **Blocked by:** ARCH-5, A7 (its test is the safety net for this change)
  - **How:** every `job.status = ...` in `sat_web/manager.py` becomes a call
    to `next_status`. Persisting and publishing stay where they are.
  - **Done when:** `job.status` is assigned in one helper of the manager (a
    repo search); the API tests, A7's test and the end-to-end tests pass.

## Part 5: job, result and row shapes declared once

What a job, an instance summary, a result and a row look like is written as
dict literals in `sat_core/jobs.py` and `sat_web/manager.py`, and mirrored by
hand in `frontend/src/api/types.ts` and `docs/guide/api.md`. The solve result
that travels is a dict with a different shape from the `SolveResult`
dataclass in `sat_core/models.py`. Nothing compares the two languages. META-2,
RUNNER-6, MEM-2 and MEM-6 each add a field here.

- [x] **ARCH-7. The travelling shapes are typed in Python** - Done 2026-11-19.
  - **Difficulty:** medium
  - **How:** frozen dataclasses for the instance summary and the solve
    outcome (today `instance_payload` and the result dict in `solve_job`),
    serialised with one `to_dict()` each. The JSON does not change.
  - **Done when:** `sat_core/jobs.py` builds no payload dict literal; the
    JSON of a solve job's instance and result events is identical before and
    after for a fixed Sudoku (record it first, as a test).

    Built as written, with details the plan left open. The classes are
    `InstanceSummary` and `SolveOutcome` in `sat_core/models.py`; `to_dict()`
    is shallow (the values are shared, not copied) and keeps field order, so
    the JSON is byte-identical. `instance_payload` became
    `instance_summary(...)`, which returns the dataclass; the two callers
    (`jobs.py` and the case-rebuild endpoint in `sat_web/api.py`) call
    `.to_dict()`. The recorded JSON is `tests/fixtures/solve_payloads.golden.json`
    (the three timing values are zeroed before comparing). The job and row
    shapes in `sat_web/manager.py` and `BenchmarkRow` are not part of this
    task.

- [x] **ARCH-8. A test keeps `types.ts` in step with the Python shapes** - Done 2026-11-19.
  - **Difficulty:** medium
  - **Blocked by:** ARCH-7
  - **Decided (2026-11-19):** option 1, sample payloads checked against the
    types. Rejected: option 2, generating `types.ts` from the Python
    dataclasses (it catches every drift, but only the instance summary, the
    solve outcome and `BenchmarkRow` are dataclasses so far, the job summary
    and detail are still dict literals in `sat_web/manager.py`, and it adds a
    generator and a build step); option 3, leaving it (drift stays silent while
    the features add fields). Option 1 does not stop a move to option 2 later,
    once the job shapes are typed too.
  - **How:** a Python test writes real payloads (a job summary, a job detail,
    an instance, a result, a row) to `tests/fixtures/wire_samples.json` and
    fails when they change, in the pattern of
    `tests/fixtures/show_if_cases.json`. A TypeScript file assigns each sample
    to its type, so `npm run typecheck` fails when a field the type requires
    is missing. This alone does not catch a new Python field that the type
    lacks, so a vitest check also requires every key of a sample to be a key
    the frontend reads. JSON imports type `"SAT"` as `string`, not as
    `RunStatus`; how the samples reach the type check (a generated `.ts`
    file, or a cast checked another way) is settled while building it.
  - **Done when:** removing a field from one Python payload fails CI, and
    renaming a field in `types.ts` fails CI.

    Built as decided, with two details the plan left open. The samples are one
    generated TypeScript file, `frontend/src/api/wireSamples.ts`, written and
    compared by `tests/test_wire_samples.py`; there is no separate
    `wire_samples.json`, because it would hold the same text twice. Each sample
    is declared `satisfies <its type>`, which keeps `"done"` a literal that
    fits a status union (a JSON import would type it as `string`) and also
    rejects a field the type does not declare, so the vitest check of "every
    key of a sample is a key the frontend reads" was not needed. The three
    samples are a job summary, a job detail (its instance and result are
    checked inside it, so they are not repeated) and a benchmark row, from a
    fixed Sudoku solve and a one-case benchmark, with the timings zeroed.
    Values typed `any` or `Record<string, unknown>` are not looked into, and
    each payload has one sample, so a field that is null in it is not checked
    against a real value. The detail sample is checked as
    `Omit<JobDetail, "request"> & { request: SolveRequest }` because
    `JobDetail.request` is typed as a solve and a benchmark request at once
    (filed as A33). Checked by hand, then reverted: renaming `elapsed` in
    `JobSummary`, removing a field from `SolveOutcome`, and adding a field to
    `InstanceSummary` each failed CI (the `tsc` run, the Python test, and the
    `tsc` run again).

## Part 6: benchmark cases without the solvers

`sat_core/benchmark.py` holds four jobs: the plan types, request parsing,
running, and CSV export. `parse_request` is one function that expands the
cases and validates solvers and limit rules together. To rebuild the case of
one row, `_rebuild_case` in `sat_web/api.py` has to pass a made-up solver
list, `{"solvers": ["cdcl"], "rules": []}`, so that solver checks cannot
fail. A caller working around an interface means the seam is in the wrong
place.

- [x] **ARCH-9. The cases of a request can be asked for on their own** - Done 2026-11-19.
  - **Difficulty:** medium (case order sets every row index)
  - **How:** `parse_cases(raw: dict) -> list[Case]` in
    `sat_core/benchmark.py` expands problems and parameters only;
    `parse_request` calls it and adds solvers and rules. `_rebuild_case` in
    `sat_web/api.py` calls `parse_cases`.
  - **Done when:** no caller passes a placeholder solver list (a repo
    search); a test gets the cases of a request that names an unknown solver;
    for every preset in `sat_core/presets.py` the case labels and indices are
    identical before and after (record them first, as a test).

- [ ] **ARCH-10. CSV export gets its own module**
  - **Difficulty:** easy
  - **How:** move `STAT_COLUMNS`, `BASE_COLUMNS` and `rows_to_csv` to
    `sat_core/export.py` (add it to `ENGINE` in `tests/test_layers.py`). If
    ARCH-2 is done, the columns come from the catalog.
  - **Done when:** `sat_core/benchmark.py` has no CSV code; the CSV of a
    fixed benchmark is byte-identical before and after.

## Part 7: benchmark results logic out of the page

`frontend/src/pages/BenchmarkResults.tsx` is the largest page and has no
test. It decides how rows of compared runs are merged and labelled, which
parameters become chart axes by default, and how the runs table is sorted and
filtered. None of it can be tested without rendering the whole page. A15 and
A16 are the same move for two other components; A22 is a bug in how this page
loads compared runs.

- [x] **ARCH-11. Merging the rows of compared runs is a tested function** - Done 2026-11-19.
  - **Difficulty:** medium
  - **How:** a function in `frontend/src/lib/benchmark.ts` takes the own
    rows and the compared runs and returns the combined rows with
    `run_label` set and the chartable `problem` and `run` parameters added.
    Each row also carries the id of its job, so the run drawer stops reading
    it back out of the label (today `run_label.slice(1)`, which depends on the
    `J<id>` format).
  - **Done when:** unit tests cover one run, a comparison of two, and a
    graph suite; the page contains no `slice(1)` on a label; the end-to-end
    tests pass.

    Built as written, with details the plan left open. The function is
    `mergeRuns(own, compared)` in `lib/benchmark.ts`; each run is a `RunRows`
    (`jobId`, `label`, `rows`), and `job_id` is a new optional field of
    `BenchmarkRow` next to `run_label`. `isGraphSuite(rows)` is exported so the
    page's "show the Problem column" check and the merge agree. The drawer
    takes the job from `row.job_id` and decides "own run" by comparing it with
    the page's job id, not by comparing labels. `comparing` inside the merge
    means "at least one compared run has loaded", so while a selected run is
    still loading, the own rows have no `run` parameter yet (it would be a
    single value and no axis anyway).

- [x] **ARCH-12. Default chart axes, sorting and filtering are tested functions** - Done 2026-11-19.
  - **Difficulty:** medium
  - **Blocked by:** ARCH-3 (the sort keys come from the catalog)
  - **How:** move the default x-axis and facet choice, `sortValue` and the
    row filter to `frontend/src/lib/stats.ts`.

    Built as written, with details the plan left open. The functions are
    `defaultAxes(varying)`, `sortValue`, `sortRows(rows, key, desc)` and
    `filterRows(rows, filter)` (a `RowFilter`: statuses, solvers, query,
    only-suspicious). `CASE_X` moved from `BenchmarkCharts.tsx` to
    `lib/stats.ts` (a library must not import from a component), and the page
    and charts import it from there. `isSuspicious` is new and
    `suspiciousRows` uses it, so the filter and the warning flag cannot
    disagree. Behaviour is unchanged: the sort keys are the five built-in
    columns plus the catalog's `chart` statistics (which the table passes
    in), and a run that lacks the sorted statistic still counts as -1.
  - **Done when:** unit tests cover the default axis for a sweep over one
    parameter, over two, and over none; sorting by a statistic a row lacks;
    and each filter; the page only wires them up.
