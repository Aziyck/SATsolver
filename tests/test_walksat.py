import random
import unittest

from sat_core.runtime import EVENT_LOG, RunToken
from sat_core.solver_registry import run_solver
from solvers.walksat import LocalSearchState, probsat_weights, walksat


def satisfies(clauses, model):
    if model is None:
        return False
    return all(any(model.get(abs(lit)) == (lit > 0) for lit in clause) for clause in clauses)


def unsatisfied_count(clauses, model):
    return sum(1 for clause in clauses if not any(model.get(abs(lit)) == (lit > 0) for lit in clause))


def brute_force_breaks(clauses, values, variable):
    """Clauses satisfied only by `variable`: the ones its flip would break."""
    count = 0
    for clause in clauses:
        true_vars = [abs(lit) for lit in clause if values[abs(lit)] == (lit > 0)]
        if true_vars == [variable]:
            count += 1
    return count


class LocalSearchStateTests(unittest.TestCase):
    def test_break_counts_stay_exact_after_many_flips(self):
        rng = random.Random(7)
        variables = list(range(1, 13))
        clauses = [[v * rng.choice((-1, 1)) for v in rng.sample(variables, 3)] for _ in range(50)]
        values = [False] + [rng.random() < 0.5 for _ in variables]
        state = LocalSearchState(clauses, variables, values)

        for _ in range(300):
            state.flip(rng.choice(variables))
            for variable in variables:
                self.assertEqual(state.breaks[variable], brute_force_breaks(clauses, values, variable))
            expected_unsat = {index for index, clause in enumerate(clauses) if not any(values[abs(l)] == (l > 0) for l in clause)}
            self.assertEqual(set(state.unsat), expected_unsat)

    def test_make_and_break_of_a_small_example(self):
        clauses = [[1], [-1, 2], [-2]]
        state = LocalSearchState(clauses, [1, 2], [False, False, False])
        # x1=False, x2=False: [1] is unsatisfied, [-1, 2] and [-2] are satisfied.
        self.assertEqual(state.make_of(1), 1)       # flipping x1 satisfies [1]
        self.assertEqual(state.breaks[1], 1)        # ... and breaks [-1, 2], whose only true literal is -1
        self.assertEqual(state.breaks[2], 1)        # x2 alone satisfies [-2]

    def test_probsat_weights_fall_with_break(self):
        poly, family, cb = probsat_weights(3, 4)
        self.assertEqual((family, cb), ("poly", 2.06))
        self.assertTrue(all(a > b for a, b in zip(poly, poly[1:])))
        _exp, family, cb = probsat_weights(5, 4)
        self.assertEqual((family, cb), ("exp", 3.7))


