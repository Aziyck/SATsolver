"""
One solver run in its own process, from JSON to JSON.

Started as `python -m sat_core.solver_process` with the repository root as the
working directory. It reads one request object from stdin, runs the solver
with run_solver, and writes one JSON object per line to stdout:

    {"type": "log", "message": "..."}                       once per log line, as it happens
    {"type": "result", "status", "solution", "stats",
     "error", "elapsed"}                                    last, once

The request is {"clauses", "solver", "options", "log_level",
"progress_interval", "timeout"}, and optionally "label" (the name the log
lines use, as run_solver's label). The child reads stdin to its end before it
starts, so the parent closes stdin after writing the request. "timeout" is
enforced here, by run_solver; its clock starts after the interpreter has
started and the request has been parsed, which can take seconds for a
formula near the clause limit. A parent that kills a hung child counts that
in its margin.

Nothing else may reach stdout, so the parent can read it line by line: while a
run is going, sys.stdout points at stderr, so a stray print() lands there. That
guards Python-level writes only; the solvers are pure Python, so nothing
writes to file descriptor 1 behind it. The parent must read stderr too (on
its own thread), or a chatty run could fill the pipe and block. The model's
variable numbers become strings in JSON (the parent turns them back into
ints). Input is read as UTF-8, whatever the platform default is; output is
plain ASCII (json escapes the rest).

The module imports only sat_core and solvers (no web framework), so the
interpreter that runs it needs nothing installed beyond itself. A request that
cannot run (broken JSON, an unknown solver, invalid options) ends the process
with a traceback on stderr and no result line. The parent validates the
request before starting the child, so run_solver's ValueError for those
mistakes still reaches the caller; a child that ends without a result anyway
is reported as an ERROR run.

The parent side is run_in_child, which run_solver calls when
WIZSAT_SOLVER_PYTHON is set.
"""

from __future__ import annotations

from collections import deque
import contextlib
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
from typing import Any, Callable, TextIO

from sat_core.runtime import EVENT_LOG, RunEvent, emit
from sat_core.solver_registry import SOLVER_PYTHON_ENV, run_solver

ROOT = Path(__file__).resolve().parents[1]
STDERR_TAIL_LINES = 20


def run_in_child(python: str, request: dict[str, Any], event_callback=None) -> tuple[dict[str, Any] | None, str]:
    """
    Run one request in a child process of `python`; return (its result line, the end of its stderr).

    The result line is None when the child ended without one. Log lines reach
    event_callback on the calling thread as they arrive. The request is not
    checked here: run_solver validates it before it calls this.
    """

    # Without the setting the child runs the solver itself instead of starting
    # a child of its own. Its stderr would be in the locale code page on
    # Windows; UTF-8 keeps the error tail readable.
    env = {name: value for name, value in os.environ.items() if name != SOLVER_PYTHON_ENV}
    env["PYTHONIOENCODING"] = "utf-8"
    if os.path.dirname(python):
        # Popen runs the child in ROOT, and a relative path would be looked up
        # there on POSIX but in our own folder on Windows: fix it to ours.
        python = os.path.abspath(python)
    lines: queue.Queue[str | None] = queue.Queue()
    stderr_tail: deque[str] = deque(maxlen=STDERR_TAIL_LINES)
    result = None
    with subprocess.Popen(
        [python, "-m", "sat_core.solver_process"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        # A byte that is not UTF-8 must not kill a reader thread: nobody would
        # drain that pipe any more, and the child would block on it.
        errors="replace",
        cwd=ROOT,
        env=env,
    ) as child:
        # Both pipes are read on threads from the start: a child that fills
        # either pipe while nobody reads it would block.
        readers = [
            threading.Thread(target=_read_lines, args=(child.stdout, lines.put, lines.put), daemon=True),
            threading.Thread(target=_read_lines, args=(child.stderr, stderr_tail.append, None), daemon=True),
        ]
        for reader in readers:
            reader.start()
        try:
            try:
                child.stdin.write(json.dumps(request))
                child.stdin.close()
            except OSError:
                # The child ended before reading its request, so it has no
                # result. Close again: the first close may have failed while
                # flushing, and Popen's own close would raise the same error.
                with contextlib.suppress(OSError):
                    child.stdin.close()
            while (line := lines.get()) is not None:
                message = json.loads(line)
                if message["type"] == "log":
                    emit(event_callback, EVENT_LOG, message["message"])
                elif message["type"] == "result":
                    result = message
        finally:
            if child.poll() is None:
                child.kill()
            child.wait()
            for reader in readers:
                reader.join(timeout=5)
    return result, "".join(stderr_tail).strip()


def _read_lines(stream: TextIO, sink: Callable[[str], None], at_end: Callable[[None], None] | None) -> None:
    # at_end runs however the reading ends, so the waiting parent always wakes up.
    try:
        for line in stream:
            sink(line)
    finally:
        if at_end is not None:
            at_end(None)


def serve(request: dict[str, Any], out: TextIO) -> None:
    """Run the request and write its log lines and its result to `out`."""

    def write(line: dict[str, Any]) -> None:
        out.write(json.dumps(line) + "\n")
        out.flush()  # the parent shows log lines while the solver runs

    def on_event(event: RunEvent) -> None:
        # Solvers send only log lines; anything else has no meaning to the parent.
        if event.type == EVENT_LOG:
            write({"type": "log", "message": event.message})

    result = run_solver(
        request["clauses"],
        request["solver"],
        request.get("options"),
        timeout=request.get("timeout"),
        log_level=request.get("log_level", "normal"),
        progress_interval=request.get("progress_interval"),
        event_callback=on_event,
        label=request.get("label"),
    )
    write(
        {
            "type": "result",
            "status": result.status,
            "solution": result.solution,
            "stats": result.stats,
            "error": result.error,
            "elapsed": result.elapsed,
        }
    )


def main(stdin: TextIO | None = None, stdout: TextIO | None = None) -> int:
    stdin = stdin if stdin is not None else sys.stdin
    stdout = stdout if stdout is not None else sys.stdout
    request = json.loads(stdin.read())

    real_stdout, sys.stdout = sys.stdout, sys.stderr
    try:
        serve(request, stdout)
    finally:
        sys.stdout = real_stdout
    return 0


if __name__ == "__main__":
    # The parent leaves the setting out already; dropping it here as well means
    # a child started any other way cannot start a chain of children.
    os.environ.pop(SOLVER_PYTHON_ENV, None)
    sys.stdin.reconfigure(encoding="utf-8")
    sys.exit(main())
