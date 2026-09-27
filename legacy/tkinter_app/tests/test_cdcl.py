import unittest

from solvers.cdcl import Clause, cdcl, clause_lbd, learned_clause_delete_key, learned_clauses_to_delete
from solvers.dpll import dpll
from problems.clique import clique_var
from problems.hamiltonian_path import hamiltonian_var
from problems.independent_set import independent_var
from problems.n_queens import n_queens_problem, n_queens_var
from sat_core.dimacs import load_dimacs
from utils.general_utils import color_var, sudoku_var
from utils.sudoku_general import generate_sudoku_clauses


def satisfies(clauses, model):
    if model is None:
        return False

    for clause in clauses:
        clause_ok = False

        for lit in clause:
            value = model.get(abs(lit))
            if value is None:
                continue
            if (lit > 0 and value) or (lit < 0 and not value):
                clause_ok = True
                break

        if not clause_ok:
            return False

    return True


class CDCLTests(unittest.TestCase):
    def test_lbd_counts_distinct_decision_levels(self):
        levels = [0, 8, 8, 5, 2]

        self.assertEqual(clause_lbd([1, -2, 3, -4], levels), 3)

    def test_lbd_delete_key_prefers_binary_and_low_lbd_clauses(self):
        binary = Clause([1, -2], learnt=True, created=1, lbd=2, last_used=1)
        low_lbd = Clause([1, -2, 3], learnt=True, created=2, lbd=2, last_used=1)
        high_lbd = Clause([1, -2, 3], learnt=True, created=3, lbd=5, last_used=1)

        ordered = sorted([high_lbd, binary, low_lbd], key=learned_clause_delete_key)

        self.assertEqual(ordered, [binary, low_lbd, high_lbd])

    def test_lbd_delete_key_prefers_recent_active_clauses_when_other_scores_match(self):
        old_clause = Clause([1, -2, 3], learnt=True, created=1, lbd=4, last_used=1)
        recent_clause = Clause([1, -2, 3], learnt=True, created=2, lbd=4, last_used=8)

        ordered = sorted([old_clause, recent_clause], key=learned_clause_delete_key)

        self.assertEqual(ordered, [recent_clause, old_clause])

    def test_lbd_pruning_keeps_locked_clauses(self):
        locked_bad_clause = Clause([1, -2, 3, -4, 5], learnt=True, created=1, lbd=5)
        low_lbd_clause = Clause([1, 2, 3], learnt=True, created=2, lbd=2)
        high_lbd_clause = Clause([1, -2, 3, -4], learnt=True, created=3, lbd=4)

        removed = learned_clauses_to_delete(
            [locked_bad_clause, low_lbd_clause, high_lbd_clause],
            {locked_bad_clause},
            learned_clause_limit=1,
        )

        self.assertNotIn(locked_bad_clause, removed)
        self.assertIn(high_lbd_clause, removed)

    def test_unit_sat(self):
        formula = [[1]]
        solution = cdcl(formula)

        self.assertIsNotNone(solution)
        self.assertTrue(solution[1])
        self.assertTrue(satisfies(formula, solution))

    def test_unit_unsat(self):
        self.assertIsNone(cdcl([[1], [-1]]))

    def test_implication_chain_sat(self):
        formula = [[1], [-1, 2], [-2, 3]]
        solution = cdcl(formula)

        self.assertIsNotNone(solution)
        self.assertTrue(solution[1])
        self.assertTrue(solution[2])
        self.assertTrue(solution[3])
        self.assertTrue(satisfies(formula, solution))

    def test_conflict_learning_unsat(self):
        # This formula has no unit clauses at the start. The solver must make
        # a decision, hit a conflict, learn, backjump, and then prove UNSAT.
        formula = [
            [1, 2],
            [1, -2],
            [-1, 2],
            [-1, -2],
        ]

        solution, stats = cdcl(formula, return_stats=True)

        self.assertIsNone(solution)
        self.assertEqual(stats["status"], "UNSAT")
        self.assertGreaterEqual(stats["learned_clauses"], 1)

    def test_graph_coloring_dimacs_matches_dpll(self):
        formula = load_dimacs("input/examples/graph_coloring/gc_n10_p10_k2.cnf")
        cdcl_solution = cdcl(formula)
        dpll_solution = dpll(formula)

        self.assertEqual(cdcl_solution is None, dpll_solution is None)
        if cdcl_solution is not None:
            self.assertTrue(satisfies(formula, cdcl_solution))

    def test_n_queens_sat_with_limited_conflicts(self):
        problem = n_queens_problem(15)

        solution, stats = cdcl(problem.clauses, max_conflicts=500, return_stats=True)

        self.assertEqual(stats["status"], "SAT")
        self.assertTrue(satisfies(problem.clauses, solution))

    def test_branching_modes_solve_representative_formula(self):
        formula = [[1, 2], [-1, 2], [1, -2]]

        for branching in ("VSIDS", "Most frequent", "MOMS", "DLIS", "Random"):
            with self.subTest(branching=branching):
                solution, stats = cdcl(
                    formula,
                    return_stats=True,
                    logging_options={"branching": branching, "random_seed": 7},
                )
                self.assertEqual(stats["status"], "SAT")
                self.assertTrue(satisfies(formula, solution))

    def test_phase_modes_accept_seeded_runs(self):
        formula = [[1, 2], [-1, 2], [1, -2]]

        for phase in ("Positive first", "Negative first", "Polarity based", "Random"):
            with self.subTest(phase=phase):
                first, first_stats = cdcl(
                    formula,
                    return_stats=True,
                    logging_options={"initial_phase": phase, "random_seed": 11},
                )
                second, second_stats = cdcl(
                    formula,
                    return_stats=True,
                    logging_options={"initial_phase": phase, "random_seed": 11},
                )
                self.assertEqual(first_stats["status"], "SAT")
                self.assertEqual(second_stats["status"], "SAT")
                self.assertEqual(first, second)

    def test_restarts_and_learned_clause_limit_preserve_correctness(self):
        formula = [
            [1, 2],
            [1, -2],
            [-1, 2],
            [-1, -2],
        ]

        solution, stats = cdcl(
            formula,
            return_stats=True,
            logging_options={"restart_interval": 1, "learned_clause_limit": 1},
        )

        self.assertIsNone(solution)
        self.assertEqual(stats["status"], "UNSAT")
        self.assertIn("restarts", stats)
        self.assertIn("deleted_learned_clauses", stats)
        self.assertIn("avg_lbd", stats)

    def test_encoder_split_and_sudoku_generation(self):
        self.assertEqual(sudoku_var(1, 2, 3), 10203)
        self.assertEqual(n_queens_var(1, 1, 4), 101)
        self.assertEqual(color_var(2, 3, 10), 203)
        self.assertEqual(color_var(2, 101, 101), 2101)
        self.assertEqual(hamiltonian_var(1, 3, 10), 103)
        self.assertEqual(clique_var(2, 3, 10), 203)
        self.assertEqual(independent_var(2, 3, 10), 203)

        grid = [[0] * 4 for _ in range(4)]
        clauses = generate_sudoku_clauses(grid)

        self.assertIn([sudoku_var(1, 1, 1), sudoku_var(1, 1, 2), sudoku_var(1, 1, 3), sudoku_var(1, 1, 4)], clauses)


if __name__ == "__main__":
    unittest.main()
