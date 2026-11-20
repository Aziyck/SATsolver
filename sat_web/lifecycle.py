"""
The job status rule: which status follows which happening.

Pure and lock-free on purpose. The JobManager owns processes, threads and the
lock; it asks `next_status` what a job's status becomes and keeps persisting
and publishing for itself. The arrows are drawn in
docs/guide/architecture.md ("Statuses"); tests/test_lifecycle.py lists them
as a table and checks the function against it.
"""

from __future__ import annotations

from typing import Literal, get_args

Status = Literal["queued", "running", "cancelling", "done", "failed", "cancelled", "interrupted"]
Happening = Literal[
    "slot_free",         # a queued job gets a worker slot
    "start_failed",      # the worker process could not be started
    "stop",              # the user pressed Stop
    "done_event",        # the job sent its `done` event
    "error_event",       # the job sent its `error` event
    "cancelled_event",   # the job sent its `cancelled` event
    "process_exited",    # the worker process ended
    "server_stopping",   # the server is shutting down
    "found_at_startup",  # a job saved as active, found when the server starts
]

STATUSES: tuple[str, ...] = get_args(Status)
HAPPENINGS: tuple[str, ...] = get_args(Happening)
FINISHED: tuple[str, ...] = ("done", "failed", "cancelled", "interrupted")
# Derived, so a new status is either finished or active and cannot be neither.
ACTIVE: tuple[str, ...] = tuple(status for status in STATUSES if status not in FINISHED)


def next_status(status: Status, happening: Happening, *, terminal_seen: bool = False) -> Status:
    """The status after `happening`; the same status when no arrow leaves it.

    `terminal_seen` matters only for `process_exited` of a running job: did the
    job send a final event (done, error or cancelled) before its process
    ended? Without one the process died on its own, and the job failed. The
    default is False, as `Job.terminal_seen`: a caller that forgets it gets
    the failure, not a false "done".

    An unknown status or happening raises ValueError: a typo must not read as
    "nothing happens".
    """

    if status not in STATUSES:
        raise ValueError(f"unknown job status: {status!r}")
    if happening not in HAPPENINGS:
        raise ValueError(f"unknown happening: {happening!r}")
    if status in FINISHED:
        return status

    if happening in ("server_stopping", "found_at_startup"):
        return "interrupted"
    if status == "queued":
        if happening == "slot_free":
            return "running"
        if happening == "stop":
            return "cancelled"
        return status

    # From here the status is running or cancelling.
    if happening == "done_event":
        # Also from cancelling: the Stop came after the work was finished.
        return "done"
    if happening == "error_event":
        return "failed"
    if happening == "start_failed" and status == "running":
        return "failed"
    if happening == "stop" and status == "running":
        return "cancelling"
    if happening == "process_exited":
        if status == "cancelling":
            # The Stop decides, even when no final event came: a cancelled
            # worker often ends without one.
            return "cancelled"
        return "done" if terminal_seen else "failed"
    # cancelled_event only sets terminal_seen; the status changes when the
    # process exits, and a running job nobody stopped then ends done (its log
    # still says "Cancelled.").
    return status
