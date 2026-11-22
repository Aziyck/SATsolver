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
lines use, as run_solver's label). It comes as one line (json.dumps writes no
line breaks), and stdin then stays open for the whole run: it is the child's
lifeline (below). "timeout" is
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
An interpreter that cannot start, a child that ends without a result and a
line that is not part of the protocol raise SolverProcessError, with a
readable message; run_solver turns it into an ERROR run.

The lifeline (ADR 0006): a parent that is itself ended (a job process
terminated, a pool worker that leaves with os._exit) cannot kill its child.
But the operating system closes every pipe of a process that ends, however
it ends, so the parent keeps the write end of the child's stdin until the
run is over, and the child ends itself when its stdin reaches its end
(exit_when_stdin_closes). A child whose stdin closes early (`echo request |
python -m sat_core.solver_process`) therefore ends without a result.
"""

from __future__ import annotations

from collections import deque
import contextlib
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
from typing import Any, Callable, TextIO

from sat_core.models import STATUS_SAT, STATUS_TIMEOUT, STATUSES
from sat_core.runtime import EVENT_LOG, RunEvent, RunToken, cancellation_status, emit, stop_requested
from sat_core.solver_registry import SOLVER_PYTHON_ENV, run_solver

ROOT = Path(__file__).resolve().parents[1]
STDERR_TAIL_LINES = 20
STDERR_TAIL_CHARACTERS = 2000  # a traceback's end fits; one huge line does not flood the message
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
# The fields every result line carries.
RESULT_FIELDS = ("status", "solution", "stats", "error", "elapsed")
# How much of a broken line an error message quotes.
QUOTED_CHARACTERS = 200


class SolverProcessError(Exception):
    """The child could not start, or ended or broke the protocol without a result. The message is for the user."""


def run_in_child(
    python: str,
    request: dict[str, Any],
    event_callback=None,
    cancel_token: RunToken | None = None,
) -> dict[str, Any]:
    """
    Run one request in a child process of `python`; return its result line.

    Log lines reach event_callback on the calling thread as they arrive. The
    model's variables come back as ints. The request is not checked here:
    run_solver validates it before it calls this.

    SolverProcessError, with a message that carries the end of the child's
    stderr, when the interpreter cannot be started, the child ends without a
    result, or it sends a line that is not part of the protocol (the child is
    killed then: whatever it sends next cannot be trusted either).

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
    text = json.dumps(request) + "\n"
    timeout = request.get("timeout")
    lines: queue.Queue[str | None] = queue.Queue()
    stderr_tail: deque[str] = deque(maxlen=STDERR_TAIL_LINES)
    result = None
    stop_status = killed_by = broken = None
    first_line_at = None
    started = time.perf_counter()

    def take(line: str) -> dict[str, Any] | None:
        """Handle one stdout line; return it when it is the result."""

        nonlocal first_line_at
        if first_line_at is None:
            first_line_at = time.perf_counter()
        message = _parse_line(line)
        if message["type"] == "log":
            emit(event_callback, EVENT_LOG, message["message"])
            return None
        return message

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

    try:
        child = subprocess.Popen(
            [python, "-m", "sat_core.solver_process"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            # A byte that is not UTF-8 must not kill a reader thread: nobody
            # would drain that pipe any more, and the child would block on it.
            errors="replace",
            cwd=ROOT,
            env=env,
        )
    except OSError as exc:
        raise SolverProcessError(_start_failure(python, exc)) from exc
    with child:
        # Both pipes are read on threads from the start: a child that fills
        # either pipe while nobody reads it would block. The request is
        # written on a thread too: a big one takes seconds to go through the
        # pipe, and a stop must not wait for that.
        writer = threading.Thread(target=_write_request, args=(child.stdin, text), daemon=True)
        threads = [
            threading.Thread(target=_read_lines, args=(child.stdout, lines.put, lines.put), daemon=True),
            threading.Thread(target=_read_lines, args=(child.stderr, stderr_tail.append, None), daemon=True),
            writer,
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
                    try:
                        result = drain()
                    except _BrokenLine:
                        # Killed anyway: the stop the user asked for is the answer.
                        result = None
                    if result is None:
                        stop_status, killed_by = stop
                    break
        except _BrokenLine as exc:
            broken = exc.line
        finally:
            # Also reached after the result line: the child is exiting then,
            # and a kill only saves the wait.
            if child.poll() is None:
                child.kill()
            # The lifeline next, before waiting for the readers: when the
            # interpreter path is a wrapper that started the real interpreter
            # as its own child, the kill ended the wrapper alone, and that
            # child, which still holds stdout, ends only when its stdin does.
            # The writer goes first: a close waits for a write in progress.
            writer.join(timeout=5)
            with contextlib.suppress(OSError):
                child.stdin.close()
            child.wait()
            for thread in threads:
                thread.join(timeout=5)
    stderr = "".join(stderr_tail).strip()
    if len(stderr) > STDERR_TAIL_CHARACTERS:
        # The message lands in the log, the database and the page.
        stderr = "..." + stderr[-STDERR_TAIL_CHARACTERS:]
    if broken is not None:
        quoted = broken.strip()
        if len(quoted) > QUOTED_CHARACTERS:
            quoted = quoted[:QUOTED_CHARACTERS] + "..."
        raise SolverProcessError(
            _with_stderr(f"The solver process ({python}) sent a line that is not part of the protocol: {quoted!r}.", stderr)
        )
    if stop_status is not None:
        return {
            "type": "result",
            "status": stop_status,
            "solution": None,
            "stats": {},
            "error": None,
            "elapsed": time.perf_counter() - (first_line_at or started),
            "killed": killed_by,
        }
    if result is None:
        raise SolverProcessError(_with_stderr(f"The solver process ({python}) ended without a result.", stderr))
    return result


class _BrokenLine(Exception):
    def __init__(self, line: str) -> None:
        super().__init__(line)
        self.line = line


def _parse_line(line: str) -> dict[str, Any]:
    """One stdout line as a protocol message (the model's variables as ints), or _BrokenLine."""

    try:
        message = json.loads(line)
    except (ValueError, RecursionError):
        # RecursionError: a deeply nested line. It is not a ValueError.
        raise _BrokenLine(line) from None
    if not isinstance(message, dict):
        raise _BrokenLine(line)
    if message.get("type") == "log" and isinstance(message.get("message"), str):
        return message
    if message.get("type") != "result" or any(field not in message for field in RESULT_FIELDS):
        raise _BrokenLine(line)
    solution, stats = message["solution"], message["stats"]
    if (
        message["status"] not in STATUSES
        or not _is_finite_number(message["elapsed"])
        or not (message["error"] is None or isinstance(message["error"], str))
        or not isinstance(stats, dict)
        # The child sends public_stats: small scalars only. json accepts NaN,
        # which the API's JSON responses refuse.
        or not all(_is_scalar(value) for value in stats.values())
        # A model goes with SAT only, as run_solver does in-process.
        or (solution is not None and (message["status"] != STATUS_SAT or not isinstance(solution, dict)))
    ):
        raise _BrokenLine(line)
    # Only the parent marks a run as killed (run_in_child's own result line).
    message.pop("killed", None)
    if solution is not None:
        # JSON object keys are strings; variables are ints.
        model = {}
        for var, value in solution.items():
            if not (var.isdigit() and int(var) > 0 and isinstance(value, bool)):
                raise _BrokenLine(line)
            model[int(var)] = value
        message["solution"] = model
    return message


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (bool, str)) or _is_finite_number(value)


def _start_failure(python: str, exc: OSError) -> str:
    if isinstance(exc, FileNotFoundError):
        return f"The solver interpreter {python} was not found. Check {SOLVER_PYTHON_ENV}."
    return f"The solver interpreter {python} could not be started ({exc}). Check {SOLVER_PYTHON_ENV}."


def _with_stderr(message: str, stderr: str) -> str:
    return f"{message} Its last output: {stderr}" if stderr else message


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
    # stdin stays open after the request: it is the child's lifeline, closed
    # when the run is over (Popen's `with` block), or by the OS when this
    # process ends.
    try:
        stdin.write(text)
        stdin.flush()
    except OSError:
        # The child ended (or was killed) before reading its request, so it
        # has no result. Close now: the unsent text would make Popen's own
        # close raise the same error while flushing.
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


def exit_when_stdin_closes(stdin: TextIO) -> None:
    """
    Start a daemon thread that ends this process once stdin reaches its end.

    The parent kills the child itself when a run stops, but a parent that is
    killed (the manager's force stop terminates a job process; a pool worker
    leaves with os._exit) never gets to: without this, its child would run
    on, with no one to report to and, without a timeout, for ever. The write
    end of stdin is held by the parent alone (Popen passes a child only its
    own pipes), so its end means the parent closed it or is gone. Nothing
    in between counts: a launcher or wrapper that starts the real
    interpreter as its own child (a venv's python.exe on Windows) passes the
    pipe on, and the signal still comes when the parent ends, or when it
    closes stdin right after killing the wrapper (run_in_child).
    """

    # The file descriptor, not the stream: a daemon thread blocked inside the
    # stream would hold its lock, and Python aborts when it cannot take that
    # lock at shutdown, after a normal run. The parent sends nothing after the
    # request line, so the stream's buffer holds nothing this misses.
    descriptor = stdin.fileno()

    def watch() -> None:
        with contextlib.suppress(OSError):
            while os.read(descriptor, 4096):
                pass
        os._exit(1)  # no one is left to read a result or the exit code

    threading.Thread(target=watch, daemon=True, name="stdin-lifeline").start()


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


def main(stdin: TextIO | None = None, stdout: TextIO | None = None, lifeline: bool = False) -> int:
    """Serve the request on stdin's first line. With lifeline, the process also ends when stdin does."""

    stdin = stdin if stdin is not None else sys.stdin
    stdout = stdout if stdout is not None else sys.stdout
    request = json.loads(stdin.readline())
    if lifeline:
        exit_when_stdin_closes(stdin)

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
    sys.exit(main(lifeline=True))