class WalkSATTests(unittest.TestCase):
    def test_walksat_finds_simple_sat_model(self):
        formula = [[1], [2, -1]]
        solution, stats = walksat(formula, return_stats=True, logging_options={"random_seed": 1, "max_tries": 5, "max_flips": 20})
        self.assertEqual(stats["status"], "SAT")
        self.assertTrue(satisfies(formula, solution))

    def test_both_strategies_solve_random_3sat(self):
        rng = random.Random(3)
        formula = [[v * rng.choice((-1, 1)) for v in rng.sample(range(1, 61), 3)] for _ in range(200)]
        for mode in ("walksat", "probsat"):
            with self.subTest(mode=mode):
                solution, stats = walksat(formula, return_stats=True, logging_options={"random_seed": 5, "selection_mode": mode})
                self.assertEqual(stats["status"], "SAT")
                self.assertTrue(satisfies(formula, solution))

    def test_walksat_makes_free_moves_first(self):
        # From x1=x2=False, clause [1, 2] is unsatisfied and neither flip breaks anything.
        _solution, stats = walksat([[1, 2]], return_stats=True, logging_options={"random_seed": 1, "noise": 1.0})
        self.assertEqual(stats["status"], "SAT")
        self.assertEqual(stats["noise_flips"], 0)

    def test_walksat_exhaustion_is_unknown_not_unsat(self):
        solution, stats = walksat([[1], [-1]], return_stats=True, logging_options={"random_seed": 1, "max_tries": 1, "max_flips": 1})
        self.assertIsNone(solution)
        self.assertEqual(stats["status"], "UNKNOWN")
        self.assertEqual(stats["termination_reason"], "budget_exhausted")

    def test_best_assignment_matches_best_unsatisfied_on_exhaustion(self):
        formula = [[1], [-1]]
        solution, stats = walksat(formula, return_stats=True, logging_options={"random_seed": 1, "max_tries": 1, "max_flips": 1})
        self.assertIsNone(solution)
        self.assertIsNotNone(stats["best_assignment"])
        self.assertEqual(unsatisfied_count(formula, stats["best_assignment"]), stats["best_unsatisfied"])

    def test_restart_stats_and_hard_clause_hits_are_recorded(self):
        _solution, stats = walksat([[1], [-1]], return_stats=True, logging_options={"random_seed": 2, "max_tries": 3, "max_flips": 2})
        self.assertEqual(stats["status"], "UNKNOWN")
        self.assertEqual(len(stats["restart_stats"]), 3)
        self.assertEqual(sum(stats["hard_clause_hits"].values()), stats["flips"])
        for restart in stats["restart_stats"]:
            self.assertEqual(set(restart), {"try", "best_unsatisfied", "flips_until_best", "final_unsatisfied"})

    def test_seeded_runs_are_reproducible(self):
        rng = random.Random(4)
        formula = [[v * rng.choice((-1, 1)) for v in rng.sample(range(1, 31), 3)] for _ in range(120)]
        for mode in ("walksat", "probsat"):
            with self.subTest(mode=mode):
                options = {"random_seed": 11, "selection_mode": mode}
                first = walksat(formula, return_stats=True, logging_options=options)
                second = walksat(formula, return_stats=True, logging_options=options)
                self.assertEqual(first[0], second[0])
                self.assertEqual(first[1]["flips"], second[1]["flips"])

    def test_periodic_logging_describes_the_strategy(self):
        events = []
        walksat(
            [[1], [-1]],
            return_stats=True,
            event_callback=events.append,
            logging_options={"random_seed": 1, "max_tries": 1, "max_flips": 2, "mode": "periodic", "progress_interval": 1, "adaptive_noise": True},
        )
        messages = [event.message for event in events if event.type == EVENT_LOG]
        self.assertTrue(any("WalkSAT options" in m and "strategy=walksat" in m for m in messages))
        self.assertTrue(any("WalkSAT progress" in m and "adaptive_noise=on" in m and "last_break=" in m for m in messages))

    def test_debug_logging_includes_probsat_weight(self):
        events = []
        walksat(
            [[1, 2], [-1], [-2]],
            return_stats=True,
            event_callback=events.append,
            logging_options={"random_seed": 1, "max_tries": 1, "max_flips": 2, "mode": "debug", "verbose_limit": 10, "selection_mode": "probsat"},
        )
        messages = [event.message for event in events if event.type == EVENT_LOG]
        self.assertTrue(any("probsat flip variable" in m and "weight=" in m for m in messages))

    def test_adaptive_noise_records_final_noise(self):
        _solution, stats = walksat(
            [[1], [-1]],
            return_stats=True,
            logging_options={"random_seed": 4, "max_tries": 1, "max_flips": 120, "noise": 0.1, "adaptive_noise": True},
        )
        self.assertGreaterEqual(stats["final_noise"], 0.1)
        self.assertLessEqual(stats["final_noise"], 0.9)

    def test_cancellation_and_timeout_statuses(self):
        cancelled = RunToken()
        cancelled.cancel()
        self.assertEqual(walksat([[1]], return_stats=True, cancel_token=cancelled)[1]["status"], "CANCELLED")
        timed_out = RunToken(timeout_seconds=0)
        self.assertEqual(walksat([[1]], return_stats=True, cancel_token=timed_out)[1]["status"], "TIMEOUT")

    def test_timeout_stops_a_long_search(self):
        token = RunToken(timeout_seconds=0.2)
        _solution, stats = walksat([[1], [-1]], return_stats=True, cancel_token=token, logging_options={"max_tries": 10**6, "max_flips": 10**6})
        self.assertEqual(stats["status"], "TIMEOUT")
        self.assertLess(stats["elapsed"], 2)


class RegistryTests(unittest.TestCase):
    def test_run_solver_maps_walksat_options(self):
        result = run_solver([[1], [-1]], "walksat", {"random_seed": 9, "max_tries": 2, "max_flips": 3, "noise": 0.25, "adaptive_noise": True})
        self.assertEqual(result.status, "UNKNOWN")
        self.assertEqual(result.stats["tries"], 2)
        self.assertEqual(result.stats["flips"], 6)
        self.assertEqual(result.stats["selection_mode"], "walksat")
        self.assertTrue(result.stats["adaptive_noise"])
        self.assertNotIn("best_assignment", result.stats)
        self.assertNotIn("hard_clause_hits", result.stats)

    def test_run_solver_maps_probsat_options(self):
        result = run_solver([[1], [-1]], "ProbSAT", {"random_seed": 11, "max_tries": 4, "max_flips": 5, "cb": 3})
        self.assertEqual(result.solver, "probsat")
        self.assertEqual(result.stats["flips"], 20)
        self.assertEqual(result.stats["selection_mode"], "probsat")
        self.assertEqual(result.stats["cb"], 3)

    def test_defaults_follow_the_literature(self):
        result = run_solver([[1]], "walksat", {"random_seed": 3})
        self.assertEqual(result.status, "SAT")
        self.assertEqual(result.stats["final_noise"], 0.567)

    def test_run_solver_rejects_invalid_options(self):
        with self.assertRaises(ValueError):
            run_solver([[1]], "walksat", {"noise": 1.5})
        with self.assertRaises(ValueError):
            run_solver([[1]], "probsat", {"noise": 0.3})  # ProbSAT has no noise


if __name__ == "__main__":
    unittest.main()
