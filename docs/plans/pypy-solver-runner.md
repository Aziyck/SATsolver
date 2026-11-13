# Plan: run metadata, and an opt-in PyPy runner for the solvers

- **Status:** proposed, not started
- **Written:** 2026-10-19, against commit `9e11958`
- **Related:** [Solver optimisations](solver-optimisations.md),
  [Memory measurement](memory-measurement.md) (reuses the solver runner of
  Part 2 and the metadata of Part 1),
  [Solver performance](../guide/performance.md),
  [Benchmarking](../guide/benchmarking.md), [Architecture](../guide/architecture.md)

Two parts. Part 1 is small and useful for the thesis on its own, so do it
first; Part 2 builds on it (the metadata is how a result says it ran under
PyPy).

---

## Part 1: record where and how every run happened

### Goal

Every solve job and every benchmark records the machine and the software it
ran on, shows it in the UI and carries it into the CSV, so a result table can
say exactly what produced it and two benchmarks from different machines are
never compared by accident.

### What to record

Collected once per job, inside the process that runs the solver (so it shows
PyPy when PyPy is used):

| Field | Example | How (standard library only) |
|---|---|---|
| `python_implementation` | `CPython` / `PyPy` | `platform.python_implementation()` |
| `python_version` | `3.11.15` | `platform.python_version()` |
| `os` | `Linux 6.8 (x86_64)` | `platform.system()`, `platform.release()`, `platform.machine()` |
| `cpu_model` | `AMD Ryzen 7 5800U` | Linux: `model name` in `/proc/cpuinfo`; macOS: `sysctl -n machdep.cpu.brand_string`; Windows: registry `HKLM\HARDWARE\DESCRIPTION\System\CentralProcessor\0\ProcessorNameString` (`winreg`); fall back to `platform.processor()` |
| `cpu_logical_cores` | `16` | `os.cpu_count()` |
| `cpu_physical_cores` | `8` or `null` | Linux: distinct `(physical id, core id)` pairs in `/proc/cpuinfo`; elsewhere `null` unless cheap |
| `ram_total_gb` | `15.5` | POSIX: `os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")`; Windows: `ctypes` `GlobalMemoryStatusEx` |
| `wizsat_version` | `2.0.0` | today `VERSION` in `sat_web/api.py`; move it to `sat_core` so the job process can read it |
| `git_commit` | `9e11958` or `null` | `git rev-parse --short HEAD` in the repo root, if git is there |
| `git_dirty` | `true` / `false` / `null` | `git status --porcelain` is not empty |
| `workers` | `1` | benchmark request (parallel cases) |
| `started_at` | ISO time with zone | already stored on the job |

- **Hostname:** not recorded by default (CSV files get shared). If wanted, an
  opt-in setting such as `WIZSAT_RECORD_HOSTNAME=1`.
- No new runtime dependency (`psutil` would make this easier, but the project
  avoids dependencies). Every lookup is wrapped so a failure gives `null`, never
  an error.
- Cache the result per process: CPU model and RAM do not change during a job.

### Where it goes

- [ ] New module `sat_core/environment.py` with `run_environment() -> dict`
  (pure standard library; no `sat_web` import).
- [ ] `sat_core/jobs.py`: `run_job` sends it once at the start (a new
  `EVENT_ENVIRONMENT`, or inside the existing plan/instance payload).
- [ ] `sat_web/store.py`: a new JSON column `environment` on `jobs`. The table
  is created with `CREATE TABLE IF NOT EXISTS`, so existing databases need a
  small migration: `ALTER TABLE jobs ADD COLUMN environment TEXT` when the
  column is missing.
- [ ] `sat_web/manager.py`: keep it on `Job`, include it in `detail()` (not in
  the summary list, it is not needed there).
- [ ] `frontend/src/api/types.ts`: `environment` on `JobDetail` (nullable: jobs
  from before this change have none and show "not recorded").
- [ ] UI: a "Machine" block in the solve job's Settings tab
  (`components/SolverSettingsTable.tsx` area) and in the benchmark Setup tab
  (`components/BenchmarkSetup.tsx`).
- [ ] CSV (`rows_to_csv` in `sat_core/benchmark.py`): a few columns per row,
  for example `python`, `cpu`, `cores`, `ram_gb`, `os`, `wizsat_commit`.
  Per-row columns (not header comments) keep the file a valid CSV and keep the
  information when benchmarks from different machines are exported together
  with `/api/export.csv?jobs=...`.
- [ ] Docs: `docs/guide/benchmarking.md` (CSV columns, "what to report"),
  `docs/guide/api.md` (job detail), `docs/report/benchmark-plan.md` (record
  the machine).

### Tests

