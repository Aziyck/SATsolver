"""
Job manager: runs solve/generate/benchmark jobs in worker processes.

- Each job runs in its own process (spawn start method on every OS), so a
  CPU-heavy solver never blocks the server and can be stopped for good.
- At most Settings.max_parallel_jobs run at once; the rest wait as "queued".
- A reader thread per job drains the job's event queue, updates the job,
  persists it and publishes messages to WebSocket subscribers. Publishing
  hops onto the asyncio loop with call_soon_threadsafe.
- Cancel is cooperative first (the solvers check a shared event often) and
  forceful after a grace period.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
import multiprocessing as mp
import queue as queue_module
import shutil
import threading
import time
from pathlib import Path
from typing import Any

from sat_core.jobs import run_job
from sat_core.runtime import (
    EVENT_CANCELLED,
    EVENT_DONE,
    EVENT_ERROR,
    EVENT_INSTANCE,
    EVENT_LOG,
    EVENT_PLAN,
    EVENT_PROGRESS,
    EVENT_RESULT,
    EVENT_ROW,
    RunEvent,
)
from sat_web.config import Settings
from sat_web.store import Store


ACTIVE = ("queued", "running", "cancelling")
FINISHED = ("done", "failed", "cancelled", "interrupted")
CANCEL_GRACE_SECONDS = 3.0
LOG_LINES_PER_SECOND = 60
LOG_TAIL_STORED = 1000
SUMMARY_INTERVAL = 0.2


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


@dataclass
class Job:
    id: int
    kind: str
    title: str
    status: str
    request: dict[str, Any]
    created_at: str
    workdir: Path
    started_at: str | None = None
    finished_at: str | None = None
    progress: dict[str, Any] = field(default_factory=lambda: {"current": None, "total": None, "message": ""})
    instance: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    errors: dict[str, str] | None = None
    logs: deque = field(default_factory=lambda: deque(maxlen=5000))
    rows: list[dict[str, Any]] | None = None
    row_count: int = 0
    process: Any = None
    reader: Any = None
    cancel_event: Any = None
    skip_event: Any = None
    terminal_seen: bool = False
    cancel_requested: bool = False
    dirty: bool = False
    # Bumped every time a summary is published, so clients can drop stale copies
    # (an HTTP response can arrive after newer WebSocket events).
    rev: int = 0
    log_window: float = 0.0
    log_sent: int = 0
    log_suppressed: int = 0

    @property
    def label(self) -> str:
        return f"J{self.id}"

    def summary(self) -> dict[str, Any]:
        result = self.result or {}
        request = self.request or {}
        return {
            "id": self.id,
            "rev": self.rev,
            "label": self.label,
            "kind": self.kind,
            "title": self.title,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "progress": self.progress,
            "row_count": self.row_count,
            "problems": request.get("problems") or ([request["problem"]] if request.get("problem") else []),
            "solver": request.get("solver"),
            "result_status": result.get("status"),
            "verified": result.get("verified"),
            "elapsed": result.get("elapsed"),
            "error": self.error,
        }

    def detail(self, log_tail: int = 400) -> dict[str, Any]:
        data = self.summary()
        data.update(
            {
                "request": self.request,
                "instance": self.instance,
                "result": self.result,
                "errors": self.errors,
                "logs": list(self.logs)[-log_tail:],
                "log_count": len(self.logs),
            }
        )
        return data


class JobManager:
    def __init__(self, settings: Settings, store: Store):
        self.settings = settings
        self.store = store
        self.jobs: dict[int, Job] = {}
        self.lock = threading.RLock()
        self.loop: asyncio.AbstractEventLoop | None = None
        self.subscribers: set[asyncio.Queue] = set()
        self.context = mp.get_context("spawn")
        self.closing = False
        self._load()

    # -- persistence ---------------------------------------------------------

    def _load(self) -> None:
        counts = self.store.row_counts()
        for record in self.store.load_jobs():
            status = record["status"]
            error = record.get("error")
            if status in ACTIVE:
                status = "interrupted"
                error = "The server stopped while this job was running."
                self.store.update_job(record["id"], status=status, error=error)
            job = Job(
                id=record["id"],
                kind=record["kind"],
                title=record["title"],
                status=status,
                request=record.get("request") or {},
                created_at=record.get("created_at") or "",
                workdir=Path(record.get("workdir") or self.settings.jobs_dir / str(record["id"])),
                started_at=record.get("started_at"),
                finished_at=record.get("finished_at"),
                progress=record.get("progress") or {"current": None, "total": None, "message": ""},
                instance=record.get("instance"),
                result=record.get("result"),
                error=error,
                errors=record.get("errors"),
                row_count=counts.get(record["id"], 0),
            )
            job.logs = deque(record.get("logs") or [], maxlen=self.settings.log_lines_per_job)
            self.jobs[job.id] = job

    def _persist(self, job: Job, **extra: Any) -> None:
        values = {
            "status": job.status,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
            "progress": job.progress,
            "error": job.error,
            "errors": job.errors,
        }
        values.update(extra)
        self.store.update_job(job.id, **values)

    # -- pub/sub ---------------------------------------------------------------

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

    def subscribe(self) -> asyncio.Queue:
        subscriber: asyncio.Queue = asyncio.Queue(maxsize=20_000)
        self.subscribers.add(subscriber)
        return subscriber

    def unsubscribe(self, subscriber: asyncio.Queue) -> None:
        self.subscribers.discard(subscriber)

    def _fanout(self, message: dict[str, Any]) -> None:
        for subscriber in list(self.subscribers):
            try:
                subscriber.put_nowait(message)
            except asyncio.QueueFull:
                # A client that cannot keep up gets a resync request instead.
                while not subscriber.empty():
                    subscriber.get_nowait()
                subscriber.put_nowait({"type": "resync"})

    def publish(self, message: dict[str, Any]) -> None:
        loop = self.loop
        if loop is None or loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(self._fanout, message)
        except RuntimeError:
            pass

    def publish_job(self, job: Job) -> None:
        with self.lock:
            job.rev += 1
            job.dirty = False
            self.publish({"type": "job", "job": job.summary()})

    async def flush_summaries(self) -> None:
        """Push throttled progress updates for jobs marked dirty."""

        while True:
            await asyncio.sleep(SUMMARY_INTERVAL)
            with self.lock:
                dirty = [job for job in self.jobs.values() if job.dirty]
            for job in dirty:
                self.publish_job(job)

    # -- queries ---------------------------------------------------------------

    def get(self, job_id: int) -> Job:
        with self.lock:
            if job_id not in self.jobs:
                raise KeyError(job_id)
            return self.jobs[job_id]

    def summaries(self) -> list[dict[str, Any]]:
        with self.lock:
            return [job.summary() for job in self.jobs.values()]

    def summary(self, job: Job) -> dict[str, Any]:
        with self.lock:
            return job.summary()

    def detail(self, job: Job) -> dict[str, Any]:
        # Under the lock so the snapshot is consistent with its rev and the log
        # deque is not mutated while it is copied.
        with self.lock:
            return job.detail()

    def rows(self, job: Job) -> list[dict[str, Any]]:
        with self.lock:
            if job.rows is None:
                job.rows = self.store.load_rows(job.id)
                job.row_count = len(job.rows)
            return list(job.rows)

    # -- lifecycle ------------------------------------------------------------

    def submit(self, kind: str, request: dict[str, Any], title: str) -> Job:
        created = now_iso()
        job_id = self.store.insert_job(
            {"kind": kind, "title": title, "status": "queued", "created_at": created, "request": request}
        )
        workdir = self.settings.jobs_dir / str(job_id)
        self.store.update_job(job_id, workdir=str(workdir))
        job = Job(
            id=job_id,
            kind=kind,
            title=title,
            status="queued",
            request=request,
            created_at=created,
            workdir=workdir,
            rows=[],
        )
        job.logs = deque(maxlen=self.settings.log_lines_per_job)
        with self.lock:
            self.jobs[job_id] = job
        self.publish_job(job)
        self._schedule()
        return job

    def _schedule(self) -> None:
        with self.lock:
            running = sum(1 for job in self.jobs.values() if job.status in ("running", "cancelling"))
            for job in self.jobs.values():
                if running >= self.settings.max_parallel_jobs:
                    break
                if job.status == "queued":
                    self._start(job)
                    running += 1

    def _start(self, job: Job) -> None:
        job.workdir.mkdir(parents=True, exist_ok=True)
        event_queue = self.context.Queue()
        job.cancel_event = self.context.Event()
        job.skip_event = self.context.Event()
        job.process = self.context.Process(
            target=run_job,
            args=(job.kind, job.request, str(job.workdir), event_queue, job.cancel_event, job.skip_event),
            daemon=True,
        )
        job.status = "running"
        job.started_at = now_iso()
        self._log(job, "Starting worker process...")
        self._persist(job)
        self.publish_job(job)
        try:
            job.process.start()
        except Exception as exc:  # noqa: BLE001
            job.status = "failed"
            job.error = f"Could not start a worker process: {exc}"
            job.finished_at = now_iso()
            self._persist(job)
            self.publish_job(job)
            return
        job.reader = threading.Thread(target=self._reader, args=(job, event_queue), daemon=True, name=f"job-{job.id}")
        job.reader.start()

    def _reader(self, job: Job, event_queue) -> None:
        process = job.process
        while True:
            try:
                event = event_queue.get(timeout=0.25)
            except queue_module.Empty:
                if process.is_alive():
                    continue
                # The process is gone: drain what it flushed before exiting.
                while True:
                    try:
                        self._apply(job, event_queue.get(timeout=0.1))
                    except queue_module.Empty:
                        break
                    except (EOFError, OSError):
                        break
                break
            except (EOFError, OSError):
                break
            self._apply(job, event)
        process.join(timeout=2)
        self._finalize(job, process.exitcode)

    def _log(self, job: Job, message: str) -> None:
        line = [datetime.now().strftime("%H:%M:%S"), message]
        job.logs.append(line)
        now = time.monotonic()
        if now - job.log_window >= 1.0:
            if job.log_suppressed:
                self.publish({"type": "log", "job_id": job.id, "line": [line[0], f"... {job.log_suppressed} more log lines (open the full log to see them)"], "synthetic": True})
            job.log_window = now
            job.log_sent = 0
            job.log_suppressed = 0
        if job.log_sent < LOG_LINES_PER_SECOND:
            job.log_sent += 1
            self.publish({"type": "log", "job_id": job.id, "line": line})
        else:
            job.log_suppressed += 1

    def _apply(self, job: Job, event: RunEvent) -> None:
        kind = event.type
        with self.lock:
            if kind == EVENT_LOG:
                self._log(job, event.message)
                return
            if kind in (EVENT_PROGRESS, EVENT_PLAN):
                job.progress = {"current": event.current, "total": event.total, "message": event.message}
                if kind == EVENT_PLAN:
                    self._log(job, event.message)
                job.dirty = True
                return
            if kind == EVENT_INSTANCE:
                job.instance = event.payload
                self.store.update_job(job.id, instance=job.instance)
                self.publish({"type": "instance", "job_id": job.id, "instance": job.instance})
                return
            if kind == EVENT_RESULT:
                job.result = event.payload
                self.store.update_job(job.id, result=job.result)
                self.publish({"type": "result", "job_id": job.id, "result": job.result})
                job.dirty = True
                return
            if kind == EVENT_ROW:
                row = event.payload["row"]
                if job.rows is None:
                    job.rows = []
                job.rows.append(row)
                job.row_count = len(job.rows)
                self.store.add_row(job.id, row["index"], row)
                if event.total:
                    job.progress = {"current": event.current, "total": event.total, "message": f"{event.current}/{event.total} runs"}
                self.publish({"type": "row", "job_id": job.id, "row": row})
                job.dirty = True
                return
            if kind == EVENT_ERROR:
                job.terminal_seen = True
                job.status = "failed"
                job.error = event.message
                job.errors = event.payload.get("errors")
                self._log(job, f"ERROR: {event.message}")
                return
            if kind == EVENT_CANCELLED:
                # Sent by benchmarks when they stop, and by the job wrapper at the end.
                job.terminal_seen = True
                self._log(job, event.message or "Cancelled.")
                return
            if kind == EVENT_DONE:
                job.terminal_seen = True
                if job.status in ("running", "cancelling"):
                    job.status = "done"
                return

    def _finalize(self, job: Job, exitcode: int | None) -> None:
        with self.lock:
            if job.status in ("running", "cancelling") and self.closing:
                job.status = "interrupted"
                job.error = "The server stopped while this job was running."
            if job.status in ("running", "cancelling"):
                if job.cancel_requested:
                    job.status = "cancelled"
                elif not job.terminal_seen:
                    job.status = "failed"
                    job.error = f"The worker process stopped unexpectedly (exit code {exitcode})."
                else:
                    job.status = "done"
            if job.status == "done" and job.progress.get("total"):
                job.progress = {**job.progress, "current": job.progress["total"]}
            job.finished_at = now_iso()
            if job.log_suppressed:
                self._log(job, f"({job.log_suppressed} log lines were not streamed live)")
                job.log_suppressed = 0
            self._log(job, f"Job {job.status}.")
            self._persist(job, logs=list(job.logs)[-LOG_TAIL_STORED:])
            job.process = None
            self.publish_job(job)
        self._schedule()

    # -- actions --------------------------------------------------------------

    def cancel(self, job_id: int) -> Job:
        job = self.get(job_id)
        with self.lock:
            if job.status == "queued":
                job.status = "cancelled"
                job.finished_at = now_iso()
                job.cancel_requested = True
                self._log(job, "Cancelled before it started.")
                self._persist(job)
                self.publish_job(job)
                return job
            if job.status != "running":
                return job
            job.cancel_requested = True
            job.status = "cancelling"
            job.cancel_event.set()
            self._log(job, "Cancel requested; stopping at the next solver checkpoint.")
            self.publish_job(job)
            process = job.process

        def force_stop() -> None:
            if process is not None and process.is_alive():
                self._log(job, "The worker did not stop in time; terminating it.")
                process.terminate()

        timer = threading.Timer(CANCEL_GRACE_SECONDS, force_stop)
        timer.daemon = True
        timer.start()
        return job

    def skip(self, job_id: int) -> Job:
        job = self.get(job_id)
        with self.lock:
            if job.kind == "benchmark" and job.status == "running" and job.skip_event is not None:
                job.skip_event.set()
                self._log(job, "Skip requested; the current case will be marked SKIPPED.")
        return job

    def delete(self, job_id: int) -> None:
        job = self.get(job_id)
        with self.lock:
            if job.status in ("running", "cancelling"):
                raise RuntimeError("Cancel the job before deleting it.")
            del self.jobs[job_id]
        self.store.delete_job(job_id)
        shutil.rmtree(job.workdir, ignore_errors=True)
        self.publish({"type": "deleted", "job_id": job_id})

    def clear_finished(self, kinds: list[str] | None = None) -> list[int]:
        with self.lock:
            ids = [
                job.id
                for job in self.jobs.values()
                if job.status in FINISHED and (not kinds or job.kind in kinds)
            ]
        for job_id in ids:
            self.delete(job_id)
        return ids

    def shutdown(self) -> None:
        """Stop running jobs (they become "interrupted") and wait for their readers."""

        self.closing = True
        with self.lock:
            for job in self.jobs.values():
                if job.status == "queued":
                    job.status = "interrupted"
                    job.error = "The server stopped before this job started."
                    self._persist(job)
            running = [job for job in self.jobs.values() if job.process is not None]
        for job in running:
            if job.cancel_event is not None:
                job.cancel_event.set()
        deadline = time.monotonic() + 2
        for job in running:
            process = job.process
            if process is not None:
                process.join(timeout=max(0.0, deadline - time.monotonic()))
                if process.is_alive():
                    process.terminate()
        for job in running:
            if job.reader is not None:
                job.reader.join(timeout=5)
