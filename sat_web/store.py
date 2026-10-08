"""
SQLite persistence for jobs and benchmark rows.

Jobs survive a server restart: the job list, requests, encoded-instance
summaries, results, the tail of each log and every benchmark row are kept in
output/wizsat.db. Large files (the CNF, the model) live in the job's folder.
The store is used from several threads, so one connection is shared behind a
lock.
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import threading
from typing import Any


JSON_COLUMNS = ("request", "progress", "instance", "result", "errors", "logs")
COLUMNS = (
    "kind",
    "title",
    "status",
    "created_at",
    "started_at",
    "finished_at",
    "request",
    "progress",
    "instance",
    "result",
    "error",
    "errors",
    "logs",
    "workdir",
)


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._closed = False
        self._db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA synchronous=NORMAL")
            self._db.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT,
                    started_at TEXT,
                    finished_at TEXT,
                    request TEXT,
                    progress TEXT,
                    instance TEXT,
                    result TEXT,
                    error TEXT,
                    errors TEXT,
                    logs TEXT,
                    workdir TEXT
                )
                """
            )
            self._db.execute(
                """
                CREATE TABLE IF NOT EXISTS rows (
                    job_id INTEGER NOT NULL,
                    idx INTEGER NOT NULL,
                    data TEXT NOT NULL,
                    PRIMARY KEY (job_id, idx)
                )
                """
            )

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._db.close()

    def _execute(self, sql: str, parameters=()) -> sqlite3.Cursor | None:
        """Run a statement under the lock; writes after close() are ignored."""

        with self._lock:
            if self._closed:
                return None
            return self._db.execute(sql, parameters)

    @staticmethod
    def _encode(name: str, value: Any) -> Any:
        return json.dumps(value) if name in JSON_COLUMNS and value is not None else value

    def insert_job(self, values: dict[str, Any]) -> int:
        names = [name for name in COLUMNS if name in values]
        placeholders = ", ".join("?" for _ in names)
        cursor = self._execute(
            f"INSERT INTO jobs ({', '.join(names)}) VALUES ({placeholders})",
            [self._encode(name, values[name]) for name in names],
        )
        if cursor is None:
            raise RuntimeError("the job store is closed")
        return int(cursor.lastrowid)

    def update_job(self, job_id: int, **values: Any) -> None:
        if not values:
            return
        names = [name for name in values if name in COLUMNS]
        assignments = ", ".join(f"{name} = ?" for name in names)
        self._execute(
            f"UPDATE jobs SET {assignments} WHERE id = ?",
            [self._encode(name, values[name]) for name in names] + [job_id],
        )

    def add_row(self, job_id: int, index: int, data: dict[str, Any]) -> None:
        self._execute(
            "INSERT OR REPLACE INTO rows (job_id, idx, data) VALUES (?, ?, ?)",
            (job_id, index, json.dumps(data)),
        )

    def load_jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            records = self._db.execute("SELECT * FROM jobs ORDER BY id").fetchall()
        jobs = []
        for record in records:
            job = dict(record)
            for name in JSON_COLUMNS:
                if job.get(name) is not None:
                    job[name] = json.loads(job[name])
            jobs.append(job)
        return jobs

    def load_rows(self, job_id: int) -> list[dict[str, Any]]:
        with self._lock:
            records = self._db.execute("SELECT data FROM rows WHERE job_id = ? ORDER BY idx", (job_id,)).fetchall()
        return [json.loads(record["data"]) for record in records]

    def row_counts(self) -> dict[int, int]:
        with self._lock:
            records = self._db.execute("SELECT job_id, COUNT(*) AS n FROM rows GROUP BY job_id").fetchall()
        return {record["job_id"]: record["n"] for record in records}

    def delete_job(self, job_id: int) -> None:
        self._execute("DELETE FROM rows WHERE job_id = ?", (job_id,))
        self._execute("DELETE FROM jobs WHERE id = ?", (job_id,))

    def reset_numbering(self) -> bool:
        """
        Make the next job J1 again, but only while there are no jobs at all.

        AUTOINCREMENT never reuses an id on its own, so a deleted job's number
        cannot come back while any job exists. The check and the reset run
        under one lock, so a job inserted concurrently either comes first (and
        the reset is refused) or gets id 1.
        """
        with self._lock:
            if self._closed:
                return False
            if self._db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]:
                return False
            self._db.execute("DELETE FROM rows")
            self._db.execute("DELETE FROM sqlite_sequence WHERE name = 'jobs'")
            return True
