"""
Randomised cross-check: every complete solver configuration must agree with
brute force on small random formulas, and every model it returns must satisfy
the formula. Local search (WalkSAT, ProbSAT) must find a model of every
satisfiable formula within a generous budget and never claim one for an
unsatisfiable formula. This catches subtle bugs in propagation, learning, clause
deletion and restarts that hand-written examples miss.
"""

import itertools
import random
import unittest

from solvers.cdcl import cdcl
from solvers.dpll import dpll
from solvers.walksat import walksat
from sat_core.verify import check_assignment


CDCL_CONFIGS = (
    {},
    {"branching": "moms"},
    {"branching": "dlis"},
    {"branching": "frequent"},
    {"branching": "random", "random_seed": 3},
    {"initial_phase": "negative"},
    {"restarts": False, "clause_deletion": False},
    {"restart_strategy": "fixed", "restart_interval": 1, "learned_clause_limit": 1},
)


def brute_force_sat(clauses, variables):
    for bits in itertools.product((False, True), repeat=variables):
        if all(any(bits[abs(lit) - 1] == (lit > 0) for lit in clause) for clause in clauses):
            return True
    return False


def random_formula(rng):
    variables = rng.randint(1, 9)
    clauses = [
        [rng.choice((-1, 1)) * rng.randint(1, variables) for _ in range(rng.randint(1, 4))]
        for _ in range(rng.randint(1, 40))
    ]
    return clauses, variables


class SolverAgreementTests(unittest.TestCase):
    def test_complete_solvers_agree_with_brute_force(self):
        rng = random.Random(2024)
        for case in range(400):
            clauses, variables = random_formula(rng)
            expected = brute_force_sat(clauses, variables)
            runs = [("dpll", dpll(clauses))] + [(f"cdcl {config}", cdcl(clauses, logging_options=config)) for config in CDCL_CONFIGS]
            for name, model in runs:
                with self.subTest(case=case, solver=name):
                    self.assertEqual(model is not None, expected, clauses)
                    if model is not None:
                        self.assertTrue(check_assignment(clauses, model), clauses)
                        # Every variable of the input gets a value.
                        mentioned = {abs(lit) for clause in clauses for lit in clause}
                        self.assertTrue(mentioned <= set(model), clauses)

    def test_local_search_finds_models_and_never_claims_unsat_ones(self):
        rng = random.Random(77)
        for case in range(200):
            clauses, variables = random_formula(rng)
            expected = brute_force_sat(clauses, variables)
            for mode in ("walksat", "probsat"):
                with self.subTest(case=case, mode=mode):
                    model, stats = walksat(
                        clauses,
                        return_stats=True,
                        logging_options={"selection_mode": mode, "random_seed": case, "max_tries": 5, "max_flips": 1000},
                    )
                    if expected:
                        self.assertEqual(stats["status"], "SAT", clauses)
                        self.assertTrue(check_assignment(clauses, model), clauses)
                        mentioned = {abs(lit) for clause in clauses for lit in clause}
                        self.assertTrue(mentioned <= set(model), clauses)
                    else:
                        self.assertIsNone(model)
                        self.assertEqual(stats["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
