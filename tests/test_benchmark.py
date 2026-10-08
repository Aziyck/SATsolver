import csv
import dataclasses
import io
import unittest
from unittest import mock

from sat_core.benchmark import (
    DPLL_FALLBACK_RULE,
    limits_for,
    parse_request,
    rows_to_csv,
    run_benchmark,
)
from sat_core import solver_registry
from sat_core.params import ParamError
from sat_core.solver_registry import get_solver
from sat_core.presets import all_presets, get_preset
from sat_core.runtime import EVENT_CANCELLED, EVENT_PLAN, EVENT_PROGRESS, EVENT_ROW, RunToken


def request(**overrides):
    base = {
        "problems": ["n_queens"],
        "segments": [{"size": "4, 5"}],
        "solvers": [{"solver": "cdcl"}],
        "repeats": 1,
        "timeout": 30,
    }
    base.update(overrides)
    return base


class PlanTests(unittest.TestCase):
    def test_grid_times_repeats_times_solvers(self):
        plan = parse_request(request(repeats=3, solvers=["cdcl", "dpll"]))

        self.assertEqual(len(plan.cases), 6)
        self.assertEqual(plan.total_runs, 12)
        self.assertEqual([case.label for case in plan.cases[:3]], ["n=4", "n=4", "n=4"])

    def test_segments_describe_non_rectangular_grids(self):
        plan = parse_request(
            request(
                problems=["random_3sat"],
                segments=[
                    {"variables": "20, 30", "ratio": "3, 4", "seed": "1..2"},
                    {"variables": "40", "ratio": "4", "seed": 1},
                ],
            )
        )

        self.assertEqual(len(plan.cases), 9)
        self.assertEqual([case.segment for case in plan.cases].count(1), 1)

    def test_repeats_derive_independent_seeds_but_keep_the_first(self):
        plan = parse_request(request(problems=["random_3sat"], segments=[{"variables": 20, "seed": 5}], repeats=3))
        seeds = [case.params["seed"] for case in plan.cases]

        self.assertEqual(seeds[0], 5)
        self.assertEqual(len(set(seeds)), 3)

    def test_blank_seed_uses_the_request_seed(self):
        plan = parse_request(request(problems=["random_3sat"], segments=[{"variables": 20, "seed": ""}], seed=42))

        self.assertEqual(plan.cases[0].params["seed"], 42)
        self.assertEqual(plan.seed, 42)

    def test_graph_suite_shares_graphs_and_groups_cases(self):
        plan = parse_request(
            request(
                problems=["clique", "independent_set", "graph_coloring"],
                segments=[{"nodes": 8, "probability": 0.4, "target": "2, 3", "colors": 3, "seed": "1..2"}],
            )
        )

        self.assertEqual(len(plan.cases), 10)
        self.assertEqual(
            [case.problem for case in plan.cases[:5]],
            ["clique", "clique", "independent_set", "independent_set", "graph_coloring"],
        )
        rows = run_benchmark(plan)
        graphs = {}
        for row in rows:
            graphs.setdefault(row.params["seed"], set()).add((row.params["nodes"], row.params["probability"]))
        self.assertEqual(len(rows), 10)

    def test_same_solver_twice_gets_distinct_labels(self):
        plan = parse_request(
            request(solvers=[{"solver": "cdcl", "options": {"branching": "moms"}}, {"solver": "cdcl"}, {"solver": "cdcl"}])
        )

        self.assertEqual([solver.label for solver in plan.solvers], ["CDCL (branching=MOMS)", "CDCL (defaults)", "CDCL (defaults) #2"])

    def test_invalid_requests_name_the_field(self):
        checks = [
            (request(problems=[]), "problems"),
            (request(problems=["sudoku", "clique"]), "problems"),
            (request(solvers=[]), "solvers"),
            (request(solvers=[{"solver": "cdcl", "options": {"branching": "x"}}]), "solvers.0.options.branching"),
            (request(segments=[{"size": "0"}]), "segments.0.size"),
            (request(segments=[{"colors": 3}]), "segments.0.colors"),
            (request(repeats=0), "repeats"),
            (request(rules=[{"solver": "dpll", "action": "cap"}]), "rules.0.seconds"),
            (request(timeout="soon"), "timeout"),
        ]
        for raw, key in checks:
            with self.subTest(key=key):
                with self.assertRaises(ParamError) as context:
                    parse_request(raw)
                self.assertIn(key, context.exception.errors)


