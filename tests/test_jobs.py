import json
import os
import platform
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fake_python import write_fake_python
from sat_core.benchmark import parse_request
from sat_core.dimacs import parse_dimacs
from sat_core.environment import run_environment
from sat_core.jobs import execute_job, parse_solve_request, solve_job
from sat_core.params import ParamError
from sat_core.runtime import (
    EVENT_CANCELLED,
    EVENT_DONE,
    EVENT_ENVIRONMENT,
    EVENT_ERROR,
    EVENT_INSTANCE,
    EVENT_PROGRESS,
    EVENT_RESULT,
    EVENT_ROW,
    RunToken,
)


def run(kind, request, workdir=None, token=None):
    events = []
    execute_job(kind, request, workdir, events.append, token or RunToken())
    return events


def of_type(events, event_type):
    return [event for event in events if event.type == event_type]


class JobTests(unittest.TestCase):
    def test_solve_job_reports_instance_result_and_files(self):
        with tempfile.TemporaryDirectory() as workdir:
            events = run("solve", {"problem": "n_queens", "params": {"size": 6}, "solver": "cdcl"}, workdir)

            instance = of_type(events, EVENT_INSTANCE)[0].payload
            result = of_type(events, EVENT_RESULT)[0].payload
            self.assertEqual(events[-1].type, EVENT_DONE)
            self.assertEqual(instance["problem"], "n_queens")
            self.assertEqual(instance["expected"], "SAT")
            self.assertEqual(instance["visual"], {"size": 6})
            self.assertEqual(result["status"], "SAT")
            self.assertTrue(result["verified"])
            self.assertEqual(len(result["decoded"]["queens"]), 6)

            cnf = parse_dimacs((Path(workdir) / instance["cnf_file"]).read_text())
            self.assertEqual(cnf.app_header, {"problem": "n_queens", "params": {"size": 6}})
            self.assertEqual(len(cnf.clauses), instance["clauses"])
            self.assertTrue((Path(workdir) / result["model_file"]).read_text().startswith("s SATISFIABLE"))

    SOLVE_REQUEST = {"problem": "n_queens", "params": {"size": 6}, "solver": "cdcl"}

    def test_a_solve_job_reports_its_peak_memory_and_the_baseline_after_encoding(self):
        stats = of_type(run("solve", self.SOLVE_REQUEST), EVENT_RESULT)[0].payload["stats"]

        self.assertGreater(stats["baseline_memory_mb"], 0)
        self.assertGreaterEqual(stats["peak_memory_mb"], stats["baseline_memory_mb"])

    def test_the_baseline_is_read_before_the_solver_and_the_peak_after_it(self):
        # Two readings in this order; reading both at one moment, or swapped, would not give 10 and 25.
        with mock.patch("sat_core.jobs.peak_memory_mb", side_effect=[10.04, 25.0]):
            stats = of_type(run("solve", self.SOLVE_REQUEST), EVENT_RESULT)[0].payload["stats"]

        self.assertEqual((stats["baseline_memory_mb"], stats["peak_memory_mb"]), (10.0, 25.0))

    def test_a_platform_that_cannot_say_leaves_the_memory_stats_out_never_zero(self):
        with mock.patch("sat_core.jobs.peak_memory_mb", return_value=None):
            stats = of_type(run("solve", self.SOLVE_REQUEST), EVENT_RESULT)[0].payload["stats"]

        self.assertNotIn("peak_memory_mb", stats)
        self.assertNotIn("baseline_memory_mb", stats)

    def test_with_the_solver_child_the_job_peak_is_not_reported_as_the_solvers(self):
        # The solver runs in another process then, so this process's peak says nothing about it (MEM-3 measures that).
        with mock.patch.dict(os.environ, {"WIZSAT_SOLVER_PYTHON": sys.executable}):
            stats = of_type(run("solve", {**self.SOLVE_REQUEST, "interpreter": "pypy"}), EVENT_RESULT)[0].payload["stats"]

        self.assertIn("decisions", stats)  # the run itself worked, in the child
        self.assertNotIn("peak_memory_mb", stats)
        self.assertNotIn("baseline_memory_mb", stats)

    def test_every_job_first_reports_the_environment_it_runs_in(self):
        # Sent before the request is checked, so a job that fails still says where it ran (META-2).
        for kind, request in (
            ("solve", {"problem": "n_queens", "params": {"size": 4}, "solver": "cdcl"}),
            ("benchmark", {"problems": ["n_queens"], "segments": [{"size": 4}], "solvers": ["cdcl"]}),
            ("solve", {"problem": "chess"}),
        ):
            with self.subTest(kind=kind, request=request), mock.patch.dict(os.environ):
                # The job's own interpreter is the one compared with.
                os.environ.pop("WIZSAT_SOLVER_PYTHON", None)
                events = run(kind, request)
                self.assertEqual(events[0].type, EVENT_ENVIRONMENT)
                self.assertEqual(events[0].payload, run_environment())
                self.assertEqual(len(of_type(events, EVENT_ENVIRONMENT)), 1)

    def test_jobs_that_run_solvers_record_the_solver_interpreter(self):
        # RUNNER-6: with the setting on, the solvers run under that
        # interpreter. A generate job runs none, so it keeps its own.
        with tempfile.TemporaryDirectory() as folder:
            fake = write_fake_python(folder, "PyPy", "3.10.14")
            for kind, request, expected in (
                ("solve", {"problem": "n_queens", "params": {"size": 4}, "solver": "cdcl", "interpreter": "pypy"}, ("PyPy", "3.10.14")),
                (
                    "benchmark",
                    {"problems": ["n_queens"], "segments": [{"size": 4}], "solvers": ["cdcl"], "interpreter": "pypy"},
                    ("PyPy", "3.10.14"),
                ),
                ("generate", {"problem": "n_queens", "params": {"size": 4}}, (platform.python_implementation(), platform.python_version())),
            ):
                with self.subTest(kind=kind), mock.patch.dict(os.environ, {"WIZSAT_SOLVER_PYTHON": fake}):
                    environment = of_type(run(kind, request), EVENT_ENVIRONMENT)[0].payload
                    self.assertEqual((environment["python_implementation"], environment["python_version"]), expected)

    def test_a_job_that_names_python_runs_in_process_even_when_the_setting_is_set(self):
        # INTERP-2: the setting makes PyPy available; the request chooses. No field means python.
        with tempfile.TemporaryDirectory() as folder:
            fake = write_fake_python(folder, "PyPy", "3.10.14")
            for interpreter in ({"interpreter": "python"}, {}):
                with self.subTest(interpreter), mock.patch.dict(os.environ, {"WIZSAT_SOLVER_PYTHON": fake}):
                    events = run("solve", {**self.SOLVE_REQUEST, **interpreter})

                    environment = of_type(events, EVENT_ENVIRONMENT)[0].payload
                    self.assertEqual(environment["python_implementation"], platform.python_implementation())
                    self.assertEqual(of_type(events, EVENT_RESULT)[0].payload["status"], "SAT")  # solved here, not by the fake

    def test_a_job_that_names_pypy_finds_it_itself_on_path(self):
        # The setting is unset: the job process looks pypy3 up on PATH, as the server did (find_pypy).
        with tempfile.TemporaryDirectory() as folder:
            write_fake_python(folder, "PyPy", "3.10.14", name="pypy3")
            with mock.patch.dict(os.environ, {"PATH": folder}):
                os.environ.pop("WIZSAT_SOLVER_PYTHON", None)
                events = run("solve", {**self.SOLVE_REQUEST, "interpreter": "pypy"})

        environment = of_type(events, EVENT_ENVIRONMENT)[0].payload
        self.assertEqual((environment["python_implementation"], environment["python_version"]), ("PyPy", "3.10.14"))

    def test_a_job_that_names_pypy_when_there_is_none_ends_in_an_error_that_says_so(self):
        with tempfile.TemporaryDirectory() as empty, mock.patch.dict(os.environ, {"PATH": empty}):
            os.environ.pop("WIZSAT_SOLVER_PYTHON", None)
            events = run("solve", {**self.SOLVE_REQUEST, "interpreter": "pypy"})

        self.assertEqual(events[0].type, EVENT_ENVIRONMENT)  # a failed job still says where it ran
        self.assertEqual(events[-1].type, EVENT_ERROR)
        self.assertIn("interpreter", events[-1].payload["errors"])
        self.assertEqual(of_type(events, EVENT_RESULT), [])

    def test_the_interpreter_is_python_or_pypy_and_nothing_else(self):
        self.assertEqual(parse_solve_request(self.SOLVE_REQUEST)["interpreter"], "python")
        self.assertEqual(parse_solve_request({**self.SOLVE_REQUEST, "interpreter": "pypy"})["interpreter"], "pypy")
        bench = {"problems": ["n_queens"], "segments": [{"size": 4}], "solvers": ["cdcl"]}
        self.assertEqual(parse_request(bench).normalized["interpreter"], "python")
        self.assertEqual(parse_request({**bench, "interpreter": "pypy"}).normalized["interpreter"], "pypy")
        for bad in ("jython", "PyPy", "", None, 3, ["pypy"]):
            with self.subTest(bad=bad):
                with self.assertRaises(ParamError) as caught:
                    parse_solve_request({**self.SOLVE_REQUEST, "interpreter": bad})
                self.assertIn("interpreter", caught.exception.errors)
                with self.assertRaises(ParamError) as caught:
                    parse_request({**bench, "interpreter": bad})
                self.assertIn("interpreter", caught.exception.errors)

    def test_generate_job_only_encodes(self):
        events = run("generate", {"problem": "graph_coloring", "params": {"seed": None}})

        self.assertEqual(len(of_type(events, EVENT_INSTANCE)), 1)
        self.assertEqual(of_type(events, EVENT_RESULT), [])
        self.assertIsInstance(of_type(events, EVENT_INSTANCE)[0].payload["params"]["seed"], int)

    def test_benchmark_job_streams_rows(self):
        events = run("benchmark", {"problems": ["n_queens"], "segments": [{"size": "4,5"}], "solvers": ["cdcl"]})

        self.assertEqual(len(of_type(events, EVENT_ROW)), 2)
        self.assertEqual(events[-1].type, EVENT_DONE)

    def test_invalid_parameters_end_in_an_error_event_with_field_errors(self):
        events = run("solve", {"problem": "n_queens", "params": {"size": 0}, "solver": "cdcl"})

        self.assertEqual(events[-1].type, EVENT_ERROR)
        self.assertIn("size", events[-1].payload["errors"])

        events = run("solve", {"problem": "n_queens", "params": {}, "solver": "cdcl", "options": {"branching": "?"}})
        self.assertIn("options.branching", events[-1].payload["errors"])

    def test_unknown_kind_or_problem(self):
        self.assertEqual(run("dance", {})[-1].type, EVENT_ERROR)
        self.assertEqual(run("solve", {"problem": "chess"})[-1].type, EVENT_ERROR)

    def test_solve_job_refuses_a_negative_timeout(self):
        # The API refuses it too, but solve_job is also reached without the API (audit item A10).
        for timeout in (-1, "abc"):
            with self.subTest(timeout=timeout), self.assertRaises(ParamError) as caught:
                solve_job({"problem": "n_queens", "params": {"size": 4}, "solver": "cdcl", "timeout": timeout}, None, lambda event: None, RunToken())
            self.assertIn("timeout", caught.exception.errors)

    def test_timeout_is_reported_as_a_result(self):
        events = run("solve", {"problem": "n_queens", "params": {"size": 8}, "solver": "cdcl", "timeout": 0})

        self.assertEqual(of_type(events, EVENT_RESULT)[0].payload["status"], "TIMEOUT")
        self.assertEqual(events[-1].type, EVENT_DONE)


