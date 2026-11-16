import unittest

from problems import get_problem
from sat_core.answers import Verdict, judge_answer
from sat_core.models import ProblemInstance, SolveResult
from sat_core.solver_registry import get_solver, run_solver


class FakeSpec:
    """Just the two methods of ProblemSpec that judge_answer relies on."""

    def __init__(self, decoded="answer", problems=(), raises=None):
        self.decoded = decoded
        self.problems = list(problems)
        self.raises = raises

    def decode(self, instance, solution):
        if self.raises:
            raise self.raises
        return self.decoded

    def check(self, instance, decoded):
        return list(self.problems)


def instance(clauses):
    return ProblemInstance(name="t", problem_type="fake", clauses=clauses)


def result(status, solution):
    return SolveResult(solver="cdcl", status=status, elapsed=0.0, solution=solution)


class JudgeAnswerTests(unittest.TestCase):
    def test_a_satisfying_model_is_verified_and_decoded(self):
        verdict = judge_answer(FakeSpec(), instance([[1, 2], [-1]]), result("SAT", {1: False, 2: True}))

        self.assertEqual(verdict, Verdict(verified=True, decoded="answer", errors=[]))

    def test_a_model_that_violates_a_clause_is_not_verified(self):
        verdict = judge_answer(FakeSpec(), instance([[1], [2]]), result("SAT", {1: True, 2: False}))

        self.assertIs(verdict.verified, False)
        self.assertEqual(verdict.errors, ["the model does not satisfy every clause"])

    def test_a_decoder_that_raises_is_reported_not_raised(self):
        verdict = judge_answer(FakeSpec(raises=ValueError("boom")), instance([[1]]), result("SAT", {1: True}))

        self.assertIs(verdict.verified, False)
        self.assertIsNone(verdict.decoded)
        self.assertEqual(verdict.errors, ["decoding failed: boom"])

    def test_a_failing_problem_check_makes_the_answer_unverified(self):
        verdict = judge_answer(FakeSpec(problems=["two queens attack"]), instance([[1]]), result("SAT", {1: True}))

        self.assertIs(verdict.verified, False)
        self.assertEqual(verdict.decoded, "answer")
        self.assertEqual(verdict.errors, ["two queens attack"])

    def test_a_decoder_that_returns_nothing_skips_the_problem_check(self):
        verdict = judge_answer(FakeSpec(decoded=None, problems=["never asked"]), instance([[1]]), result("SAT", {1: True}))

        self.assertEqual(verdict, Verdict(verified=True, decoded=None, errors=[]))

    def test_unsat_has_no_verdict(self):
        verdict = judge_answer(FakeSpec(), instance([[1], [-1]]), result("UNSAT", None))

        self.assertEqual(verdict, Verdict(verified=None, decoded=None, errors=[]))

    def test_sat_without_a_solution_has_no_verdict_and_does_not_raise(self):
        verdict = judge_answer(FakeSpec(), instance([[1]]), result("SAT", None))

        self.assertEqual(verdict, Verdict(verified=None, decoded=None, errors=[]))

    def test_a_real_problem_is_judged_end_to_end(self):
        spec = get_problem("n_queens")
        built = spec.build(spec.parse({"size": 4}))
        solved = run_solver(built.clauses, "cdcl", get_solver("cdcl").parse_options({}), timeout=10)
        verdict = judge_answer(spec, built, solved)

        self.assertIs(verdict.verified, True)
        self.assertEqual(len(verdict.decoded["queens"]), 4)


if __name__ == "__main__":
    unittest.main()
