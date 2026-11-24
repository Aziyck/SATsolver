# Defense questions

Questions the thesis committee may ask at the defense, each with a short
answer to say aloud, the code that backs it, and how well the owner knows it
(kept by the `/defense-questions` skill).

## With WIZSAT_SOLVER_PYTHON set, the solvers run in a separate process. What happens to a run when the process that started it dies, and how do you make sure no orphaned solver keeps running?

- Asked: 2026-11-22
- Answer: Neither Windows nor POSIX ends a child when its parent ends, so a solver child whose job was force-stopped would run on, and without a timeout for ever. The child's stdin is its lifeline: the parent keeps the pipe open for the whole run, and the operating system closes a dead process's pipes however it died. The child sees the end of its stdin and exits. A first version had the child watch its parent's process instead, but that needed different code per OS and broke behind launchers.
- Evidence: `sat_core/solver_process.py:exit_when_stdin_closes`, `sat_core/solver_process.py:run_in_child`, `tests/test_api.py:SolverChildTests.test_a_job_process_that_is_killed_leaves_no_child_behind`, `docs/adr/0006-the-solver-child-ends-with-its-stdin.md`
- Doc gap: none (`docs/guide/how-it-works.md`, "Daemons and the watchdog")
- Confidence: ok

## Why did you end the solver child through its stdin pipe instead of a watchdog that checks the parent, or an OS feature such as Windows job objects or Linux PR_SET_PDEATHSIG?

- Asked: 2026-11-22
- Answer: The watchdog needed the parent's process ID passed in by hand (past a Windows launcher), a different mechanism per OS, and still had gaps: a reused PID or a zombie parent looks alive. Job objects exist only on Windows; Linux's PR_SET_PDEATHSIG fires when the starting thread ends, not the process, and macOS has no equivalent. The pipe is one mechanism on every OS, with no PIDs and no OS-specific code.
- Evidence: `docs/adr/0006-the-solver-child-ends-with-its-stdin.md` ("Alternatives considered"), `docs/plans/done/pypy-solver-runner.md` ("Considered and rejected")
- Doc gap: none (ADR 0006)
- Confidence: shaky

## How do the server side and the solver child talk to each other?

- Asked: 2026-11-22
- Answer: JSON over the child's three standard pipes. The parent sends the request (clauses, solver, options, log level, timeout) as one line on stdin and keeps stdin open; the child writes one JSON line per log message on stdout, then one result line (status, model, statistics, error, elapsed), and exits by itself. stderr carries error text and is read on its own thread so the child never blocks on a full pipe. On cancel, skip or a hung child, the parent kills the child and closes stdin.
- Evidence: `sat_core/solver_process.py` (module docstring), `sat_core/solver_process.py:run_in_child`, `sat_core/solver_process.py:serve`, `sat_core/solver_process.py:main`, `sat_core/solver_protocol.py:parse_line` (the line rules, moved there in RUNNER-11)
- Doc gap: fixed: `docs/guide/how-it-works.md`, "Daemons and the watchdog"
- Confidence: shaky

## Does the design still work when the interpreter is started through a launcher or a wrapper, such as a venv's python.exe on Windows or a script that runs PyPy?

- Asked: 2026-11-22
- Answer: Yes, because the pipes are inherited: the parent starts the launcher or wrapper, and it passes the same stdin and stdout on to the real interpreter. So the end of stdin reaches the process that really runs the solver. One case needed a fix: on a Stop the parent kills only the wrapper, so it closes stdin right after the kill, and the real interpreter then exits too.
- Evidence: `sat_core/solver_process.py:run_in_child` (the `finally` that closes stdin after the kill), `tests/test_solver_process.py:StopReachesTheChildTests.test_a_cancel_reaches_a_child_behind_a_wrapper`
- Doc gap: none (`docs/guide/how-it-works.md`, ADR 0006 "Decision")
- Confidence: shaky

## How is the solver interpreter chosen, and how does the setting reach the processes that run the solvers?

- Asked: 2026-11-22
- Answer: One environment variable, WIZSAT_SOLVER_PYTHON, holds the interpreter's path, for example PyPy. run_solver reads it at every run, in the job or pool worker process, which inherit the server's environment; unset, the solver runs in-process and no child starts. The child never sees the setting: run_in_child removes it from the child's environment, so a child cannot start children of its own.
- Evidence: `sat_core/solver_registry.py:run_solver` (`SOLVER_PYTHON_ENV`), `sat_core/solver_process.py:run_in_child` (the `env` it builds), `sat_core/solver_process.py` (`__main__`)
- Doc gap: none (RUNNER-8 adds the setting to `README.md`)
- Confidence: ok
