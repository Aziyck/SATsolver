# 0007. Each job chooses its interpreter; the server finds PyPy

- **Status:** Accepted (2026-11-23)
- **Decided by:** the repository owner

## Context

The solvers can run in a child process of PyPy, about 3 times faster on runs
of several seconds and slower on runs under a second
([solver runner plan](../plans/done/pypy-solver-runner.md)). At first the setting
`WIZSAT_SOLVER_PYTHON` sent every run of every job to PyPy for as long as the
server ran, so comparing the two interpreters, or using PyPy only for long
runs, meant restarting the server. The owner wanted to choose in the UI, per
job. The browser cannot name a program to start: the server has no login, and
any page that reaches it could then make it run any program.

## Decision

- The server finds PyPy itself, once, when it starts: `WIZSAT_SOLVER_PYTHON`
  when set, otherwise the first of `pypy3` and `pypy` on `PATH`, accepted only
  when it answers PyPy with Python 3.10 or newer (`find_pypy()`,
  `sat_core/environment.py`). The catalog says whether it is available and
  its version, never its path.
- A solve or benchmark request names `"interpreter": "python"` or `"pypy"`;
  a missing field means Python. The setting only makes PyPy available.
- The choice belongs to the whole job: the job process sets or clears the
  variable in itself before any run (`choose_solver_python()`,
  `sat_core/jobs.py`), and its pool workers inherit it. One benchmark never
  mixes interpreters.
- Python is the default, and the forms do not remember a PyPy choice between
  visits: CPython is the interpreter of reported results.
- A job's interpreter is its request's choice, or, for a job saved before the
  field existed, the one its environment record names
  (`recorded_interpreter()`, `sat_core/jobs.py`): Rerun and the job summary
  use that one rule, and the forms read the summary. It names the choice;
  the environment record names what really ran.

## Alternatives considered

- **A path typed in the browser.** Set aside: a request that names a program
  to run is a hole in a server without a login.
- **The setting forces PyPy, as before.** Set aside: switching needs a
  restart, and a benchmark started from the UI cannot say which it wants.
- **Per solver or per case inside one benchmark.** Set aside: the times would
  then measure the interpreter, not the algorithm.
- **Pass the found path from the server to each job.** Set aside: it goes
  through `sat_web/manager.py` for nothing; the job process finds the same
  first candidate with the same lookup.
- **PyPy as the default, or the last choice remembered.** Set aside: it makes
  it easy to start a thesis benchmark on the wrong interpreter without
  noticing.

## Consequences

- A server started with `WIZSAT_SOLVER_PYTHON` runs a job on PyPy only when
  the job asks for it.
- Installing PyPy, or fixing a PyPy that did not answer the probe in time,
  needs a server restart.
- When the first `pypy3` on `PATH` is not a usable PyPy, a usable `pypy` after
  it is not used: the job takes the first candidate without probing it again,
  so the server must judge that same one.
