import csv
import tempfile
import unittest
import time
import tkinter as tk
import random

import app as app_module
import sat_core.benchmark_presets.random_3sat_presets as random_3sat_presets_module
from app import BENCHMARK_AUTO_CHART_MAX_ROWS, BENCHMARK_DETAIL_PANEL_WIDTH, BENCHMARK_LEFT_PANEL_WIDTH, BENCHMARK_PROBLEMS, CNF_AUTO_DISPLAY_MAX_CHARS, FEED_MAX_LINES, PROBLEM_KINDS, SATApp, SOLVE_SOLVERS, SUDOKU_SIZES
from problems.clique import (
    average_degree_clique_problem,
    clique_var,
    exact_edges_clique_problem,
    manual_clique_problem,
    random_clique_problem,
)
from problems.dimacs_problem import dimacs_problem_from_text
from problems.graph_coloring import (
    average_degree_graph_coloring_problem,
    edge_count_from_average_degree,
    exact_edges_graph_coloring_problem,
    manual_graph_coloring_problem,
    parse_edge_list,
    random_graph_coloring_problem,
)
from problems.hamiltonian_path import hamiltonian_var, manual_hamiltonian_path_problem, random_hamiltonian_path_problem
from problems.independent_set import independent_var, manual_independent_set_problem, random_independent_set_problem
from problems.n_queens import n_queens_problem, n_queens_var
from problems.random_3sat import random_3sat_problem
from problems.sudoku import sudoku_problem, validate_sudoku_grid
from sat_core.benchmark import (
    MAX_STORED_BENCHMARK_CLAUSES,
    RANDOM_3SAT_CSV_HEADERS,
    RANDOM_3SAT_PRESET_A,
    RANDOM_3SAT_PRESET_B,
    RANDOM_3SAT_PRESET_C,
    _random_3sat_preset_skip,
    _random_3sat_preset_timeout,
    graph_coloring_sweep,
    random_3sat_csv_row,
    random_3sat_preset_case_count,
    random_3sat_preset_cases,
    random_3sat_preset_default_solvers,
    result_to_row,
    run_clique_sweep,
    run_graph_suite_sweep,
    run_random_3sat_sweep,
    write_random_3sat_benchmark_csv,
)
from sat_core.dimacs import clauses_to_dimacs, parse_dimacs_text
from sat_core.models import BenchmarkRow, ProblemInstance, SolveResult
from sat_core.process_workers import problem_from_snapshot
from sat_core.benchmark_presets.random_3sat_presets import (
    Random3SATPreset,
    Random3SATPresetSpec,
    Random3SATPresetUiValues,
    matrix_cases,
    random_3sat_preset_names,
    random_3sat_preset_should_skip_solver,
    random_3sat_preset_summary,
    random_3sat_preset_solver_timeout,
    random_3sat_preset_ui_values,
    register_random_3sat_preset,
)
from sat_core.runtime import EVENT_CNF, EVENT_LOG, EVENT_PROGRESS, EVENT_ROW, RunEvent, RunToken
from sat_core.solver_runner import SOLVERS, solve_clauses, solve_problem
from utils.general_utils import color_var, sudoku_var
from utils.graph_utils import decode_coloring, generate_random_graph_exact_edges, graph_edges


