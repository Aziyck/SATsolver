"""
The job status rule (sat_web/lifecycle.py) as a table, and its match with the
state diagram of docs/guide/architecture.md.
"""

import re
import unittest
from pathlib import Path

from sat_web.lifecycle import ACTIVE, FINISHED, HAPPENINGS, STATUSES, next_status

GUIDE = Path(__file__).resolve().parents[1] / "docs" / "guide" / "architecture.md"

# Every arrow of the diagram: (status, happening) -> new status. Anything
# that is not listed leaves the status unchanged (see the test below).
ARROWS = {
    ("queued", "slot_free"): "running",
    ("queued", "stop"): "cancelled",
    ("queued", "server_stopping"): "interrupted",
    ("queued", "found_at_startup"): "interrupted",
    ("running", "start_failed"): "failed",
    ("running", "stop"): "cancelling",
    ("running", "done_event"): "done",
    ("running", "error_event"): "failed",
    ("running", "server_stopping"): "interrupted",
    ("running", "found_at_startup"): "interrupted",
    ("cancelling", "done_event"): "done",
    ("cancelling", "error_event"): "failed",
    ("cancelling", "process_exited"): "cancelled",
    ("cancelling", "server_stopping"): "interrupted",
    ("cancelling", "found_at_startup"): "interrupted",
}


class NextStatusTests(unittest.TestCase):
    def test_every_arrow(self):
        for (status, happening), expected in ARROWS.items():
            with self.subTest(status=status, happening=happening):
                self.assertEqual(next_status(status, happening), expected)

    def test_a_happening_without_an_arrow_changes_nothing(self):
        for status in STATUSES:
            for happening in HAPPENINGS:
                if (status, happening) in ARROWS or (status, happening) == ("running", "process_exited"):
                    continue
                with self.subTest(status=status, happening=happening):
                    self.assertEqual(next_status(status, happening), status)

    def test_every_final_status_ignores_every_happening(self):
        for status in FINISHED:
            for happening in HAPPENINGS:
                for seen in (True, False):
                    with self.subTest(status=status, happening=happening, terminal_seen=seen):
                        self.assertEqual(next_status(status, happening, terminal_seen=seen), status)

    def test_the_final_event_defaults_to_not_seen(self):
        # Safe when a caller forgets it: the worker is reported as failed.
        self.assertEqual(next_status("running", "process_exited"), "failed")

    def test_the_process_ending_decides_a_running_job_by_its_final_event(self):
        self.assertEqual(next_status("running", "process_exited", terminal_seen=True), "done")
        self.assertEqual(next_status("running", "process_exited", terminal_seen=False), "failed")

    def test_a_stop_wins_over_a_missing_final_event(self):
        # A cancelled worker often ends without a final event of its own.
        self.assertEqual(next_status("cancelling", "process_exited", terminal_seen=False), "cancelled")
        self.assertEqual(next_status("cancelling", "process_exited", terminal_seen=True), "cancelled")

    def test_the_cancelled_event_alone_does_not_end_a_job(self):
        # The status changes when the process exits, not when the event arrives.
        for status in ("running", "cancelling"):
            self.assertEqual(next_status(status, "cancelled_event"), status)

    def test_a_running_job_that_sent_cancelled_without_a_stop_ends_done(self):
        self.assertEqual(next_status("running", "process_exited", terminal_seen=True), "done")

    def test_a_late_done_event_after_stop_still_counts(self):
        self.assertEqual(next_status("cancelling", "done_event"), "done")

    def test_an_unknown_happening_or_status_is_a_bug_not_a_no_op(self):
        with self.assertRaises(ValueError):
            next_status("running", "stoped")
        with self.assertRaises(ValueError):
            next_status("paused", "stop")

    def test_the_server_stopping_before_the_process_exits_ends_interrupted(self):
        # The order _finalize uses while the server shuts down.
        status = next_status("cancelling", "server_stopping")
        self.assertEqual(next_status(status, "process_exited", terminal_seen=False), "interrupted")


class DiagramTests(unittest.TestCase):
    def diagram(self):
        text = GUIDE.read_text(encoding="utf-8")
        return text.split("stateDiagram-v2", 1)[1].split("```", 1)[0]

    def test_the_guide_diagram_lists_the_same_arrows_as_the_table(self):
        drawn = set(re.findall(r"^\s*(\w+) --> (\w+)", self.diagram(), flags=re.MULTILINE))
        coded = {(status, new) for (status, _), new in ARROWS.items()}

        self.assertEqual(drawn, coded)

    def test_the_diagram_starts_at_queued_and_ends_in_the_final_statuses(self):
        diagram = self.diagram()

        self.assertEqual(re.findall(r"^\s*\[\*\] --> (\w+)", diagram, flags=re.MULTILINE), ["queued"])
        self.assertEqual(set(re.findall(r"^\s*(\w+) --> \[\*\]", diagram, flags=re.MULTILINE)), set(FINISHED))

    def test_active_is_every_status_that_is_not_finished(self):
        self.assertEqual(ACTIVE, ("queued", "running", "cancelling"))


if __name__ == "__main__":
    unittest.main()