class RuleTests(unittest.TestCase):
    def test_caps_take_the_smallest_limit_and_skips_win(self):
        plan = parse_request(
            request(
                timeout=30,
                rules=[
                    {"solver": "dpll", "action": "cap", "min_variables": 100, "seconds": 10},
                    {"solver": "*", "action": "cap", "min_variables": 0, "seconds": 20},
                    {"solver": "dpll", "action": "skip", "min_variables": 500},
                ],
            )
        )

        self.assertEqual(limits_for(plan, "cdcl", 50)[:2], (False, 20))
        self.assertEqual(limits_for(plan, "dpll", 150)[:2], (False, 10))
        self.assertEqual(limits_for(plan, "dpll", 600)[0], True)

    def test_rules_apply_during_a_run(self):
        plan = parse_request(
            request(
                segments=[{"size": 5}],
                solvers=["cdcl", "dpll"],
                rules=[{"solver": "dpll", "action": "skip", "min_variables": 10}],
            )
        )
        rows = run_benchmark(plan)

        self.assertEqual([row.status for row in rows], ["SAT", "SKIPPED"])
        self.assertEqual(rows[1].rule, "skip DPLL when variables >= 10")

    def test_zero_cap_times_out(self):
        rows = run_benchmark(parse_request(request(segments=[{"size": 5}], rules=[{"solver": "cdcl", "action": "cap", "seconds": 0}])))

        self.assertEqual(rows[0].status, "TIMEOUT")
        self.assertEqual(rows[0].timeout, 0)


class PresetTests(unittest.TestCase):
    def test_random_3sat_preset_sizes(self):
        counts = {preset.key: preset.to_dict()["cases"] for preset in all_presets()}

        self.assertEqual(counts["3sat_planted"], 350)
        self.assertEqual(counts["3sat_forced_unsat"], 100)
        self.assertEqual(counts["3sat_mixed"], 270)

    def test_preset_seed_ranges(self):
        seeds = {case.params["seed"] for case in parse_request(get_preset("3sat_mixed").request).cases}
        self.assertEqual(seeds, set(range(1, 31)))

        plan = parse_request(get_preset("3sat_planted").request)
        seeds_300 = {case.params["seed"] for case in plan.cases if case.params["variables"] == 300}
        self.assertEqual(seeds_300, set(range(1, 11)))

    def test_preset_b_caps_dpll_at_150_and_skips_it_at_200(self):
        plan = parse_request(get_preset("3sat_forced_unsat").request)

        self.assertEqual(limits_for(plan, "dpll", 100)[:2], (False, 30))
        self.assertEqual(limits_for(plan, "dpll", 150)[:2], (False, 10))
        self.assertTrue(limits_for(plan, "dpll", 200)[0])
        self.assertEqual(limits_for(plan, "cdcl", 200)[:2], (False, 30))

    def test_dpll_fallback_cap_is_ten_seconds(self):
        self.assertEqual(DPLL_FALLBACK_RULE["seconds"], 10.0)
        plan = parse_request(get_preset("3sat_mixed").request)
        self.assertEqual(limits_for(plan, "dpll", 200)[:2], (False, 10))
        self.assertEqual(limits_for(plan, "walksat", 100)[:2], (False, 1))

    def test_every_preset_parses(self):
        for preset in all_presets():
            with self.subTest(preset=preset.key):
                self.assertGreater(preset.to_dict()["runs"], 0)


