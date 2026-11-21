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
import os
import re
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from child_process_spy import replace_child_program
from problems import build_problem
from sat_core import solver_process, solver_registry
from sat_core.runtime import EVENT_LOG, RunToken
from sat_core.solver_process import SolverProcessError, run_in_child
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
        # elapsed is the solver's own clock, which starts a moment after the timeout's clock.
        self.assertGreater(result["elapsed"], 0.2)
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

    def test_log_lines_reach_the_parent_while_the_solver_runs(self):
        # Only a flushed line can be read before the run ends: the run lasts 5 s, the read must not.
        huge = {"random_seed": 1, "max_tries": 1_000_000, "max_flips": 1_000_000_000}
        request = request_for("walksat", UNSAT_CLAUSES, options=huge, timeout=5)
        child = subprocess.Popen(
            [sys.executable, "-m", "sat_core.solver_process"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            cwd=ROOT,
        )
        try:
            child.stdin.write(json.dumps(request))
            child.stdin.close()
            started = time.perf_counter()
            first = json.loads(child.stdout.readline())
            waited = time.perf_counter() - started
            still_running = child.poll() is None
        finally:
            child.kill()
            child.wait()
            child.stdout.close()

        self.assertEqual(first["type"], "log")
        self.assertLess(waited, 4)
        self.assertTrue(still_running)

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
        def without_times(messages):
            return [re.sub(r"\d+\.\d+(e-?\d+)?s", "<time>", message) for message in messages]

        for solver in ("cdcl", "walksat"):
            with self.subTest(solver=solver):
                request = request_for(solver, UNSAT_CLAUSES, log_level="debug")
                events = []
                run_solver(
                    UNSAT_CLAUSES,
                    solver,
                    request["options"],
                    log_level="debug",
                    progress_interval=request["progress_interval"],
                    event_callback=events.append,
                )
                expected = [event.message for event in events if event.type == EVENT_LOG]

                _, lines, _ = start_child(request)

                received = [line["message"] for line in lines if line["type"] == "log"]
                self.assertGreater(len(expected), 3)
                self.assertEqual(without_times(received), without_times(expected))


class ParentSideTests(unittest.TestCase):
    def test_stderr_that_is_not_utf8_neither_stops_nor_hangs_the_parent(self):
        # On Windows a child's stderr is in the locale code page. One such byte,
        # then more than a pipe buffer: a reader thread that died on the byte
        # would leave the child blocked and the parent waiting for ever.
        script = "import sys; sys.stderr.buffer.write(b'caf\\xe9 ' + b'x' * 300000 + b' end'); sys.exit(3)"
        replace_child_program(self, script=script)
        outcome = []

        def run():
            try:
                run_in_child(sys.executable, request_for("cdcl", SAT_CLAUSES))
            except SolverProcessError as exc:
                outcome.append(exc)

        worker = threading.Thread(target=run, daemon=True)  # a hang fails the test instead of the test run
        worker.start()
        worker.join(timeout=30)

        self.assertFalse(worker.is_alive(), "run_in_child did not return")
        # No result: the error carries the end of stderr, past the byte that is not UTF-8.
        self.assertTrue(str(outcome[0]).endswith("end"))


# A WalkSAT budget that would run for minutes on UNSAT_CLAUSES: only a stop ends the run.
ENDLESS = {"random_seed": 1, "max_tries": 1_000_000, "max_flips": 1_000_000_000}

# A child whose solver sleeps instead of searching, so it never notices its timeout.
SLEEPING_CHILD = (
    "import dataclasses, sys, time\n"
    "from sat_core import solver_process, solver_registry\n"
    "spec = solver_registry.get_solver('walksat')\n"
    "solver_registry._SOLVERS['walksat'] = dataclasses.replace(spec, runner=lambda *args: time.sleep(60))\n"
    "sys.stdin.reconfigure(encoding='utf-8')\n"
    "sys.exit(solver_process.main())\n"
)


class StopReachesTheChildTests(unittest.TestCase):
    """Cancel, skip and timeout end a run in the child process (RUNNER-3)."""

    def run_in_background(self, token=None, timeout=None, command=None, on_first_log=None):
        """
        Start run_solver in the child on an endless run, on a thread.

        Returns (thread, outcome, children, first_log): outcome gets "result"
        and "returned" (perf_counter time) when run_solver returns.

        on_first_log runs once, when the child's first log line arrives, so a
        stop is sent while the solver is really running. command replaces the
        child's command line. Every child is killed at the end of the test.
        """

        children = replace_child_program(self, command=command)
        first_log = threading.Event()

        def on_event(event):
            if event.type == EVENT_LOG and not first_log.is_set():
                first_log.set()
                if on_first_log is not None:
                    on_first_log()

        outcome = {}

        def run():
            outcome["result"] = run_solver(
                UNSAT_CLAUSES, "walksat", ENDLESS, timeout=timeout, cancel_token=token, event_callback=on_event
            )
            outcome["returned"] = time.perf_counter()

        # Patched on the test thread, so a run that hangs cannot leave it on for later tests.
        patcher = mock.patch.dict(os.environ, {"WIZSAT_SOLVER_PYTHON": sys.executable})
        patcher.start()
        self.addCleanup(patcher.stop)
        worker = threading.Thread(target=run, daemon=True)  # a hang fails the test instead of the test run
        worker.start()
        return worker, outcome, children, first_log

    def stop_and_wait(self, stop):
        # Sent from the test thread while the child is quiet (log level normal),
        # as a real Stop comes: the parent must notice it without a new line.
        token = RunToken()
        worker, outcome, children, first_log = self.run_in_background(token=token)
        self.assertTrue(first_log.wait(30), "the child sent no log line")
        time.sleep(0.3)
        self.assertTrue(worker.is_alive(), "the run ended before the stop")
        stopped = {"at": time.perf_counter()}
        stop(token)
        worker.join(timeout=10)
        self.assertFalse(worker.is_alive(), "run_solver did not return after the stop")
        return outcome["result"], outcome["returned"] - stopped["at"], children

    def test_cancel_returns_cancelled_within_a_second_and_the_child_is_gone(self):
        result, waited, children = self.stop_and_wait(RunToken.cancel)

        self.assertEqual(result.status, "CANCELLED")
        self.assertLess(waited, 1.0)
        self.assertEqual(len(children), 1)
        self.assertIsNotNone(children[0].poll(), "the child process is still running")
        self.assertIsNone(result.solution)

    def test_a_skip_request_returns_skipped(self):
        result, waited, children = self.stop_and_wait(RunToken.skip)

        self.assertEqual(result.status, "SKIPPED")
        self.assertLess(waited, 1.0)
        self.assertIsNotNone(children[0].poll(), "the child process is still running")

    def test_a_timeout_of_a_fifth_of_a_second_returns_timeout(self):
        worker, outcome, children, _ = self.run_in_background(timeout=0.2)
        worker.join(timeout=30)

        self.assertFalse(worker.is_alive(), "run_solver did not return")
        result = outcome["result"]
        self.assertEqual(result.status, "TIMEOUT")
        # The child's own clock: from the start of its run_solver to the solver noticing the limit.
        self.assertGreaterEqual(result.elapsed, 0.19)
        self.assertLess(result.elapsed, 0.5)

    def test_a_child_that_ignores_its_timeout_is_killed_shortly_after_the_limit(self):
        started = {}
        worker, outcome, children, first_log = self.run_in_background(
            timeout=0.2,
            command=[sys.executable, "-c", SLEEPING_CHILD],
            on_first_log=lambda: started.setdefault("at", time.perf_counter()),
        )
        self.assertTrue(first_log.wait(30), "the child sent no log line")
        worker.join(timeout=10)

        self.assertFalse(worker.is_alive(), "run_solver did not return")
        result = outcome["result"]
        self.assertEqual(result.status, "TIMEOUT")
        # The sleeping solver would run for 60 s; the parent ends it within its margin of the limit.
        self.assertLess(outcome["returned"] - started["at"], 0.2 + solver_process.KILL_MARGIN_SECONDS + 1.0)
        self.assertIsNotNone(children[0].poll(), "the child process is still running")
        self.assertIsNone(result.error)

    def test_a_result_already_sent_wins_over_a_stop(self):
        # The parent lags behind the child's lines (a slow event callback). The
        # stop comes after the child sent its result: the run finished, and its
        # result must not be replaced by CANCELLED.
        script = (
            "import json, sys\n"
            "sys.stdin.read()\n"
            "for n in range(3): print(json.dumps({'type': 'log', 'message': f'line {n}'}))\n"
            "print(json.dumps({'type': 'result', 'status': 'SAT', 'solution': {'1': True},"
            " 'stats': {}, 'error': None, 'elapsed': 0.01}))\n"
        )
        replace_child_program(self, script=script)
        token = RunToken()

        def slow_callback(event):
            if not token.is_cancelled():
                token.cancel()
                time.sleep(0.5)  # meanwhile the other lines and the end of stdout are queued

        result = run_in_child(sys.executable, request_for("cdcl", SAT_CLAUSES), slow_callback, token)

        self.assertEqual(result["status"], "SAT")
        self.assertNotIn("killed", result)


def result_line(**fields):
    """A result line as the child writes it, with some fields replaced."""

    line = {"type": "result", "status": "SAT", "solution": {"1": True}, "stats": {}, "error": None, "elapsed": 0.01}
    line.update(fields)
    return json.dumps(line)


class ChildFailuresBecomeErrorTests(unittest.TestCase):
    """A child that cannot run, or breaks the protocol, gives an ERROR run; run_solver never raises (RUNNER-4)."""

    def run_solver_with(self, python=sys.executable, script=None):
        """
        run_solver in the child, on a thread so a hang fails the test; return (result, log messages, children).

        script replaces the child's program (run as `python -c script`).
        """

        children = replace_child_program(self, script=script)
        patcher = mock.patch.dict(os.environ, {"WIZSAT_SOLVER_PYTHON": python})
        patcher.start()
        self.addCleanup(patcher.stop)
        events = []
        outcome = {}

        def run():
            try:
                outcome["result"] = run_solver(SAT_CLAUSES, "cdcl", event_callback=events.append)
            except BaseException as exc:  # noqa: BLE001 - the test reports it
                outcome["raised"] = exc

        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        worker.join(timeout=30)
        self.assertFalse(worker.is_alive(), "run_solver did not return")
        self.assertNotIn("raised", outcome, f"run_solver raised {outcome.get('raised')!r}")
        return outcome["result"], [event.message for event in events if event.type == EVENT_LOG], children

    def assert_error(self, result, messages, *parts):
        self.assertEqual(result.status, "ERROR")
        self.assertIsNone(result.solution)
        for part in parts:
            self.assertIn(part, result.error)
        # The run's log says what went wrong too.
        self.assertTrue(any(result.error in message for message in messages), messages)

    def test_an_interpreter_that_does_not_exist(self):
        missing = str(Path(ROOT, "no-such-folder", "python"))

        result, messages, _ = self.run_solver_with(python=missing)

        self.assert_error(result, messages, missing, "not found", "WIZSAT_SOLVER_PYTHON")

    def test_a_child_that_exits_without_a_result_shows_the_end_of_its_stderr(self):
        script = "import sys; sys.stderr.write('early lines\\n' * 50 + 'Traceback: the last words\\n'); sys.exit(1)"

        result, messages, _ = self.run_solver_with(script=script)

        self.assert_error(result, messages, "ended without a result", "the last words")

    def test_a_child_that_prints_a_broken_line(self):
        # Each child then hangs: the parent must not wait for it to end.
        broken_lines = {
            "not JSON": "not json at all",
            "JSON that is not an object": "[1, 2]",
            "an unknown type": json.dumps({"type": "progress"}),
            "a log line without its message": json.dumps({"type": "log"}),
            "a result without its fields": json.dumps({"type": "result", "status": "SAT"}),
            "a result with an unknown status": json.dumps(
                {"type": "result", "status": "MAYBE", "solution": None, "stats": {}, "error": None, "elapsed": 0}
            ),
            "a model with a variable that is not a number": result_line(solution={"x": True}),
            "a model with a value that is not a boolean": result_line(solution={"1": "yes"}),
            "a model with an UNSAT status": result_line(status="UNSAT", solution={"1": True}),
            "an elapsed time that is NaN": result_line(elapsed=float("nan")),
            "an error that is not a string": result_line(error={"x": 1}),
            "a statistic that is not a scalar": result_line(stats={"conflicts": [1, 2]}),
        }
        # Built in the child: too long for a command line. json raises RecursionError on it, not ValueError.
        deep = "'[' * 100000 + ']' * 100000"
        for name, line, expression in [(name, line, repr(line)) for name, line in broken_lines.items()] + [
            ("a line nested too deeply", "[[[[[[[[", deep)
        ]:
            with self.subTest(name):
                script = (
                    "import sys, time\n"
                    "sys.stdin.read()\n"
                    f"print({expression}, flush=True)\n"
                    "sys.stderr.write('stderr of the broken child\\n'); sys.stderr.flush()\n"
                    "time.sleep(60)\n"
                )
                started = time.perf_counter()
                result, messages, children = self.run_solver_with(script=script)

                self.assert_error(result, messages, "not part of the protocol", line[:20])
                self.assertLess(time.perf_counter() - started, 10)
                self.assertIsNotNone(children[-1].poll(), "the child process is still running")

    def test_a_good_result_line_is_accepted(self):
        # Guards the broken lines above: the same line with nothing replaced is a result.
        script = f"import sys; sys.stdin.read(); print({result_line()!r})"

        result, _, _ = self.run_solver_with(script=script)

        self.assertEqual((result.status, result.solution), ("SAT", {1: True}))

    def test_a_huge_stderr_does_not_flood_the_message(self):
        script = "import sys; sys.stderr.write('x' * 5_000_000 + ' the last words'); sys.exit(1)"

        result, _, _ = self.run_solver_with(script=script)

        self.assertEqual(result.status, "ERROR")
        self.assertLess(len(result.error), 3000)
        self.assertTrue(result.error.endswith("the last words"))

    def test_a_stop_wins_over_a_broken_line_read_after_it(self):
        # The stop comes while the broken line waits in the queue: the child is
        # killed for the stop, and the run is CANCELLED, not ERROR.
        script = (
            "import json, sys, time\n"
            "sys.stdin.read()\n"
            "print(json.dumps({'type': 'log', 'message': 'started'}), flush=True)\n"
            "print('not json', flush=True)\n"
            "time.sleep(60)\n"
        )
        replace_child_program(self, script=script)
        token = RunToken()

        def slow_callback(event):
            if not token.is_cancelled():
                token.cancel()
                time.sleep(0.5)  # meanwhile the broken line is queued

        result = run_in_child(sys.executable, request_for("cdcl", SAT_CLAUSES), slow_callback, token)

        self.assertEqual(result["status"], "CANCELLED")


if __name__ == "__main__":
    unittest.main()
