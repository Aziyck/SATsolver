# Plan: choose Python or PyPy per job, in the UI

- **Status:** done (2026-11-23)
- **Written:** 2026-11-23
- **Related:** [solver runner](../pypy-solver-runner.md) (the child process and
  `WIZSAT_SOLVER_PYTHON`), [Solver performance](../../guide/performance.md#running-the-solvers-under-pypy),
  [Architecture](../../guide/architecture.md)
- Item format, difficulty and closing rule: [README.md](../README.md)

## Goal

The Solve form and the benchmark builder get a switch, **Run with: Python |
PyPy**. The choice belongs to the job: every run of that job, in every
worker, uses the chosen interpreter. The switch starts on Python. When the
server finds no PyPy, PyPy is greyed out with a hint on how to install it.

## Why

Today `WIZSAT_SOLVER_PYTHON` sends every run of every job to PyPy for as long
as the server runs. Comparing the two interpreters, or using PyPy only for
the long runs, means restarting the server with a different environment.

## Non-goals

- A path typed in the browser. The server finds the interpreter; the browser
  only says "python" or "pypy".
- Choosing per solver or per case inside one benchmark: the times would then
  measure the interpreter, not the algorithm (rule in the runner plan,
  "Rules for results").
- Installing PyPy from the app. `pip` cannot install it (it is an
  interpreter, not a package); the hint links to pypy.org and conda.
- Interpreters other than PyPy (several CPython versions, for example).

## Design

- **Finding PyPy (decided 2026-11-23):** `WIZSAT_SOLVER_PYTHON` when set,
  otherwise the first of `pypy3`, `pypy` on `PATH`. The candidate counts only
  when `interpreter_facts()` (`sat_core/environment.py`) answers `PyPy` with
  Python 3.10 or newer. Looked up once when the server starts; installing
  PyPy later needs a restart.
- **Meaning of the setting changes:** `WIZSAT_SOLVER_PYTHON` now makes PyPy
  *available*; it no longer forces it on every job. A job without the field
  runs on Python. README and the user guide say so.
- **Default (decided 2026-11-23):** Python. CPython stays the reference for
  reported results; PyPy is chosen per job.
- **Catalog:** `GET /api/catalog` gains
  `"interpreters": {"pypy": {"available": bool, "version": str | null}}`.
  Never the path: the browser does not need it, and it names a folder of the
  owner's disk.
- **Request:** solve and benchmark jobs take `"interpreter": "python" | "pypy"`
  (missing means `"python"`). An unknown value, or `"pypy"` when none was
  found, is a `ParamError` at submit (HTTP 422, like every field error), so it never becomes a job
  that fails later. Stored with the request, so Rerun keeps it.
- **Applying it:** every job already runs in a fresh job process
  (`sat_web/manager.py`). At the start of `execute_job` (`sat_core/jobs.py`)
  the job process sets `WIZSAT_SOLVER_PYTHON` in its own environment to the
  PyPy path, or removes it, before the environment probe. `run_solver` reads
  the setting as today, and pool workers started by that job inherit it, the
  way the setting reaches them since RUNNER-5. The manager, the pool and the
  child protocol do not change. The job process finds the path itself with
  the same lookup, so the path does not travel through the manager either.
- **Showing it:** job detail and CSV already name the solver interpreter
  (RUNNER-6). The job list gets a small "PyPy" badge on PyPy jobs.

## Tasks

- [x] **INTERP-1. The server finds PyPy and says so in the catalog** - Done 2026-11-23.
  - **Difficulty:** medium
  - **Built as:** `find_pypy()` in `sat_core/environment.py`; `catalog()` in
    `sat_web/api.py` reports `interpreters.pypy`. Rulings: a setting that is
    set but unusable gives "not available" and does not fall back to `PATH`
    (a wrong setting must show); the catalog, with its probe, is built once
    when the server starts (FastAPI lifespan); a probe that times out stays
    "not available" until a restart; the `PATH` lookup skips the current
    folder (Windows `shutil.which` searches it first).
  - **How:** a `find_pypy()` in `sat_core/environment.py` returning the path
    and version, or None, by the lookup in the Design; the catalog reports
    availability and version, not the path.
  - **Done when:** tests with the stand-in interpreter of
    `tests/fake_python.py` show: the setting wins over `PATH`; a `pypy3` on
    `PATH` is found when the setting is unset; a candidate that answers
    `CPython`, or PyPy older than 3.10, or does not answer, is not
    available; `GET /api/catalog` carries `interpreters.pypy` and no path.

- [x] **INTERP-2. A job runs on the interpreter its request names** - Done 2026-11-23.
  - **Difficulty:** medium
  - **Built as:** `parse_interpreter()` (`sat_core/solver_registry.py`) is used by
    the solve and benchmark parsers, so the normalized request always carries
    `interpreter`; `validate_job` (`sat_web/api.py`) refuses `pypy` when the
    catalog says none was found; `choose_solver_python()` (`sat_core/jobs.py`)
    sets or clears the variable in the job process from `pypy_path()`,
    without probing again; `find_pypy()` judges only that first candidate,
    so the server and the job agree. Rerun of a job saved without the field
    takes the interpreter from its environment record. Until INTERP-3, only an API request can choose PyPy.
  - **Not hard:** the job process sets an environment variable in itself
    before any run starts; `sat_web/manager.py`, `sat_core/parallel.py` and
    `sat_core/solver_process.py` are not changed, and the pool workers get
    the setting by inheritance as they already do (RUNNER-5).
  - **Blocked by:** INTERP-1
  - **Done when:** API tests, with the stand-in interpreter as PyPy, show:
    a solve job and a `workers: 2` benchmark with `"interpreter": "pypy"`
    record the stand-in interpreter in the job detail and the CSV; the same
    requests without the field, or with `"python"`, record the server's
    interpreter even while `WIZSAT_SOLVER_PYTHON` is set; `"pypy"` with none
    found, and an unknown value, get 422, as every field error does (the plan first said 400); Rerun keeps
    the choice.
    `docs/guide/api.md`, `README.md` (the setting's new meaning) and
    `docs/guide/how-it-works.md` updated.

- [x] **INTERP-3. The switch on the Solve form and the benchmark builder** - Done 2026-11-23.
  - **Difficulty:** medium
  - **Blocked by:** INTERP-2
  - **How:** a SegmentedControl "Run with" (Python | PyPy, with the version)
    sent as `interpreter`; PyPy disabled with a tooltip ("PyPy not found.
    Install it from pypy.org, then add its folder to PATH or set
    WIZSAT_SOLVER_PYTHON, and restart the server.")
    when the catalog says it is unavailable; a "PyPy" badge in the job list.
  - **Built as:** `InterpreterSwitch` (`components/InterpreterSwitch.tsx`) on
    the Solve page (inside `SolverPanel`) and in the benchmark builder's run
    settings; `lib/interpreter.ts` (`effectiveInterpreter`, `interpreterOf`).
    The choice lives in page state, not in the stored settings or the draft,
    so every visit starts on Python (the rejected "last choice remembered");
    Edit and "copy as new" bring back the interpreter of that job. The
    Setup tab of a benchmark shows "Run with". The hint is visible text under
    the switch, not a tooltip (a tooltip does not reach touch or keyboard
    users). **The job-list badge moved to INTERP-4:** the job summary has no
    interpreter, and adding it is a change in `sat_web/manager.py`, a hard
    trigger.
  - **Done when:** component tests show the request carries the choice, the
    switch starts on Python, and PyPy is disabled when unavailable; an e2e
    test (server started with the stand-in as `WIZSAT_SOLVER_PYTHON`) runs a
    solve with PyPy chosen and sees the stand-in interpreter on the job
    detail. `docs/guide/user-guide.md` updated.

- [x] **INTERP-4. A "PyPy" badge in the job list** - Done 2026-11-23.
  - **Difficulty:** hard (`sat_web/manager.py`: `Job.summary`)
  - **Blocked by:** INTERP-3
  - **How:** the job summary gains `interpreter` (`"python"` or `"pypy"`: the
    request's choice, and for a job saved before INTERP-2 the one its
    environment record names); the jobs drawer and the Jobs page show a small
    "PyPy" badge on PyPy jobs. `docs/guide/api.md` (job summary) and the wire
    samples updated.
  - **Done when:** an API test shows the summary of a PyPy job and of a Python
    job, and of a job saved without the field that ran on PyPy; a component
    test shows the badge on the first and not on the others.
  - **Built as:** `recorded_interpreter()` in `sat_core/jobs.py`, one rule
    for `Job.summary` (`sat_web/manager.py`) and Rerun (`sat_web/api.py`);
    `InterpreterBadge` in the jobs drawer and the Jobs page. The summary is
    built from the request, which does not change while a job runs, so no
    new event or lock is involved. Decisions of the plan:
    [ADR 0007](../../adr/0007-each-job-chooses-its-interpreter.md).

## Considered and rejected

- **A path sent from the browser:** any page that reaches the server could
  make it start any program. The server finds the interpreter instead.
- **Setting only, no `PATH` lookup:** works, but the owner has to set the
  variable on every start; the lookup costs one probe at start-up.
- **A launcher flag remembered in `output/` (`--pypy <path>`):** one more
  stored setting to keep in sync with the variable; the `PATH` lookup covers
  the same need.
- **PyPy as the default when available, or the last choice remembered:**
  CPython is the reference for reported results, and a remembered choice
  makes it easy to start a thesis benchmark on the wrong interpreter without
  noticing.
- **Passing the path from the manager to the job process:** touches
  `sat_web/manager.py` (a hard trigger) for nothing, since the job process
  can run the same lookup.
- **Installing PyPy with pip:** not possible; PyPy is an interpreter, not a
  package.
