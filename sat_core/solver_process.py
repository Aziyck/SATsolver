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
WIZSAT_SOLVER_PYTHON is set. The child cannot see the parent's cancel token,
so the parent watches it while it waits: a cancel or a skip kills the child,
and so does a child still running KILL_MARGIN_SECONDS past its timeout
(measured from its first log line, when the child's own clock has started).
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
import time
from typing import Any, Callable, TextIO

from sat_core.models import STATUS_TIMEOUT
from sat_core.runtime import EVENT_LOG, RunEvent, RunToken, cancellation_status, emit, stop_requested
from sat_core.solver_registry import SOLVER_PYTHON_ENV, run_solver

ROOT = Path(__file__).resolve().parents[1]
STDERR_TAIL_LINES = 20
# How often the waiting parent looks at the cancel token.
POLL_SECONDS = 0.05
# The child enforces the timeout itself. The parent kills it only when it is
# still running this long after its limit: a hung child, or a solver that does
# not reach a stop check in time (either way the run is over its limit).
KILL_MARGIN_SECONDS = 1.0
# The child's clock starts after its interpreter has started and it has parsed
# the request, and its first log line comes right then. The parent measures
# the limit from that line; until it arrives, it allows this much for the
# start-up (seconds near the clause limit) before it counts a child as hung.
START_UP_SECONDS = 60.0
# Why the parent killed the child ("killed" in the result line it makes).
KILLED_BY_TOKEN = "token"  # the caller's cancel token: cancel, skip or its own timeout
KILLED_BY_TIME_LIMIT = "time limit"  # still running KILL_MARGIN_SECONDS past the request's timeout


def run_in_child(
    python: str,
    request: dict[str, Any],
    event_callback=None,
    cancel_token: RunToken | None = None,
) -> tuple[dict[str, Any] | None, str]:
    """
    Run one request in a child process of `python`; return (its result line, the end of its stderr).

    The result line is None when the child ended without one. Log lines reach
    event_callback on the calling thread as they arrive. The request is not
    checked here: run_solver validates it before it calls this.

    A cancel or skip on cancel_token, or a child still running
    KILL_MARGIN_SECONDS past the request's timeout, kills the child. The
    result line is then made here, with the stop's status, no solution or
    stats, and "killed" set to KILLED_BY_TOKEN or KILLED_BY_TIME_LIMIT. A
    result the child had already sent wins over a stop.
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
    # Encoded here, so a request that cannot be encoded raises to the caller.
    text = json.dumps(request)
    timeout = request.get("timeout")
    lines: queue.Queue[str | None] = queue.Queue()
    stderr_tail: deque[str] = deque(maxlen=STDERR_TAIL_LINES)
    result = None
    stop_status = killed_by = None
    first_line_at = None
    started = time.perf_counter()

    def take(line: str) -> dict[str, Any] | None:
        """Handle one stdout line; return it when it is the result."""

        nonlocal first_line_at
        if first_line_at is None:
            first_line_at = time.perf_counter()
        message = json.loads(line)
        if message["type"] == "log":
            emit(event_callback, EVENT_LOG, message["message"])
        elif message["type"] == "result":
            return message
        return None

    def drain() -> dict[str, Any] | None:
        """Handle the lines already queued; return the result if one is among them."""

        while True:
            try:
                line = lines.get_nowait()
            except queue.Empty:
                return None
            if line is None:
                return None
            message = take(line)
            if message is not None:
                return message

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
        # either pipe while nobody reads it would block. The request is
        # written on a thread too: a big one takes seconds to go through the
        # pipe, and a stop must not wait for that.
        threads = [
            threading.Thread(target=_read_lines, args=(child.stdout, lines.put, lines.put), daemon=True),
            threading.Thread(target=_read_lines, args=(child.stderr, stderr_tail.append, None), daemon=True),
            threading.Thread(target=_write_request, args=(child.stdin, text), daemon=True),
        ]
        for thread in threads:
            thread.start()
        try:
            while True:
                try:
                    line = lines.get(timeout=POLL_SECONDS)
                except queue.Empty:
                    line = ""
                if line is None:
                    break
                if line and (result := take(line)) is not None:
                    # The run is over: a stop that comes now changes nothing.
                    break
                # Checked after every line as well: a chatty child may never
                # leave the queue empty.
                stop = _stop_reason(cancel_token, timeout, started, first_line_at)
                if stop is not None:
                    # The child may have finished already, with its result
                    # queued behind log lines not read yet: that result wins.
                    result = drain()
                    if result is None:
                        stop_status, killed_by = stop
                    break
        finally:
            # Also reached after the result line: the child is exiting then,
            # and a kill only saves the wait.
            if child.poll() is None:
                child.kill()
            child.wait()
            for thread in threads:
                thread.join(timeout=5)
    if stop_status is not None:
        result = {
            "type": "result",
            "status": stop_status,
            "solution": None,
            "stats": {},
            "error": None,
            "elapsed": time.perf_counter() - (first_line_at or started),
            "killed": killed_by,
        }
    return result, "".join(stderr_tail).strip()


def _stop_reason(
    cancel_token: RunToken | None, timeout: float | None, started: float, first_line_at: float | None
) -> tuple[str, str] | None:
    """(status, KILLED_BY_*) to kill the child with, or None while it may go on."""

    if stop_requested(cancel_token):
        return cancellation_status(cancel_token), KILLED_BY_TOKEN
    if timeout is None:
        return None
    clock_start = first_line_at if first_line_at is not None else started + START_UP_SECONDS
    if time.perf_counter() > clock_start + timeout + KILL_MARGIN_SECONDS:
        return STATUS_TIMEOUT, KILLED_BY_TIME_LIMIT
    return None


def _write_request(stdin: TextIO, text: str) -> None:
    try:
        stdin.write(text)
        stdin.close()
    except OSError:
        # The child ended (or was killed) before reading its request, so it
        # has no result. Close again: the first close may have failed while
        # flushing, and Popen's own close would raise the same error.
        with contextlib.suppress(OSError):
            stdin.close()


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