- [ ] `run_environment()` returns every key, values are JSON-serialisable, and
  it does not raise when `/proc/cpuinfo` or git is missing (patch them away).
- [ ] An API test: a finished job's detail has `environment` with
  `python_implementation`.
- [ ] A benchmark CSV has the new columns.
- [ ] Opening a database created before the change works (the migration).

---

## Part 2: opt-in PyPy for the solver processes

### Why

PyPy runs the solvers unchanged and is about 3x faster on runs that take
seconds (measured, see below). It is slower on very short runs because its JIT
compiler needs to warm up.

### Measurements (2026-10-19)

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

### Goal

With a setting such as `WIZSAT_SOLVER_PYTHON=/path/to/pypy3`, every solver run
(solve jobs, benchmarks, parallel benchmark workers) happens in a child process
of that interpreter. Without the setting nothing changes. The server itself
stays on CPython.

### Design

- **One switch point:** `run_solver()` in `sat_core/solver_registry.py`. Solve
  jobs (`sat_core/jobs.py`), benchmark cases (`run_case` in
  `sat_core/benchmark.py`) and parallel workers (`sat_core/parallel.py`) all go
  through it, so one change covers every path.
- **Child process:** a new module, for example `sat_core/solver_process.py`, run as
  `[WIZSAT_SOLVER_PYTHON, "-m", "sat_core.solver_process"]` with the repo root
  as working directory. It imports only `solvers/` and `sat_core` (no FastAPI),
  so PyPy needs nothing installed beyond itself.
- **Protocol:** JSON over pipes.
  - In: `{"clauses", "solver", "options", "log_level", "progress_interval",
    "timeout"}` on stdin.
  - Out: one JSON object per line on stdout. `{"type": "log", "message"}` for
    each log line, then one `{"type": "result", "status", "solution", "stats",
    "error"}`.
  - The model's keys become strings in JSON; convert them back to ints.
- **Cancel, skip, timeout:**
  - The parent reads the child's output on a thread.
  - While waiting, it checks `stop_requested(cancel_token)` every ~50 ms. On
    cancel or skip it kills the child and returns `CANCELLED` / `SKIPPED`.
  - The child enforces the timeout itself (a `RunToken` with
    `timeout_seconds`). The parent also kills it a little after the timeout,
    in case it hangs.
- **Errors:** a child that exits without a result gives status `ERROR` with its
  stderr tail, like any solver failure today (`run_solver` never raises).
- **Data size:** at the 2,000,000-clause limit the JSON input is a few tens of
  MB. That is acceptable, but measure the cost on a large case.
- **Metadata:** the child sends `run_environment()` (Part 1) with its result,
  so jobs and rows show `PyPy 3.x`.
- **UI:** a small badge in the Settings and Setup tabs, from the metadata.
  Nothing else changes.
- **Docs:**
  - `docs/guide/performance.md`: a PyPy section with the table above and the
    warm-up caveat.
  - `docs/guide/benchmarking.md`: what to report.
  - `README.md`: how to install PyPy and set the variable.
  - `AGENTS.md`: the new module and setting.

### Steps

- [ ] Part 1 done (metadata), so results can show the interpreter.
- [ ] `sat_core/solver_process.py` (child) and the subprocess path in
  `run_solver` behind the setting.
- [ ] Tests using `sys.executable` (CPython) as `WIZSAT_SOLVER_PYTHON`. This
  checks the protocol, logs, cancel, skip, timeout and the ERROR path without
  needing PyPy installed.
- [ ] Optional CI job: `actions/setup-python` with `pypy3.10`, running
  `tests/test_solver_agreement.py` under PyPy, plus one API test with the
  setting on.
- [ ] Re-run the measurement table with PyPy 3.10 or newer on the target machine
  and put it in `docs/guide/performance.md`.

### Getting PyPy (3.10 or newer)

- **Linux/macOS/Windows:** official builds at https://pypy.org/download.html
  (unpack, no installer). Conda: `conda install -c conda-forge pypy3.10`.
- **Distribution packages** may be older: Ubuntu's `pypy3` was 3.9 in
  October 2026, too old for this repo.
- **In GitHub Actions:** `actions/setup-python` with `python-version:
  pypy3.10`.
- The solvers use only the standard library, so no `pip install` is needed
  in PyPy.

### Rules for results (thesis)

- Keep CPython as the reference interpreter for reported results.
- The setting is global, so every solver in a benchmark uses the same
  interpreter. Never compare a PyPy run of one solver with a CPython run of
  another: that measures the runtime, not the algorithm.
- If PyPy results are reported, say so, and note the warm-up effect: PyPy
  is slower on runs under about half a second, which can change the ranking on
  small instances.

### Considered and rejected

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
