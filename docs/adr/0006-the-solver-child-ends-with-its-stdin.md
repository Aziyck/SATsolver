# 0006. The solver child ends when its stdin reaches its end

- **Status:** Accepted (2026-11-22)
- **Decided by:** the repository owner

## Context

With `WIZSAT_SOLVER_PYTHON` set, every solver run happens in a child process
that `subprocess` starts (`sat_core/solver_process.py`,
[plan](../plans/pypy-solver-runner.md)). The parent, `run_in_child`, kills
the child when a run is cancelled, skipped or over its time limit. A parent
that is itself ended never gets to: the manager's force stop and
`shutdown()` terminate job processes, and a pool worker whose job died
leaves through `os._exit`. Neither Windows nor POSIX ends a child when its
parent ends, so the child ran on, with no one to read its result and, with
no timeout, for ever (RUNNER-5).

The child is outside `multiprocessing`, so the watchdog that job processes
and pool workers use (`exit_when_parent_dies` in `sat_core/parallel.py`)
does not apply to it.

## Decision

The child's stdin is its lifeline. The parent writes the request as one
line and keeps the write end of the pipe open until the run is over. The
child reads that one line, then a thread blocks on stdin; when it reaches
the end of stdin, the child ends itself with `os._exit`
(`exit_when_stdin_closes`).

The operating system closes a process's pipes however the process ends, so
the end of stdin arrives when the parent closes it after the run, or when
the parent dies in any way. When the parent stops a run itself (cancel,
skip, time limit, a broken line), it closes stdin right after it kills the
child: if the interpreter path is a wrapper that started the real
interpreter as its own child, the kill ends the wrapper alone, and the real
interpreter ends at the end of its stdin. Only the parent holds the write end: Python
creates pipes that later children do not inherit (PEP 446 on POSIX; on
Windows `Popen` makes only the child's own ends inheritable).

Code that starts the child keeps stdin open until the child has ended.
`subprocess.run(input=...)`, `communicate()` and `echo request |` close it
right after the request, and the child then ends without a result.

## Alternatives considered

- **A watchdog thread in the child that watches its parent** (built first,
  in pull request #63). On POSIX it polled `os.getppid()`; on Windows it
  waited on a handle to the parent through `ctypes`. On Windows a venv's
  `python.exe` is a launcher that starts the real interpreter as its own
  child and outlives a killed parent, so the child had to be told the real
  parent's pid in an environment variable. Each platform then needed its
  own guard against a reused pid, and a POSIX wrapper that forks the
  interpreter (instead of `exec`) left a check that a zombie or a reused pid
  fools. More code, two mechanisms, and still a gap.
- **A Windows job object with "kill on job close", set up by the parent.**
  The operating system kills the child the moment the parent ends, launcher
  included. But it works on Windows only, and needs a large `ctypes`
  structure and a short window between starting the child and assigning it
  to the job. POSIX would need its own mechanism: Linux's
  `PR_SET_PDEATHSIG` fires when the parent *thread* that started the child
  ends, not the process, which is wrong for `run_in_child` (it runs on
  different threads); it has to be set in `preexec_fn`, which is unsafe in
  a process with threads; and macOS has no equivalent.
- **The parent's pid in the JSON request** instead of in the environment
  (a variant of the watchdog). The child reads the request first, so a
  parent that died while sending a large request would not be watched yet.

## Consequences

- One mechanism on every platform, with no pids, no `ctypes` and no
  polling, and nothing a launcher or wrapper in between can break: they
  pass the pipe on.
- The protocol's input side changed: the request is one line, and stdin is
  not closed after it. Every script that plays the child in a test reads
  one line (`sys.stdin.readline()`), and every test that starts the child
  keeps stdin open until it has read the result (`start_child` in
  `tests/test_solver_process.py`).
- Running the child by hand needs a pipe that stays open; a quick
  `echo ... | python -m sat_core.solver_process` ends without a result.
- To watch: anything that hands the write end of the pipe to another
  process (an inheritable duplicate, a fork without exec) would keep the
  pipe open after the parent dies and silently disable the lifeline.
