# Plan: run the solvers in a child process, optionally under PyPy

- **Status:** in progress (RUNNER-1 and RUNNER-2 done 2026-11-20, RUNNER-3
  and RUNNER-4 done 2026-11-21, RUNNER-5 and RUNNER-6 done 2026-11-22,
  RUNNER-7 to RUNNER-10 done 2026-11-23,
  RUNNER-11 done 2026-11-24)
- **Written:** 2026-10-19; broken into tasks 2026-11-13, when the metadata
  part moved to its own plan
- **Related:** [run metadata](done/run-metadata.md) (how a result says which
  interpreter ran it), [memory measurement](memory-measurement.md) (reuses the
  child process), [solver optimisations](solver-optimisations.md),
  [Solver performance](../guide/performance.md),
  [Architecture](../guide/architecture.md)
- Item format, difficulty and closing rule: [README.md](README.md)

## Goal

With a setting such as `WIZSAT_SOLVER_PYTHON=/path/to/pypy3`, every solver run
(solve jobs, benchmarks, parallel benchmark workers) happens in a child process
of that interpreter. Without the setting nothing changes. The server itself
stays on CPython.

## Why

PyPy runs the solvers unchanged and is about 3x faster on runs that take
seconds (measured below). It is slower on very short runs because its JIT
compiler needs to warm up. The same child process is also what makes an
honest per-run memory number possible (see the memory plan).

## Design

- **One switch point:** `run_solver()` in `sat_core/solver_registry.py`. Solve
  jobs (`sat_core/jobs.py`), benchmark cases (`run_case` in
  `sat_core/benchmark.py`) and parallel workers (`sat_core/parallel.py`) all go
  through it, so one change covers every path.
- **Child process:** a new module, `sat_core/solver_process.py`, run as
  `[WIZSAT_SOLVER_PYTHON, "-m", "sat_core.solver_process"]` with the repo root
  as working directory. It imports only `solvers/` and `sat_core` (no FastAPI),
  so PyPy needs nothing installed beyond itself.