class AppBackendTests(unittest.TestCase):
    def test_dimacs_round_trip(self):
        clauses = [[1, -2], [2], [-1, 3]]
        text = clauses_to_dimacs(clauses, ["round trip"])

        self.assertEqual(parse_dimacs_text(text), clauses)

    def test_dimacs_problem_from_text(self):
        problem = dimacs_problem_from_text("p cnf 2 2\n1 2 0\n-1 0\n")

        self.assertEqual(problem.problem_type, "DIMACS")
        self.assertEqual(problem.clause_count, 2)

    def test_dimacs_problem_from_text_can_be_typed(self):
        problem = dimacs_problem_from_text("p cnf 2 1\n1 0\n", problem_type="Graph Coloring")

        self.assertEqual(problem.problem_type, "Graph Coloring")
        self.assertEqual(problem.metadata["loaded_as"], "Graph Coloring")

    def test_sudoku_problem_contains_given_and_decodes_solution(self):
        grid = [
            [1, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
        ]
        problem = sudoku_problem(grid)

        self.assertIn([sudoku_var(1, 1, 1)], problem.clauses)

        solved_grid = [
            [1, 2, 3, 4],
            [3, 4, 1, 2],
            [2, 1, 4, 3],
            [4, 3, 2, 1],
        ]
        solution = {
            sudoku_var(r + 1, c + 1, solved_grid[r][c]): True
            for r in range(4)
            for c in range(4)
        }

        self.assertEqual(problem.decode_solution(solution), solved_grid)

    def test_sudoku_25x25_is_supported_by_app_and_validator(self):
        self.assertIn(25, SUDOKU_SIZES)
        validate_sudoku_grid([[0] * 25 for _ in range(25)])

    def test_n_queens_problem_solves_and_decodes(self):
        problem = n_queens_problem(4)

        self.assertIn([n_queens_var(1, 1, 4), n_queens_var(1, 2, 4), n_queens_var(1, 3, 4), n_queens_var(1, 4, 4)], problem.clauses)

        result = solve_problem(problem, "CDCL")

        self.assertEqual(result.status, "SAT")
        self.assertEqual(len(result.decoded["positions"]), 4)
        self.assertEqual(len(result.decoded["board"]), 4)

    def test_random_3sat_problem_is_buildable_and_reproducible(self):
        first = random_3sat_problem(6, 12, seed=4, planted=True)
        second = random_3sat_problem(6, 12, seed=4, planted=True)

        self.assertEqual(first.problem_type, "Random 3-SAT")
        self.assertEqual(first.clauses, second.clauses)
        self.assertEqual(first.metadata["variables"], 6)
        self.assertEqual(first.metadata["clauses_requested"], 12)
        self.assertEqual(first.metadata["width"], 3)
        self.assertEqual(first.metadata["mode"], "Planted SAT")
        self.assertTrue(all(len(clause) == 3 for clause in first.clauses))
        self.assertTrue(all(len({abs(lit) for lit in clause}) == 3 for clause in first.clauses))

        result = solve_problem(first, "CDCL")
        self.assertEqual(result.status, "SAT")

    def test_random_3sat_forced_unsat_mode(self):
        problem = random_3sat_problem(6, 12, seed=4, formula_mode="Forced UNSAT")

        self.assertEqual(problem.metadata["mode"], "Forced UNSAT")
        self.assertTrue(problem.metadata["forced_unsat"])
        self.assertTrue(all(len(clause) == 3 for clause in problem.clauses))
        self.assertEqual(solve_problem(problem, "CDCL").status, "UNSAT")

    def test_random_3sat_random_mode_can_force_sat_mix(self):
        problem = random_3sat_problem(6, 12, seed=4, formula_mode="Random", sat_percentage=100)

        self.assertEqual(problem.metadata["mode"], "Random")
        self.assertEqual(problem.metadata["selected_mode"], "Planted SAT")
        self.assertEqual(problem.metadata["sat_percentage"], 100.0)
        self.assertEqual(problem.metadata["unsat_percentage"], 0.0)
        self.assertTrue(problem.metadata["planted"])
        self.assertEqual(solve_problem(problem, "CDCL").status, "SAT")

    def test_random_3sat_random_mode_can_force_unsat_mix(self):
        problem = random_3sat_problem(6, 12, seed=4, formula_mode="Random", sat_percentage=0)

        self.assertEqual(problem.metadata["mode"], "Random")
        self.assertEqual(problem.metadata["selected_mode"], "Forced UNSAT")
        self.assertEqual(problem.metadata["sat_percentage"], 0.0)
        self.assertEqual(problem.metadata["unsat_percentage"], 100.0)
        self.assertTrue(problem.metadata["forced_unsat"])
        self.assertEqual(solve_problem(problem, "CDCL").status, "UNSAT")

    def test_random_3sat_random_mode_keeps_pure_random_when_target_is_blank(self):
        problem = random_3sat_problem(6, 12, seed=4, formula_mode="Random", sat_percentage=None)

        self.assertEqual(problem.metadata["mode"], "Random")
        self.assertEqual(problem.metadata["selected_mode"], "Random")
        self.assertIsNone(problem.metadata["sat_percentage"])
        self.assertFalse(problem.metadata["planted"])
        self.assertFalse(problem.metadata["forced_unsat"])

    def test_random_3sat_sat_mix_percentage_is_validated(self):
        with self.assertRaises(ValueError):
            random_3sat_problem(6, 12, seed=4, formula_mode="Random", sat_percentage=101)

    def test_hamiltonian_path_problem_sat_and_unsat(self):
        sat_problem = manual_hamiltonian_path_problem(3, "1-2, 2-3")
        unsat_problem = manual_hamiltonian_path_problem(3, "1-2")

        self.assertIn([hamiltonian_var(1, 1, 3), hamiltonian_var(1, 2, 3), hamiltonian_var(1, 3, 3)], sat_problem.clauses)
        self.assertEqual(solve_problem(sat_problem, "CDCL").status, "SAT")
        self.assertEqual(solve_problem(unsat_problem, "CDCL").status, "UNSAT")

    def test_independent_set_problem_sat_and_unsat(self):
        sat_problem = manual_independent_set_problem(3, 2, "1-2")
        unsat_problem = manual_independent_set_problem(3, 2, "1-2, 1-3, 2-3")

        self.assertIn([independent_var(1, 1, 3), independent_var(1, 2, 3), independent_var(1, 3, 3)], sat_problem.clauses)
        self.assertEqual(solve_problem(sat_problem, "CDCL").status, "SAT")
        self.assertEqual(solve_problem(unsat_problem, "CDCL").status, "UNSAT")

    def test_clique_problem_sat_and_unsat(self):
        sat_problem = manual_clique_problem(3, 3, "1-2, 1-3, 2-3")
        unsat_problem = manual_clique_problem(3, 3, "1-2, 2-3")

        self.assertIn([clique_var(1, 1, 3), clique_var(1, 2, 3), clique_var(1, 3, 3)], sat_problem.clauses)
        self.assertEqual(solve_problem(sat_problem, "CDCL").status, "SAT")
        self.assertEqual(solve_problem(unsat_problem, "CDCL").status, "UNSAT")

    def test_clique_target_validation(self):
        with self.assertRaises(ValueError):
            manual_clique_problem(3, 0, "1-2")
        with self.assertRaises(ValueError):
            manual_clique_problem(3, 4, "1-2")

    def test_clique_random_graph_modes_are_buildable(self):
        first = random_clique_problem(5, 0.4, 2, seed=3)
        second = random_clique_problem(5, 0.4, 2, seed=3)
        exact = exact_edges_clique_problem(5, 4, 2, seed=3)
        average = average_degree_clique_problem(5, 2, 2, seed=3)

        self.assertEqual(first.problem_type, "Clique")
        self.assertEqual(first.clauses, second.clauses)
        self.assertEqual(first.metadata["target"], 2)
        self.assertEqual(first.metadata["mode"], "probability")
        self.assertEqual(exact.metadata["mode"], "exact_edges")
        self.assertEqual(exact.metadata["requested_edges"], 4)
        self.assertEqual(average.metadata["mode"], "average_degree")
        self.assertEqual(average.metadata["average_degree"], 2)

    def test_clique_problem_from_snapshot(self):
        problem = problem_from_snapshot({
            "kind": "Clique",
            "mode": "Manual",
            "nodes": 3,
            "target": 3,
            "seed": None,
            "edge_text": "1-2, 1-3, 2-3",
        })

        self.assertEqual(problem.problem_type, "Clique")
        self.assertEqual(problem.metadata["target"], 3)
        self.assertEqual(solve_problem(problem, "CDCL").status, "SAT")

    def test_clique_graph_preview_helpers(self):
        app = SATApp.__new__(SATApp)
        row = BenchmarkRow(
            "Clique n3_k2",
            "Clique",
            "CDCL",
            "SAT",
            0.0,
            1,
            3,
            1,
            node_count=3,
            graph_edges=[(1, 2)],
            decoded={"selected": [1, 2]},
        )

        self.assertTrue(app._is_graph_benchmark_row(row))
        self.assertEqual(app._benchmark_node_color(row, 1), "#59a14f")
        self.assertEqual(app._benchmark_node_color(row, 3), "#d8d8d8")

    def test_graph_coloring_manual_encoder(self):
        problem = manual_graph_coloring_problem(2, 2, "1-2")

        self.assertIn([-color_var(1, 1, 2), -color_var(2, 1, 2)], problem.clauses)
        self.assertIn([-color_var(1, 2, 2), -color_var(2, 2, 2)], problem.clauses)

    def test_graph_edge_parser_accepts_commas_and_lines(self):
        self.assertEqual(parse_edge_list("1-2, 2-3\n3-4"), [(1, 2), (2, 3), (3, 4)])

    def test_solver_wrapper_returns_stats(self):
        problem = dimacs_problem_from_text("p cnf 1 1\n1 0\n")
        result = solve_problem(problem, "CDCL")

        self.assertEqual(result.status, "SAT")
        self.assertIn("decisions", result.stats)

    def test_tiny_benchmark_sweep_rows(self):
        rows = graph_coloring_sweep([3], [0.2], [2], ["CDCL"], repeats=1, seed=7)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].problem_type, "Graph Coloring")
        self.assertEqual(rows[0].solver, "CDCL")

    def test_walksat_benchmark_sweep_rows(self):
        rows = graph_coloring_sweep([3], [0.2], [2], ["WalkSAT"], repeats=1, seed=7)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].solver, "WalkSAT")
        self.assertIn(rows[0].status, ("SAT", "UNKNOWN"))

    def test_random_3sat_benchmark_sweep_rows(self):
        rows = run_random_3sat_sweep([6], [3.0], ["CDCL"], repeats=1, seed=7, formula_mode="Planted SAT")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].problem_type, "Random 3-SAT")
        self.assertEqual(rows[0].status, "SAT")
        self.assertEqual(rows[0].problem_metadata["variables"], 6)
        self.assertEqual(rows[0].problem_metadata["clauses_requested"], 18)

    def test_random_3sat_benchmark_sweep_supports_sat_mix(self):
        rows = run_random_3sat_sweep([6], [3.0], ["CDCL"], repeats=1, seed=7, formula_mode="Random", sat_percentage=100)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].status, "SAT")
        self.assertEqual(rows[0].problem_metadata["mode"], "Random")
        self.assertEqual(rows[0].problem_metadata["selected_mode"], "Planted SAT")
        self.assertEqual(rows[0].problem_metadata["sat_percentage"], 100.0)

    def test_random_3sat_sweep_reuses_generated_instance_for_solvers(self):
        rows = run_random_3sat_sweep(
            [5],
            [2.0],
            ["CDCL", "ProbSAT"],
            repeats=1,
            seed=11,
            formula_mode="Planted SAT",
            logging_options={"walksat_max_tries": 1, "walksat_max_flips": 1},
        )

        self.assertEqual([row.solver for row in rows], ["CDCL", "ProbSAT"])
        self.assertEqual(rows[0].problem_clauses, rows[1].problem_clauses)
        self.assertEqual(rows[0].problem_metadata["seed"], rows[1].problem_metadata["seed"])

    def test_random_3sat_preset_case_counts_and_seed_ranges(self):
        self.assertEqual(
            random_3sat_preset_names()[:4],
            ("Custom", RANDOM_3SAT_PRESET_A, RANDOM_3SAT_PRESET_B, RANDOM_3SAT_PRESET_C),
        )
        self.assertEqual(random_3sat_preset_case_count(RANDOM_3SAT_PRESET_A), 350)
        self.assertEqual(random_3sat_preset_case_count(RANDOM_3SAT_PRESET_B), 100)
        self.assertEqual(random_3sat_preset_case_count(RANDOM_3SAT_PRESET_C), 270)
        self.assertEqual(random_3sat_preset_default_solvers(RANDOM_3SAT_PRESET_A), ("CDCL", "DPLL", "WalkSAT", "ProbSAT"))
        self.assertEqual(random_3sat_preset_default_solvers(RANDOM_3SAT_PRESET_B), ("CDCL", "DPLL"))

        preset_a_cases = random_3sat_preset_cases(RANDOM_3SAT_PRESET_A)
        seeds_for_200 = {
            case["seed"]
            for case in preset_a_cases
            if case["variable_count"] == 200
        }
        seeds_for_300 = {
            case["seed"]
            for case in preset_a_cases
            if case["variable_count"] == 300
        }
        ratios_for_300 = {
            case["ratio"]
            for case in preset_a_cases
            if case["variable_count"] == 300
        }
        self.assertEqual(max(seeds_for_200), 20)
        self.assertEqual(min(seeds_for_200), 1)
        self.assertEqual(max(seeds_for_300), 10)
        self.assertEqual(min(seeds_for_300), 1)
        self.assertEqual(ratios_for_300, {3.5, 4.25, 5.5})

        preset_b_cases = random_3sat_preset_cases(RANDOM_3SAT_PRESET_B)
        ratios_for_150 = {
            case["ratio"]
            for case in preset_b_cases
            if case["variable_count"] == 150
        }
        ratios_for_200 = {
            case["ratio"]
            for case in preset_b_cases
            if case["variable_count"] == 200
        }
        self.assertEqual(ratios_for_150, {4.25, 5.5})
        self.assertEqual(ratios_for_200, {4.25, 5.5})

        preset_c_fractions = {
            case["sat_fraction"]
            for case in random_3sat_preset_cases(RANDOM_3SAT_PRESET_C)
        }
        self.assertEqual(preset_c_fractions, {0.3, 0.5, 0.7})

    def test_random_3sat_preset_registry_accepts_programmatic_presets(self):
        preset_name = "Preset Test: Tiny Registry SAT"
        register_random_3sat_preset(
            Random3SATPreset(
                name=preset_name,
                spec=Random3SATPresetSpec(
                    variables=(4, 5),
                    ratios=(2.0,),
                    seeds=range(1, 3),
                    formula_mode="Planted SAT",
                ),
                default_solvers=("CDCL", "ProbSAT"),
                ui_values=Random3SATPresetUiValues(
                    variables="4,5",
                    ratios="2.0",
                    seed="1",
                    formula_mode="Planted SAT",
                    sat_percentage="",
                ),
                summary="Tiny registry test preset.",
            )
        )

        cases = random_3sat_preset_cases(preset_name)
        self.assertIn(preset_name, random_3sat_preset_names())
        self.assertEqual(len(cases), 4)
        self.assertEqual(cases[0]["variable_count"], 4)
        self.assertEqual(cases[0]["clause_count"], 8)
        self.assertEqual(cases[0]["sat_fraction"], 1.0)
        self.assertEqual(random_3sat_preset_default_solvers(preset_name), ("CDCL", "ProbSAT"))
        self.assertEqual(random_3sat_preset_ui_values(preset_name).variables, "4,5")
        self.assertEqual(random_3sat_preset_summary(preset_name), "Tiny registry test preset.")

    def test_random_3sat_matrix_cases_support_mixed_sat_fractions(self):
        cases = matrix_cases(
            Random3SATPresetSpec(
                variables=(10,),
                ratios=(4.25,),
                seeds=range(1, 3),
                formula_mode="Random",
                sat_fractions=(0.25, 0.75),
            )
        )

        self.assertEqual(len(cases), 4)
        self.assertEqual({case.sat_percentage for case in cases}, {25.0, 75.0})
        self.assertEqual({case.sat_fraction for case in cases}, {0.25, 0.75})

    def test_random_3sat_matrix_cases_support_ratios_by_variable_count(self):
        cases = matrix_cases(
            Random3SATPresetSpec(
                variables=(100, 300),
                ratios=lambda n_vars: (3.5, 4.25, 5.5) if n_vars == 300 else (2.5, 3.5, 4.25, 5.5),
                seeds=range(1, 2),
                formula_mode="Planted SAT",
            )
        )

        ratios_by_n = {}
        for case in cases:
            ratios_by_n.setdefault(case.variable_count, set()).add(case.ratio)
        self.assertEqual(ratios_by_n[100], {2.5, 3.5, 4.25, 5.5})
        self.assertEqual(ratios_by_n[300], {3.5, 4.25, 5.5})

    def test_random_3sat_unknown_preset_raises_value_error(self):
        with self.assertRaises(ValueError):
            random_3sat_preset_cases("Preset X: Missing")
        with self.assertRaises(ValueError):
            random_3sat_preset_default_solvers("Preset X: Missing")
        with self.assertRaises(ValueError):
            random_3sat_preset_ui_values("Preset X: Missing")

    def test_random_3sat_preset_caps_large_dpll_timeout(self):
        small_problem = ProblemInstance("small", "Random 3-SAT", [[1]], metadata={"variables": 100})
        large_problem = ProblemInstance("large", "Random 3-SAT", [[1]], metadata={"variables": 200})
        forced_150_problem = ProblemInstance(
            "forced",
            "Random 3-SAT",
            [[1]],
            metadata={"variables": 150, "preset": RANDOM_3SAT_PRESET_B},
        )
        forced_200_problem = ProblemInstance(
            "forced large",
            "Random 3-SAT",
            [[1]],
            metadata={"variables": 200, "preset": RANDOM_3SAT_PRESET_B},
        )

        self.assertEqual(_random_3sat_preset_timeout("DPLL", large_problem, 30.0), 10.0)
        self.assertEqual(_random_3sat_preset_timeout("DPLL", large_problem, None), 10.0)
        self.assertEqual(_random_3sat_preset_timeout("DPLL", small_problem, 30.0), 30.0)
        self.assertEqual(_random_3sat_preset_timeout("CDCL", large_problem, 30.0), 30.0)
        self.assertEqual(_random_3sat_preset_timeout("DPLL", forced_150_problem, 30.0), 10.0)
        self.assertFalse(_random_3sat_preset_skip("DPLL", forced_150_problem))
        self.assertTrue(_random_3sat_preset_skip("DPLL", forced_200_problem))

    def test_random_3sat_preset_solver_policy_knobs(self):
        original_cap_min = random_3sat_presets_module.DPLL_TIMEOUT_CAP_MIN_VARIABLES
        original_cap_seconds = random_3sat_presets_module.DPLL_TIMEOUT_CAP_SECONDS
        original_skip_above = random_3sat_presets_module.DPLL_SKIP_ABOVE_VARIABLES
        try:
            random_3sat_presets_module.DPLL_TIMEOUT_CAP_MIN_VARIABLES = 150
            random_3sat_presets_module.DPLL_TIMEOUT_CAP_SECONDS = 4.0
            random_3sat_presets_module.DPLL_SKIP_ABOVE_VARIABLES = 200

            self.assertEqual(random_3sat_preset_solver_timeout("DPLL", 150, 30.0), 4.0)
            self.assertEqual(random_3sat_preset_solver_timeout("CDCL", 150, 30.0), 30.0)
            self.assertFalse(random_3sat_preset_should_skip_solver("DPLL", 200))
            self.assertTrue(random_3sat_preset_should_skip_solver("DPLL", 201))
            self.assertFalse(random_3sat_preset_should_skip_solver("CDCL", 300))
        finally:
            random_3sat_presets_module.DPLL_TIMEOUT_CAP_MIN_VARIABLES = original_cap_min
            random_3sat_presets_module.DPLL_TIMEOUT_CAP_SECONDS = original_cap_seconds
            random_3sat_presets_module.DPLL_SKIP_ABOVE_VARIABLES = original_skip_above

    def test_probsat_solver_alias_uses_walksat_strategy_and_label(self):
        result = solve_clauses(
            [[1, 2, 3], [-1, -2, -3]],
            "ProbSAT",
            logging_options={"walksat_max_tries": 1, "walksat_max_flips": 10, "walksat_selection_mode": "walksat"},
        )

        self.assertEqual(result.solver, "ProbSAT")
        self.assertIn(result.status, ("SAT", "UNKNOWN"))
        self.assertIn("strategy=probsat", result.stats["solver_options"])

    def test_random_3sat_csv_export_uses_dedicated_headers_and_stats(self):
        row = BenchmarkRow(
            "Random 3-SAT n10_m42",
            "Random 3-SAT",
            "ProbSAT",
            "UNKNOWN",
            0.25,
            42,
            10,
            7,
            decisions="-",
            conflicts="-",
            propagations="-",
            learned_clauses="-",
            seed=7,
            problem_metadata={
                "mode": "Random",
                "variables": 10,
                "ratio": 4.25,
                "clauses_requested": 42,
                "seed": 7,
                "sat_percentage": 50.0,
            },
            flips=100,
            tries=2,
            best_unsatisfied=1,
            timeout=30.0,
        )

        self.assertEqual(random_3sat_csv_row(row)[0:7], ["Random", 10, 4.25, 42, 0.5, 7, "ProbSAT"])
        with tempfile.TemporaryDirectory() as tmpdir:
            path = f"{tmpdir}/random_3sat.csv"
            write_random_3sat_benchmark_csv(path, [row])
            with open(path, newline="", encoding="utf-8") as handle:
                rows = list(csv.reader(handle))

        self.assertEqual(rows[0], RANDOM_3SAT_CSV_HEADERS)
        self.assertEqual(rows[1][0:7], ["Random", "10", "4.25", "42", "0.5", "7", "ProbSAT"])
        self.assertEqual(rows[1][-4:], ["100", "2", "1", "30.0"])

    def test_clique_benchmark_sweep_rows(self):
        rows = run_clique_sweep([3], [1.0], [3], ["CDCL"], repeats=1, seed=7)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].problem_type, "Clique")
        self.assertEqual(rows[0].status, "SAT")
        self.assertIn("k=3", rows[0].detail)

    def test_graph_suite_reuses_graph_for_clique_and_independent_set(self):
        rows = run_graph_suite_sweep(
            [5],
            [0.4],
            ["Clique", "Independent Set"],
            ["CDCL"],
            repeats=1,
            seed=7,
            target_sizes=[2],
        )

        self.assertEqual({row.problem_type for row in rows}, {"Clique", "Independent Set"})
        self.assertEqual(len({tuple(row.graph_edges) for row in rows}), 1)
        self.assertEqual(len({row.problem_metadata["shared_graph_id"] for row in rows}), 1)
        self.assertTrue(all(row.problem_metadata["suite"] for row in rows))
        self.assertTrue(all("graph=" in row.detail for row in rows))

    def test_graph_suite_reuses_graph_across_target_and_color_values(self):
        rows = run_graph_suite_sweep(
            [5],
            [0.4],
            ["Clique", "Graph Coloring"],
            ["CDCL"],
            repeats=1,
            seed=7,
            target_sizes=[2, 3],
            color_counts=[2, 3],
        )

        self.assertEqual(len(rows), 4)
        self.assertEqual(len({tuple(row.graph_edges) for row in rows}), 1)
        self.assertEqual(
            [row.problem_type for row in rows],
            ["Graph Coloring", "Graph Coloring", "Clique", "Clique"],
        )
        self.assertEqual({row.problem_metadata.get("colors") for row in rows if row.problem_type == "Graph Coloring"}, {2, 3})
        self.assertEqual({row.problem_metadata.get("target") for row in rows if row.problem_type == "Clique"}, {2, 3})

    def test_graph_suite_validates_problem_selection(self):
        with self.assertRaises(ValueError):
            run_graph_suite_sweep([5], [0.4], [], ["CDCL"], repeats=1, target_sizes=[2])
        with self.assertRaises(ValueError):
            run_graph_suite_sweep([5], [0.4], ["Clique"], ["CDCL"], repeats=1)
        with self.assertRaises(ValueError):
            run_graph_suite_sweep([5], [0.4], ["Graph Coloring"], ["CDCL"], repeats=1)

    def test_average_benchmark_groups_finished_repeats_only(self):
        app = SATApp.__new__(SATApp)
        rows = [
            BenchmarkRow("Graph Coloring n10_p30_k2", "Graph Coloring", "CDCL", "SAT", 1.0, 20, 10, 1, detail="probability, edges=8", conflicts=4, decisions=8, edge_count=8),
            BenchmarkRow("Graph Coloring n10_p30_k2", "Graph Coloring", "CDCL", "UNSAT", 3.0, 24, 10, 2, detail="probability, edges=10", conflicts=8, decisions=12, edge_count=10),
            BenchmarkRow("Graph Coloring n10_p30_k2", "Graph Coloring", "CDCL", "TIMEOUT", 30.0, 28, 10, 3, detail="probability, edges=12", edge_count=12),
            BenchmarkRow("Graph Coloring n10_p30_k2", "Graph Coloring", "CDCL", "SKIPPED", 0.0, 30, 10, 4, detail="probability, edges=13", edge_count=13),
        ]

        groups = app._aggregate_benchmark_rows(rows)

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["status_counts"], {"SAT": 1, "UNSAT": 1, "TIMEOUT": 1, "SKIPPED": 1})
        self.assertAlmostEqual(app._benchmark_group_metric_value(groups[0], "Raw Time"), 2.0)
        self.assertAlmostEqual(app._benchmark_group_metric_value(groups[0], "Normalized Time"), 0.2)
        self.assertAlmostEqual(app._benchmark_group_metric_value(groups[0], "Conflicts"), 6.0)
        self.assertEqual(app._benchmark_status_count_label(groups[0]["status_counts"]), "S:1 U:1 T:1 K:1")

    def test_average_benchmark_separates_case_and_solver_groups(self):
        app = SATApp.__new__(SATApp)
        rows = [
            BenchmarkRow("Graph Coloring n10_p30_k2", "Graph Coloring", "CDCL", "SAT", 1.0, 20, 10, 1),
            BenchmarkRow("Graph Coloring n10_p30_k2", "Graph Coloring", "DPLL", "SAT", 2.0, 20, 10, 1),
            BenchmarkRow("Graph Coloring n20_p30_k2", "Graph Coloring", "CDCL", "SAT", 3.0, 40, 20, 1),
        ]

        groups = app._aggregate_benchmark_rows(rows)

        self.assertEqual(len(groups), 3)
        self.assertEqual([group["solver"] for group in groups], ["CDCL", "DPLL", "CDCL"])
        self.assertEqual([group["case_name"] for group in groups], [
            "Graph Coloring n10_p30_k2",
            "Graph Coloring n10_p30_k2",
            "Graph Coloring n20_p30_k2",
        ])

    def test_average_benchmark_five_random_repeats_make_one_case_group(self):
        app = SATApp.__new__(SATApp)
        rows = [
            BenchmarkRow("Graph Coloring n10_p10_k2", "Graph Coloring", "CDCL", "SAT", 0.1, 20, 10, 1, detail="probability, edges=3", edge_count=3),
            BenchmarkRow("Graph Coloring n10_p10_k2", "Graph Coloring", "CDCL", "SAT", 0.2, 24, 10, 2, detail="probability, edges=5", edge_count=5),
            BenchmarkRow("Graph Coloring n10_p10_k2", "Graph Coloring", "CDCL", "UNSAT", 0.3, 28, 10, 3, detail="probability, edges=7", edge_count=7),
            BenchmarkRow("Graph Coloring n10_p10_k2", "Graph Coloring", "CDCL", "UNSAT", 0.4, 30, 10, 4, detail="probability, edges=8", edge_count=8),
            BenchmarkRow("Graph Coloring n10_p10_k2", "Graph Coloring", "CDCL", "UNSAT", 0.5, 32, 10, 5, detail="probability, edges=9", edge_count=9),
            BenchmarkRow("Graph Coloring n10_p30_k2", "Graph Coloring", "CDCL", "UNSAT", 1.0, 40, 10, 1, detail="probability, edges=14", edge_count=14),
        ]

        groups = app._aggregate_benchmark_rows(rows)

        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0]["case_name"], "Graph Coloring n10_p10_k2")
        self.assertEqual(len(groups[0]["rows"]), 5)
        self.assertEqual(groups[0]["status_counts"], {"SAT": 2, "UNSAT": 3})
        self.assertAlmostEqual(app._benchmark_group_metric_value(groups[0], "Raw Time"), 0.3)

    def test_average_benchmark_all_unfinished_group_has_zero_metric(self):
        app = SATApp.__new__(SATApp)
        rows = [
            BenchmarkRow("N-Queens n8", "N-Queens", "CDCL", "TIMEOUT", 30.0, 100, 64, 1),
            BenchmarkRow("N-Queens n8", "N-Queens", "CDCL", "SKIPPED", 0.0, 100, 64, 2),
        ]

        groups = app._aggregate_benchmark_rows(rows)

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["finished_rows"], [])
        self.assertEqual(app._benchmark_group_metric_value(groups[0], "Raw Time"), 0.0)
        self.assertEqual(groups[0]["status_counts"], {"TIMEOUT": 1, "SKIPPED": 1})

    def test_benchmark_detail_helpers_format_edges_stats_and_preview_policy(self):
        app = SATApp.__new__(SATApp)
        row = BenchmarkRow(
            "Graph Coloring n4_p50_k3",
            "Graph Coloring",
            "CDCL",
            "SAT",
            0.2,
            20,
            12,
            1,
            node_count=4,
            edge_count=3,
            graph_edges=[(3, 4), (1, 2), (2, 4)],
            decoded={1: 1, 2: 2, 3: 1, 4: 3},
            seed=9,
        )

        self.assertIn("1-2, 2-4, 3-4", app._format_benchmark_edges(row.graph_edges))
        details = app._format_benchmark_row_details(row)
        self.assertIn("Edges: 3", details)
        self.assertIn("Density: 0.5000", details)
        self.assertIn("Decoded response:", details)
        self.assertEqual(app._graph_preview_policy(80, 250), "auto")
        self.assertEqual(app._graph_preview_policy(81, 250), "manual")
        self.assertEqual(app._graph_preview_policy(200, 800), "manual")
        self.assertEqual(app._graph_preview_policy(201, 800), "skip")

    def test_random_graph_problem_is_buildable(self):
        problem = random_graph_coloring_problem(4, 0.5, 3, seed=1)

        self.assertEqual(problem.problem_type, "Graph Coloring")
        self.assertGreater(problem.clause_count, 0)
        self.assertEqual(problem.metadata["mode"], "probability")
        self.assertEqual(problem.metadata["nodes"], 4)
        self.assertEqual(len(problem.metadata["graph_edges"]), problem.metadata["edges"])

    def test_graph_benchmark_problem_metadata_keeps_edges(self):
        coloring = random_graph_coloring_problem(5, 0.4, 3, seed=2)
        hamiltonian = random_hamiltonian_path_problem(5, 0.4, seed=2)
        independent = random_independent_set_problem(5, 0.4, 2, seed=2)

        for problem in (coloring, hamiltonian, independent):
            self.assertEqual(problem.metadata["nodes"], 5)
            self.assertIn("graph_edges", problem.metadata)
            self.assertEqual(len(problem.metadata["graph_edges"]), problem.metadata["edges"])

    def test_result_to_row_preserves_graph_details_and_decoded_response(self):
        problem = random_graph_coloring_problem(4, 0.5, 3, seed=3)
        decoded = {1: 1, 2: 2, 3: 1, 4: 3}
        result = SolveResult(
            solver="CDCL",
            status="SAT",
            elapsed=0.25,
            solution={},
            decoded=decoded,
            stats={"conflicts": 2, "decisions": 3},
        )

        row = result_to_row(problem, result, repeat=5)

        self.assertEqual(row.node_count, 4)
        self.assertEqual(row.graph_edges, problem.metadata["graph_edges"])
        self.assertEqual(row.decoded, decoded)
        self.assertEqual(row.seed, 3)
        self.assertEqual(row.problem_metadata["nodes"], 4)
        self.assertEqual(row.problem_clauses, problem.clauses)

    def test_result_to_row_skips_oversized_benchmark_clauses(self):
        clauses = [[index, -index - 1] for index in range(MAX_STORED_BENCHMARK_CLAUSES + 1)]
        problem = ProblemInstance("huge", "N-Queens", clauses, {"size": 300})
        result = SolveResult("CDCL", "SAT", 0.1, {}, stats={})

        row = result_to_row(problem, result, repeat=1)

        self.assertEqual(row.problem_clauses, [])
        self.assertIn("skipped", row.problem_metadata["cnf_storage"])

    def test_benchmark_row_dimacs_uses_stored_clauses(self):
        app = SATApp.__new__(SATApp)
        row = BenchmarkRow(
            "Tiny benchmark",
            "Graph Coloring",
            "CDCL",
            "SAT",
            0.1,
            2,
            2,
            1,
            problem_clauses=[[1, -2], [2]],
        )

        dimacs = app._benchmark_row_dimacs(row)

        self.assertIn("c Tiny benchmark", dimacs)
        self.assertIn("p cnf 2 2", dimacs)
        self.assertEqual(parse_dimacs_text(dimacs), [[1, -2], [2]])

    def test_solver_option_form_builder(self):
        app = SATApp.__new__(SATApp)

        options = app._logging_options(
            False,
            "Periodic progress",
            "MOMS",
            "Random",
            True,
            "25",
            "200",
            "7",
        )

        self.assertEqual(options["mode"], "normal")
        self.assertEqual(options["branching"], "MOMS")
        self.assertEqual(options["initial_phase"], "Random")
        self.assertEqual(options["restart_interval"], 25)
        self.assertEqual(options["learned_clause_limit"], 200)
        self.assertEqual(options["random_seed"], 7)
        self.assertEqual(options["cdcl_random_seed"], 7)
        self.assertEqual(options["walksat_max_tries"], 10)
        self.assertEqual(options["walksat_max_flips"], 10000)
        self.assertEqual(options["walksat_noise"], 0.5)
        self.assertEqual(options["walksat_selection_mode"], "walksat")
        self.assertFalse(options["walksat_adaptive_noise"])
        self.assertIsNone(options["walksat_random_seed"])
        self.assertEqual(options["probsat_max_tries"], 10)
        self.assertEqual(options["probsat_max_flips"], 10000)
        self.assertEqual(options["probsat_noise"], 0.5)
        self.assertFalse(options["probsat_adaptive_noise"])
        self.assertIsNone(options["probsat_random_seed"])

    def test_walksat_option_form_builder(self):
        app = SATApp.__new__(SATApp)

        options = app._logging_options(
            False,
            "Periodic progress",
            walksat_max_tries="3",
            walksat_max_flips="40",
            walksat_noise="0.25",
            walksat_selection_mode="ProbSAT",
            walksat_adaptive_noise=True,
            walksat_random_seed="9",
        )

        self.assertEqual(options["walksat_max_tries"], 3)
        self.assertEqual(options["walksat_max_flips"], 40)
        self.assertEqual(options["walksat_noise"], 0.25)
        self.assertEqual(options["walksat_selection_mode"], "probsat")
        self.assertTrue(options["walksat_adaptive_noise"])
        self.assertEqual(options["walksat_random_seed"], 9)

    def test_probsat_benchmark_option_form_builder(self):
        app = SATApp.__new__(SATApp)

        options = app._logging_options(
            False,
            "Periodic progress",
            walksat_max_tries="3",
            walksat_max_flips="40",
            walksat_noise="0.25",
            walksat_selection_mode="Classic WalkSAT",
            walksat_adaptive_noise=False,
            walksat_random_seed="9",
            probsat_max_tries="4",
            probsat_max_flips="80",
            probsat_noise="0.15",
            probsat_adaptive_noise=True,
            probsat_random_seed="11",
        )

        self.assertEqual(options["walksat_selection_mode"], "walksat")
        self.assertEqual(options["probsat_max_tries"], 4)
        self.assertEqual(options["probsat_max_flips"], 80)
        self.assertEqual(options["probsat_noise"], 0.15)
        self.assertTrue(options["probsat_adaptive_noise"])
        self.assertEqual(options["probsat_random_seed"], 11)

    def test_walksat_solve_result_shows_reason_and_final_noise(self):
        app = SATApp.__new__(SATApp)
        app.current_problem = ProblemInstance("Tiny", "DIMACS", [[1], [-1]])
        result = SolveResult(
            solver="WalkSAT",
            status="UNKNOWN",
            elapsed=0.01,
            solution=None,
            stats={
                "tries": 1,
                "flips": 2,
                "best_unsatisfied": 1,
                "termination_reason": "budget_exhausted",
                "final_noise": 0.55,
            },
            clauses=2,
            variables=1,
        )

        text = app._format_solve_result(result)

        self.assertIn("Termination Reason: budget_exhausted", text)
        self.assertIn("Final Noise: 0.55", text)

    def test_benchmark_row_records_solver_options(self):
        problem = random_graph_coloring_problem(4, 0.5, 3, seed=3)
        result = solve_problem(
            problem,
            "CDCL",
            logging_options={"branching": "MOMS", "initial_phase": "Negative first", "restart_interval": 10},
        )

        row = result_to_row(problem, result, repeat=1)

        self.assertIn("branch=MOMS", row.solver_options)
        self.assertIn("phase=Negative first", row.solver_options)
        self.assertIn("restart=10", row.solver_options)

    def test_dpll_ignores_cdcl_options(self):
        problem = dimacs_problem_from_text("p cnf 1 1\n1 0\n")
        result = solve_problem(
            problem,
            "DPLL",
            logging_options={"branching": "Random", "initial_phase": "Random", "random_seed": 4},
        )

        self.assertEqual(result.status, "SAT")
        self.assertEqual(result.stats["solver_options"], "DPLL small-clause")

    def test_dimacs_type_inference_reads_saved_type_comment(self):
        app = SATApp.__new__(SATApp)

        self.assertEqual(app._infer_dimacs_problem_type("c type=Hamiltonian Path\np cnf 1 1\n1 0\n"), "Hamiltonian Path")
        self.assertEqual(app._infer_dimacs_problem_type("c type=Unknown\np cnf 1 1\n1 0\n"), "DIMACS")

    def test_solve_detail_row_uses_current_problem_and_result(self):
        app = SATApp.__new__(SATApp)
        app.current_problem = random_graph_coloring_problem(4, 0.5, 3, seed=3)
        app.latest_solve_result = SolveResult(
            solver="CDCL",
            status="SAT",
            elapsed=0.25,
            solution={},
            decoded={1: 1, 2: 2, 3: 1, 4: 3},
            stats={"conflicts": 2, "decisions": 3},
        )
        app.solver_name = type("SolverName", (), {"get": lambda self: "CDCL"})()

        row = app._solve_detail_row()

        self.assertEqual(row.case_name, app.current_problem.name)
        self.assertEqual(row.status, "SAT")
        self.assertEqual(row.graph_edges, app.current_problem.metadata["graph_edges"])
        self.assertEqual(row.decoded, {1: 1, 2: 2, 3: 1, 4: 3})
        self.assertIn("Graph edges", app._benchmark_problem_data_label(row))
        self.assertEqual(row.problem_clauses, app.current_problem.clauses)

    def test_non_graph_benchmark_details_show_problem_data(self):
        app = SATApp.__new__(SATApp)
        sudoku_row = BenchmarkRow(
            "Sudoku 4x4 benchmark",
            "Sudoku",
            "CDCL",
            "SAT",
            0.1,
            100,
            64,
            1,
            decoded=[
                [1, 2, 3, 4],
                [3, 4, 1, 2],
                [2, 1, 4, 3],
                [4, 3, 2, 1],
            ],
            problem_metadata={
                "size": 4,
                "box_size": 2,
                "givens": 2,
                "empty_cells": 14,
                "grid": [
                    [1, 0, 0, 4],
                    [0, 0, 0, 0],
                    [0, 0, 0, 0],
                    [4, 0, 0, 1],
                ],
            },
        )
        queens_row = BenchmarkRow(
            "N-Queens n4",
            "N-Queens",
            "CDCL",
            "SAT",
            0.1,
            80,
            16,
            1,
            decoded={"positions": [(1, 2), (2, 4), (3, 1), (4, 3)], "board": [".Q..", "...Q", "Q...", "..Q."]},
            problem_metadata={"size": 4, "queens": 4, "board_cells": 16},
        )

        sudoku_details = app._format_benchmark_row_details(sudoku_row)
        sudoku_data = app._format_benchmark_problem_data(sudoku_row)
        queens_details = app._format_benchmark_row_details(queens_row)
        queens_data = app._format_benchmark_problem_data(queens_row)

        self.assertIn("Size: 4x4", sudoku_details)
        self.assertIn("Givens: 2", sudoku_details)
        self.assertIn("Initial puzzle:", sudoku_data)
        self.assertIn("1 . . 4", sudoku_data)
        self.assertIn("Solved grid:", sudoku_data)
        self.assertIn("Board: 4x4", queens_details)
        self.assertIn("Queens: 4", queens_details)
        self.assertIn("Positions:", queens_data)
        self.assertIn(".Q..", queens_data)

    def test_exact_edge_graph_has_requested_edges(self):
        graph = generate_random_graph_exact_edges(6, 7, rng=random.Random(3))
        edges = graph_edges(graph)

        self.assertEqual(len(edges), 7)
        self.assertEqual(len(edges), len(set(edges)))
        self.assertTrue(all(u != v for u, v in edges))

    def test_exact_edge_graph_seed_is_reproducible(self):
        first = exact_edges_graph_coloring_problem(6, 7, 3, seed=11)
        second = exact_edges_graph_coloring_problem(6, 7, 3, seed=11)

        self.assertEqual(first.clauses, second.clauses)
        self.assertEqual(first.metadata["edges"], 7)
        self.assertEqual(first.metadata["mode"], "exact_edges")

    def test_exact_edge_count_above_complete_graph_saturates(self):
        problem = exact_edges_graph_coloring_problem(4, 100, 3)

        self.assertEqual(problem.metadata["edges"], 6)
        self.assertEqual(problem.metadata["requested_edges"], 100)
        self.assertTrue(problem.metadata["edge_request_clamped"])

    def test_negative_exact_edge_count_raises(self):
        with self.assertRaises(ValueError):
            exact_edges_graph_coloring_problem(4, -1, 3)

    def test_average_degree_edge_conversion(self):
        self.assertEqual(edge_count_from_average_degree(10, 4), 20)
        self.assertEqual(edge_count_from_average_degree(10, 0), 0)
        self.assertEqual(edge_count_from_average_degree(4, 20), 6)

    def test_negative_average_degree_raises(self):
        with self.assertRaises(ValueError):
            edge_count_from_average_degree(10, -1)

    def test_average_degree_graph_problem_metadata_and_seed(self):
        first = average_degree_graph_coloring_problem(10, 4, 3, seed=5)
        second = average_degree_graph_coloring_problem(10, 4, 3, seed=5)

        self.assertEqual(first.clauses, second.clauses)
        self.assertEqual(first.metadata["mode"], "average_degree")
        self.assertEqual(first.metadata["average_degree"], 4)
        self.assertEqual(first.metadata["requested_edges"], 20)
        self.assertEqual(first.metadata["edges"], 20)
        self.assertFalse(first.metadata["edge_request_clamped"])

    def test_average_degree_graph_above_complete_graph_saturates(self):
        problem = average_degree_graph_coloring_problem(4, 20, 3)

        self.assertEqual(problem.metadata["edges"], 6)
        self.assertEqual(problem.metadata["requested_edges"], 40)
        self.assertTrue(problem.metadata["edge_request_clamped"])

    def test_readable_color_encoding_does_not_collide_when_width_expands(self):
        colors = 101
        seen = {
            color_var(node, color, colors)
            for node in range(1, 4)
            for color in range(1, colors + 1)
        }

        self.assertEqual(len(seen), 3 * colors)
        self.assertEqual(color_var(2, 101, colors), 2101)

    def test_decode_coloring_with_readable_encoding(self):
        solution = {
            color_var(1, 2, 3): True,
            color_var(2, 1, 3): True,
            color_var(3, 3, 3): True,
        }

        self.assertEqual(decode_coloring(solution, 3), {1: 2, 2: 1, 3: 3})

    def test_decode_coloring_with_expanded_readable_encoding(self):
        solution = {
            color_var(1, 100, 101): True,
            color_var(2, 101, 101): True,
        }

        self.assertEqual(decode_coloring(solution, 101), {1: 100, 2: 101})

    def test_app_can_be_instantiated(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        root.withdraw()
        try:
            app = SATApp(root)
            self.assertIsNone(app.current_problem)
            self.assertEqual(app.solve_timeout_seconds.get(), "30")
            self.assertEqual(app.bench_timeout_seconds.get(), "30")
            self.assertEqual(app._benchmark_bar_color("TIMEOUT"), "#f58518")
            self.assertEqual(app._benchmark_bar_color("SKIPPED"), "#bab0ab")
            row = BenchmarkRow(
                case_name="Hamiltonian Path n10_p30",
                problem_type="Hamiltonian Path",
                solver="CDCL",
                status="SAT",
                elapsed=0.1,
                clauses=1,
                variables=1,
                repeat=1,
            )
            self.assertEqual(app._benchmark_chart_label(row), "n10_p30\nCDCL")
            app.benchmark_rows = [row]
            self.assertEqual(app._benchmark_chart_title("Raw Time"), "Hamiltonian Path - Raw Time")
            self.assertIn("N-Queens", PROBLEM_KINDS)
            self.assertIn("Hamiltonian Path", PROBLEM_KINDS)
            self.assertIn("Independent Set", PROBLEM_KINDS)
            self.assertIn("Clique", PROBLEM_KINDS)
            self.assertIn("Random 3-SAT", PROBLEM_KINDS)
            self.assertIn("N-Queens", BENCHMARK_PROBLEMS)
            self.assertIn("Random 3-SAT", BENCHMARK_PROBLEMS)
            self.assertIn("Clique", BENCHMARK_PROBLEMS)
            self.assertIn("Graph Suite", BENCHMARK_PROBLEMS)
            self.assertIn("WalkSAT", SOLVERS)
            self.assertIn("ProbSAT", SOLVERS)
            self.assertEqual(SOLVE_SOLVERS, ("CDCL", "DPLL", "WalkSAT"))
            self.assertEqual(root.tk.splitlist(app.solve_solver_box.cget("values")), SOLVE_SOLVERS)
            self.assertIn("WalkSAT", app.solve_solver_guide.guide_text)
            self.assertIn("UNKNOWN", app.solve_solver_guide.guide_text)
            self.assertIn("WalkSAT", app.benchmark_solver_guide.guide_text)
            self.assertFalse(app.bench_walksat.get())
            self.assertFalse(app.bench_probsat.get())
            self.assertEqual(str(app.solve_cdcl_options_frame.cget("text")), "CDCL Options")
            self.assertEqual(str(app.benchmark_cdcl_options_frame.cget("text")), "CDCL Options")
            self.assertEqual(str(app.solve_walksat_options_frame.cget("text")), "WalkSAT Options")
            self.assertEqual(str(app.benchmark_walksat_options_frame.cget("text")), "WalkSAT Options")
            self.assertEqual(str(app.benchmark_probsat_options_frame.cget("text")), "ProbSAT Options")
            self.assertEqual(
                sum(1 for child in app.benchmark_walksat_options_frame.winfo_children() if isinstance(child, app_module.ttk.Combobox)),
                0,
            )
            self.assertTrue(hasattr(app, "solve_result_pane"))
            self.assertTrue(hasattr(app, "benchmark_results_pane"))
            self.assertIn("+ Generate", str(app.generate_button.cget("text")))
            self.assertIn("> Solve", str(app.solve_button.cget("text")))
            self.assertIn("x Cancel", str(app.solve_toolbar_cancel_button.cget("text")))
            self.assertIn("@ Refresh Chart", str(app.refresh_chart_button.cget("text")))
            self.assertEqual(str(app.refresh_cnf_button.cget("text")), "Refresh CNF Preview")
            self.assertIn("Export CSV", str(app.export_csv_button.cget("text")))
            self.assertIn("Export 3-SAT CSV", str(app.export_3sat_csv_button.cget("text")))
            self.assertEqual(str(app.chart_metric_box.cget("state")), "readonly")
            self.assertEqual(str(app.chart_view_box.cget("state")), "readonly")
            self.assertEqual(int(app.benchmark_left_shell.cget("width")), BENCHMARK_LEFT_PANEL_WIDTH)
            self.assertEqual(int(app.benchmark_detail_shell.cget("width")), BENCHMARK_DETAIL_PANEL_WIDTH)
            self.assertEqual(str(app.run_progress_bar.cget("mode")), "determinate")
            self.assertEqual(app.progress_percent.get(), "0%")
            self.assertTrue(app.root.bind("<Control-w>"))
            self.assertTrue(hasattr(app.solve_tab, "_tab_scroll_canvas"))
            self.assertTrue(hasattr(app.benchmark_tab, "_tab_scroll_canvas"))
            self.assertEqual(app.walksat_max_tries.get(), "10")
            self.assertEqual(app.walksat_max_flips.get(), "10000")
            self.assertEqual(app.walksat_noise.get(), "0.5")
            self.assertEqual(app.walksat_selection_mode.get(), "Classic WalkSAT")
            self.assertFalse(app.walksat_adaptive_noise.get())
            self.assertIn("ProbSAT", app.solve_solver_guide.guide_text)
            self.assertEqual(str(app.solve_jobs_scrollbar.cget("orient")), "vertical")
            self.assertEqual(str(app.benchmark_jobs_scrollbar.cget("orient")), "vertical")

            self.assertEqual(app.problem_description.get(), "Fill an n x n grid so each row, column, and square box contains every value exactly once.")
            self.assertEqual(str(app.solver_log_box.cget("state")), "disabled")
            app.advanced_solver_logs.set(True)
            app._refresh_solver_log_controls()
            self.assertEqual(str(app.solver_log_box.cget("state")), "readonly")

            app.problem_kind.set("Graph Coloring")
            app._refresh_problem_form()
            self.assertEqual(str(app.graph_field_entries["probability"].cget("state")), "disabled")
            self.assertEqual(str(app.edge_text.cget("state")), "normal")
            app.graph_mode.set("Average degree")
            app._refresh_graph_controls()
            self.assertEqual(str(app.graph_field_entries["average_degree"].cget("state")), "normal")
            self.assertEqual(str(app.graph_field_entries["probability"].cget("state")), "disabled")
            self.assertEqual(str(app.edge_text.cget("state")), "disabled")

            app.problem_kind.set("Random 3-SAT")
            app._refresh_problem_form()
            self.assertEqual(app.random_3sat_variables.get(), "50")
            self.assertEqual(app.random_3sat_mode.get(), "Planted SAT")
            self.assertEqual(app.random_3sat_sat_percentage.get(), "50")
            self.assertEqual(str(app.random_3sat_sat_percentage_entry.cget("state")), "disabled")
            app.random_3sat_mode.set("Random")
            app._refresh_random_3sat_controls()
            self.assertEqual(str(app.random_3sat_sat_percentage_entry.cget("state")), "normal")
            app.random_3sat_variables.set("6")
            app.random_3sat_clauses.set("12")
            app.random_3sat_seed.set("3")
            app.random_3sat_sat_percentage.set("")
            problem = app.build_problem_from_form()
            self.assertEqual(problem.metadata["mode"], "Random")
            self.assertEqual(problem.metadata["selected_mode"], "Random")
            self.assertIsNone(problem.metadata["sat_percentage"])
            app.random_3sat_mode.set("Forced UNSAT")
            app._refresh_random_3sat_controls()
            problem = app.build_problem_from_form()
            self.assertEqual(problem.problem_type, "Random 3-SAT")
            self.assertEqual(problem.clause_count, 12)
            self.assertEqual(problem.metadata["mode"], "Forced UNSAT")

            app.problem_kind.set("Clique")
            app._refresh_problem_form()
            self.assertEqual(app.problem_description.get(), "Choose at least k graph nodes so every chosen pair is connected by an edge.")
            self.assertIn("target", app.graph_field_entries)
            app.graph_nodes.set("3")
            app.graph_target.set("3")
            app.edge_text.delete("1.0", tk.END)
            app.edge_text.insert("1.0", "1-2, 1-3, 2-3")
            problem = app.build_problem_from_form()
            self.assertEqual(problem.problem_type, "Clique")
            self.assertEqual(problem.metadata["target"], 3)

            app.bench_problem.set("Sudoku")
            app._refresh_benchmark_form()
            self.assertEqual(app._selected_sudoku_benchmark_sizes(), [4, 9])
            self.assertEqual(str(app.skip_benchmark_button.cget("state")), "disabled")
            skip_event = object()
            benchmark_job = app._create_job("benchmark", "Benchmarking", skip_event=skip_event)
            benchmark_job.status = "Running"
            app._update_job_row(benchmark_job)
            self.assertEqual(str(app.skip_benchmark_button.cget("state")), "normal")
            self.assertEqual(str(app.benchmark_toolbar_cancel_button.cget("state")), "normal")
            app._finish_job(benchmark_job, "Done")
            self.assertEqual(str(app.skip_benchmark_button.cget("state")), "disabled")
            self.assertEqual(str(app.benchmark_toolbar_cancel_button.cget("state")), "disabled")
            self.assertFalse(app.bench_sudoku_size_vars[16].get())
            self.assertFalse(app.bench_sudoku_size_vars[25].get())
            self.assertEqual(str(app.bench_log_box.cget("state")), "disabled")
            app.bench_advanced_solver_logs.set(True)
            app._refresh_benchmark_log_controls()
            self.assertEqual(str(app.bench_log_box.cget("state")), "readonly")
            app.bench_problem.set("Hamiltonian Path")
            app._refresh_benchmark_form()
            self.assertEqual(set(app.bench_graph_mode_buttons), {"Probability", "Exact edges", "Average degree"})
            self.assertEqual(str(app.bench_graph_mode_buttons["Probability"].cget("text")), "G(n,p)")
            self.assertEqual(str(app.bench_graph_mode_buttons["Exact edges"].cget("text")), "G(n,m)")
            self.assertEqual(str(app.bench_graph_mode_buttons["Average degree"].cget("text")), "G(n,d)")
            self.assertEqual(str(app.bench_graph_field_entries["probabilities"].cget("state")), "normal")
            app.bench_generation_mode.set("Exact edges")
            app._refresh_benchmark_graph_controls()
            self.assertEqual(str(app.bench_graph_field_entries["edge_counts"].cget("state")), "normal")
            self.assertEqual(str(app.bench_graph_field_entries["probabilities"].cget("state")), "disabled")
            app.bench_problem.set("Random 3-SAT")
            app._refresh_benchmark_form()
            self.assertEqual(app.benchmark_description.get(), "Generate random 3-literal clauses as planted SAT, forced UNSAT, pure random, or a SAT/UNSAT mix.")
            self.assertEqual(app.bench_3sat_preset.get(), "Custom")
            self.assertEqual(app.bench_3sat_variables.get(), "20,50,100")
            self.assertEqual(app.bench_3sat_mode.get(), "Planted SAT")
            self.assertEqual(app.bench_3sat_sat_percentage.get(), "50")
            self.assertEqual(str(app.bench_3sat_sat_percentage_entry.cget("state")), "disabled")
            app.bench_3sat_mode.set("Random")
            app._refresh_benchmark_random_3sat_controls()
            self.assertEqual(str(app.bench_3sat_sat_percentage_entry.cget("state")), "normal")
            app.bench_3sat_preset.set("Preset A: Planted SAT")
            app._apply_random_3sat_preset()
            self.assertEqual(app.bench_3sat_variables.get(), "50,100,150,200,300")
            self.assertEqual(app.bench_3sat_ratios.get(), "2.5,3.5,4.25,5.5")
            self.assertTrue(app.bench_probsat.get())
            self.assertEqual(str(app.bench_3sat_variables_entry.cget("state")), "disabled")
            self.assertIn("350 cases", app.bench_3sat_preset_summary.get())
            app.bench_3sat_preset.set("Custom")
            app._apply_random_3sat_preset()
            self.assertEqual(str(app.bench_3sat_variables_entry.cget("state")), "normal")
            app.bench_problem.set("Clique")
            app._refresh_benchmark_form()
            self.assertIn("targets", app.bench_graph_field_entries)
            self.assertEqual(app.benchmark_description.get(), "Choose at least k graph nodes so every chosen pair is connected by an edge.")
            app.bench_problem.set("Graph Suite")
            app._refresh_benchmark_form()
            self.assertTrue(app.bench_suite_clique.get())
            self.assertTrue(app.bench_suite_independent.get())
            self.assertFalse(app.bench_suite_graph_coloring.get())
            self.assertIn("targets", app.bench_graph_field_entries)
            self.assertIn("colors", app.bench_graph_field_entries)
            self.assertEqual(str(app.bench_graph_field_entries["targets"].cget("state")), "normal")
            self.assertEqual(str(app.bench_graph_field_entries["colors"].cget("state")), "disabled")
            app.bench_suite_graph_coloring.set(True)
            app._refresh_benchmark_graph_controls()
            self.assertEqual(str(app.bench_graph_field_entries["colors"].cget("state")), "normal")
        finally:
            root.destroy()

    def test_graph_popout_creates_window_for_graph_rows_only(self):
        if app_module.Figure is None or app_module.FigureCanvasTkAgg is None:
            self.skipTest("Matplotlib Tk support is not available")
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        root.withdraw()
        original_showinfo = app_module.messagebox.showinfo
        messages = []
        try:
            app = SATApp(root)
            graph_row = BenchmarkRow(
                "Graph Coloring n3",
                "Graph Coloring",
                "CDCL",
                "SAT",
                0.1,
                3,
                3,
                1,
                node_count=3,
                graph_edges=[(1, 2), (2, 3)],
                decoded={1: 1, 2: 2, 3: 1},
            )
            before = len([child for child in root.winfo_children() if isinstance(child, tk.Toplevel)])
            app._open_graph_popout(graph_row, "Test Graph")
            root.update_idletasks()
            after = len([child for child in root.winfo_children() if isinstance(child, tk.Toplevel)])
            self.assertEqual(after, before + 1)

            app_module.messagebox.showinfo = lambda title, message: messages.append((title, message))
            non_graph_row = BenchmarkRow("N-Queens n4", "N-Queens", "CDCL", "SAT", 0.1, 1, 1, 1)
            app._open_graph_popout(non_graph_row, "No Graph")
            self.assertTrue(messages)
        finally:
            app_module.messagebox.showinfo = original_showinfo
            for child in root.winfo_children():
                if isinstance(child, tk.Toplevel):
                    child.destroy()
            root.destroy()

    def test_app_worker_feed_events_are_processed(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        root.withdraw()
        try:
            app = SATApp(root)

            def worker(_token, event_callback):
                event_callback(RunEvent(EVENT_LOG, "background hello"))

            app._start_worker("Tiny worker", worker)
            time.sleep(0.05)
            app._poll_run_events()

            feed = app.feed_text.get("1.0", tk.END)
            self.assertIn("background hello", feed)
        finally:
            root.destroy()

    def test_feed_keeps_only_recent_lines(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        root.withdraw()
        try:
            app = SATApp(root)

            for index in range(FEED_MAX_LINES + 5):
                app.append_feed(f"line {index}")

            feed = app.feed_text.get("1.0", tk.END)
            self.assertNotIn("line 0", feed)
            self.assertIn(f"line {FEED_MAX_LINES + 4}", feed)
            self.assertLessEqual(len([line for line in feed.splitlines() if line.strip()]), FEED_MAX_LINES)
        finally:
            root.destroy()

    def test_feed_can_show_only_selected_job_logs(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        root.withdraw()
        try:
            app = SATApp(root)
            first = app._create_job("solve", "First solve")
            second = app._create_job("benchmark", "Second benchmark")
            app.append_feed("first log", first.job_id)
            app.append_feed("second log", second.job_id)

            app._select_job(first.job_id)
            app.show_selected_job_feed_logs()

            feed = app.feed_text.get("1.0", tk.END)
            self.assertIn("first log", feed)
            self.assertNotIn("second log", feed)
            self.assertEqual(app.feed_filter_job_id, first.job_id)
            self.assertEqual(str(app.feed_show_all_button.cget("state")), "normal")

            app.show_all_feed_logs()

            feed = app.feed_text.get("1.0", tk.END)
            self.assertIn("first log", feed)
            self.assertIn("second log", feed)
        finally:
            root.destroy()

    def test_feed_can_mute_and_forget_selected_job_logs(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        root.withdraw()
        try:
            app = SATApp(root)
            first = app._create_job("solve", "First solve")
            second = app._create_job("solve", "Second solve")
            first.finished = True
            app.append_feed("first before mute", first.job_id)
            app.append_feed("second stays", second.job_id)

            app._select_job(first.job_id)
            app.toggle_selected_job_feed_muted()
            app.append_feed("first muted", first.job_id)

            feed = app.feed_text.get("1.0", tk.END)
            self.assertNotIn("first before mute", feed)
            self.assertNotIn("first muted", feed)
            self.assertIn("second stays", feed)
            self.assertIn(first.job_id, app.muted_feed_job_ids)
            self.assertEqual(str(app.feed_mute_selected_button.cget("text")), "Unmute Selected")
            self.assertEqual(str(app.feed_unmute_all_button.cget("state")), "normal")
            self.assertIn("1 muted", app.feed_status.get())
            self.assertIn("selected muted", app.feed_status.get())

            app.delete_selected_solve_job()

            self.assertNotIn(first.job_id, app.muted_feed_job_ids)
            self.assertNotIn("first", app.feed_text.get("1.0", tk.END))
        finally:
            root.destroy()

    def test_feed_unmute_all_updates_indicator_and_future_logs(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        root.withdraw()
        try:
            app = SATApp(root)
            first = app._create_job("solve", "First solve")
            second = app._create_job("benchmark", "Second benchmark")

            app._select_job(first.job_id)
            app.toggle_selected_job_feed_muted()
            app._select_job(second.job_id)
            app.toggle_selected_job_feed_muted()

            self.assertEqual(app.muted_feed_job_ids, {first.job_id, second.job_id})
            self.assertEqual(str(app.feed_unmute_all_button.cget("state")), "normal")
            self.assertIn("2 muted", app.feed_status.get())

            app.unmute_all_feed_logs()
            app.append_feed("first after unmute", first.job_id)

            self.assertEqual(app.muted_feed_job_ids, set())
            self.assertEqual(str(app.feed_unmute_all_button.cget("state")), "disabled")
            self.assertIn("none muted", app.feed_status.get())
            self.assertIn("first after unmute", app.feed_text.get("1.0", tk.END))
        finally:
            root.destroy()

    def test_solve_jobs_can_multi_select_and_show_muted_marker(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        root.withdraw()
        try:
            app = SATApp(root)
            first = app._create_job("solve", "First solve")
            second = app._create_job("solve", "Second solve")

            self.assertEqual(str(app.solve_jobs_table.cget("selectmode")), "extended")

            app.solve_jobs_table.selection_set((first.job_id, second.job_id))
            app.solve_jobs_table.focus(second.job_id)
            app._on_solve_job_selected()
            app.toggle_selected_job_feed_muted()

            self.assertEqual(app.muted_feed_job_ids, {first.job_id, second.job_id})
            self.assertIn("[M]", app.solve_jobs_table.item(first.job_id, "values")[0])
            self.assertIn("[M]", app.solve_jobs_table.item(second.job_id, "values")[0])
            self.assertIn("muted", app.solve_jobs_table.item(first.job_id, "tags"))
            self.assertIn("muted", app.solve_jobs_table.item(second.job_id, "tags"))
            self.assertIn("2 muted", app.feed_status.get())

            app.toggle_selected_job_feed_muted()

            self.assertEqual(app.muted_feed_job_ids, set())
            self.assertNotIn("[M]", app.solve_jobs_table.item(first.job_id, "values")[0])
            self.assertNotIn("muted", app.solve_jobs_table.item(first.job_id, "tags"))
        finally:
            root.destroy()

    def test_graph_suite_run_benchmark_builds_shared_graph_params(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        root.withdraw()
        try:
            app = SATApp(root)
            app.bench_problem.set("Graph Suite")
            app._refresh_benchmark_form()
            app.bench_nodes.set("5")
            app.bench_probs.set("0.4")
            app.bench_targets.set("2,3")
            app.bench_colors.set("2")
            app.bench_repeats.set("1")
            app.bench_suite_graph_coloring.set(False)
            app.bench_suite_hamiltonian.set(False)
            app.bench_suite_independent.set(True)
            app.bench_suite_clique.set(True)
            captured = {}

            class DummyJob:
                pending_chart_refresh = False

            def fake_start(title, process_target, params, **kwargs):
                captured["title"] = title
                captured["params"] = params
                captured["kwargs"] = kwargs
                return DummyJob()

            app._start_process_worker = fake_start
            app.run_benchmark()

            self.assertEqual(captured["title"], "Benchmarking 4 solver runs")
            self.assertEqual(captured["params"]["problem_type"], "Graph Suite")
            self.assertEqual(captured["params"]["suite_problems"], ["Clique", "Independent Set"])
            self.assertEqual(captured["params"]["target_sizes"], [2, 3])
            self.assertEqual(captured["params"]["probabilities"], [0.4])
        finally:
            root.destroy()

    def test_parallel_jobs_can_start_while_another_job_is_running(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        root.withdraw()
        try:
            app = SATApp(root)
            app._create_job("benchmark", "Long benchmark")

            def worker(_token, event_callback):
                event_callback(RunEvent(EVENT_LOG, "parallel hello"))

            solve_job = app._start_worker("Tiny solve", worker, kind="solve")
            time.sleep(0.05)
            app._poll_run_events()

            self.assertEqual(len(app.jobs), 2)
            self.assertEqual(solve_job.kind, "solve")
            self.assertIn("parallel hello", app.feed_text.get("1.0", tk.END))
        finally:
            root.destroy()

    def test_job_tagged_solve_events_update_only_selected_job(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        root.withdraw()
        try:
            app = SATApp(root)
            first = app._create_job("solve", "First solve")
            second = app._create_job("solve", "Second solve")

            app._handle_run_event(RunEvent(
                EVENT_CNF,
                payload={
                    "_job_id": first.job_id,
                    "problem": {
                        "name": "first problem",
                        "problem_type": "DIMACS",
                        "clauses": [[1]],
                        "metadata": {},
                    },
                    "dimacs": "p cnf 1 1\n1 0\n",
                },
            ))

            self.assertIsNone(app.current_problem)
            app._select_job(first.job_id)
            self.assertEqual(app.current_problem.name, "first problem")
            self.assertEqual(app.selected_job_id, first.job_id)
            self.assertNotEqual(app.selected_job_id, second.job_id)
        finally:
            root.destroy()

    def test_benchmark_progress_shows_percentage(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        root.withdraw()
        try:
            app = SATApp(root)
            job = app._create_job("benchmark", "Benchmark job")

            app._handle_run_event(RunEvent(EVENT_PROGRESS, "Halfway", payload={"_job_id": job.job_id}, current=2, total=4))

            self.assertEqual(app.benchmark_jobs_table.set(job.job_id, "progress"), "2/4 (50%)")
            self.assertEqual(app.progress_percent.get(), "50%")
            self.assertEqual(float(app.progress_value.get()), 50.0)
        finally:
            root.destroy()

    def test_initial_benchmark_sash_uses_left_panel_width(self):
        app = SATApp.__new__(SATApp)
        calls = []

        class WorkspaceStub:
            def update_idletasks(self):
                pass

            def winfo_width(self):
                return 1200

            def panes(self):
                return ("left", "center", "detail")

            def sashpos(self, index, position):
                calls.append((index, position))

        app.benchmark_workspace = WorkspaceStub()
        app.benchmark_sash_initialized = False

        app._set_initial_benchmark_sash()

        self.assertEqual(calls, [(0, BENCHMARK_LEFT_PANEL_WIDTH), (1, 1200 - BENCHMARK_DETAIL_PANEL_WIDTH)])
        self.assertTrue(app.benchmark_sash_initialized)

    def test_initial_benchmark_sash_waits_for_visible_width(self):
        app = SATApp.__new__(SATApp)
        calls = []

        class HiddenWorkspaceStub:
            def update_idletasks(self):
                pass

            def winfo_width(self):
                return 1

            def sashpos(self, index, position):
                calls.append((index, position))

        app.benchmark_workspace = HiddenWorkspaceStub()
        app.benchmark_sash_initialized = False

        app._set_initial_benchmark_sash()

        self.assertEqual(calls, [])
        self.assertFalse(app.benchmark_sash_initialized)

    def test_cancel_selected_job_does_not_cancel_other_jobs(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        root.withdraw()
        try:
            app = SATApp(root)
            first = app._create_job("solve", "First solve")
            second = app._create_job("solve", "Second solve")
            first.token = RunToken()
            second.token = RunToken()

            app._select_job(first.job_id)
            app.cancel_active_run()

            self.assertTrue(first.token.is_cancelled())
            self.assertFalse(second.token.is_cancelled())
            self.assertEqual(first.status, "Cancelling...")
        finally:
            root.destroy()

    def test_job_selection_event_does_not_recurse(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        root.withdraw()
        try:
            app = SATApp(root)
            job = app._create_job("solve", "Selectable solve")
            app.updating_job_selection = True
            app._on_solve_job_selected()
            app.updating_job_selection = False

            self.assertEqual(app.selected_job_id, job.job_id)
            self.assertEqual(app.solve_jobs_table.selection(), (job.job_id,))
        finally:
            root.destroy()

    def test_combobox_mousewheel_scrolls_page_instead_of_value(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        root.withdraw()
        try:
            app = SATApp(root)
            calls = []
            canvas = app.solve_tab._tab_scroll_canvas
            original_yview_scroll = canvas.yview_scroll

            def fake_yview_scroll(amount, units):
                calls.append((amount, units))

            canvas.yview_scroll = fake_yview_scroll

            event = type("Event", (), {})()
            event.widget = app.solver_log_box
            event.delta = -120
            event.state = 0

            self.assertEqual(app._scroll_page_from_combobox(event), "break")
            self.assertEqual(calls, [(1, "units")])
            canvas.yview_scroll = original_yview_scroll
        finally:
            root.destroy()

    def test_per_tab_job_tables_separate_solve_and_benchmark_jobs(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        root.withdraw()
        try:
            app = SATApp(root)
            solve_job = app._create_job("solve", "Solve job")
            benchmark_job = app._create_job("benchmark", "Benchmark job")

            self.assertTrue(app.solve_jobs_table.exists(solve_job.job_id))
            self.assertFalse(app.solve_jobs_table.exists(benchmark_job.job_id))
            self.assertTrue(app.benchmark_jobs_table.exists(benchmark_job.job_id))
            self.assertFalse(app.benchmark_jobs_table.exists(solve_job.job_id))
        finally:
            root.destroy()

    def test_selecting_finished_solve_job_reloads_result_view(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        root.withdraw()
        try:
            app = SATApp(root)
            job = app._create_job("solve", "Finished solve")
            app._handle_run_event(RunEvent(
                EVENT_CNF,
                payload={
                    "_job_id": job.job_id,
                    "problem": {
                        "name": "tiny cnf",
                        "problem_type": "DIMACS",
                        "clauses": [[1]],
                        "metadata": {},
                    },
                    "dimacs": "p cnf 1 1\n1 0\n",
                },
            ))
            job.result = SolveResult("CDCL", "SAT", 0.01, {1: True}, clauses=1, variables=1)
            job.finished = True

            app.cnf_text.delete("1.0", tk.END)
            app._select_job(job.job_id)

            self.assertEqual(app.current_problem.name, "tiny cnf")
            self.assertIn("p cnf 1 1", app.cnf_text.get("1.0", tk.END))
            self.assertIn("Status: SAT", app.result_text.get("1.0", tk.END))
        finally:
            root.destroy()

    def test_parallel_benchmark_rows_are_appended_and_labeled(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        root.withdraw()
        try:
            app = SATApp(root)
            first = app._create_job("benchmark", "First benchmark")
            second = app._create_job("benchmark", "Second benchmark")
            first_row = BenchmarkRow("case one", "N-Queens", "CDCL", "SAT", 0.1, 1, 1, 1)
            second_row = BenchmarkRow("case two", "N-Queens", "WalkSAT", "UNKNOWN", 0.2, 1, 1, 1)

            app._handle_run_event(RunEvent(EVENT_ROW, payload={"_job_id": first.job_id, "row": first_row}, current=1, total=2))
            app._handle_run_event(RunEvent(EVENT_ROW, payload={"_job_id": second.job_id, "row": second_row}, current=1, total=2))

            self.assertEqual(len(app.benchmark_rows), 2)
            self.assertEqual(first_row.run_label, first.label)
            self.assertEqual(second_row.run_label, second.label)
            self.assertEqual(app.benchmark_table.set(app.benchmark_table.get_children()[0], "run"), first.label)
            self.assertEqual(app.benchmark_table.set(app.benchmark_table.get_children()[1], "run"), second.label)
            self.assertEqual(first_row.as_csv_row()[0], first.label)
        finally:
            root.destroy()

    def test_benchmark_run_filter_and_clear_actions(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        root.withdraw()
        try:
            app = SATApp(root)
            app.draw_benchmark_chart = lambda: None
            first = app._create_job("benchmark", "First benchmark")
            second = app._create_job("benchmark", "Second benchmark")
            first_row = BenchmarkRow("case one", "N-Queens", "CDCL", "SAT", 0.1, 1, 1, 1)
            second_row = BenchmarkRow("case two", "N-Queens", "WalkSAT", "UNKNOWN", 0.2, 1, 1, 1)

            app._handle_run_event(RunEvent(EVENT_ROW, payload={"_job_id": first.job_id, "row": first_row}, current=1, total=2))
            app._handle_run_event(RunEvent(EVENT_ROW, payload={"_job_id": second.job_id, "row": second_row}, current=1, total=2))

            app._select_job(first.job_id)
            app.show_selected_benchmark_run()
            self.assertEqual(app.benchmark_filter_run_label, first.label)
            self.assertEqual(len(app.benchmark_table.get_children()), 1)
            self.assertEqual(app._visible_benchmark_rows(), [first_row])
            self.assertIsNotNone(app.pending_benchmark_chart_after_id)
            app.root.after_cancel(app.pending_benchmark_chart_after_id)
            app.pending_benchmark_chart_after_id = None

            app.show_all_benchmark_runs()
            self.assertIsNone(app.benchmark_filter_run_label)
            self.assertEqual(len(app.benchmark_table.get_children()), 2)
            self.assertIsNotNone(app.pending_benchmark_chart_after_id)
            app.root.after_cancel(app.pending_benchmark_chart_after_id)
            app.pending_benchmark_chart_after_id = None

            app.benchmark_jobs_table.selection_set((first.job_id, second.job_id))
            app._on_benchmark_job_selected()
            app.show_selected_benchmark_run()
            self.assertEqual(app.benchmark_filter_run_label, (first.label, second.label))
            self.assertEqual(app._visible_benchmark_rows(), [first_row, second_row])
            if app.pending_benchmark_chart_after_id is not None:
                app.root.after_cancel(app.pending_benchmark_chart_after_id)
                app.pending_benchmark_chart_after_id = None

            app.clear_all_benchmark_results()
            self.assertEqual(app.benchmark_rows, [])
            self.assertIsNone(app.benchmark_filter_run_label)
            self.assertEqual(app._visible_benchmark_rows(), [])
            self.assertEqual(len(app.benchmark_table.get_children()), 0)
            self.assertEqual(app.benchmark_jobs_table.selection(), ())
            self.assertEqual(first.rows, [])
            self.assertEqual(second.rows, [])
            if app.pending_benchmark_chart_after_id is not None:
                app.root.after_cancel(app.pending_benchmark_chart_after_id)
                app.pending_benchmark_chart_after_id = None

            app.show_all_benchmark_runs()
            self.assertEqual(app.benchmark_rows, [])
            self.assertEqual(len(app.benchmark_table.get_children()), 0)
            if app.pending_benchmark_chart_after_id is not None:
                app.root.after_cancel(app.pending_benchmark_chart_after_id)
                app.pending_benchmark_chart_after_id = None
        finally:
            root.destroy()

    def test_show_selected_large_benchmark_run_defers_chart_refresh(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        root.withdraw()
        try:
            app = SATApp(root)
            draw_calls = []
            app.draw_benchmark_chart = lambda: draw_calls.append(True)
            job = app._create_job("benchmark", "Large benchmark")
            for index in range(BENCHMARK_AUTO_CHART_MAX_ROWS + 1):
                row = BenchmarkRow(
                    f"case {index}",
                    "N-Queens",
                    "CDCL",
                    "SAT",
                    0.1,
                    1,
                    1,
                    1,
                )
                app._handle_run_event(RunEvent(EVENT_ROW, payload={"_job_id": job.job_id, "row": row}, current=index + 1, total=BENCHMARK_AUTO_CHART_MAX_ROWS + 1))

            app.benchmark_jobs_table.selection_set((job.job_id,))
            app._on_benchmark_job_selected()
            app.show_selected_benchmark_run()

            self.assertEqual(draw_calls, [])
            self.assertIsNone(app.pending_benchmark_chart_after_id)
            self.assertIsNotNone(app.benchmark_chart_message)
            self.assertIn("chart refresh skipped", app.benchmark_status.get())
        finally:
            root.destroy()

    def test_large_cnf_preview_is_deferred_until_refresh(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        root.withdraw()
        try:
            app = SATApp(root)
            dimacs = "p cnf 1 1\n" + ("1 0\n" * ((CNF_AUTO_DISPLAY_MAX_CHARS // 4) + 10))

            app._set_cnf_preview(dimacs)

            preview_text = app.cnf_text.get("1.0", tk.END)
            self.assertIn("CNF preview skipped", preview_text)
            self.assertNotEqual(preview_text.strip(), dimacs.strip())
            self.assertEqual(app.current_cnf_dimacs, dimacs)

            app.refresh_cnf_preview()

            self.assertEqual(app.cnf_text.get("1.0", tk.END).strip(), dimacs.strip())
        finally:
            root.destroy()

    def test_solve_detail_row_reuses_large_clause_list(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        root.withdraw()
        try:
            app = SATApp(root)
            clauses = [[index, -index - 1] for index in range(2000)]
            app.current_problem = ProblemInstance(
                "large detail",
                "N-Queens",
                clauses,
                {"size": 80, "queens": 80},
            )

            row = app._solve_detail_row()

            self.assertIs(row.problem_clauses, clauses)
            self.assertEqual(row.detail, "n=80")
        finally:
            root.destroy()

    def test_export_benchmark_csv_uses_visible_rows(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        root.withdraw()
        original_dialog = app_module.filedialog.asksaveasfilename
        original_writer = app_module.write_benchmark_csv
        original_showinfo = app_module.messagebox.showinfo
        exported = {}
        try:
            app = SATApp(root)
            first = app._create_job("benchmark", "First benchmark")
            second = app._create_job("benchmark", "Second benchmark")
            first_row = BenchmarkRow("case one", "N-Queens", "CDCL", "SAT", 0.1, 1, 1, 1)
            second_row = BenchmarkRow("case two", "N-Queens", "WalkSAT", "UNKNOWN", 0.2, 1, 1, 1)
            app._handle_run_event(RunEvent(EVENT_ROW, payload={"_job_id": first.job_id, "row": first_row}, current=1, total=2))
            app._handle_run_event(RunEvent(EVENT_ROW, payload={"_job_id": second.job_id, "row": second_row}, current=1, total=2))
            app.benchmark_filter_run_label = first.label
            app._fill_benchmark_table()

            app_module.filedialog.asksaveasfilename = lambda **_kwargs: "visible.csv"
            app_module.write_benchmark_csv = lambda path, rows: exported.update(path=path, rows=list(rows))
            app_module.messagebox.showinfo = lambda *_args, **_kwargs: None

            app.export_benchmark_csv()

            self.assertEqual(exported["path"], "visible.csv")
            self.assertEqual(exported["rows"], [first_row])
        finally:
            app_module.filedialog.asksaveasfilename = original_dialog
            app_module.write_benchmark_csv = original_writer
            app_module.messagebox.showinfo = original_showinfo
            root.destroy()

    def test_export_random_3sat_csv_uses_visible_random_rows(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        root.withdraw()
        original_dialog = app_module.filedialog.asksaveasfilename
        original_writer = app_module.write_random_3sat_benchmark_csv
        original_showinfo = app_module.messagebox.showinfo
        exported = {}
        try:
            app = SATApp(root)
            job = app._create_job("benchmark", "Random benchmark")
            random_row = BenchmarkRow(
                "random case",
                "Random 3-SAT",
                "ProbSAT",
                "UNKNOWN",
                0.1,
                10,
                5,
                1,
            )
            graph_row = BenchmarkRow(
                "graph case",
                "Graph Coloring",
                "CDCL",
                "SAT",
                0.2,
                10,
                5,
                1,
            )
            app._handle_run_event(RunEvent(EVENT_ROW, payload={"_job_id": job.job_id, "row": random_row}, current=1, total=2))
            app._handle_run_event(RunEvent(EVENT_ROW, payload={"_job_id": job.job_id, "row": graph_row}, current=2, total=2))
            app.benchmark_filter_run_label = job.label
            app._fill_benchmark_table()

            app_module.filedialog.asksaveasfilename = lambda **_kwargs: "random-visible.csv"
            app_module.write_random_3sat_benchmark_csv = lambda path, rows: exported.update(path=path, rows=list(rows))
            app_module.messagebox.showinfo = lambda *_args, **_kwargs: None

            app.export_random_3sat_csv()

            self.assertEqual(exported["path"], "random-visible.csv")
            self.assertEqual(exported["rows"], [random_row])
        finally:
            app_module.filedialog.asksaveasfilename = original_dialog
            app_module.write_random_3sat_benchmark_csv = original_writer
            app_module.messagebox.showinfo = original_showinfo
            root.destroy()

    def test_clear_benchmark_table_clears_results_but_keeps_jobs(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        root.withdraw()
        try:
            app = SATApp(root)
            job = app._create_job("benchmark", "Benchmark job")
            row = BenchmarkRow("case one", "N-Queens", "CDCL", "SAT", 0.1, 1, 1, 1)
            app._handle_run_event(RunEvent(EVENT_ROW, payload={"_job_id": job.job_id, "row": row}, current=1, total=1))
            app.benchmark_filter_run_label = job.label
            app.benchmark_canvas = type("CanvasStub", (), {"get_tk_widget": lambda self: type("WidgetStub", (), {"destroy": lambda self: None})()})()
            app.benchmark_figure = object()

            app.clear_benchmark_table()

            self.assertEqual(app.benchmark_rows, [])
            self.assertTrue(app.benchmark_jobs_table.exists(job.job_id))
            self.assertIsNone(app.benchmark_filter_run_label)
            self.assertIsNone(app.benchmark_canvas)
            self.assertIsNone(app.benchmark_figure)
            self.assertEqual(len(app.benchmark_table.get_children()), 0)
            self.assertIn("Select a benchmark row", app.benchmark_detail_text.get("1.0", tk.END))
        finally:
            root.destroy()

    def test_delete_selected_solve_job_removes_only_that_job(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        root.withdraw()
        try:
            app = SATApp(root)
            first = app._create_job("solve", "First solve")
            second = app._create_job("solve", "Second solve")
            first.finished = True
            first.status = "Done"
            first.problem = ProblemInstance("first", "DIMACS", [[1]], {})
            first.dimacs = "p cnf 1 1\n1 0\n"
            second.finished = True
            second.status = "Done"

            app._select_job(first.job_id)
            app.delete_selected_solve_job()

            self.assertNotIn(first.job_id, app.jobs)
            self.assertIn(second.job_id, app.jobs)
            self.assertFalse(app.solve_jobs_table.exists(first.job_id))
            self.assertTrue(app.solve_jobs_table.exists(second.job_id))
            self.assertIsNone(app.selected_solve_job_id)
            self.assertIsNone(app.current_problem)
            self.assertIn("Generate or solve", app.result_text.get("1.0", tk.END))
        finally:
            root.destroy()

    def test_clear_finished_solve_jobs_removes_selected_view_data(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        root.withdraw()
        try:
            app = SATApp(root)
            job = app._create_job("solve", "Finished solve")
            job.finished = True
            job.status = "Done"
            job.problem = ProblemInstance("finished", "DIMACS", [[1]], {})
            job.dimacs = "p cnf 1 1\n1 0\n"
            app._display_solve_job(job)
            app._select_job(job.job_id)

            app.clear_finished_solve_jobs()

            self.assertNotIn(job.job_id, app.jobs)
            self.assertFalse(app.solve_jobs_table.exists(job.job_id))
            self.assertIsNone(app.current_problem)
            self.assertEqual(app.current_cnf_dimacs, "")
            self.assertNotIn("p cnf 1 1", app.cnf_text.get("1.0", tk.END))
            self.assertIn("Generate or solve", app.result_text.get("1.0", tk.END))
        finally:
            root.destroy()

    def test_delete_selected_benchmark_jobs_removes_their_rows_only(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        root.withdraw()
        try:
            app = SATApp(root)
            app.draw_benchmark_chart = lambda: None
            first = app._create_job("benchmark", "First benchmark")
            second = app._create_job("benchmark", "Second benchmark")
            first.finished = True
            first.status = "Done"
            second.finished = True
            second.status = "Done"
            first_row = BenchmarkRow("case one", "N-Queens", "CDCL", "SAT", 0.1, 1, 1, 1)
            second_row = BenchmarkRow("case two", "N-Queens", "WalkSAT", "UNKNOWN", 0.2, 1, 1, 1)

            app._handle_run_event(RunEvent(EVENT_ROW, payload={"_job_id": first.job_id, "row": first_row}, current=1, total=2))
            app._handle_run_event(RunEvent(EVENT_ROW, payload={"_job_id": second.job_id, "row": second_row}, current=1, total=2))
            app.benchmark_jobs_table.selection_set((first.job_id, second.job_id))
            app._on_benchmark_job_selected()
            app.benchmark_filter_run_label = (first.label, second.label)

            app.delete_selected_benchmark_job()

            self.assertNotIn(first.job_id, app.jobs)
            self.assertNotIn(second.job_id, app.jobs)
            self.assertFalse(app.benchmark_jobs_table.exists(first.job_id))
            self.assertFalse(app.benchmark_jobs_table.exists(second.job_id))
            self.assertEqual(app.benchmark_rows, [])
            self.assertIsNone(app.benchmark_filter_run_label)
            self.assertEqual(len(app.benchmark_table.get_children()), 0)

            if app.pending_benchmark_chart_after_id is not None:
                app.root.after_cancel(app.pending_benchmark_chart_after_id)
                app.pending_benchmark_chart_after_id = None
        finally:
            root.destroy()

    def test_clear_finished_benchmark_jobs_removes_inaccessible_rows(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        root.withdraw()
        try:
            app = SATApp(root)
            app.draw_benchmark_chart = lambda: None
            job = app._create_job("benchmark", "Finished benchmark")
            job.finished = True
            job.status = "Done"
            row = BenchmarkRow("case one", "N-Queens", "CDCL", "SAT", 0.1, 1, 1, 1)
            app._handle_run_event(RunEvent(EVENT_ROW, payload={"_job_id": job.job_id, "row": row}, current=1, total=1))

            app.clear_finished_benchmark_jobs()

            self.assertNotIn(job.job_id, app.jobs)
            self.assertFalse(app.benchmark_jobs_table.exists(job.job_id))
            self.assertEqual(app.benchmark_rows, [])
            self.assertEqual(len(app.benchmark_table.get_children()), 0)
            if app.pending_benchmark_chart_after_id is not None:
                app.root.after_cancel(app.pending_benchmark_chart_after_id)
                app.pending_benchmark_chart_after_id = None
        finally:
            root.destroy()

    def test_benchmark_row_selection_shows_details(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        root.withdraw()
        try:
            app = SATApp(root)
            row = BenchmarkRow(
                "Graph Coloring n3_p50_k2",
                "Graph Coloring",
                "CDCL",
                "SAT",
                0.01,
                8,
                6,
                1,
                conflicts=1,
                decisions=2,
                node_count=3,
                edge_count=2,
                graph_edges=[(1, 2), (2, 3)],
                decoded={1: 1, 2: 2, 3: 1},
                seed=4,
            )

            app._insert_benchmark_row(row)
            item = app.benchmark_table.get_children()[0]
            app.benchmark_table.selection_set(item)
            app._on_benchmark_row_selected()

            details = app.benchmark_detail_text.get("1.0", tk.END)
            edges = app.benchmark_edge_text.get("1.0", tk.END)
            self.assertIn("Status: SAT", details)
            self.assertIn("Conflicts: 1", details)
            self.assertIn("Decoded response:", details)
            self.assertIn("1-2, 2-3", edges)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
