import unittest

from sat_core.runtime import EVENT_LOG
from sat_core.runtime import RunToken
from sat_core.solver_runner import solve_clauses
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

    def test_solver_runner_supports_walksat(self):
        result = solve_clauses([[1]], "WalkSAT", logging_options={"random_seed": 3})

        self.assertEqual(result.solver, "WalkSAT")
        self.assertEqual(result.status, "SAT")
        self.assertIn("flips", result.stats)

    def test_solver_runner_maps_walksat_specific_options(self):
        result = solve_clauses(
            [[1], [-1]],
            "WalkSAT",
            logging_options={
                "random_seed": 1,
                "walksat_random_seed": 9,
                "walksat_max_tries": 2,
                "walksat_max_flips": 3,
                "walksat_noise": 0.25,
                "walksat_selection_mode": "probsat",
                "walksat_adaptive_noise": True,
            },
        )

        self.assertEqual(result.status, "UNKNOWN")
        self.assertIn("tries=2", result.stats["solver_options"])
        self.assertIn("flips=3", result.stats["solver_options"])
        self.assertIn("noise=0.25", result.stats["solver_options"])
        self.assertIn("strategy=probsat", result.stats["solver_options"])
        self.assertIn("adaptive_noise=on", result.stats["solver_options"])
        self.assertIn("seed=9", result.stats["solver_options"])

    def test_solver_runner_maps_probsat_specific_options(self):
        result = solve_clauses(
            [[1], [-1]],
            "ProbSAT",
            logging_options={
                "random_seed": 1,
                "walksat_random_seed": 9,
                "walksat_max_tries": 2,
                "walksat_max_flips": 3,
                "walksat_noise": 0.25,
                "probsat_random_seed": 11,
                "probsat_max_tries": 4,
                "probsat_max_flips": 5,
                "probsat_noise": 0.15,
                "probsat_adaptive_noise": True,
            },
        )

        self.assertEqual(result.solver, "ProbSAT")
        self.assertEqual(result.status, "UNKNOWN")
        self.assertIn("tries=4", result.stats["solver_options"])
        self.assertIn("flips=5", result.stats["solver_options"])
        self.assertIn("noise=0.15", result.stats["solver_options"])
        self.assertIn("strategy=probsat", result.stats["solver_options"])
        self.assertIn("adaptive_noise=on", result.stats["solver_options"])
        self.assertIn("seed=11", result.stats["solver_options"])


if __name__ == "__main__":
    unittest.main()