class SolveRequestTests(unittest.TestCase):
    """One parser for a solve request: the API and a direct solve_job call refuse the same things (ARCH-4)."""

    def test_parse_solve_request_returns_the_normalized_request(self):
        from sat_core.jobs import parse_solve_request

        normalized = parse_solve_request(
            {"problem": "random_3sat", "params": {"variables": 20, "ratio": 4, "mode": "random"}, "solver": "walksat", "options": {"max_flips": 500}, "timeout": "7"}
        )

        self.assertEqual(
            set(normalized), {"problem", "params", "solver", "options", "timeout", "log_level", "interpreter"}
        )
        self.assertEqual(normalized["problem"], "random_3sat")
        self.assertEqual(normalized["solver"], "walksat")
        self.assertEqual(normalized["options"]["max_flips"], 500)
        self.assertEqual(normalized["timeout"], 7.0)
        self.assertEqual(normalized["log_level"], "normal")
        self.assertIsInstance(normalized["params"]["seed"], int)  # a blank seed is made concrete
        self.assertNotIn("sat_percent", normalized["params"])  # a hidden parameter is not stored

    def test_parse_solve_request_fills_defaults_and_is_idempotent(self):
        from sat_core.jobs import DEFAULT_SOLVE_TIMEOUT, parse_solve_request

        normalized = parse_solve_request({"problem": "n_queens", "params": {"size": 6}})

        self.assertEqual(normalized["solver"], "cdcl")
        self.assertEqual(normalized["timeout"], DEFAULT_SOLVE_TIMEOUT)
        self.assertEqual(parse_solve_request(normalized), normalized)

    def test_a_normalized_request_parses_to_itself_for_every_problem_and_solver(self):
        from problems import all_problems
        from sat_core.jobs import parse_solve_request
        from sat_core.solver_registry import all_solvers

        for spec in all_problems():
            with self.subTest(problem=spec.key):
                normalized = parse_solve_request({"problem": spec.key})
                self.assertEqual(parse_solve_request(normalized), normalized)
        for solver in all_solvers():
            with self.subTest(solver=solver.key):
                normalized = parse_solve_request({"problem": "n_queens", "params": {"size": 6}, "solver": solver.key})
                self.assertEqual(parse_solve_request(normalized), normalized)

    def test_generate_job_called_directly_refuses_an_unknown_problem(self):
        events = run("generate", {"problem": "chess"})

        self.assertEqual(events[-1].type, EVENT_ERROR)
        self.assertIn("problem", events[-1].payload["errors"])

    def test_parse_solve_request_names_each_bad_field(self):
        from sat_core.jobs import parse_solve_request

        base = {"problem": "n_queens", "params": {"size": 6}, "solver": "cdcl"}
        cases = {
            "problem": {**base, "problem": "chess"},
            "solver": {**base, "solver": "minisat"},
            "options.branching": {**base, "options": {"branching": "?"}},
            "timeout": {**base, "timeout": -1},
            "log_level": {**base, "log_level": "loud"},
            "size": {**base, "params": {"size": 0}},
        }
        for field, request in cases.items():
            with self.subTest(field=field), self.assertRaises(ParamError) as caught:
                parse_solve_request(request)
            self.assertIn(field, caught.exception.errors)

    def test_solve_job_called_directly_refuses_what_the_api_refuses(self):
        base = {"problem": "n_queens", "params": {"size": 6}, "solver": "cdcl"}
        cases = {
            "problem": {**base, "problem": "chess"},
            "solver": {**base, "solver": "minisat"},
            "options.branching": {**base, "options": {"branching": "?"}},
            "timeout": {**base, "timeout": -1},
            "log_level": {**base, "log_level": "loud"},
        }
        for field, request in cases.items():
            with self.subTest(field=field), self.assertRaises(ParamError) as caught:
                solve_job(request, None, lambda event: None, RunToken())
            self.assertIn(field, caught.exception.errors)

    def test_solve_job_called_directly_refuses_an_instance_over_the_clause_limit(self):
        with self.assertRaises(ParamError) as caught:
            solve_job({"problem": "hamiltonian_path", "params": {"nodes": 400, "probability": 0.1}, "solver": "cdcl"}, None, lambda event: None, RunToken())
        self.assertIn("_", caught.exception.errors)


