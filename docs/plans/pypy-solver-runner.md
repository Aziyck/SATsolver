# Plan: run the solvers in a child process, optionally under PyPy

- **Status:** proposed, not started
- **Written:** 2026-10-19; broken into tasks 2026-11-13, when the metadata
  part moved to its own plan
- **Related:** [run metadata](run-metadata.md) (how a result says which
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
    `{"clauses", "solver", "options", "log_level", "progress_interval", "timeout"}`.
  - Out, one JSON object per line on stdout: `{"type": "log", "message"}` for
    each log line, then one
    `{"type": "result", "status", "solution", "stats", "error"}`.
  - The model's keys become strings in JSON; convert them back to ints.
- **Cancel, skip, timeout:** the parent reads the child's output on a thread.
  While waiting, it checks `stop_requested(cancel_token)` every ~50 ms; on
  cancel or skip it kills the child and returns `CANCELLED` / `SKIPPED`. The
  child enforces the timeout itself (a `RunToken` with `timeout_seconds`); the
  parent also kills it a little after the timeout, in case it hangs.
- **Errors:** a child that exits without a result gives status `ERROR` with its
  stderr tail, like any solver failure today (`run_solver` never raises).
- **Data size:** at the 2,000,000-clause limit the JSON input is a few tens of
  MB. Acceptable, but measured in RUNNER-7.

## Tasks

Tests use `sys.executable` (CPython) as `WIZSAT_SOLVER_PYTHON`, so the
protocol, logs, cancel, skip, timeout and error paths are checked without PyPy
installed.

- [ ] **RUNNER-1. The child: one solver run from JSON to JSON**
  - **Difficulty:** hard (process protocol)
  - **How:** `sat_core/solver_process.py` reads the request from stdin, calls
    the in-process solver path, writes log lines as they happen and the result
    last, and exits 0. Nothing else goes to stdout.
  - **Done when:** a test starts the module with `sys.executable`, sends a
    small SAT and a small UNSAT formula for every solver, and gets the same
    status, model and scalar stats as `run_solver` in-process (with a seed for
    the local-search solvers); at log level `debug` the log lines arrive
    before the result.

- [ ] **RUNNER-2. `run_solver` uses the child when the setting is on**
  - **Difficulty:** hard
  - **Blocked by:** RUNNER-1
  - **How:** behind `WIZSAT_SOLVER_PYTHON`, `run_solver` starts the child,
    forwards its log lines to `event_callback` and returns the usual
    `SolveResult`. With the setting unset, the code path is the one that
    exists today.
  - **Done when:** `tests/test_runtime.py` passes with the setting set to
    `sys.executable` (run the solver tests of that file twice, with and
    without the setting), and an unset setting starts no process.

- [ ] **RUNNER-3. Cancel, skip and timeout reach the child**
  - **Difficulty:** hard (process lifetime)
  - **Blocked by:** RUNNER-2
  - **Done when:** tests on a formula that runs for seconds show that
    - cancelling the token returns `CANCELLED` within a second and the child
      process no longer exists;
    - a skip request returns `SKIPPED`;
    - a timeout of 0.2 s returns `TIMEOUT` with `elapsed` close to 0.2 s;
    - a child that ignores its timeout (patch it to sleep) is killed by the
      parent shortly after the limit and reported as `TIMEOUT`.

- [ ] **RUNNER-4. Failures become `ERROR`, never an exception**
  - **Difficulty:** medium
  - **Blocked by:** RUNNER-2
  - **Done when:** tests show status `ERROR` with a readable message for: an
    interpreter path that does not exist; a child that exits without a result
    (message carries the end of its stderr); a child that prints a broken
    line.

- [ ] **RUNNER-5. Jobs and benchmarks work through the child**
  - **Difficulty:** medium
  - **Blocked by:** RUNNER-3, RUNNER-4
  - **Done when:** with the setting on, API tests run a solve job and a small
    benchmark sequentially and with `workers: 2`, get the same rows as without
    the setting (statuses and work counts), and Stop on a running benchmark
    leaves no child process behind.

- [ ] **RUNNER-6. Results say which interpreter ran them**
  - **Difficulty:** easy
  - **Blocked by:** RUNNER-2, META-2
  - **How:** the child sends `run_environment()` with its result; it replaces
    the job process's own environment for that run.
  - **Done when:** with the setting pointing at a second interpreter, the job
    detail and the CSV show that interpreter's name and version.

- [ ] **RUNNER-7. Measure what the child costs**
  - **Difficulty:** easy
  - **Blocked by:** RUNNER-2
  - **Done when:** `docs/guide/performance.md` has measured numbers for the
    start-up cost per run and for sending a formula near the clause limit,
    with and without the setting.

- [ ] **RUNNER-8. Documentation**
  - **Difficulty:** easy
  - **Blocked by:** RUNNER-5
  - **Done when:** `README.md` says how to install PyPy and set the variable;
    `docs/guide/performance.md` has a PyPy section with the table below and
    the warm-up caveat; `docs/guide/benchmarking.md` says what to report;
    `docs/guide/architecture.md` and `AGENTS.md` mention the new module and
    setting.

- [ ] **RUNNER-9. CI runs the solvers under PyPy (optional)**
  - **Difficulty:** medium
  - **Blocked by:** RUNNER-5
  - **Needs decision:** whether the extra CI minutes are worth it.
    Recommendation: yes, one job (`actions/setup-python` with `pypy3.10`) that
    runs `tests/test_solver_agreement.py` under PyPy and one API test with the
    setting on.
  - **Done when:** that job is green on a pull request.

- [ ] **RUNNER-10. Real numbers on the target machine**
  - **Difficulty:** easy (needs PyPy 3.10 or newer on the owner's machine)
  - **Blocked by:** RUNNER-5
  - **Done when:** the measurement table is re-run with the app itself on the
    machine used for the thesis, and `docs/guide/performance.md` carries those
    numbers with the machine's metadata.

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
- **mypyc, Cython, Numba:** see the
  [solver optimisations plan](solver-optimisations.md#considered-and-rejected).
