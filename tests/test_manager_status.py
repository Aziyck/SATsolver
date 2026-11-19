"""
The JobManager takes every job status from sat_web/lifecycle.next_status.

These tests build a manager without starting a worker process: with
max_parallel_jobs=0 a submitted job stays queued, and the tests put it into the
status they need and call the same methods the reader thread calls.
"""

import multiprocessing as mp
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sat_core.runtime import EVENT_CANCELLED, EVENT_DONE, EVENT_ERROR, RunEvent
from sat_web.config import Settings
from sat_web.manager import JobManager
from sat_web.store import Store

WEB_SOURCES = sorted((Path(__file__).resolve().parents[1] / "sat_web").glob("*.py"))


class ManagerCase(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = folder.name
        self.manager = self.new_manager(max_parallel_jobs=0)
        self.addCleanup(self.manager.store.close)

    def new_manager(self, **settings):
        values = {"data_dir": Path(self.folder), "max_parallel_jobs": 0, "frontend_dist": Path(self.folder) / "no-dist"}
        values.update(settings)
        config = Settings(**values)
        return JobManager(config, Store(config.db_path))

    def job_in(self, status, **fields):
        job = self.manager.submit("solve", {"problem": "n_queens"}, "t")
        job.status = status
        for name, value in fields.items():
            setattr(job, name, value)
        return job


class OneAssignmentTests(unittest.TestCase):
    def test_job_status_is_assigned_in_one_place(self):
        # Any attribute called status, so an alias or a lookup in a dict does not slip through.
        assignments = [
            f"{path.name}: {line.strip()}"
            for path in WEB_SOURCES
            for line in path.read_text(encoding="utf-8").splitlines()
            if re.search(r"\.status\s*=(?!=)", line)
        ]

        self.assertEqual(assignments, ["manager.py: job.status = status"])


class EventTests(ManagerCase):
    def test_an_error_event_fails_a_running_job_and_keeps_its_message(self):
        job = self.job_in("running")

        self.manager._apply(job, RunEvent(EVENT_ERROR, "boom", payload={"errors": {"size": "bad"}}))

        self.assertEqual((job.status, job.error, job.errors), ("failed", "boom", {"size": "bad"}))

    def test_an_error_event_after_done_does_not_undo_it(self):
        # Ruling of ARCH-6: a finished job is final, as the lifecycle table says.
        job = self.job_in("done")

        self.manager._apply(job, RunEvent(EVENT_ERROR, "late cleanup failure"))

        self.assertEqual(job.status, "done")
        self.assertIsNone(job.error)

    def test_a_cancelled_event_alone_leaves_the_status_to_the_process_ending(self):
        job = self.job_in("running")

        self.manager._apply(job, RunEvent(EVENT_CANCELLED, "stopped"))

        self.assertEqual(job.status, "running")
        self.assertTrue(job.terminal_seen)

    def test_a_done_event_ends_a_job_being_cancelled_as_done(self):
        job = self.job_in("cancelling")

        self.manager._apply(job, RunEvent(EVENT_DONE, "finished"))

        self.assertEqual(job.status, "done")
        self.assertTrue(job.terminal_seen)


class FinalizeTests(ManagerCase):
    def test_a_worker_that_died_without_a_final_event_fails_the_job(self):
        job = self.job_in("running")

        self.manager._finalize(job, -9)

        self.assertEqual(job.status, "failed")
        self.assertIn("stopped unexpectedly (exit code -9)", job.error)
        self.assertIsNotNone(job.finished_at)

    def test_a_worker_that_sent_a_final_event_ends_done(self):
        job = self.job_in("running", terminal_seen=True)

        self.manager._finalize(job, 0)

        self.assertEqual(job.status, "done")
        self.assertIsNone(job.error)

    def test_a_stopped_job_ends_cancelled_even_without_a_final_event(self):
        job = self.job_in("cancelling")

        self.manager._finalize(job, -15)

        self.assertEqual(job.status, "cancelled")
        self.assertIsNone(job.error)

    def test_a_failed_job_stays_failed(self):
        job = self.job_in("failed", error="boom", terminal_seen=True)

        self.manager._finalize(job, 0)

        self.assertEqual((job.status, job.error), ("failed", "boom"))

    def test_while_the_server_stops_a_running_job_is_interrupted(self):
        self.manager.closing = True
        for status in ("running", "cancelling"):
            with self.subTest(status=status):
                job = self.job_in(status)

                self.manager._finalize(job, -15)

                self.assertEqual(job.status, "interrupted")
                self.assertEqual(job.error, "The server stopped while this job was running.")

    def test_a_finished_benchmark_shows_every_run_done(self):
        job = self.job_in("running", terminal_seen=True, progress={"current": 3, "total": 4, "message": ""})

        self.manager._finalize(job, 0)

        self.assertEqual(job.progress["current"], 4)


class ActionTests(ManagerCase):
    def test_stop_cancels_a_queued_job_at_once(self):
        job = self.job_in("queued")

        self.manager.cancel(job.id)

        self.assertEqual(job.status, "cancelled")
        self.assertIsNotNone(job.finished_at)

    def test_stop_moves_a_running_job_to_cancelling_and_raises_the_flag(self):
        job = self.job_in("running", cancel_event=mock.Mock(), process=None)

        with mock.patch("threading.Timer"):
            self.manager.cancel(job.id)

        self.assertEqual(job.status, "cancelling")
        job.cancel_event.set.assert_called_once_with()

    def test_stop_on_a_job_that_is_not_active_changes_nothing(self):
        for status in ("cancelling", "done", "failed", "cancelled", "interrupted"):
            with self.subTest(status=status):
                job = self.job_in(status, cancel_event=mock.Mock())

                self.manager.cancel(job.id)

                self.assertEqual(job.status, status)
                job.cancel_event.set.assert_not_called()

    def test_shutdown_interrupts_queued_jobs(self):
        job = self.job_in("queued")

        self.manager.shutdown()

        self.assertEqual(job.status, "interrupted")
        self.assertEqual(job.error, "The server stopped before this job started.")

    def test_a_worker_that_cannot_start_fails_the_job(self):
        manager = self.new_manager(max_parallel_jobs=1)
        self.addCleanup(manager.store.close)
        manager.context = mock.Mock()
        manager.context.Process.return_value.start.side_effect = OSError("no memory")

        job = manager.submit("solve", {"problem": "n_queens"}, "t")

        self.assertEqual(job.status, "failed")
        self.assertIn("Could not start a worker process: no memory", job.error)

    def test_shutdown_after_a_worker_could_not_start_does_not_raise(self):
        # A real, unstarted Process: joining it raises AssertionError, as in A34.
        class Unstartable(mp.get_context("spawn").Process):
            def start(self):
                raise OSError("no memory")

        manager = self.new_manager(max_parallel_jobs=1)
        self.addCleanup(manager.store.close)
        manager.context = mock.Mock()
        manager.context.Process.side_effect = lambda **kwargs: Unstartable(**kwargs)
        job = manager.submit("solve", {"problem": "n_queens"}, "t")

        manager.shutdown()

        self.assertEqual(job.status, "failed")
        self.assertIsNone(job.process)


class StartupTests(ManagerCase):
    def test_jobs_saved_as_active_come_back_interrupted(self):
        for status in ("queued", "running", "cancelling", "done", "failed"):
            self.manager.store.insert_job({"kind": "solve", "title": status, "status": status, "request": {}})

        manager = self.new_manager()
        self.addCleanup(manager.store.close)

        found = {job.title: job for job in manager.jobs.values()}
        for status in ("queued", "running", "cancelling"):
            self.assertEqual(found[status].status, "interrupted")
            self.assertEqual(found[status].error, "The server stopped while this job was running.")
        self.assertEqual(found["done"].status, "done")
        self.assertEqual(found["failed"].status, "failed")
        saved = {record["title"]: record["status"] for record in manager.store.load_jobs()}
        self.assertEqual(saved["running"], "interrupted")


if __name__ == "__main__":
    unittest.main()
