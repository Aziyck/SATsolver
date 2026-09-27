import unittest

from sat_core.runtime import EVENT_LOG, EVENT_PROGRESS, RunEvent, RunToken
from sat_core.solver_registry import all_solvers, get_solver, options_summary, run_solver


def log_messages(events):
    return [event.message for event in events if event.type == EVENT_LOG]


class RunTokenTests(unittest.TestCase):
    def test_run_event_serializes(self):
        data = RunEvent(EVENT_PROGRESS, "halfway", current=1, total=2).as_dict()

        self.assertEqual(data["type"], EVENT_PROGRESS)
        self.assertEqual(data["message"], "halfway")
        self.assertEqual((data["current"], data["total"]), (1, 2))
        self.assertIn("created_at", data)

    def test_child_token_sees_parent_cancel_and_skip(self):
        parent = RunToken()
        child = RunToken(timeout_seconds=60, parent=parent)
        self.assertFalse(child.is_cancelled())

        parent.skip()
        self.assertTrue(child.skip_requested())
        parent.clear_skip()
        parent.cancel()
        self.assertTrue(child.is_cancelled())

    def test_zero_timeout_expires_immediately(self):
        self.assertTrue(RunToken(timeout_seconds=0).timed_out())


class RunSolverTests(unittest.TestCase):
    def test_registry_lists_four_solvers(self):
        self.assertEqual([spec.key for spec in all_solvers()], ["cdcl", "dpll", "walksat", "probsat"])
        self.assertEqual(get_solver("CDCL").key, "cdcl")
        self.assertEqual(get_solver("Prob SAT").key, "probsat")
        with self.assertRaises(ValueError):
            get_solver("minisat")

    def test_every_solver_finds_a_model(self):
        formula = [[1, 2], [-1, 2], [-2, 3]]
        for spec in all_solvers():
            with self.subTest(solver=spec.key):
                result = run_solver(formula, spec.key, {"random_seed": 1} if spec.key != "dpll" else None)
                self.assertEqual(result.status, "SAT")
                self.assertTrue(result.solution[2] and result.solution[3])

    def test_complete_solvers_prove_unsat(self):
        for key in ("cdcl", "dpll"):
            with self.subTest(solver=key):
                self.assertEqual(run_solver([[1, 2], [1, -2], [-1, 2], [-1, -2]], key).status, "UNSAT")

    def test_cancel_before_start(self):
        for key in ("cdcl", "dpll", "walksat"):
            token = RunToken()
            token.cancel()
            with self.subTest(solver=key):
                self.assertEqual(run_solver([[1]], key, cancel_token=token).status, "CANCELLED")

    def test_timeout_before_start(self):
        events = []
        result = run_solver([[1]], "cdcl", timeout=0, event_callback=events.append)

        self.assertEqual(result.status, "TIMEOUT")
        self.assertTrue(any("timed out" in message for message in log_messages(events)))

    def test_skip_before_start(self):
        token = RunToken()
        token.skip()

        self.assertEqual(run_solver([[1]], "cdcl", cancel_token=token).status, "SKIPPED")

    def test_normal_logging_reports_start_finish_and_stats(self):
        events = []
        run_solver([[1]], "cdcl", event_callback=events.append)
        messages = log_messages(events)

        self.assertTrue(any("Solving with CDCL" in message for message in messages))
        self.assertTrue(any("CDCL finished: SAT" in message for message in messages))
        self.assertTrue(any("CDCL stats" in message for message in messages))

    def test_periodic_and_debug_logging(self):
        events = []
        run_solver([[1, 2], [-1, 2]], "cdcl", log_level="periodic", progress_interval=1, event_callback=events.append)
        self.assertTrue(any("CDCL progress" in message for message in log_messages(events)))

        events = []
        run_solver([[1, 2], [-1, 2]], "dpll", log_level="debug", progress_interval=1, event_callback=events.append)
        self.assertTrue(any("DPLL debug" in message for message in log_messages(events)))

        with self.assertRaises(ValueError):
            run_solver([[1]], "cdcl", log_level="chatty")

    def test_solver_exceptions_become_error_status(self):
        # 1,500 independent 2-clauses need 1,500 nested DPLL decisions, deeper
        # than Python's default recursion limit.
        clauses = [[2 * i + 1, 2 * i + 2] for i in range(1500)]

        result = run_solver(clauses, "dpll")

        self.assertEqual(result.status, "ERROR")
        self.assertIn("recursion limit", result.error)
        self.assertEqual(run_solver(clauses, "cdcl").status, "SAT")

    def test_cdcl_options_are_applied(self):
        formula = [[1, 2], [-1, 2], [1, -2]]
        for branching in ("vsids", "frequent", "moms", "dlis", "random"):
            with self.subTest(branching=branching):
                result = run_solver(formula, "cdcl", {"branching": branching, "random_seed": 3})
                self.assertEqual(result.status, "SAT")

        spec = get_solver("cdcl")
        options = spec.parse_options({"branching": "moms", "restarts": True, "restart_interval": 5})
        self.assertEqual(options_summary(spec, options), "branching=MOMS; restarts=on; restart_interval=5")
        self.assertEqual(options_summary(spec, spec.default_options()), "defaults")

    def test_public_stats_are_small_scalars(self):
        result = run_solver([[1, 2], [-1, 2]], "walksat", {"random_seed": 2})

        self.assertTrue(all(isinstance(value, (int, float, str, bool, type(None))) for value in result.stats.values()))


if __name__ == "__main__":
    unittest.main()