class PayloadShapeTests(unittest.TestCase):
    """The JSON of a solve job's instance and result events, byte for byte (ARCH-7)."""

    golden = Path(__file__).parent / "fixtures" / "solve_payloads.golden.json"

    def test_solve_events_keep_their_json(self):
        events = run("solve", {"problem": "sudoku", "params": {"size": 9}, "solver": "cdcl"})
        payloads = {event.type: event.payload for event in events if event.type in (EVENT_INSTANCE, EVENT_RESULT)}

        # Timings and memory are the only values that differ between runs; they must still be there.
        stats = payloads["result"]["stats"]
        measured = ((payloads["instance"], "encode_seconds"), (payloads["result"], "elapsed"), (stats, "elapsed"))
        for container, key in measured + ((stats, "baseline_memory_mb"), (stats, "peak_memory_mb")):
            self.assertIsInstance(container[key], float)
            container[key] = 0.0

        recorded = json.dumps(payloads, indent=1) + "\n"
        if os.environ.get("WIZSAT_RECORD_GOLDEN") == "1":
            # A deliberate change of a payload (a new statistic, a new field): record it and review the diff.
            self.golden.write_text(recorded, encoding="utf-8", newline="\n")
        expected = self.golden.read_text(encoding="utf-8").replace("\r\n", "\n")
        self.assertEqual(recorded, expected)


