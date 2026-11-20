"""
One solver run in its own process, from JSON to JSON.

Started as `python -m sat_core.solver_process` with the repository root as the
working directory. It reads one request object from stdin, runs the solver
with run_solver, and writes one JSON object per line to stdout:

    {"type": "log", "message": "..."}                       once per log line, as it happens
    {"type": "result", "status", "solution", "stats",
     "error", "elapsed"}                                    last, once

The request is {"clauses", "solver", "options", "log_level",
"progress_interval", "timeout"}; "timeout" is enforced here, by run_solver.

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
with a traceback on stderr and no result line; the parent reports that as an
ERROR run.
"""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO

from sat_core.runtime import EVENT_LOG, RunEvent
from sat_core.solver_registry import run_solver


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
    sys.stdin.reconfigure(encoding="utf-8")
    sys.exit(main())
