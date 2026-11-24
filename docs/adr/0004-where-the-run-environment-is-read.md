# 0004. The server reads the machine once; each job reads its interpreter and git

- **Status:** Accepted (2026-11-19)
- **Decided by:** the repository owner

## Context

Every job records the machine and software it ran on
([run-metadata plan](../plans/done/run-metadata.md)). META-2 read all of it in the
job's worker, a fresh `spawn` process, so nothing was cached between jobs. On
the owner's Windows machine that took 193-232 ms per job before any work
started (audit item A39). The CPU lookup and two git calls were the largest
parts. The facts do not all change at the same rate:

- the OS, the CPU and the RAM stay the same while the server runs;
- the interpreter is the one that runs the job, which may later differ from
  the server's (PyPy, see the [solver runner plan](../plans/done/pypy-solver-runner.md));
- the code a job runs is whatever is on disk when its worker starts, because
  a `spawn` worker imports every module again. The server does not reload,
  but its workers do.

## Decision

The server reads the machine facts once with `machine_facts()`
(`sat_core/environment.py`) when `JobManager` starts. It passes them to
`run_job` for every job. The worker adds the interpreter facts and the git
facts with `run_environment(machine)`, and it runs git once per job
(`git status --porcelain=v2 --branch`).

## Alternatives considered

- **Read git once at server start too.** Set aside: the owner edits code
  while the server runs. The next job would run the edited solver and still
  be recorded under the startup commit with a clean tree. The record exists
  to keep results like these apart.
- **Read everything in the worker, as META-2 did.** Set aside: it repeats
  about 130 ms of lookups that cannot change, on every job.
- **Read everything in the server and pass it in.** Set aside: the
  interpreter facts must come from the process that runs the solver.

## Consequences

- A job spends 70-95 ms on its environment instead of 193-232 ms, as
  measured on the owner's machine.
- Starting the server costs the machine lookup once (about 100 ms).
- If the server ever runs a job on another machine, that job has to read
  its own machine facts: `run_environment()` without an argument still does.
- A commit made while the server runs shows up in the next job, because
  each job asks git again.
