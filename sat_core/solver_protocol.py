"""
The messages between the parent and the solver child process, as pure code.

The child (sat_core.solver_process.serve) writes one JSON object per line to
stdout, built here: log_message for each log line, then one result_message.
The parent (run_in_child) accepts a line only through parse_line, which checks
every rule a line must follow and raises BrokenLine for one that breaks them.
The rules live here, away from the processes, threads and pipes, so they are
tested without starting a child (tests/test_solver_protocol.py), as
sat_web/lifecycle.py does for job statuses.

    {"type": "log", "message": "..."}
    {"type": "result", "status", "solution", "stats", "error", "elapsed"}

The model's variable numbers are strings in JSON; parse_line turns them back
into ints. The parent makes one more result line itself, when it kills a
child (stopped_result); that line never travels through a pipe, and a child
that sends a "killed" field has it dropped. The request the parent sends is
not here: run_solver validates it before the child starts, and the child
reads it with json.loads.

This module is imported on both sides, so it imports only sat_core.models
(no web framework, nothing the PyPy child could lack).
"""

from __future__ import annotations

import json
import math
from typing import Any

from sat_core.models import STATUS_SAT, STATUSES

# The fields every result line carries.
RESULT_FIELDS = ("status", "solution", "stats", "error", "elapsed")


class BrokenLine(Exception):
    """A line that is not part of the protocol. `line` is the text as received."""

    def __init__(self, line: str) -> None:
        super().__init__(line)
        self.line = line


def log_message(message: str) -> dict[str, Any]:
    """The log line the child writes for one log message."""

    return {"type": "log", "message": message}


def result_message(
    status: str, solution: dict[int, bool] | None, stats: dict[str, Any], error: str | None, elapsed: float
) -> dict[str, Any]:
    """The result line the child writes, last."""

    return {"type": "result", "status": status, "solution": solution, "stats": stats, "error": error, "elapsed": elapsed}


def stopped_result(status: str, elapsed: float, killed: str) -> dict[str, Any]:
    """
    The result line the parent makes when it killed the child: the stop's
    status, no model or statistics, and "killed" saying why (the parent's
    KILLED_BY_*).
    """

    return {**result_message(status, None, {}, None, elapsed), "killed": killed}


def parse_line(line: str) -> dict[str, Any]:
    """One stdout line as a protocol message (the model's variables as ints), or BrokenLine."""

    try:
        message = json.loads(line)
    except (ValueError, RecursionError):
        # RecursionError: a deeply nested line. It is not a ValueError.
        raise BrokenLine(line) from None
    if not isinstance(message, dict):
        raise BrokenLine(line)
    if message.get("type") == "log" and isinstance(message.get("message"), str):
        return message
    if message.get("type") != "result" or any(field not in message for field in RESULT_FIELDS):
        raise BrokenLine(line)
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
        raise BrokenLine(line)
    # Only the parent marks a run as killed (stopped_result).
    message.pop("killed", None)
    if solution is not None:
        # JSON object keys are strings; variables are ints.
        model = {}
        for var, value in solution.items():
            if not (var.isdigit() and int(var) > 0 and isinstance(value, bool)):
                raise BrokenLine(line)
            model[int(var)] = value
        message["solution"] = model
    return message


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (bool, str)) or _is_finite_number(value)