class RunTests(unittest.TestCase):
    def test_events_and_rows(self):
        events = []
        rows = run_benchmark(parse_request(request(solvers=["cdcl", "walksat"])), event_callback=events.append)

        self.assertEqual(len(rows), 4)
        self.assertEqual(events[0].type, EVENT_PLAN)
        self.assertEqual(sum(1 for event in events if event.type == EVENT_ROW), 4)
        progress = [event for event in events if event.type == EVENT_PROGRESS]
        self.assertEqual((progress[-1].current, progress[-1].total), (4, 4))
        self.assertTrue(all(row.verified for row in rows if row.status == "SAT"))
        self.assertEqual(rows[0].expected, "SAT")

    def test_solver_errors_do_not_stop_the_benchmark(self):
        big_chain = {"cnf": {"name": "deep.cnf", "text": " 0\n".join(f"{2 * i + 1} {2 * i + 2}" for i in range(1500)) + " 0\n"}}
        plan = parse_request(
            request(
                problems=["dimacs"],
                segments=[{"cnf": [big_chain["cnf"], {"name": "small.cnf", "text": "1 0\n"}]}],
                solvers=["dpll", "cdcl"],
                timeout=None,
            )
        )
        # DPLL fails on the first case only.
        real = get_solver("dpll")

        def flaky(clauses, *args):
            if len(clauses) > 1:
                raise RecursionError("maximum recursion depth exceeded")
            return real.runner(clauses, *args)

        with mock.patch.dict(solver_registry._SOLVERS, {"dpll": dataclasses.replace(real, runner=flaky)}):
            rows = run_benchmark(plan)

        self.assertEqual([row.status for row in rows], ["ERROR", "SAT", "SAT", "SAT"])
        self.assertIn("recursion", rows[0].error)
        self.assertEqual(rows[0].params["cnf"], "deep.cnf")

    def test_encoding_errors_become_error_rows(self):
        plan = parse_request(request(problems=["clique"], segments=[{"nodes": 3, "target": 3, "seed": 1}]))
        plan.cases[0].params["target"] = 99  # bypasses validation, as a broken case would
        rows = run_benchmark(plan)

        self.assertEqual(rows[0].status, "ERROR")
        self.assertTrue(rows[0].error.startswith("Encoding failed"))

    def test_skip_marks_the_current_case_and_continues(self):
        token = RunToken()
        token.skip()

        rows = run_benchmark(parse_request(request(solvers=["cdcl", "dpll"])), cancel_token=token)

        self.assertEqual([row.status for row in rows], ["SKIPPED", "SKIPPED", "SAT", "SAT"])

    def test_cancel_stops_before_the_next_run(self):
        token = RunToken()
        token.cancel()
        events = []

        rows = run_benchmark(parse_request(request()), event_callback=events.append, cancel_token=token)

        self.assertEqual(rows, [])
        self.assertTrue(any(event.type == EVENT_CANCELLED for event in events))


class CsvTests(unittest.TestCase):
    def test_one_format_with_parameter_columns(self):
        rows = run_benchmark(parse_request(request(problems=["random_3sat"], segments=[{"variables": 20, "ratio": "3, 4", "seed": 1}])))
        table = list(csv.DictReader(io.StringIO(rows_to_csv(rows, run_label="J1"))))

        self.assertEqual(len(table), 2)
        self.assertEqual(table[0]["run"], "J1")
        self.assertEqual(table[0]["variables"], "20")
        self.assertEqual(table[0]["cnf_clauses"], "60")
        self.assertEqual(table[1]["ratio"], "4.0")
        self.assertEqual(table[0]["mode"], "planted")
        self.assertNotIn("sat_percent", table[0])
        self.assertEqual(table[0]["status"], "SAT")
        self.assertEqual(table[0]["verified"], "True")


if __name__ == "__main__":
    unittest.main()
