"""
The child process of the solver runner (docs/plans/pypy-solver-runner.md).

sat_core.solver_process runs one solver on one JSON request. These tests start
it with the interpreter that runs the tests, so the protocol is checked
without PyPy installed.
"""

import contextlib
import dataclasses
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from problems import build_problem
from sat_core import solver_registry
from sat_core.runtime import EVENT_LOG
from sat_core.solver_registry import all_solvers, get_solver, run_solver

ROOT = Path(__file__).resolve().parents[1]

SAT_CLAUSES = [[1, 2], [-1, 2], [1, -2]]
UNSAT_CLAUSES = [[1, 2], [-1, 2], [1, -2], [-1, -2]]
# Small budgets: a local-search solver gives up on the UNSAT formula quickly.
LOCAL_SEARCH_OPTIONS = {"random_seed": 1, "max_tries": 2, "max_flips": 500}


def options_for(solver):
    if solver in ("walksat", "probsat"):
        return dict(LOCAL_SEARCH_OPTIONS)
    return {"random_seed": 1} if solver == "cdcl" else {}


def request_for(solver, clauses, **extra):
    request = {
        "clauses": clauses,
        "solver": solver,
        "options": options_for(solver),
        "log_level": "normal",
        "progress_interval": 1000,
        "timeout": None,
    }
    request.update(extra)
    return request


def start_child(request):
    """Run the child on one request; return (exit code, parsed stdout lines, stderr)."""

    done = subprocess.run(
        [sys.executable, "-m", "sat_core.solver_process"],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=120,
    )
    lines = [json.loads(line) for line in done.stdout.splitlines()]
    return done.returncode, lines, done.stderr


def child_result(lines):
    results = [line for line in lines if line["type"] == "result"]
    assert len(results) == 1, lines
    return results[0]


class ChildMatchesInProcessTests(unittest.TestCase):
    def test_every_solver_gives_the_same_answer_as_run_solver(self):
        for spec in all_solvers():
            for name, clauses in (("sat", SAT_CLAUSES), ("unsat", UNSAT_CLAUSES)):
                with self.subTest(solver=spec.key, formula=name):
                    request = request_for(spec.key, clauses)
                    code, lines, stderr = start_child(request)
                    expected = run_solver(clauses, spec.key, request["options"])

                    self.assertEqual(code, 0, stderr)
                    result = child_result(lines)
                    self.assertEqual(result["status"], expected.status)
                    self.assertIsNone(result["error"])
                    # JSON object keys are strings; the model's variables are ints.
                    model = result["solution"]
                    if expected.solution is None:
                        self.assertIsNone(model)
                    else:
                        self.assertEqual({int(var): value for var, value in model.items()}, expected.solution)
                    # Everything but the wall-clock time is the same work.
                    self.assertEqual(
                        {key: value for key, value in result["stats"].items() if key != "elapsed"},
                        {key: value for key, value in expected.stats.items() if key != "elapsed"},
                    )
                    self.assertIn("elapsed", result)

    def test_sat_and_unsat_statuses_are_as_expected(self):
        # Guards the comparison above against two solvers that both answer wrongly.
        for solver in ("cdcl", "dpll"):
            _, sat_lines, _ = start_child(request_for(solver, SAT_CLAUSES))
            _, unsat_lines, _ = start_child(request_for(solver, UNSAT_CLAUSES))
            self.assertEqual(child_result(sat_lines)["status"], "SAT")
            self.assertEqual(child_result(unsat_lines)["status"], "UNSAT")
        _, lines, _ = start_child(request_for("walksat", UNSAT_CLAUSES))
        self.assertEqual(child_result(lines)["status"], "UNKNOWN")

    def test_renumbering_is_undone_in_the_model(self):
        # run_solver renumbers a sparse formula for CDCL; the child must send the original numbers.
        clauses = [[1, 5_000_000], [-1, 5_000_000], [1, -5_000_000]]
        _, lines, _ = start_child(request_for("cdcl", clauses))

        model = child_result(lines)["solution"]
        self.assertEqual({int(var) for var in model}, {1, 5_000_000})

    def test_a_timeout_is_enforced_by_the_child(self):
        # A budget that would run for minutes: only the timeout can stop it, in the middle of the search.
        huge = {"random_seed": 1, "max_tries": 1_000_000, "max_flips": 1_000_000_000}
        _, lines, _ = start_child(request_for("walksat", UNSAT_CLAUSES, options=huge, timeout=0.3))

        result = child_result(lines)
        self.assertEqual(result["status"], "TIMEOUT")
        self.assertIsNone(result["solution"])
        self.assertGreaterEqual(result["elapsed"], 0.3)
        self.assertLess(result["elapsed"], 5)


class ChildProtocolTests(unittest.TestCase):
    def test_debug_log_lines_arrive_before_the_result(self):
        clauses = build_problem("random_3sat", {"variables": 20, "ratio": 4.0, "mode": "random", "seed": 1}).clauses
        code, lines, stderr = start_child(request_for("cdcl", clauses, log_level="debug", progress_interval=1))

        self.assertEqual(code, 0, stderr)
        logs = [line for line in lines if line["type"] == "log"]
        self.assertGreater(len(logs), 3)
        self.assertEqual(lines[-1]["type"], "result")
        self.assertTrue(all(line["type"] == "log" for line in lines[:-1]))
        self.assertTrue(all(isinstance(line["message"], str) for line in logs))
        self.assertTrue(any("debug" in line["message"] for line in logs))

    def test_stdout_holds_only_log_and_result_lines(self):
        _, lines, _ = start_child(request_for("walksat", UNSAT_CLAUSES, log_level="periodic", progress_interval=100))

        self.assertEqual({line["type"] for line in lines}, {"log", "result"})

    def test_a_print_inside_a_solver_does_not_reach_the_protocol_stream(self):
        # In-process so the patched solver is used. The protocol goes to the stream
        # given to main(); whatever else writes to sys.stdout must not mix into it.
        from sat_core import solver_process

        def chatty(clauses, options, log_options, event_callback, token):
            print("not part of the protocol")
            return {1: True}, {"status": "SAT"}

        patched = dataclasses.replace(get_solver("cdcl"), runner=chatty)
        stdin = io.StringIO(json.dumps(request_for("cdcl", SAT_CLAUSES)))
        stdout = io.StringIO()
        with mock.patch.dict(solver_registry._SOLVERS, {"cdcl": patched}):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as stderr:
                code = solver_process.main(stdin, stdout)

        self.assertEqual(code, 0)
        self.assertIn("not part of the protocol", stderr.getvalue())
        self.assertNotIn("not part of the protocol", stdout.getvalue())
        for line in stdout.getvalue().splitlines():
            self.assertIn(json.loads(line)["type"], ("log", "result"))

    def test_log_events_carry_the_same_messages_run_solver_emits(self):
        events = []
        run_solver(SAT_CLAUSES, "cdcl", options_for("cdcl"), event_callback=events.append)
        expected_first = [event.message for event in events if event.type == EVENT_LOG][0]

        _, lines, _ = start_child(request_for("cdcl", SAT_CLAUSES))

        self.assertEqual([line["message"] for line in lines if line["type"] == "log"][0], expected_first)


if __name__ == "__main__":
    unittest.main()
