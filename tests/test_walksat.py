import unittest

from sat_core.runtime import EVENT_LOG
from sat_core.runtime import RunToken
from sat_core.solver_registry import run_solver
from solvers.walksat import _UnsatisfiedTracker, walksat


def satisfies(clauses, model):
    if model is None:
        return False

    for clause in clauses:
        if not any((lit > 0 and model.get(abs(lit))) or (lit < 0 and not model.get(abs(lit))) for lit in clause):
            return False
    return True


def unsatisfied_count(clauses, model):
    return sum(
        1
        for clause in clauses
        if not any((lit > 0 and model.get(abs(lit))) or (lit < 0 and not model.get(abs(lit))) for lit in clause)
    )


class WalkSATTests(unittest.TestCase):
    def test_walksat_finds_simple_sat_model(self):
        formula = [[1], [2, -1]]

        solution, stats = walksat(
            formula,
            return_stats=True,
            logging_options={"random_seed": 1, "max_tries": 5, "max_flips": 20},
        )

        self.assertEqual(stats["status"], "SAT")
        self.assertTrue(satisfies(formula, solution))

    def test_walksat_exhaustion_is_unknown_not_unsat(self):
        solution, stats = walksat(
            [[1], [-1]],
            return_stats=True,
            logging_options={"random_seed": 1, "max_tries": 1, "max_flips": 1},
        )

        self.assertIsNone(solution)
        self.assertEqual(stats["status"], "UNKNOWN")
        self.assertEqual(stats["termination_reason"], "budget_exhausted")
        self.assertNotEqual(stats["status"], "UNSAT")

    def test_best_assignment_matches_best_unsatisfied_on_exhaustion(self):
        formula = [[1], [-1]]

        solution, stats = walksat(
            formula,
            return_stats=True,
            logging_options={"random_seed": 1, "max_tries": 1, "max_flips": 1},
        )

        self.assertIsNone(solution)
        self.assertIsNotNone(stats["best_assignment"])
        self.assertEqual(unsatisfied_count(formula, stats["best_assignment"]), stats["best_unsatisfied"])

    def test_flip_effect_reports_make_and_break(self):
        clauses = [[1], [-1, 2], [-2]]
        tracker = _UnsatisfiedTracker(clauses, [1, 2], {1: False, 2: False})

        effect = tracker.flip_effect(1)

        self.assertEqual(effect["make"], 1)
        self.assertEqual(effect["break"], 1)
        self.assertEqual(effect["unsatisfied_after"], 1)
        self.assertEqual(effect["delta"], 0)

    def test_restart_stats_and_hard_clause_hits_are_recorded(self):
        _solution, stats = walksat(
            [[1], [-1]],
            return_stats=True,
            logging_options={"random_seed": 2, "max_tries": 3, "max_flips": 2},
        )

        self.assertEqual(stats["status"], "UNKNOWN")
        self.assertEqual(len(stats["restart_stats"]), 3)
        self.assertEqual(sum(stats["hard_clause_hits"].values()), stats["flips"])
        for restart in stats["restart_stats"]:
            self.assertIn("best_unsatisfied", restart)
            self.assertIn("flips_until_best", restart)
            self.assertIn("final_unsatisfied", restart)

    def test_seeded_walksat_runs_are_reproducible(self):
        formula = [[1, 2], [-1, 2], [1, -2]]
        options = {"random_seed": 11, "max_tries": 3, "max_flips": 20, "noise": 0.4}

        first_solution, first_stats = walksat(formula, return_stats=True, logging_options=options)
        second_solution, second_stats = walksat(formula, return_stats=True, logging_options=options)

        self.assertEqual(first_stats["status"], second_stats["status"])
        self.assertEqual(first_stats["flips"], second_stats["flips"])
        self.assertEqual(first_solution, second_solution)

    def test_seeded_probsat_runs_are_reproducible(self):
        formula = [[1, 2], [-1, 2], [1, -2]]
        options = {
            "random_seed": 11,
            "max_tries": 3,
            "max_flips": 20,
            "noise": 0.0,
            "selection_mode": "probsat",
        }

        first_solution, first_stats = walksat(formula, return_stats=True, logging_options=options)
        second_solution, second_stats = walksat(formula, return_stats=True, logging_options=options)

        self.assertEqual(first_stats["status"], second_stats["status"])
        self.assertEqual(first_stats["flips"], second_stats["flips"])
        self.assertEqual(first_stats["last_make"], second_stats["last_make"])
        self.assertEqual(first_stats["last_break"], second_stats["last_break"])
        self.assertEqual(first_solution, second_solution)

    def test_periodic_logging_includes_walksat_strategy_and_noise(self):
        events = []

        walksat(
            [[1], [-1]],
            return_stats=True,
            event_callback=events.append,
            logging_options={
                "random_seed": 1,
                "max_tries": 1,
                "max_flips": 2,
                "mode": "periodic",
                "progress_interval": 1,
                "selection_mode": "probsat",
                "adaptive_noise": True,
            },
        )

        messages = [event.message for event in events if event.type == EVENT_LOG]
        self.assertTrue(any("WalkSAT options" in message and "strategy=probsat" in message for message in messages))
        self.assertTrue(any("WalkSAT progress" in message and "adaptive_noise=on" in message for message in messages))
        self.assertTrue(any("last_make=" in message and "last_break=" in message for message in messages))

    def test_debug_logging_includes_probsat_weight(self):
        events = []

        walksat(
            [[1, 2], [-1], [-2]],
            return_stats=True,
            event_callback=events.append,
            logging_options={
                "random_seed": 1,
                "max_tries": 1,
                "max_flips": 2,
                "noise": 0,
                "mode": "debug",
                "verbose_limit": 10,
                "selection_mode": "probsat",
            },
        )

        messages = [event.message for event in events if event.type == EVENT_LOG]
        self.assertTrue(any("probsat flip variable" in message and "weight=" in message for message in messages))

    def test_adaptive_noise_records_final_noise(self):
        _solution, stats = walksat(
            [[1], [-1]],
            return_stats=True,
            logging_options={
                "random_seed": 4,
                "max_tries": 1,
                "max_flips": 120,
                "noise": 0.1,
                "adaptive_noise": True,
            },
        )

        self.assertIn("final_noise", stats)
        self.assertGreaterEqual(stats["final_noise"], 0.1)
        self.assertLessEqual(stats["final_noise"], 0.9)

    def test_walksat_cancellation_and_timeout_statuses(self):
        cancelled = RunToken()
        cancelled.cancel()
        _solution, cancelled_stats = walksat([[1]], return_stats=True, cancel_token=cancelled)

        timed_out = RunToken(timeout_seconds=0)
        _solution, timeout_stats = walksat([[1]], return_stats=True, cancel_token=timed_out)

        self.assertEqual(cancelled_stats["status"], "CANCELLED")
        self.assertEqual(timeout_stats["status"], "TIMEOUT")

    def test_run_solver_supports_walksat(self):
        result = run_solver([[1]], "walksat", {"random_seed": 3})

        self.assertEqual(result.solver, "walksat")
        self.assertEqual(result.status, "SAT")
        self.assertIn("flips", result.stats)

    def test_run_solver_maps_walksat_options(self):
        result = run_solver(
            [[1], [-1]],
            "walksat",
            {"random_seed": 9, "max_tries": 2, "max_flips": 3, "noise": 0.25, "adaptive_noise": True},
        )

        self.assertEqual(result.status, "UNKNOWN")
        self.assertIsNone(result.solution)
        self.assertEqual(result.stats["tries"], 2)
        self.assertEqual(result.stats["flips"], 6)
        self.assertEqual(result.stats["selection_mode"], "walksat")
        self.assertTrue(result.stats["adaptive_noise"])
        self.assertNotIn("best_assignment", result.stats)
        self.assertNotIn("hard_clause_hits", result.stats)

    def test_run_solver_probsat_uses_probabilistic_selection(self):
        result = run_solver([[1], [-1]], "ProbSAT", {"random_seed": 11, "max_tries": 4, "max_flips": 5, "noise": 0.15})

        self.assertEqual(result.solver, "probsat")
        self.assertEqual(result.status, "UNKNOWN")
        self.assertEqual(result.stats["tries"], 4)
        self.assertEqual(result.stats["flips"], 20)
        self.assertEqual(result.stats["selection_mode"], "probsat")

    def test_run_solver_rejects_invalid_options(self):
        with self.assertRaises(ValueError):
            run_solver([[1]], "walksat", {"noise": 1.5})
        with self.assertRaises(ValueError):
            run_solver([[1]], "walksat", {"unknown": 1})

if __name__ == "__main__":
    unittest.main()
