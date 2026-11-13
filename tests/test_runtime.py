import contextlib
import dataclasses
import time
import unittest
from unittest import mock

from problems import build_problem
from sat_core.runtime import EVENT_LOG, EVENT_PROGRESS, RunEvent, RunToken
from sat_core import solver_registry
from sat_core.solver_registry import all_solvers, get_solver, options_summary, run_solver
from sat_core.verify import check_assignment


@contextlib.contextmanager
def failing_solver(key):
    """Temporarily replace a solver by one that raises, to test the ERROR path."""

    def boom(*_args):
        raise RecursionError("maximum recursion depth exceeded")

    broken = dataclasses.replace(get_solver(key), runner=boom)
    with mock.patch.dict(solver_registry._SOLVERS, {key: broken}):
        yield


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
        with failing_solver("dpll"):
            result = run_solver([[1, 2]], "dpll")

        self.assertEqual(result.status, "ERROR")
        self.assertIn("recursion limit", result.error)

    def test_dpll_has_no_recursion_limit(self):
        # 1,500 independent 2-clauses need 1,500 nested decisions; the old
        # recursive DPLL failed here, the iterative one does not.
        clauses = [[2 * i + 1, 2 * i + 2] for i in range(1500)]

        result = run_solver(clauses, "dpll")

        self.assertEqual(result.status, "SAT")
        self.assertEqual(result.stats["max_depth"], 1500)
        self.assertEqual(run_solver(clauses, "cdcl").status, "SAT")

    def test_cdcl_options_are_applied(self):
        formula = [[1, 2], [-1, 2], [1, -2]]
        for branching in ("vsids", "frequent", "moms", "dlis", "random"):
            with self.subTest(branching=branching):
                result = run_solver(formula, "cdcl", {"branching": branching, "random_seed": 3})
                self.assertEqual(result.status, "SAT")

        spec = get_solver("cdcl")
        options = spec.parse_options({"branching": "moms", "restarts": False, "restart_interval": 5})
        self.assertEqual(options_summary(spec, options), "branching=MOMS; restarts=off")
        self.assertEqual(options_summary(spec, spec.default_options()), "defaults")

    def test_public_stats_are_small_scalars(self):
        result = run_solver([[1, 2], [-1, 2]], "walksat", {"random_seed": 2})

        self.assertTrue(all(isinstance(value, (int, float, str, bool, type(None))) for value in result.stats.values()))


class SparseNumberingTests(unittest.TestCase):
    """The cost of a run follows the number of variables, not the largest variable number (audit A2)."""

    def test_one_huge_variable_number_is_solved_at_once(self):
        formula = [[10_000_000], [-5]]
        for spec in all_solvers():
            with self.subTest(solver=spec.key):
                events = []
                started = time.perf_counter()
                result = run_solver(formula, spec.key, event_callback=events.append)
                elapsed = time.perf_counter() - started
                self.assertEqual(result.status, "SAT")
                self.assertEqual(result.solution, {5: False, 10_000_000: True})
                self.assertEqual(result.variables, 2)
                self.assertLess(elapsed, 1.0)
                # CDCL and DPLL debug lines then show new numbers, so the log says that they changed.
                # The local-search solvers renumber by themselves and log the original numbers.
                self.assertEqual(any("renumbered" in message for message in log_messages(events)), spec.complete)

    def test_renumbered_formulas_keep_every_outcome(self):
        big = 10_000_000
        for key in ("cdcl", "dpll"):
            with self.subTest(solver=key):
                self.assertEqual(run_solver([[big], [-big]], key).status, "UNSAT")
                self.assertEqual(run_solver([[big, 7], [-big, 7], [big, -7], [-big, -7]], key).status, "UNSAT")
                self.assertEqual(run_solver([[big], [-5]], key, timeout=0).status, "TIMEOUT")
                # A variable that only appears in a tautology still gets a value.
                self.assertEqual(sorted(run_solver([[big, -big], [-5]], key).solution), [5, big])

    def test_far_apart_numbers_give_the_same_search_as_compact_ones(self):
        compact = build_problem("random_3sat", {"variables": 50, "ratio": 4.26, "mode": "random", "seed": 1}).clauses
        # Same order of the variables, largest number 2,501,050.
        spread = [[lit * 50_021 for lit in clause] for clause in compact]
        seeded = {"branching": "random", "phase": "random", "random_seed": 3}
        runs = [("cdcl", None), ("cdcl", seeded), ("cdcl", {"branching": "moms"}), ("cdcl", {"branching": "dlis"}), ("dpll", None)]
        runs += [(key, {"random_seed": 5}) for key in ("walksat", "probsat")]
        for solver, options in runs:
            with self.subTest(solver=solver, options=options):
                near = run_solver(compact, solver, options)
                far = run_solver(spread, solver, options)
                self.assertEqual(far.status, near.status)
                self.assertEqual(far.variables, near.variables)
                for key in ("decisions", "conflicts", "propagations", "flips"):
                    self.assertEqual(far.stats.get(key), near.stats.get(key), key)
                if near.solution is not None:
                    self.assertEqual(far.solution, {var * 50_021: value for var, value in near.solution.items()})
                    self.assertTrue(check_assignment(spread, far.solution))

    def test_readable_encoder_numbers_are_kept(self):
        # Renumbering is for numbers no encoder produces: large and mostly unused.
        self.assertTrue(solver_registry.needs_renumbering(10_000_000, 2))
        self.assertFalse(solver_registry.needs_renumbering(252_525, 15_625))    # 25x25 Sudoku
        self.assertFalse(solver_registry.needs_renumbering(1_000_000, 2))
        self.assertFalse(solver_registry.needs_renumbering(3_000_000, 2_900_000))  # a big, dense DIMACS file
        # A literal 0 inside a clause is passed on as it was.
        self.assertEqual(solver_registry.compact_numbering([[70, 0, -30]], {0, 30, 70}), ([[2, 0, -1]], [30, 70]))

        events = []
        result = run_solver([[90_909], [-5]], "cdcl", event_callback=events.append)
        self.assertEqual(result.solution, {5: False, 90_909: True})
        self.assertFalse(any("renumbered" in message for message in log_messages(events)))


if __name__ == "__main__":
    unittest.main()