class PayloadTypeTests(unittest.TestCase):
    def test_instance_summary_is_frozen_and_serialises_in_its_field_order(self):
        from dataclasses import FrozenInstanceError

        from sat_core.models import InstanceSummary

        summary = InstanceSummary(
            name="N", problem="p", params={"a": 1}, variables=2, clauses=3, size_variables=2, max_variable=2,
            facts=[], visual={}, expected=None, encode_seconds=0.5, cnf_file=None,
        )

        self.assertEqual(
            list(summary.to_dict()),
            ["name", "problem", "params", "variables", "clauses", "size_variables", "max_variable", "facts", "visual", "expected", "encode_seconds", "cnf_file"],
        )
        self.assertEqual(summary.to_dict()["params"], {"a": 1})
        with self.assertRaises(FrozenInstanceError):
            summary.name = "other"

    def test_solve_outcome_is_frozen_and_serialises_in_its_field_order(self):
        from dataclasses import FrozenInstanceError

        from sat_core.models import SolveOutcome

        outcome = SolveOutcome(
            solver="cdcl", solver_label="CDCL", options={}, options_summary="defaults", status="SAT", elapsed=0.1, stats={},
            decoded=None, verified=True, check_errors=[], expected=None, timeout=60.0, error=None, model_file=None,
        )

        self.assertEqual(
            list(outcome.to_dict()),
            ["solver", "solver_label", "options", "options_summary", "status", "elapsed", "stats", "decoded", "verified", "check_errors", "expected", "timeout", "error", "model_file"],
        )
        with self.assertRaises(FrozenInstanceError):
            outcome.status = "UNSAT"

    def test_the_job_module_builds_no_payload_dict_literal(self):
        source = (Path(__file__).parent.parent / "sat_core" / "jobs.py").read_text(encoding="utf-8")

        for key in ("encode_seconds", "options_summary", "model_file", "size_variables"):
            self.assertFalse(f'"{key}":' in source, f"sat_core/jobs.py still builds a payload dict with the key {key!r}")