- **Protocol:** JSON over pipes.
  - In, one object on stdin:
    `{"clauses", "solver", "options", "log_level", "progress_interval", "timeout"}`,
    and optionally `"label"` (the solver name in log lines, as `run_solver`'s
    `label`; a benchmark passes its solver label).
    The request is one line; stdin then stays open for the whole run as the
    child's lifeline: the child ends when stdin reaches its end, so a parent
    that dies takes its child with it
    ([ADR 0006](../adr/0006-the-solver-child-ends-with-its-stdin.md)).
  - Out, one JSON object per line on stdout: `{"type": "log", "message"}` for
    each log line, then one
    `{"type": "result", "status", "solution", "stats", "error", "elapsed"}`
    (`elapsed` is the child's run time, without its start-up).
  - The model's keys become strings in JSON; convert them back to ints.
- **Cancel, skip, timeout:** the parent reads the child's output on a thread.
  While waiting, it checks `stop_requested(cancel_token)` every ~50 ms; on
  cancel or skip it kills the child and returns `CANCELLED` / `SKIPPED`. The
  child enforces the timeout itself (a `RunToken` with `timeout_seconds`); the
  parent also kills it a little after the timeout, in case it hangs. The
  child's clock starts after interpreter start-up and parsing the request
  (seconds near the clause limit), so the parent's margin covers those.
- **Errors:** a child that exits without a result gives status `ERROR` with its
  stderr tail, like any solver failure today (`run_solver` never raises).
  The parent reads stderr on its own thread too: the child sends stray prints
  there, and a full pipe would block it. Request mistakes (unknown solver,
  invalid options, unknown log level) are not run failures: the parent checks
  them before starting the child (`get_solver`, `parse_options`,
  `log_options_for`) and raises `ValueError`, as `run_solver` does in-process.
- **Data size:** at the 2,000,000-clause limit the JSON input is a few tens of
  MB (53.6 MB for three literals per clause). Measured in RUNNER-7: about 5 s
  more per run there, see
  [Solver performance](../guide/performance.md#the-solver-child-process).

## Tasks

Tests use `sys.executable` (CPython) as `WIZSAT_SOLVER_PYTHON`, so the
protocol, logs, cancel, skip, timeout and error paths are checked without PyPy
installed.

- [x] **RUNNER-1. The child: one solver run from JSON to JSON** - Done 2026-11-20.
  - **Difficulty:** hard (process protocol)
  - **How:** `sat_core/solver_process.py` reads the request from stdin, calls
    the in-process solver path, writes log lines as they happen and the result
    last, and exits 0. Nothing else goes to stdout.
  - **Done when:** a test starts the module with `sys.executable`, sends a
    small SAT and a small UNSAT formula for every solver, and gets the same
    status, model and scalar stats as `run_solver` in-process (with a seed for
    the local-search solvers); at log level `debug` the log lines arrive
    before the result.

- [x] **RUNNER-2. `run_solver` uses the child when the setting is on** - Done 2026-11-20.
  - **Difficulty:** hard
  - **Blocked by:** RUNNER-1
  - **How:** behind `WIZSAT_SOLVER_PYTHON`, `run_solver` starts the child,
    forwards its log lines to `event_callback` and returns the usual
    `SolveResult`. With the setting unset, the code path is the one that
    exists today.
  - **Done when:** `tests/test_runtime.py` passes with the setting set to
    `sys.executable` (run the solver tests of that file twice, with and
    without the setting), and an unset setting starts no process.

- [x] **RUNNER-3. Cancel, skip and timeout reach the child** - Done 2026-11-21.
  - **Difficulty:** hard (process lifetime)
  - **Blocked by:** RUNNER-2
  - **Done when:** tests on a formula that runs for seconds show that
    - cancelling the token returns `CANCELLED` within a second and the child
      process no longer exists;
    - a skip request returns `SKIPPED`;
    - a timeout of 0.2 s returns `TIMEOUT` with `elapsed` close to 0.2 s;
    - a child that ignores its timeout (patch it to sleep) is killed by the
      parent shortly after the limit and reported as `TIMEOUT`.

- [x] **RUNNER-4. Failures become `ERROR`, never an exception** - Done 2026-11-21.
  - **Difficulty:** hard (re-rated 2026-11-21 from medium: the fix is in `run_in_child`'s
    read loop, which owns the child process, its reader threads and its queue)
  - **Blocked by:** RUNNER-2
  - **Done when:** tests show status `ERROR` with a readable message for: an
    interpreter path that does not exist; a child that exits without a result
    (message carries the end of its stderr); a child that prints a broken
    line.

- [x] **RUNNER-5. Jobs and benchmarks work through the child** - Done 2026-11-22.
  - **Difficulty:** hard (re-rated 2026-11-20 from medium: jobs and benchmarks start the solver child process)
  - **Blocked by:** RUNNER-3, RUNNER-4
  - **How:** the child must end when the process that started it ends. Today
    only `run_in_child`'s own clean-up kills it, and that never runs when the
    manager's force stop terminates the job process or a pool worker leaves
    with `os._exit` (`exit_when_parent_dies`): the child is orphaned and, with
    no timeout, runs for ever (found in the RUNNER-3 review). The fix is the
    stdin lifeline in the Design ("Protocol"): the parent keeps the child's
    stdin open until the run is over, the OS closes it when the parent ends,
    and the child exits at the end of its stdin (`exit_when_stdin_closes`).
  - **Done when:** with the setting on, API tests run a solve job and a small
    benchmark sequentially and with `workers: 2`, get the same rows as without
    the setting (statuses and work counts), and Stop on a running benchmark
    leaves no child process behind.

- [x] **RUNNER-6. Results say which interpreter ran them** - Done 2026-11-22.
  - **Difficulty:** medium (re-rated 2026-11-22 twice: hard while the
    interpreter was to travel with each result line, which crosses
    `sat_core/parallel.py` (a pool worker hands back only its log lines and
    rows) and `sat_web/manager.py`; medium once the owner chose a probe at
    job start, which touches neither)
  - **Blocked by:** RUNNER-2, META-2
  - **Decided (2026-11-22):** one probe per job, not one answer per run. The
    setting cannot change while a job runs (the job process's environment is
    fixed when it starts), so one answer covers every run of the job.
  - **Built as:** `execute_job` (`sat_core/jobs.py`) passes the setting to
    `run_environment(machine, solver_python)`, which asks that interpreter
    for its name and version (`interpreter_facts()` in
    `sat_core/environment.py`: one `-c` process start per job) and records
    them instead of the job process's own; a generate job runs no solver and
    keeps its own. The result line of the child is unchanged. An interpreter
    that does not answer is recorded as `unknown`, never as the job process's
    interpreter.
  - **Done when:** with the setting pointing at a second interpreter, the job
    detail and the CSV show that interpreter's name and version
    (`test_the_job_detail_and_the_csv_name_the_solver_interpreter` in
    `tests/test_api.py`, with a stand-in interpreter from
    `tests/fake_python.py`).

- [x] **RUNNER-7. Measure what the child costs** - Done 2026-11-23.
  - **Difficulty:** hard (re-rated 2026-11-21: may change `START_UP_SECONDS`,
    which decides when the parent kills a child: the stopping trigger)
  - **Blocked by:** RUNNER-2
  - **How:** `START_UP_SECONDS` in `sat_core/solver_process.py` (RUNNER-3)
    is how long the parent waits for the child's first log line before it
    counts the child as hung. 60 s was a guess with no numbers behind it.
    Too low, and a healthy child still parsing a huge formula is killed as
    `TIMEOUT`. Too high, and a hung child holds its slot that much longer.
  - **Done when:** `docs/guide/performance.md` has measured numbers for the
    start-up cost per run and for sending a formula near the clause limit,
    with and without the setting, under CPython and, if installed, PyPy; and
    `START_UP_SECONDS` is set from the worst measured start-up (a few times
    it, so a busy machine does not trip it), or kept at 60 s with the reason
    written next to it.
  - **Note:** if sending a formula near the clause limit costs seconds,
    file a new item for a binary request format instead of JSON: the
    literals as 4-byte integers plus the clause lengths, read with the
    `array` module at C speed (works under PyPy too). Smaller and faster to
    parse than JSON text, and the change stays inside `solver_process.py`.
    Shared memory was considered and is not worth it: the child still has
    to build the solvers' lists from the buffer, and that is most of the
    parse cost, and a killed child can leak the segment on POSIX.
  - **Built as:** `scripts/child_cost.py` measures both, and the numbers are
    in [Solver performance](../guide/performance.md#the-solver-child-process):
    0.3 s per run (almost all interpreter start), 5 s more per run at the
    clause limit, a start-up window of 4.5 s at worst there. PyPy was not
    installed. `START_UP_SECONDS` stays at 60 s, with the reason next to it:
    the limit counts clauses, not literals, and 60 s covers about 70 million
    literals. Sending the formula costs seconds, so RUNNER-12 is filed; so
    is F6 (the variables are counted in the parent and again in the child).

- [x] **RUNNER-8. Documentation** - Done 2026-11-23.
  - **Difficulty:** easy
  - **Blocked by:** RUNNER-5
  - **Done when:** `README.md` says how to install PyPy and set the variable;
    `docs/guide/performance.md` has a PyPy section with the table below and
    the warm-up caveat; `docs/guide/benchmarking.md` says what to report;
    `docs/guide/architecture.md` and `AGENTS.md` mention the new module and
    setting.

- [x] **RUNNER-9. CI runs the solvers under PyPy (optional)** - Done 2026-11-23.
  - **Difficulty:** medium
  - **Blocked by:** RUNNER-5
  - **Decided (2026-11-23):** yes, one job on every push and pull request,
    as recommended: `actions/setup-python` with `pypy3.10` runs
    `tests/test_solver_agreement.py` under PyPy, and one API test runs with
    the setting on.
  - **Built as:** the job "Solvers under PyPy" in `.github/workflows/ci.yml`.
    The server and the test runner stay on CPython 3.12. The API test is
    `test_a_solve_job_and_benchmarks_give_the_same_results_through_the_child`:
    it takes the child's interpreter from `WIZSAT_TEST_SOLVER_PYTHON` (default
    `sys.executable`), so under PyPy it checks that statuses and work counts
    match a CPython run. The step refuses an interpreter that is not PyPy
    first, so an empty path cannot fall back to CPython and pass. Closed
    with the change; the done-when was seen afterwards: the job passed on
    PR #68 under PyPy 7.3.19 (Python 3.10.16).
  - **Done when:** that job is green on a pull request.

- [x] **RUNNER-10. Real numbers on the target machine** - Done 2026-11-23.
  - **Difficulty:** easy (needs PyPy 3.10 or newer on the owner's machine)
  - **Blocked by:** RUNNER-5
  - **Built as:** `scripts/pypy_timings.py` runs the table's cases through
    `run_solver`, in process and in a PyPy child. On Windows 11, Ryzen 7
    4800H, CPython 3.13.14 and PyPy 8.0.1 (Python 3.12.15): 3.0x to 4.2x on
    the long CDCL runs, 8.0x for DPLL, same work counts; slower on runs
    under a second once the child's start-up is counted. `child_cost.py`
    under PyPy: 0.35 s per run, window 3.3 s at most at the clause limit,
    so `START_UP_SECONDS` stays at 60 s. Numbers in
    [Solver performance](../guide/performance.md#running-the-solvers-under-pypy).
  - **Done when:** the measurement table is re-run with the app itself on the
    machine used for the thesis, and `docs/guide/performance.md` carries those
    numbers with the machine's metadata.

- [x] **RUNNER-11. The child protocol in its own pure module** - Done 2026-11-24.
  - **Difficulty:** medium
  - **Not hard:** it moves pure code only (the message shapes and the
    parent's parser); `run_in_child`'s read loop, threads and kill paths stay
    as they are, proven by the stop and failure tests passing unchanged.
  - **Blocked by:** RUNNER-4, RUNNER-6, MEM-3
  - **What:** the protocol (the request, the log and result lines, and the
    rules a line must follow) lives in `sat_core/solver_process.py` beside
    the process handling. MEM-3 (memory) adds fields to the result line, so
    it grows (RUNNER-6 left it as it was). As with `sat_web/lifecycle.py`
    and `sat_core/answers.py`, the rule moves out of the stateful code, so it
    is tested without starting processes.
  - **How:** a module `sat_core/solver_protocol.py` with the message shapes
    the child writes and the parser the parent uses (after RUNNER-4,
    `_parse_line` and `RESULT_FIELDS`). Both sides in `solver_process.py`
    import it, and `tests/test_layers.py` places it in the engine layer.
  - **Built as:** `sat_core/solver_protocol.py` has `RESULT_FIELDS`,
    `BrokenLine`, `parse_line`, `log_message`, `result_message` and
    `stopped_result` (the line the parent makes when it kills the child);
    `solver_process.py` imports them on both sides. The broken-line cases are
    in `tests/test_solver_protocol.py`; `tests/test_solver_process.py` keeps
    two through a real child (not JSON, a model with an UNSAT status).
  - **Done when:** the broken-line cases of RUNNER-4 are tested against the
    parser directly, without a child process; one broken-line test through a
    real child remains; the other tests in `tests/test_solver_process.py`
    pass unchanged.

- [ ] **RUNNER-12. A binary request format instead of JSON**
  - **Difficulty:** hard (`sat_core/solver_process.py`)
  - **Blocked by:** RUNNER-11
  - **What:** at the clause limit, encoding the request (`json.dumps`,
    0.9 s) and parsing it in the child (`json.loads`, 1.4 s) are about half
    of what the child adds to a run (RUNNER-7).
  - **How:** as in RUNNER-7's note: the literals as 4-byte integers and the
    clause lengths, read with the `array` module; the other request fields
    stay JSON. The change stays inside the protocol (`solver_protocol.py`
    after RUNNER-11) and `solver_process.py`.
  - **Done when:** the tests of `tests/test_solver_process.py` pass
    unchanged, and `scripts/child_cost.py` shows a shorter window at the
    clause limit, with the new numbers in `docs/guide/performance.md`.

## Measurements (2026-10-19)

**Method:**
- copies of `solvers/` plus `sat_core/runtime.py`;
- the same instances, generated once with CPython and saved as JSON;
- same seeds, runs one at a time on one container.

The work counts (conflicts, flips) were identical under both interpreters,
so the comparison is like for like.

| Instance | CPython 3.11.15 | PyPy 7.3.15 (3.9) | Speed-up |
|---|---:|---:|---:|
| CDCL, 3-SAT n=250 r=4.26 seed 2 (UNSAT) | 58.70 s | 20.55 s | 2.9x |
| CDCL, Sudoku 25x25 40% seed 1 | 31.24 s | 9.17 s | 3.4x |
| CDCL, 3-SAT n=200 r=4.26 seed 1 | 4.05 s | 2.24 s | 1.8x |
| DPLL, 25-Queens | 2.76 s | 0.32 s | 8.6x |
| WalkSAT, 3-SAT n=60 r=6 (UNSAT), 10 x 100,000 flips | 3.60 s | 1.07 s | 3.4x |
| WalkSAT, planted n=5000 r=4.2 | 0.19 s | 0.44 s | 0.4x |
| ProbSAT, planted n=5000 r=4.2 | 0.18 s | 0.24 s | 0.75x |
| CDCL, 3-SAT n=150 r=4.26 seed 3 | 0.02 s | 0.24 s | 0.1x |
| CDCL, Sudoku 16x16 40% seed 1 | 0.69 s | 0.45 s | 1.5x |
| CDCL, 40-Queens | 0.37 s | 0.49 s | 0.75x |
| DPLL, 3-SAT n=100 r=4.26 seed 1 | 0.10 s | 0.16 s | 0.6x |

**Notes:**
- The PyPy available in that container was 3.9 (Ubuntu's `apt-get install
  pypy3`; the download from downloads.python.org was blocked by the network
  policy).
- The repo needs Python 3.10+. For the test, `from __future__ import
  annotations` was added to the copy of `solvers/cdcl.py`, the only solver file
  without it. With PyPy 3.10 or newer no change is needed.
- Every job is a fresh process, so the JIT warm-up (about 0.1-0.3 s) is paid
  on every run.

**Reproduce:** save this as `make_cases.py` (anywhere) and run it with CPython
from the repo root as `PYTHONPATH=. python make_cases.py`, so it can import
`problems`:

```python
import json
from problems import build_problem
cases = [  # (label, problem, params, solver, options)
    ("3-SAT n=200", "random_3sat", {"variables": 200, "ratio": 4.26, "mode": "random", "seed": 1}, "cdcl", {}),
    ("25-Queens, DPLL", "n_queens", {"size": 25}, "dpll", {}),
    ("UNSAT n=60, WalkSAT", "random_3sat", {"variables": 60, "ratio": 6, "mode": "random", "seed": 2},
     "walksat", {"random_seed": 1, "max_tries": 10, "max_flips": 100000}),
]
json.dump([{"label": l, "solver": s, "options": o, "clauses": build_problem(p, pr).clauses}
           for l, p, pr, s, o in cases], open("cases.json", "w"))
```

Then time them with the same script under each interpreter (`python3 bench.py
<repo> cases.json`, `pypy3 bench.py <repo> cases.json`):

```python
import json, platform, sys, time
sys.path.insert(0, sys.argv[1])                      # the repo root
from solvers.cdcl import cdcl
from solvers.dpll import dpll
from solvers.walksat import walksat
print(platform.python_implementation(), platform.python_version())
for case in json.load(open(sys.argv[2])):
    options = dict(case["options"])
    started = time.perf_counter()
    if case["solver"] == "cdcl":
        _, stats = cdcl(case["clauses"], return_stats=True, logging_options=options)
    elif case["solver"] == "dpll":
        _, stats = dpll(case["clauses"], return_stats=True)
    else:
        options["selection_mode"] = case["solver"]
        _, stats = walksat(case["clauses"], return_stats=True, logging_options=options)
    work = stats.get("conflicts", stats.get("flips"))
    print(f"{case['label']:30} {stats['status']:8} {time.perf_counter() - started:8.2f}s work={work}")
```

## Getting PyPy (3.10 or newer)

- **Linux/macOS/Windows:** official builds at https://pypy.org/download.html
  (unpack, no installer). Conda: `conda install -c conda-forge pypy3.10`.
- **Distribution packages** may be older: Ubuntu's `pypy3` was 3.9 in
  October 2026, too old for this repo.
- **In GitHub Actions:** `actions/setup-python` with `python-version:
  pypy3.10`.
- The solvers use only the standard library, so no `pip install` is needed
  in PyPy.

## Rules for results (thesis)

- Keep CPython as the reference interpreter for reported results.
- The setting is global, so every solver in a benchmark uses the same
  interpreter. Never compare a PyPy run of one solver with a CPython run of
  another: that measures the runtime, not the algorithm.
- If PyPy results are reported, say so, and note the warm-up effect: PyPy
  is slower on runs under about half a second, which can change the ranking on
  small instances.

## Considered and rejected

- **The whole server under PyPy:** `uvloop` (used by `uvicorn[standard]`) does
  not support PyPy, and FastAPI/pydantic under PyPy was not verified. Running
  only the solvers under PyPy avoids the question.
- **`multiprocessing.set_executable(pypy)` for the existing job processes:**
  the job process shares multiprocessing queues and events with the CPython
  server. Mixing interpreters on those objects is not something to rely on.
  A plain child process with JSON pipes is simpler and fully under our
  control.
- **Switching to PyPy only for big instances:** within one benchmark, different
  cases would then run on different interpreters, so the times would not be
  comparable.
- **The interpreter in every result line (RUNNER-6's first design):** the
  child would send `run_environment()` with each result. A pool worker hands
  back only its log lines and rows, so the answer would need a path through
  `sat_core/parallel.py` and a merge in `sat_web/manager.py`, and asking git
  and the machine on every run costs 70-95 ms. The interpreter cannot change
  within a job, so one probe at job start gives the same answer.
- **mypyc, Cython, Numba:** see the
  [solver optimisations plan](solver-optimisations.md#considered-and-rejected).
- **A watchdog thread in the child that watches its parent's pid
  (RUNNER-5's first fix):** needs a different mechanism per platform, an
  extra variable to name the parent past a launcher, and still misses a
  parent behind a POSIX wrapper that forks. See
  [ADR 0006](../adr/0006-the-solver-child-ends-with-its-stdin.md).
- **A Windows job object (and `PR_SET_PDEATHSIG` on Linux) set up by the
  parent:** two platform-specific mechanisms, none for macOS, and
  `PR_SET_PDEATHSIG` fires when the starting thread ends, not the process.
  See [ADR 0006](../adr/0006-the-solver-child-ends-with-its-stdin.md).
