import tempfile
import unittest
from pathlib import Path

from sat_core.dimacs import parse_dimacs
from sat_core.jobs import execute_job
from sat_core.runtime import (
    EVENT_DONE,
    EVENT_ERROR,
    EVENT_INSTANCE,
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

    def test_timeout_is_reported_as_a_result(self):
        events = run("solve", {"problem": "n_queens", "params": {"size": 8}, "solver": "cdcl", "timeout": 0})

        self.assertEqual(of_type(events, EVENT_RESULT)[0].payload["status"], "TIMEOUT")
        self.assertEqual(events[-1].type, EVENT_DONE)


if __name__ == "__main__":
    unittest.main()
