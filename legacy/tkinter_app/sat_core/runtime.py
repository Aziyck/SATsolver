from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import threading
import time
from typing import Any, Callable


EVENT_LOG = "log"
EVENT_PROGRESS = "progress"
EVENT_RESULT = "result"
EVENT_ROW = "row"
EVENT_CNF = "cnf"
EVENT_ERROR = "error"
EVENT_DONE = "done"
EVENT_CANCELLED = "cancelled"
EVENT_SKIPPED = "skipped"


class CancellationError(Exception):
    """Raised internally when a cooperative run notices a cancel request."""


@dataclass
class RunEvent:
    type: str
    message: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    current: int | None = None
    total: int | None = None
    created_at: datetime = field(default_factory=datetime.now)

    def as_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "message": self.message,
            "payload": self.payload,
            "current": self.current,
            "total": self.total,
            "created_at": self.created_at.isoformat(timespec="seconds"),
        }


class RunToken:
    def __init__(
        self,
        event=None,
        timeout_seconds: float | None = None,
        parent=None,
        skip_event=None,
    ) -> None:
        self._cancelled = event if event is not None else threading.Event()
        self._skipped = skip_event if skip_event is not None else threading.Event()
        self._timeout_seconds = timeout_seconds
        self._started = time.perf_counter()
        self._parent = parent

    def cancel(self) -> None:
        self._cancelled.set()

    def skip(self) -> None:
        self._skipped.set()

    def clear_skip(self) -> None:
        self._skipped.clear()

    def skip_requested(self) -> bool:
        if self._parent is not None and self._parent.skip_requested():
            return True
        return self._skipped.is_set()

    def timed_out(self) -> bool:
        if self._parent is not None and self._parent.timed_out():
            return True
        if self._timeout_seconds is None:
            return False
        return time.perf_counter() - self._started >= self._timeout_seconds

    def is_cancelled(self) -> bool:
        if self._parent is not None and self._parent.is_cancelled():
            return True
        return self._cancelled.is_set() or self.timed_out()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled():
            raise CancellationError()


EventCallback = Callable[[RunEvent], None]


def emit(
    event_callback: EventCallback | None,
    event_type: str,
    message: str = "",
    *,
    payload: dict[str, Any] | None = None,
    current: int | None = None,
    total: int | None = None,
) -> None:
    if event_callback is None:
        return

    event_callback(
        RunEvent(
            type=event_type,
            message=message,
            payload=payload or {},
            current=current,
            total=total,
        )
    )


def cancel_requested(cancel_token: RunToken | None) -> bool:
    return cancel_token is not None and cancel_token.is_cancelled()


def timeout_requested(cancel_token: RunToken | None) -> bool:
    return cancel_token is not None and cancel_token.timed_out()


def skip_requested(cancel_token: RunToken | None) -> bool:
    return cancel_token is not None and cancel_token.skip_requested()


def stop_requested(cancel_token: RunToken | None) -> bool:
    return cancel_requested(cancel_token) or skip_requested(cancel_token)


def cancellation_status(cancel_token: RunToken | None) -> str:
    if timeout_requested(cancel_token):
        return "TIMEOUT"
    if cancel_requested(cancel_token):
        return "CANCELLED"
    if skip_requested(cancel_token):
        return "SKIPPED"
    return "CANCELLED"
