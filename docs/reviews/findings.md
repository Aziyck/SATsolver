# Findings made while working

Problems met while working on something else: a bug, a weak spot, a review
finding left unfixed. Each is filed the moment it is found
([`docs/plans/README.md`](../plans/README.md), "Statuses and closing an
item") and fixed in a session of its own. A deliberate review of the code
gets a dated file of its own in this folder instead, like
[`2026-10-16-audit.md`](2026-10-16-audit.md).

- **IDs.** A new finding gets the next F number (F1, F2, ...). A18 to A41
  were filed in the 2026-10-16 audit before this file existed and moved here
  on 2026-11-20 with their IDs unchanged, so commits and docs that name them
  still find them.
- **Format.** The item format, the difficulty rules and how to close an item
  are in [`docs/plans/README.md`](../plans/README.md).

---

- [x] **A18. A Stop that lands after the result can end a job as cancelled**
  (added 2026-11-16, found while rewriting `docs/guide/architecture.md`;
  read off the code, not reproduced) - Done 2026-11-16.
  - **Difficulty:** medium
  - **Problem:** `execute_job` (`sat_core/jobs.py`) asks
    `token.is_cancelled()` once more after the job body has returned, and
    sends `cancelled` instead of `done` when it is set. A Stop that sets the
    event after `solve_job` has sent its result, but before that last check,
    therefore ends the job as `cancelled` (`_finalize` in
    `sat_web/manager.py` sees the job in `cancelling`), although the result is
    complete and stored. The page may then show an answer under a
    "cancelled" badge. The window is short and nothing is lost.
  - **Fix:** first reproduce it (a test that sets the cancel event between
    the result event and the end of `execute_job`). If it reproduces, a
    solve or encode job that has already sent its result ends `done`. A
    benchmark also returns normally after a Stop, so it must keep ending
    `cancelled`.
  - **Done when:** a test shows that a solve job whose result event was sent
    before the Stop ends as `done`, and that a Stop during the search still
    ends as `cancelled`.

- [x] **A19. Nothing checks the import rule** - Done 2026-11-16.
  (added 2026-11-16, found while rewriting `docs/guide/architecture.md`)
  - **Difficulty:** easy
  - **Problem:** "every arrow points down" (`docs/guide/architecture.md`,
    "Layers") was kept by convention. One import in the wrong direction,
    for example a solver importing `problems`, would pass every test.
  - **Fix:** a test that parses every import statement of `solvers/`,
    `problems/`, `sat_core/` and `sat_web/`, the ones inside functions
    included, and compares it with the layers of the diagram.
  - **Done when:** `tests/test_layers.py` passes on the current tree and
    fails when a module imports a layer above its own.

- [x] **A20. Nothing checks that the three `show_if` implementations agree** - Done 2026-11-16.
  (added 2026-11-16, found while rewriting `docs/guide/architecture.md`)
  - **Difficulty:** easy
  - **Problem:** field visibility is computed by `ParamField.visible` and
    `expand_params` on the server, and by `isVisible` and `isVisibleSweep`
    in the frontend. Each had its own tests with its own cases, so one side
    could change alone and the form would show a field the server ignores.
  - **Fix:** one fixture of fields and cases, run by a Python test and a
    vitest test, each asserting the same list of visible fields.
  - **Done when:** `tests/test_show_if_agreement.py` and
    `frontend/src/lib/visibility.test.ts` both read
    `tests/fixtures/show_if_cases.json` and pass.

- [x] **A21. A field that depends on a conditional field is shown differently by the server and the frontend** - Done 2026-11-16.
  (added 2026-11-16, found while A20)
  - **Difficulty:** easy
  - **Problem:** take A, B shown if A is `x`, and C shown if B is `b1`. With
    A at `y` and the form still holding `b1` for the hidden B, the server
    gives B its default and hides C (`expand_params` returns
    `{"a": "y", "b": "b0", "c": 1}`), while `isVisible` and `isVisibleSweep`
    read the stale `b1` and show C. No registered field is chained today
    (8 problems, 4 solvers), and
    `test_no_registered_field_depends_on_a_conditional_field` keeps it so.
  - **Fix:** refuse the shape where it is declared: `check_field_order`
    (`sat_core/params.py`) raises when a `show_if` names a field that has a
    `show_if` of its own. Then drop the guard test.
  - **Done when:** registering a spec with such a field raises
    `ValueError`, covered by a test in `tests/test_params.py`.

- [x] **A22. A compared run that is still running can miss rows**
  (added 2026-11-16, found while reviewing the architecture; read off the
  code, not reproduced) - Done 2026-11-16.
  - **Difficulty:** medium (live updates)
  - **Problem:** `BenchmarkResults` in `frontend/src/pages/BenchmarkResults.tsx`
    fetches the rows of each compared run under the cache key
    `["rows", id]` with a plain `api.rows`. `useRows` fills the same key
    through `trackFetch` and `mergeRowsSnapshot` (`frontend/src/api/live.ts`),
    which keep the row events that arrive while the fetch is in flight. The
    plain fetch has no such stash, so a row event that arrives before the
    reply finds no cached list to patch and is dropped (`applyEvents` skips
    `["rows", id]` when the cache is empty), and the reply, taken earlier,
    lacks it too. The row stays missing from the comparison until the query
    runs again (a `resync`, a reload, or the page mounting anew).
  - **Fix:** fetch compared runs the way `useRows` does: one query function,
    used by both.
  - **Done when:** a test in `frontend/src/api/` fetches the rows of a run
    through the function the comparison uses, delivers a row event while the
    fetch is in flight, and finds the row in the cache after the reply; the
    test fails with the plain `api.rows`.

- [ ] **A23. The sweep grammar is written twice with no shared cases**
  (added 2026-11-16, found while reviewing the architecture)
  - **Difficulty:** easy
  - **Problem:** lists and ranges such as `"10, 20; 30"`, `"1..30"` and
    `"0.1..0.5:0.1"` are parsed by `parse_number_list` in
    `sat_core/params.py` and by `parseNumberList` in
    `frontend/src/lib/params.ts`. Each has its own tests with its own cases,
    and the frontend copy writes the 10,000-value limit as a literal, apart
    from `MAX_SWEEP_VALUES`. A change on one side can leave the form accepting
    what the server refuses, the problem A20 solved for `show_if`.
  - **Fix:** one fixture, `tests/fixtures/number_list_cases.json`, with
    inputs and the expected list or error kind (empty, ends before it starts,
    not a whole number, not a number, too many values), read by a Python test
    and a vitest test, as `tests/fixtures/show_if_cases.json` is.
  - **Done when:** both tests read the fixture and pass, and the fixture has
    a case one past the limit.

- [ ] **A24. An instance's size is recounted on every read**
  (added 2026-11-16, found while reviewing the architecture)
  - **Difficulty:** medium (in the path of every benchmark case)
  - **Problem:** `variable_count`, `max_variable` and `size_variables` of
    `ProblemInstance` (`sat_core/models.py`) are properties that walk every
    clause each time. Measured on 2,000,000 random 3-literal clauses:
    `variable_count` 1.34 s, `size_variables` 1.40 s, `max_variable` 0.46 s
    per read (0.06 s each at 200,000 clauses). For a problem without a
    declared size, a benchmark case with S solver entries reads them 1 + 3S
    times (the encode log line, `limits_for` per entry, and `_row` per entry
    in `sat_core/benchmark.py`): 13 reads with four solvers, about 17 s per
    case at the clause limit (an estimate from the per-read times, not
    measured end to end). A solve job reads three of them for its instance
    event.
  - **Fix:** compute each once per instance. First check that nothing
    changes `instance.clauses` after `build` returns; if something does, the
    cached values must be dropped there.
  - **Done when:** a second read of `variable_count` on a 2,000,000-clause
    instance takes under 1 ms, and the existing tests pass.

- [ ] **A25. Solver options travel in a parameter named `logging_options`**
  (added 2026-11-16, found while reviewing the architecture)
  - **Difficulty:** easy
  - **Blocked by:** B2 (it reshapes option parsing in the solvers)
  - **Needs decision:** whether to rename. Option 1: `cdcl()`, `dpll()` and
    `walksat()` accept `options=`, and `logging_options=` stays as an alias,
    as `solvers/AGENTS.md` asks for these signatures. Option 2: leave it and say in
    the solvers' docstrings that the dict carries search options too.
    Recommendation: option 1, inside B2's change.
  - **Problem:** the runners in `sat_core/solver_registry.py` put the search
    options (branching, restarts, selection mode, seed) into the dict they
    pass as `logging_options`. A reader of a solver signature cannot tell
    where its search options come from.
  - **Fix:** as decided.
  - **Done when:** the runners pass search options under a name that says
    so, existing callers that pass `logging_options` still work, and the
    shared checks of Part B pass.

- [x] **A26. A cross-site image load still reaches the API under a LAN name**
  (added 2026-11-16, found while reviewing A13) - Done 2026-11-16.
  - **Difficulty:** hard (security)
  - **Problem:** A13 refuses `/api` requests whose `Sec-Fetch-Site` is
    `cross-site`, but browsers send `Sec-Fetch-*` only to trustworthy
    origins (`localhost`, `127.0.0.1`, https). Started with `--host 0.0.0.0`
    and `WIZSAT_ALLOWED_HOSTS=192.168.1.20`, the server gets no such header
    from `<img src="http://192.168.1.20:8000/api/jobs/1/rows/0/cnf">` on
    another site, so each load still re-encodes an instance. The page cannot
    read the answer, and the framing headers still apply.
  - **Decided (2026-11-16):** option 1, leave it. LAN use under `--host` is
    already "not a password", the page cannot read the answer, and option 2
    (refusing header-less GETs of expensive routes) would break plain
    `curl`. The caveat is in `docs/guide/architecture.md`,
    `docs/guide/api.md` and the `LocalOnlyGuard` docstring.
  - **Fix:** none in code; document the limitation.
  - **Done when:** the decision is recorded, and for option 2 a test shows a
    header-less GET of a CNF export refused while the app's own request
    passes.

- [ ] **A27. A stopped benchmark logs its cancellation twice**
  (added 2026-11-16, found while reviewing A18)
  - **Difficulty:** hard (re-rated 2026-11-20 from easy: changes which event ends a stopped benchmark)
  - **Problem:** `run_benchmark` (`sat_core/benchmark.py`) sends
    `cancelled` "Benchmark cancelled." when a Stop cuts it short, and
    `execute_job` (`sat_core/jobs.py`) then sends a second `cancelled`
    "Cancelled.". The job log shows both lines.
  - **Fix:** one of the two stops sending it; `execute_job` is the one every
    job kind goes through, so `run_benchmark` drops its event (its log line
    can stay as an `EVENT_LOG`).
  - **Done when:** a test shows a benchmark stopped part-way emits exactly
    one `cancelled` event.

- [ ] **A28. The comparison can keep old rows of a compared run**
  (added 2026-11-16, found while reviewing A22; read off the code, not
  reproduced)
  - **Difficulty:** easy
  - **Problem:** the `rows` memo in `BenchmarkResults`
    (`frontend/src/pages/BenchmarkResults.tsx`) reads `compareRows` without
    listing it, and refreshes on the joined `dataUpdatedAt` of the compared
    queries. Two row patches stamped in the same millisecond leave the
    string unchanged, so the memo keeps the rows from before the second.
  - **Fix:** depend on the queries' `data` references, or combine the rows
    in `useQueries({ combine })`.
  - **Done when:** a test patches a compared run's rows twice with the same
    `dataUpdatedAt` and the page shows both new rows.

- [ ] **A29. Nothing makes a fetch of a row list go through `trackFetch`**
  (added 2026-11-16, found while reviewing A22)
  - **Difficulty:** hard (re-rated 2026-11-20 from medium: changes how live.ts merges a REST reply with WebSocket events)
  - **Problem:** `live.ts` keeps streamed rows only for fetches wrapped in
    `trackFetch`. A22 routed both callers through `rowsOptions`, but a new
    caller with its own `queryFn` for `["rows", id]` would drop rows again,
    and no test covers the page's wiring.
  - **Fix:** make the rule structural: `applyEvents` stashes a row when the
    cache reports `["rows", id]` as fetching
    (`queryClient.getQueryState(...)?.fetchStatus`), or
    `setQueryDefaults(["rows"], ...)` makes the tracked fetch the only one.
  - **Done when:** a test fetches `["rows", id]` with a plain `api.rows`
    query function, delivers a row event during the fetch, and finds the
    row in the cache after the reply.

- [ ] **A30. Rows stashed during a failed fetch reach a later job with the same number**
  (added 2026-11-16, found while reviewing A22; read off the code, not
  reproduced)
  - **Difficulty:** hard (re-rated 2026-11-20 from easy: changes the pending stash in live.ts)
  - **Problem:** `pending` in `frontend/src/api/live.ts` is cleared only by
    a successful merge or a `deleted` event. When the fetch fails, or the
    numbering is reset, the stashed rows stay, and the next successful
    fetch for that id merges them into a different job's rows.
  - **Fix:** clear the entry when a tracked fetch fails and the last one for
    that id ends, and clear `pending` on `numbering_reset`.
  - **Done when:** a test stashes a row during a fetch that rejects, then
    fetches the same id again and gets only the reply's rows.

- [ ] **A31. A compared run that was deleted or renumbered stays in the comparison**
  (added 2026-11-16, found while reviewing A22; read off the code, not
  reproduced)
  - **Difficulty:** easy
  - **Problem:** the `compare` state of `BenchmarkResults` keeps job ids.
    After a `deleted` event the page refetches a 404 for that id; after a
    numbering reset, a new job with the same number is fetched and mixed
    into the charts and the CSV export.
  - **Fix:** drop ids from `compare` that are not in the live list of
    benchmarks, and clear it on a numbering reset.
  - **Done when:** a component test compares a run, delivers its `deleted`
    event, and the comparison no longer lists or fetches it.

- [ ] **A32. A graph suite compared with a single-problem benchmark cannot be split by problem**
  (added 2026-11-19, found while ARCH-11; read off the code, not reproduced)
  - **Difficulty:** easy
  - **Problem:** `mergeRuns` (`frontend/src/lib/benchmark.ts`) adds the
    `problem` parameter to every row only when the page's own run is a graph
    suite. Compare a single-problem benchmark with a suite and the suite's rows
    get no `problem`, so the charts cannot split them by problem and the Runs
    table hides its Problem column. Compare a suite with a single-problem
    benchmark and every compared row gets `problem` although it never varies
    within that run.
  - **Fix:** decide `suite` over the merged rows (`isGraphSuite` of all of
    them) instead of the own rows.
  - **Done when:** a unit test of `mergeRuns` with a single-problem own run
    and a suite as the compared run finds `params.problem` on the suite's
    rows, and the page shows the Problem column in that case.

- [ ] **A33. `JobDetail.request` is typed as a solve and a benchmark request at once**
  (added 2026-11-19, found while ARCH-8)
  - **Difficulty:** easy
  - **Problem:** `JobDetail.request` in `frontend/src/api/types.ts` is
    `SolveRequest & BenchmarkRequest`, which requires `problem` and `problems`,
    `params` and `segments` together. No real job has both, so a sample of a
    solve job's detail does not satisfy the type, and
    `tests/test_wire_samples.py` has to check `Omit<JobDetail, "request">` and
    the request separately.
  - **Fix:** type it by the job's kind, a union of `SolveRequest` and
    `BenchmarkRequest` narrowed on `kind`, and fix the call sites that read
    fields of the wrong half.
  - **Done when:** the detail sample in `wireSamples.ts` is checked against
    `JobDetail` itself (the `Omit` is gone from the test), and `npm run
    typecheck` passes.

- [x] **A34. A job whose worker could not start breaks the server's shutdown** - Done 2026-11-19.
  (added 2026-11-19, found while ARCH-6)
  - **Difficulty:** easy
  - **Problem:** in `JobManager._start` (`sat_web/manager.py`), when
    `process.start()` raises (out of memory, the process limit), the job
    becomes `failed` but `job.process` keeps the unstarted `Process` object
    and no reader thread exists. `shutdown()` joins every job whose `process`
    is not `None`, and `multiprocessing` raises `AssertionError` ("can only
    join a started process") for an unstarted one, so shutdown stops before it
    has joined and terminated the other jobs' processes.
  - **Fix:** set `job.process = None` in the `except` branch of `_start`.
  - **Done when:** a test makes `Process.start` raise, calls `shutdown()` and
    sees no exception (`tests/test_manager_status.py` builds a manager without
    a worker, see `test_a_worker_that_cannot_start_fails_the_job`).

- [ ] **A35. A worker that fails to start still takes a job slot until the next schedule**
  (added 2026-11-19, found by the review of ARCH-6; read off the code, not reproduced)
  - **Difficulty:** hard (re-rated 2026-11-20 from medium: changes how the manager starts processes and counts slots)
  - **Problem:** `JobManager._schedule` (`sat_web/manager.py`) counts a slot
    as taken after every `_start`, even when `process.start()` raised and the
    job is already `failed`, and the failure path never schedules again. With
    `WIZSAT_MAX_JOBS=2` and J2 to J4 queued: J2 fails to start, J3 starts, the
    loop stops at two, and J4 waits while one slot is free, until J3 ends or a
    new job is submitted.
  - **Fix:** `_start` returns whether the process started, and `_schedule`
    counts only the jobs that did.
  - **Done when:** a test with two slots, three queued jobs and a first start
    that raises sees the other two running (`tests/test_manager_status.py`
    shows how to make `Process.start` raise without a worker).

- [ ] **A36. A job whose worker could not start keeps no log of why**
  (added 2026-11-19, found by the review of ARCH-6; read off the code, not reproduced)
  - **Difficulty:** hard (re-rated 2026-11-20 from easy: changes the manager's handling of a process that could not start)
  - **Problem:** the `except` branch of `JobManager._start`
    (`sat_web/manager.py`) sets `error` and persists the job, but adds no log
    line and saves no log tail, unlike `_finalize`. The job's log ends at
    "Starting worker process..." and after a restart it is empty. The job's
    `multiprocessing` queue is not closed either, which leaves its pipe open on
    a machine that may already be out of resources.
  - **Fix:** log the error and "Job failed.", persist the log tail as
    `_finalize` does, and close the queue.
  - **Done when:** a test makes `Process.start` raise and finds the error in
    the job's log and in the stored log tail.

- [x] **A37. `ram_total_gb` reports the host's RAM inside a container with a memory limit** - Done 2026-11-19.
  (added 2026-11-19, found while META-1; read off the code, not reproduced)
  - **Difficulty:** easy
  - **Problem:** `sat_core/environment.py` reads `os.sysconf("SC_PHYS_PAGES")`,
    which is the host's memory. In a Docker or cloud container limited to 2 GB
    on a 64 GB host, a run records 64.0, which misleads when results from
    different machines are compared.
  - **Fix:** on Linux also read the cgroup limit (`/sys/fs/cgroup/memory.max`,
    or `/sys/fs/cgroup/memory/memory.limit_in_bytes` for cgroup v1) and take
    the smaller value; ignore "max" and absurdly large numbers.
  - **Done when:** a test with a patched cgroup file holding 2 GB and a
    larger host value gets 2.0.

- [x] **A38. A job detail opened before its worker starts keeps `environment: null` until a reload** - Done 2026-11-19.
  (added 2026-11-19, found while META-2; reproduced 2026-11-19 while META-3)
  - **Difficulty:** medium
  - **Blocked by:** META-3 (nothing shows the environment before it)
  - **Problem:** `environment` reaches the server in the first event of the
    worker, but the server does not publish it (META-2 keeps it in the detail
    only), and `frontend/src/api/live.ts` never refetches a job detail when
    its status changes. A job page opened while the job is queued, or
    fetched just before the worker reports, keeps `environment: null` while
    the job runs and after it ends. This is the ordinary path, not a rare
    race: in the e2e test "solver options reset to their defaults" (Solve,
    then the Settings tab of the finished job) the Machine block says "The
    machine this job ran on was not recorded." for a job that has an
    environment. Every job started from the UI shows it until the page is
    reloaded.
  - **Fix:** publish an `environment` live event from `JobManager._apply`
    and handle it in `live.ts` the way `instance` is handled, including the
    merge into a detail fetch in flight (`stash` / `mergeJobSnapshot`). The
    alternative is to refetch the detail when the summary moves from `queued`
    to `running`.
  - **Done when:** a `live.test.ts` test opens the detail of a queued job,
    applies the environment event, and finds the environment in the cached
    detail, also when the event arrives while that detail is being fetched;
    and the e2e test above finds the interpreter (`CPython x.y` or `PyPy
    x.y`) in the Machine block of the job it just ran. META-3 left that last
    assertion out in `frontend/e2e/solve.spec.ts` because it fails until this
    is fixed.

- [x] **A39. Every job spends about 0.3 s collecting its environment before it starts** - Done 2026-11-19.
  (added 2026-11-19, found by the review of META-2; measured on the owner's Windows machine)
  - **Difficulty:** medium
  - **Problem:** `execute_job` calls `run_environment()` first, in a freshly
    spawned worker, so its per-process cache never helps. In a fresh process
    on Windows it took 345-416 ms: importing `sat_core.environment` 125 ms,
    `_cpu_model` 79 ms (mostly the first `platform.system()` call), and the
    two git calls (`rev-parse`, `status`) about 75 ms each. A small solve job
    that solves in milliseconds now starts that much later. The token is not
    checked meanwhile, so a Stop in that window waits for it to end.
  - **Fix:** the plan keeps collecting in the worker on purpose (it must name
    the interpreter that runs the solver). Within that: one git call instead
    of two (`git status --porcelain=v2 --branch` prints the commit and the
    changes), and check what of the import time is new to a worker that
    imports the solvers anyway. Moving the git and hardware facts into the
    server and passing them to `run_job` is the larger option, and it changes
    the plan's design, so it needs the owner.
  - **Decided (2026-11-19):** the server reads the machine facts (OS, CPU,
    cores, RAM) once and passes them to `run_job`; the worker adds the
    interpreter facts; git stays per job, in one call. Git is not read once
    at server start: every worker imports the code from disk, so a solver
    edited while the server runs would be recorded under a clean commit.
  - **Done when:** a job's `environment` carries the machine facts the
    server read; the worker runs one git command; and what a worker spends
    on its environment, after the imports it needs anyway, is at most half
    the 193-232 ms measured before the fix on the same machine.

- [x] **A40. The Stop timer writes to a job's log without the lock** - Done 2026-11-20.
  (added 2026-11-20, found while checking `docs/guide/how-it-works.md`; read
  off the code, not reproduced)
  - **Difficulty:** hard (re-rated 2026-11-20 from easy: a thread and the manager's lock)
  - **Problem:** `JobManager.cancel` (`sat_web/manager.py`) starts a
    `threading.Timer` whose `force_stop` calls `self._log(job, ...)` without
    taking `JobManager.lock`. `_log` appends to `job.logs` and changes the
    per-second log counters (`log_window`, `log_sent`, `log_suppressed`),
    which the reader thread changes under the lock at the same time. Two
    threads changing the counters together can let a burst of lines past the
    60-per-second limit or lose a "more log lines" notice. The line itself is
    unlikely to be lost: `list.append` does not tear under the GIL.
  - **Fix:** take the lock in `force_stop` around the log call.
  - **Done when:** `force_stop` writes its log line while holding
    `JobManager.lock`, and the API tests pass.

- [x] **A41. `docs/README.md` links to `images/README.md`, which does not exist** - Done 2026-11-20.
  (added 2026-11-20, found while checking the links after META-5)
  - **Difficulty:** easy
  - **Problem:** the row for `images/` in the table of `docs/README.md` has
    the link text "what to add" pointing at `images/README.md`. The folder
    holds three screenshots and no README, so the link is dead.
  - **Fix:** drop the third column's link, or write the short
    `docs/images/README.md` it promises (which screenshots the project README
    uses and how to retake them).
  - **Built as:** the link now points at the project README, where the
    screenshots are used. The deleted file was a to-do list for adding them,
    finished in `deea25e`; the one fact worth keeping (PNG, about 1440 x 900,
    light theme) moved into the row.
  - **Done when:** every relative link in the Markdown files under `docs/`
    resolves to a file that exists.

- [ ] **F1. The Stop timer can act on a worker that has already ended**
  (added 2026-11-20, found while A40; review finding, read off the code, not
  reproduced)
  - **Difficulty:** hard (concurrency and stopping: `sat_web/manager.py`, a
    timer thread)
  - **Problem:** `force_stop` in `JobManager.cancel` decides only from
    `process.is_alive()` on the process it captured. Two ways that is wrong:
    1. The reader thread's `process.join(timeout=2)` can time out on a worker
       that closed its queue but hangs on exit. `_finalize` then logs
       "Job cancelled.", saves the logs and sets `job.process = None`. When
       the timer fires later, it appends "terminating it" after the final
       line; that line is published but never saved, so the live log and the
       reloaded log differ. The job may even have been deleted by then.
    2. On POSIX, `is_alive()` calls `waitpid(WNOHANG)`. If the reader thread
       (`join`) or `shutdown()` reaps the child at the same moment, the
       timer's call gets `ECHILD`, `poll` returns `None`, and `is_alive()`
       says True: a bogus log line, and `terminate()` sends SIGTERM to a PID
       the OS may have reused. Windows is not affected.
  - **Fix:** under the lock (A40 already takes it there), also return early
    when `job.process is not process` or the job is no longer
    `cancelling`. Check whether that closes case 2 too, or whether only one
    thread may wait on the child.
  - **Done when:** a test shows that a timer firing after `_finalize` adds
    no log line and does not call `terminate()`, and the API tests pass.

- [x] **F2. Tests that replace the solver child's program each build their own `Popen` spy** - Done 2026-11-21.
  (added 2026-11-21, found by retro)
  - **Difficulty:** easy
  - **Problem:** five tests in `tests/test_solver_process.py` and
    `tests/test_runtime.py` (`run_in_background`, `run_solver_with`, the
    non-UTF-8 stderr test, the two "wins over a stop" tests,
    `FAILING_DPLL_CHILD`) each patch `subprocess.Popen` with a hand-written
    spy. In RUNNER-4 one of them captured `subprocess.Popen` after an
    earlier subtest had patched it: the patches stacked, every subtest ran
    the first subtest's program, and all failed with the same misleading
    error. RUNNER-5 and RUNNER-11 will write more such tests.
  - **Fix:** one helper in `tests/` that takes the real `Popen` once at
    import, runs a given program in place of the child, records the
    children and kills the ones still running in cleanup; the five tests
    use it.
  - **Done when:** no test in `tests/` patches `subprocess.Popen` with its
    own spy for the solver child, and the tests pass unchanged in what they
    check.

- [x] **F3. Nothing says that line endings need no handling in this repository** - Done 2026-11-21.
  (added 2026-11-21, found by retro)
  - **Difficulty:** easy
  - **Problem:** in RUNNER-4 the agent edited files with Python scripts in
    shell heredocs to keep CRLF, following the CRLF rule of the parent
    folder's `CLAUDE.md` (meant for the coursework). The shell rewrote the
    backslashes in those scripts twice, which gave two `SyntaxError`s and
    four extra round trips. Here git stores LF and checks out CRLF
    (`core.autocrlf=true` on the owner's machine, index `i/lf`), and the
    Edit tool keeps a file's line endings, so no handling is needed.
    `core.autocrlf` is a local setting, so a cloud clone does not share it.
  - **Fix:** one line in the "Notes for Claude Code" of `CLAUDE.md`: git
    normalises line endings; edit with Edit. Optionally a `.gitattributes`
    with `* text=auto`, so the same holds for every clone.
  - **Done when:** `CLAUDE.md` carries the line, and, if the
    `.gitattributes` is added, `git ls-files --eol` shows `i/lf` for every
    text file.

- [x] **F4. The hard triggers do not name `sat_core/solver_process.py`** - Done 2026-11-21.
  (added 2026-11-21, found by retro)
  - **Difficulty:** easy
  - **Problem:** the "Concurrency" trigger in `docs/plans/README.md` lists
    `manager.py`, `parallel.py`, `runtime.py` and `live.ts`, not the solver
    child's module, which owns a process, three threads and a queue.
    RUNNER-4 was rated medium, so `/do-item` on Sonnet started it,
    re-rated it hard and stopped, costing the owner a turn; RUNNER-7 was
    re-rated for the same reason.
  - **Fix:** add `sat_core/solver_process.py` to the trigger's file list,
    and re-rate the open items that touch it: RUNNER-6 (easy, changes the
    child's `serve()`) becomes hard or gets a `Not hard:` line.
  - **Done when:** the trigger names the file and every open item that
    touches it is hard or carries a `Not hard:` line.

- [x] **F5. "Order of work" lists finding IDs that go stale** - Done 2026-11-21.
  (added 2026-11-21, found by retro)
  - **Difficulty:** easy
  - **Problem:** `docs/plans/README.md` names the open findings of
    `findings.md` by ID ("A23-A25, A27-A33, A35, A36, A40"). A40 is done
    and F1-F5 are missing, although the same file says statuses live on
    the items, not there. The list is a copy of what the items already
    record, and every closed or new finding makes it wrong.
  - **Fix:** replace the ID list with a pointer to the items themselves
    (the file already gives the command: `grep -n "^- \[ \]"
    docs/reviews/*.md docs/plans/*.md`). Check the audit list on the line
    above it the same way.
  - **Done when:** "Order of work" names no finding ID that can go stale,
    and following it still leads to every open finding.

- [ ] **F6. With the solver child, the variables of a formula are counted twice**
  (added 2026-11-23, found while RUNNER-7)
  - **Difficulty:** hard (the fix changes the child's result line, in
    `sat_core/solver_process.py`)
  - **Problem:** `run_solver` (`sat_core/solver_registry.py`) builds the set
    of variable numbers before it decides where the solver runs. With
    `WIZSAT_SOLVER_PYTHON` set, the child's own `run_solver` builds it
    again. At the clause limit (2,000,000 clauses of three literals) each
    count takes 2.5 s, half of the 5 s the child adds to such a run
    (`scripts/child_cost.py`, "The solver child process" in
    `docs/guide/performance.md`).
  - **Fix:** count once. The child already counts, so its result line can
    carry the number of variables. The parent counts only when no child
    result has the number: the in-process path, and the results the parent
    makes itself (stopped before starting, an `ERROR` from
    `SolverProcessError`, a run killed by the token or the time limit).
  - **Done when:** with the setting on, `variables` matches the in-process
    run for a finished run and for a killed or cancelled one, and a finished
    run no longer counts in the parent (a test that patches the count, or
    the "first line" of `scripts/child_cost.py` at the limit drops by the
    counting time).

- [ ] **F7. A run the parent kills reports an `elapsed` short by the variable count**
  (added 2026-11-23, found by the review of RUNNER-7)
  - **Difficulty:** hard (`sat_core/solver_process.py`, a killed run: the
    stopping trigger)
  - **Problem:** when `run_in_child` kills the child (cancel, skip, or past
    its time limit), it reports `elapsed` from the child's first log line.
    The child's clock starts earlier: `run_solver` makes its `RunToken`
    before it counts the variables, and logs only after the count (2.5 s at
    the clause limit, `docs/guide/performance.md`, "The solver child
    process"). A run killed at its limit therefore shows an `elapsed`
    seconds below the limit, unlike the same run in-process.
  - **Fix:** take the first line closer to the child's clock: the child's
    `run_solver` logs before it counts, or the token is made after the
    count, the same on both paths.
  - **Done when:** at a formula whose count takes a measurable time, a run
    killed by its time limit through the child reports an `elapsed` no
    shorter than its timeout.

- [x] **F8. The test suite ends with a warning about leaked semaphores** - Dropped 2026-11-23: accepted. All 11 come from
  `test_a_job_process_that_is_killed_leaves_no_child_behind`
  (`tests/test_api.py`), which kills a job process on purpose; every other
  test leaves none (each test file, then each test of `SolverChildTests`,
  run alone). The killed job cannot delete its pool's and queues'
  semaphores; the resource tracker deletes them at exit, so in the server
  they last only until it stops, after a force stop. Explained next to that
  test and in `README.md`; not silenced, so a real leak still shows.
  (added 2026-11-23, found while RUNNER-9; seen in the output, cause not traced)
  - **Difficulty:** hard (the fix is in how processes, queues or events are
    closed)
  - **Problem:** `WIZSAT_REQUIRE_API_TESTS=1 python -m unittest discover -s
    tests` passes, then `multiprocessing`'s resource tracker warns "There
    appear to be 11 leaked semaphore objects to clean up at shutdown" (Linux,
    CPython 3.13, on `main` at 005dd0f). Something creates `multiprocessing`
    locks, queues or events and never closes them: in the tests, or in
    `JobManager` or the benchmark pool when a job ends. If it is the server,
    a long-running server holds one more set per job.
  - **Fix:** find which test leaves them (run the files one at a time), then
    close the objects where they are made; a test fixture that is not torn
    down is fixed in the test.
  - **Done when:** the full suite ends without the resource tracker warning,
    and a test that runs one job through `JobManager` and shuts it down sees
    no leaked semaphore.

- [x] **F9. On macOS, the solver child's peak memory may be its parent's** - Done 2026-11-24.
  (added 2026-11-23, found while MEM-3; not measured, no Mac here)
  - **Difficulty:** easy (a measurement first; the fix depends on it)
  - **Problem:** on Linux, `ru_maxrss` in a child started by `subprocess`
    carries the parent's peak (measured in MEM-1), so `peak_memory_mb()`
    reads `VmHWM` there. macOS has no `VmHWM` and uses `ru_maxrss`; whether
    it inherits the same way is unknown. If it does, every run through the
    solver child on a Mac reports the job process's peak (MEM-3), and MEM-4's
    benchmark numbers would be wrong there. CI has no macOS job.
  - **Fix:** on a Mac, run `tests/test_memory.py` (its growth test holds 150
    MB in the parent except on macOS: take that exception out for the
    check) and `ChildMemoryTests` in `tests/test_solver_process.py`. If the
    child inherits, read the peak another way on macOS (`task_info` through
    `ctypes`) or report `None` there.
  - **Done when:** the growth test passes on macOS with the 150 MB parent,
    and its `darwin` exception is removed.
  - **Measured on macOS:** with a 150 MiB allocation held in the parent, the
    child's `ru_maxrss` grew from 20.0 to 70.0 MiB. The small, large, and
    small solver runs peaked at 22.2, 318.0, and 22.3 MiB. Both tests passed
    with CPython 3.14. The growth test now uses the same parent allocation
    on every platform.

- [x] **F10. An old PyPy job whose interpreter probe timed out counts as Python** - Done 2026-11-23.
  (added 2026-11-23, found while INTERP-4, in the review; the rule is INTERP-2's)
  - **Difficulty:** easy
  - **Decided (2026-11-23):** count it as PyPy. Before INTERP-2 only the
    `WIZSAT_SOLVER_PYTHON` interpreter was probed (the job's own is read
    in-process and always answers), so `unknown` means the solvers ran on
    the setting's interpreter. Built in `recorded_interpreter()`.
  - **Problem:** a job saved before requests carried `interpreter` is taken
    as PyPy only when its environment record says `PyPy`
    (`recorded_interpreter()` in `sat_core/jobs.py`). A PyPy that did not
    answer the probe within 15 s was recorded as `unknown`, so such a job
    shows no PyPy badge, and Rerun runs it on Python: its new times are then
    compared with PyPy times without a warning.
  - **Fix:** decide what `unknown` means for an old job: leave it Python and
    say so in `docs/guide/api.md`, or refuse to guess (Rerun asks, the
    summary says `unknown`). Rare: only jobs from before INTERP-2 on a server
    with `WIZSAT_SOLVER_PYTHON` set and a slow PyPy start.
  - **Done when:** a test with an old job whose environment says `unknown`
    shows the chosen behaviour in the summary and in Rerun.

- [ ] **F11. Ctrl+C stops the server only on the second press, with a traceback**
  (added 2026-11-23, reported by the owner, reproduced)
  - **Difficulty:** hard (a second waiting task in the WebSocket handler: concurrency; and how the server stops)
  - **Problem:** with a browser tab of the app open, the first Ctrl+C on
    `python -m sat_web` seems to do nothing; the second one stops the server
    and prints a `KeyboardInterrupt` traceback. Reproduced: server on a temp
    data dir, one WebSocket on `/api/ws`, Ctrl+Break to its process group:
    still running after 8 s; without the WebSocket it exits in 0.2 s.
    Causes:
    - uvicorn's graceful shutdown asks every connection to close and waits
      for them. The handler of `/api/ws` (`events` in `sat_web/api.py`) only
      awaits `subscriber.get()` and never reads the socket, so it never sees
      the close and never ends. uvicorn's "Waiting for connections to close.
      (CTRL+C to force quit)" is hidden by `log_level="warning"` in
      `sat_web/__main__.py`.
    - The second Ctrl+C forces the exit, which skips the lifespan shutdown:
      `manager.shutdown()` never runs (running jobs are marked interrupted
      only at the next start; their workers exit through the parent
      watchdog).
    - After `uvicorn.run` returns, uvicorn re-raises the captured SIGINT
      (`capture_signals`), and nothing in `__main__.py` catches the
      `KeyboardInterrupt`.
  - **Fix:** in `events`, wait for either the next event or a message from
    the socket (`websocket.receive()`), and return on a disconnect, so the
    handler ends when the browser leaves or the server closes it. In
    `__main__.py`, catch `KeyboardInterrupt` around `uvicorn.run` and print
    one line (`[wizsat] Stopped.`). Set `timeout_graceful_shutdown` (a few
    seconds) as a safety net for any other stuck connection.
  - **Done when:** a test (the reproduction above as a script or an API
    test) shows one Ctrl+C stops a server with an open WebSocket within a
    few seconds, the lifespan shutdown runs (`manager.shutdown()`), and the
    output has no traceback.

- [x] **F12. The solver child parses its request with the garbage collector on**
  (added 2026-11-24, found while RUNNER-12) - Dropped 2026-11-24 (the
  owner chose to build it in the RUNNER-12 session, then to drop it on these
  numbers): the time saved in the parse comes back at the next collection. Built and measured
  (2026-11-24, Windows 11, Ryzen 7 4800H, the 2,000,000-clause formula of
  `scripts/child_cost.py`): in a process laid out as the child, parse plus
  counting the variables plus 1,000,000 new lists took 3.76-3.96 s with the
  collector on and 3.72-3.86 s with it off during the parse (CPython 3.13);
  2.03-2.08 s and 2.05-2.17 s under PyPy 3.12. With the collector off, the
  clause lists stay in the youngest generation, and the first collection
  after `gc.enable` scans them all. The child's window in
  `scripts/child_cost.py` (7 runs each, alone) agreed: 2.84 s with the change
  and 2.88 s without on CPython, 2.42 s and 2.36 s on PyPy. `gc.freeze()`
  after the parse does help CPython: F13.
  - **Difficulty:** hard (`sat_core/solver_process.py`)
  - **Problem:** `main` in `sat_core/solver_process.py` reads the request
    with `json.loads` while CPython's cyclic garbage collector runs. Building
    the 2,000,000 clause lists of a formula at the clause limit sets off
    collections that scan every list built so far: `json.loads` takes
    1.21 s with the collector on and 0.77 s with it off (CPython 3.13);
    1.32 s and 1.10 s under PyPy 3.12. Lists of ints cannot form cycles, so
    the collections find nothing.
  - **Fix:** turn the collector off while the request is parsed and back on
    before the solver runs (`gc.disable`, `gc.enable` in a `finally`), so
    the solver runs as it does today.
  - **Done when:** a test shows the request is parsed with the collector
    off and the solver runs with it on, also after a request that cannot be
    parsed; and `scripts/child_cost.py` shows a shorter window at the
    clause limit, with the numbers in `docs/guide/performance.md`.

- [x] **F13. CPython's garbage collector rescans the formula during a solve**
  (added 2026-11-24, found while RUNNER-12) - Done 2026-11-24. 100-Queens
  (1.6 million clauses) runs about 17% faster; the other measured cases
  stay within noise (`docs/guide/performance.md`).
  - **Difficulty:** hard (changes the reported solve times of the reference
    interpreter; touches `sat_core/solver_process.py` if the child does it too)
  - **Decided (2026-11-24):** (a), freeze in `run_solver`, in-process and
    in the child, measured with `scripts/solver_timings.py` before and after.
    (b) would have helped no app run: a job runs its solvers in-process on
    CPython unless it asks for PyPy, and only a PyPy job uses the child.
  - **Problem:** CPython's collector (3.13 and earlier; 3.14's incremental
    collector works differently, so re-measure there) runs a full
    collection whenever the objects that survived since the last one
    exceed a quarter of the long-lived ones, and each full collection scans every clause list of
    the formula. At the clause limit (2,000,000 clause lists) a solver that
    builds lists pays that again and again: in a process that has just
    parsed the formula, building 1,000,000 small lists took 0.96-1.01 s, and
    0.33-0.34 s once the formula was frozen with `gc.freeze()` (CPython
    3.13, Windows 11, Ryzen 7 4800H). Not measured on a real solve yet.
  - **Fix:** call `gc.freeze()` once the formula is built and before the
    solver starts, so the collector never scans its lists again (they hold
    only ints, so they cannot be part of a cycle); `gc.unfreeze()` after the
    run where the process goes on (a job process, a pool worker).
  - **Done when:** `scripts/solver_timings.py` on CPython shows the same
    conflict counts before and after, with the times of both runs in
    `docs/guide/performance.md`; and a test shows the formula is frozen
    while the solver runs and unfrozen afterwards.
  - **Python 3.12:** the interpreter starts with a few hundred objects
    frozen by itself (375 on 3.12.3, 377 on the Windows CI runner; 3.13
    none). The first version skipped the freeze whenever the count was not
    0, to leave a caller's own freeze alone, so on 3.12 it never froze, and
    its tests failed in CI's Windows job (the only 3.12 one). The check now
    compares with the count when `sat_core/solver_registry.py` is imported
    (`_INTERPRETER_FROZEN`); `test_the_child_freezes_its_clauses_as_well`
    failed under 3.12 before that ("scanned clauses: 2 of 2") and passes now.

- [ ] **F14. The collector still scans the solvers' own copies of the formula**
  (added 2026-11-24, found by the review of F13)
  - **Difficulty:** hard (touches every solver's setup in `solvers/`, and
    changes CPython solve times)
  - **Problem:** F13 freezes the objects that exist when `run_solver`
    calls the solver, the input clause lists among them. Every solver then
    copies the formula into its own structures (CDCL: `_normalise_formula`
    makes a new list per clause, then a `Clause` object with its own list
    and the watch lists), and those are made after the freeze, so each full
    collection during the search still scans two or more copies of the
    formula. After F13 only 100-Queens (1.6 million clauses) got clearly
    faster, about 17%, against the threefold gain measured for building
    lists next to a frozen formula (`docs/guide/performance.md`, "The
    garbage collector and big formulas"). Not measured: how much of the
    rest a later freeze would win.
  - **Fix:** first measure: freeze once a solver's clause database is
    built (a hook the solver calls after its setup, or the freeze moved
    there), on 100-Queens and Sudoku 25x25, freeze off and on in turn. If
    it gains, build that hook; the unfreeze stays in `run_solver`.
  - **Done when:** `scripts/solver_timings.py` shows the same conflict
    counts, and a test shows the clause objects a solver searches with are
    frozen during the search; or the item is dropped with the measured
    numbers when the later freeze gains nothing over F13.


- [x] **F15. A Bash redirect into the scratchpad fails when its folder does not exist yet** - Done 2026-11-25.
  (added 2026-11-25, found by retro)
  - **Difficulty:** easy
  - **Problem:** the session's scratchpad folder is created only when
    something writes to it with the Write tool. A Bash command that
    redirects into it first (`> "$S/out.txt"`) fails with "No such file or
    directory". Seen in four sessions (RUNNER-10, RUNNER-5, the dark-theme
    change, A39). In RUNNER-10 the background timing run
    (`scripts/pypy_timings.py`) never started; the agent found out only when
    it read the missing output file, after the owner had asked twice
    whether the run was done.
  - **Fix:** one line in "Notes for Claude Code" in `CLAUDE.md`: before a
    Bash command writes into the scratchpad, `mkdir -p` it (the Write tool
    creates folders by itself).
  - **Done when:** `CLAUDE.md` carries the line.

- [x] **F16. The review does not check that a CI or test-setup change can fail** - Done 2026-11-25.
  (added 2026-11-25, found by retro)
  - **Difficulty:** easy
  - **Problem:** on RUNNER-9 (PR #68, the "Solvers under PyPy" job in
    `.github/workflows/ci.yml`), `/code-review` at `medium` found nothing.
    The owner's second review, in a fresh context, found three problems:
    the PyPy job could pass while running on CPython, the baseline read the
    shell's `WIZSAT_SOLVER_PYTHON`, and RUNNER-9 was closed before its CI
    run had been seen. A change to CI or to the test setup passes for the
    wrong reason more easily than a code change, because nothing tests the
    test.
  - **Fix:** in the instructions the `reviewer` agent
    (`.claude/agents/reviewer.md`) gives `code-review`, two checks for a
    diff that touches CI, test fixtures or test environment variables: does
    the new check fail when the thing it guards is missing or wrong (for
    example the wrong interpreter), and is the item closed only once its
    "done when" has been observed (a CI run, not the change that adds it).
  - **Done when:** `reviewer.md` passes the two checks, and a reviewer run
    on the diff of PR #68's first commit names at least the
    "passes on CPython" problem.

- [ ] **F17. A hard item's design fork is decided silently and shown only after the PR**
  (added 2026-11-25, found by retro)
  - **Difficulty:** easy
  - **Problem:** RUNNER-5's plan said the solver child ends with its
    parent, not how. The agent chose a watchdog thread in the child, built
    it, had it reviewed at `high` and opened PR #63. The alternative, a
    stdin lifeline, appeared only in the PR's "choices you may want to
    change". The owner chose the lifeline, which cost a second build, a
    second `high` review and ADR 0006 after the fact. `AGENTS.md` already
    says to stop at what the item does not settle, but no step in
    `/do-item` makes the agent look for such a fork before building.
  - **Fix:** in `.claude/skills/do-item/SKILL.md`, step 1, for a hard item:
    when the plan's design leaves a choice open that would need an ADR
    (hard to reverse, or chosen over a real alternative), ask before going
    red. The question gives two or three options, what each costs, and a
    recommendation. When the choice is about how processes or messages
    flow, add a mermaid diagram in a throwaway `.md` in the scratchpad, for
    the owner to open in the preview; it is not kept. A hard item with no
    open fork goes on without asking (RUNNER-3, 4, 7, 11 had none). Read
    the `writing-for-agents` skill first.
  - **Done when:** the step is in the skill, and a dry run on RUNNER-5's
    item text as it stood before the build (git history of
    `docs/plans/done/pypy-solver-runner.md`) stops with watchdog and
    lifeline as options.

- [ ] **F18. A speed-up is built in full before its gain is measured**
  (added 2026-11-25, found by retro)
  - **Difficulty:** easy
  - **Problem:** F12 (garbage collector off while the child parses) was
    built with its tests and docs in the RUNNER-12 session, then measured
    and dropped: the time saved came back at the next collection. For F13
    the owner had to say "measure first". No item says how much gain makes
    the change worth keeping, so the agent judges after seeing the numbers.
  - **Fix:** in the item format of `docs/plans/README.md`, an item whose
    purpose is speed (or memory) carries a `Worth it when:` line, for
    example "at least 10% on 100-Queens in `scripts/solver_timings.py`,
    same conflict counts". The work goes: measure the current code, build
    a rough version, measure it; below the bar, drop the item with the
    numbers (the existing "Dropped: reason" status); above it, build it
    properly with tests and docs, measure again and report both numbers.
    Also in `/write-plan`'s item list if it names fields.
  - **Done when:** the README defines the line and the order, and the open
    speed items (F14, the OPT tasks in `docs/plans/solver-optimisations.md`)
    carry a `Worth it when:` line or a `Needs decision` for it.

- [ ] **F19. A plan closes without checking that the owner can reach what its Goal promised**
  (added 2026-11-25, found by retro)
  - **Difficulty:** easy
  - **Problem:** the PyPy runner plan reached RUNNER-10 before the owner
    asked where to install PyPy and whether it could be chosen in the UI.
    Neither was in the plan; the answer became the four INTERP items
    (`docs/plans/done/solver-interpreter-choice.md`). The gap was against
    the plan's own Goal, not a new feature, and nothing at a plan's end
    looks for it.
  - **Fix:** in "Statuses and closing an item" of `docs/plans/README.md`:
    when the last item of a plan closes, the agent answers one question in
    its report to the owner: what can the owner still not do that the Goal
    promised (how to install, where to switch it on, where the result
    shows)? At most three lines; nothing is filed unless the owner says
    so. Not a list of new feature ideas.
  - **Done when:** the README carries the rule.

- [ ] **F20. The retro skill reads PR comments, but reviews are recorded in the PR body**
  (added 2026-11-25, found by retro)
  - **Difficulty:** easy
  - **Blocked by:** two more `/retro` runs (a skill changes only after
    three uses since its last change, `AGENTS.md` "Conventions"; last
    changed 2026-11-22, used once since). Later retros add their evidence
    here.
  - **Problem:** step 1 of `.claude/skills/retro/SKILL.md` starts with
    `gh pr view <n> --comments` and the inline comments API. In this
    repository the owner reviews in the session, so none of PRs #49-#79
    has a comment or a GitHub review; the review record is the "Review:"
    section `write-pr` puts in each PR body (for example PR #57: "reviewer
    agent at level high reported 8 findings: Fixed ... Pre-existing ...").
    Also, `--comments` cannot be combined with `--json`, which cost a retry.
  - **Fix:** step 1 reads the PR bodies' "Review:" and "Rulings" sections
    (`gh pr view <n> --json body --jq .body`), and keeps the comments call
    as a second source.
  - **Done when:** the skill names the body as the first source, and its
    command runs as written.