def stop_on(kind, request, should_stop):
    """Run a job and press Stop as soon as the job emits an event for which should_stop is true."""

    token = RunToken()
    events = []

    def emit(event):
        events.append(event)
        if should_stop(event):
            token.cancel()

    execute_job(kind, request, None, emit, token)
    return events


class StopTimingTests(unittest.TestCase):
    """A Stop ends a job as cancelled only when it cut the work short (finding A18)."""

    request = {"problem": "n_queens", "params": {"size": 6}, "solver": "cdcl"}

    def test_stop_after_the_result_ends_done(self):
        events = stop_on("solve", self.request, lambda event: event.type == EVENT_RESULT)

        self.assertEqual(of_type(events, EVENT_RESULT)[0].payload["status"], "SAT")
        self.assertEqual(events[-1].type, EVENT_DONE)

    def test_stop_during_the_search_ends_cancelled(self):
        # The Stop lands after the solver has asked the token a few times: inside the search,
        # not at run_solver's check before it starts. 20 queens takes about 30 checks.
        class StopMidSearch(RunToken):
            checks = None

            def is_cancelled(self):
                if self.checks is not None:
                    self.checks += 1
                    if self.checks == 5:
                        self.cancel()
                return super().is_cancelled()

        token = StopMidSearch()
        events = []

        def emit(event):
            events.append(event)
            if event.type == EVENT_PROGRESS and event.message.startswith("Solving"):
                token.checks = 0

        execute_job("solve", {**self.request, "params": {"size": 20}}, None, emit, token)

        self.assertEqual(of_type(events, EVENT_RESULT)[0].payload["status"], "CANCELLED")
        self.assertGreater(token.checks, 5)
        self.assertEqual(events[-1].type, EVENT_CANCELLED)

    def test_stop_before_the_search_ends_cancelled(self):
        events = stop_on("solve", self.request, lambda event: event.type == EVENT_INSTANCE)

        self.assertEqual(of_type(events, EVENT_RESULT), [])
        self.assertEqual(events[-1].type, EVENT_CANCELLED)

    benchmark = {"problems": ["n_queens"], "segments": [{"size": "4,5,6"}], "solvers": ["cdcl"]}

    def test_stopped_benchmark_still_ends_cancelled(self):
        # run_benchmark returns normally after a Stop, with the rows it finished.
        events = stop_on("benchmark", self.benchmark, lambda event: event.type == EVENT_ROW)

        self.assertLess(len(of_type(events, EVENT_ROW)), 3)
        self.assertEqual(events[-1].type, EVENT_CANCELLED)

    def test_stop_after_the_last_benchmark_row_ends_done(self):
        events = stop_on("benchmark", self.benchmark, lambda event: event.type == EVENT_ROW and event.current == event.total)

        self.assertEqual(len(of_type(events, EVENT_ROW)), 3)
        self.assertEqual(events[-1].type, EVENT_DONE)


if __name__ == "__main__":
    unittest.main()
