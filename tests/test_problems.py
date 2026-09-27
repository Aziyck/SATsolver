import json
import unittest

from problems import all_problems, build_problem, get_problem
from problems.base import MAX_CLAUSES
from problems.graph import build_graph
from problems.sudoku import generated_puzzle, givens_conflicts, units
from sat_core.params import ParamError
from sat_core.solver_registry import run_solver
from sat_core.verify import check_assignment


def solve_and_decode(key, params=None, solver="cdcl"):
    spec = get_problem(key)
    instance = spec.build(spec.parse(params))
    result = run_solver(instance.clauses, solver)
    decoded = spec.decode(instance, result.solution) if result.solution else None
    return spec, instance, result, decoded


class RegistryTests(unittest.TestCase):
    def test_registry_order_and_catalog_is_json(self):
        keys = [spec.key for spec in all_problems()]

        self.assertEqual(
            keys,
            ["sudoku", "n_queens", "graph_coloring", "hamiltonian_path", "independent_set", "clique", "random_3sat", "dimacs"],
        )
        json.dumps([spec.to_dict() for spec in all_problems()])
        with self.assertRaises(ValueError):
            get_problem("chess")

    def test_every_problem_builds_solves_and_verifies_with_defaults(self):
        for spec in all_problems():
            with self.subTest(problem=spec.key):
                instance = spec.build(spec.parse({}))
                result = run_solver(instance.clauses, "cdcl")
                self.assertIn(result.status, ("SAT", "UNSAT"))
                json.dumps(spec.describe(instance))
                json.dumps(spec.visual(instance))
                if result.status == "SAT":
                    self.assertTrue(check_assignment(instance.clauses, result.solution))
                    decoded = spec.decode(instance, result.solution)
                    json.dumps(decoded)
                    self.assertEqual(spec.check(instance, decoded), [])

    def test_estimates_match_deterministic_instances(self):
        cases = [
            ("sudoku", {}),
            ("sudoku", {"source": "generated", "size": 4, "givens": 50}),
            ("n_queens", {"size": 6}),
            ("graph_coloring", {"graph_mode": "gnm", "nodes": 12, "edge_count": 20, "colors": 4}),
            ("hamiltonian_path", {"graph_mode": "gnm", "nodes": 7, "edge_count": 10}),
            ("independent_set", {"graph_mode": "gnm", "nodes": 9, "edge_count": 12, "target": 3}),
            ("clique", {"graph_mode": "gnm", "nodes": 9, "edge_count": 12, "target": 3}),
            ("random_3sat", {"variables": 40, "ratio": 4.0}),
        ]
        for key, params in cases:
            with self.subTest(problem=key):
                spec = get_problem(key)
                parsed = spec.parse(params)
                instance = spec.build(parsed)
                self.assertEqual(spec.estimate(parsed)["clauses"], instance.clause_count)

    def test_oversized_instances_are_refused_before_encoding(self):
        spec = get_problem("hamiltonian_path")
        params = spec.parse({"graph_mode": "gnp", "nodes": 400, "probability": 0.01})

        self.assertGreater(spec.estimate(params)["clauses"], MAX_CLAUSES)
        with self.assertRaises(ParamError):
            spec.build(params)


class GraphTests(unittest.TestCase):
    def test_same_parameters_and_seed_give_the_same_graph(self):
        spec = get_problem("graph_coloring")
        params = spec.parse({"graph_mode": "gnp", "nodes": 30, "probability": 0.2, "seed": 7})

        self.assertEqual(build_graph(params).edges, build_graph(dict(params)).edges)
        other = build_graph({**params, "seed": 8}).edges
        self.assertNotEqual(build_graph(params).edges, other)

    def test_problem_specific_fields_do_not_change_the_graph(self):
        graph_params = {"graph_mode": "gnm", "nodes": 15, "edge_count": 30, "seed": 3}
        coloring = build_problem("graph_coloring", {**graph_params, "colors": 3})
        clique = build_problem("clique", {**graph_params, "target": 4})

        self.assertEqual(coloring.metadata["graph_edges"], clique.metadata["graph_edges"])

    def test_edge_count_modes(self):
        spec = get_problem("independent_set")
        gnm = build_graph(spec.parse({"graph_mode": "gnm", "nodes": 6, "edge_count": 100, "target": 1}))
        gnd = build_graph(spec.parse({"graph_mode": "gnd", "nodes": 10, "average_degree": 3, "target": 1}))

        self.assertEqual(len(gnm.edges), 15)
        self.assertTrue(gnm.meta["edge_request_clamped"])
        self.assertEqual(len(gnd.edges), 15)
        self.assertEqual(len(set(gnd.edges)), 15)
        self.assertTrue(all(1 <= u < v <= 10 for u, v in gnd.edges))

    def test_blank_seed_is_resolved_and_recorded(self):
        instance = build_problem("graph_coloring", {"seed": None})

        self.assertIsInstance(instance.params["seed"], int)
        self.assertEqual(instance.metadata["seed"], instance.params["seed"])

    def test_manual_edges_must_fit_the_node_count(self):
        with self.assertRaises(ParamError) as context:
            get_problem("clique").parse({"graph_mode": "manual", "nodes": 3, "edges": "1-2, 2-5", "target": 2})
        self.assertIn("edges", context.exception.errors)

    def test_target_must_fit_the_graph(self):
        with self.assertRaises(ParamError):
            get_problem("clique").parse({"nodes": 3, "target": 4})

    def test_graph_answers_are_checked(self):
        triangle = {"graph_mode": "manual", "nodes": 3, "edges": "1-2, 2-3, 1-3"}
        _spec, _instance, result, decoded = solve_and_decode("graph_coloring", {**triangle, "colors": 2})
        self.assertEqual(result.status, "UNSAT")

        spec, instance, result, decoded = solve_and_decode("graph_coloring", {**triangle, "colors": 3})
        self.assertEqual(sorted(decoded["coloring"]), [1, 2, 3])
        self.assertTrue(spec.check(instance, {"coloring": [1, 1, 2], "colors_used": 2}))

        spec, instance, result, decoded = solve_and_decode("clique", {**triangle, "target": 3})
        self.assertEqual(decoded["selected"], [1, 2, 3])

        spec, instance, result, decoded = solve_and_decode("independent_set", {**triangle, "target": 1})
        self.assertEqual(len(decoded["selected"]), 1)
        self.assertEqual(solve_and_decode("independent_set", {**triangle, "target": 2})[2].status, "UNSAT")

        spec, instance, result, decoded = solve_and_decode("hamiltonian_path", {"graph_mode": "manual", "nodes": 4, "edges": "1-2, 2-3, 3-4"})
        self.assertIn(decoded["path"], ([1, 2, 3, 4], [4, 3, 2, 1]))
        self.assertTrue(spec.check(instance, {"path": [1, 3, 2, 4]}))


class PuzzleTests(unittest.TestCase):
    def test_generated_sudoku_is_a_valid_partial_solution(self):
        for size in (4, 9, 16, 25):
            with self.subTest(size=size):
                puzzle, solution = generated_puzzle(size, 40, seed=5)
                for _unit, _number, cells in units(size):
                    self.assertEqual(sorted(solution[r][c] for r, c in cells), list(range(1, size + 1)))
                givens = sum(1 for row in puzzle for value in row if value)
                self.assertEqual(givens, round(size * size * 0.4))
                self.assertEqual(givens_conflicts(puzzle), [])

    def test_generated_sudoku_is_expected_sat_and_solves(self):
        spec, instance, result, decoded = solve_and_decode("sudoku", {"source": "generated", "size": 9, "givens": 35, "seed": 2})

        self.assertEqual(spec.expected_status(instance), "SAT")
        self.assertEqual(result.status, "SAT")
        self.assertEqual(spec.check(instance, decoded), [])

    def test_contradictory_sudoku_is_expected_unsat(self):
        grid = [[1, 1, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
        spec, instance, result, _decoded = solve_and_decode("sudoku", {"size": 4, "grid": grid})

        self.assertEqual(spec.expected_status(instance), "UNSAT")
        self.assertEqual(result.status, "UNSAT")

    def test_sudoku_grid_must_match_size(self):
        with self.assertRaises(ParamError):
            get_problem("sudoku").parse({"size": 4})

    def test_n_queens_expectations(self):
        for size, expected in ((1, "SAT"), (3, "UNSAT"), (6, "SAT")):
            with self.subTest(size=size):
                spec, instance, result, decoded = solve_and_decode("n_queens", {"size": size})
                self.assertEqual(spec.expected_status(instance), expected)
                self.assertEqual(result.status, expected)
                if decoded:
                    self.assertEqual(len(decoded["queens"]), size)
                    self.assertEqual(spec.check(instance, decoded), [])


class Random3SatTests(unittest.TestCase):
    def test_planted_and_forced_modes(self):
        spec, instance, result, decoded = solve_and_decode("random_3sat", {"variables": 30, "ratio": 5, "mode": "planted", "seed": 4})
        self.assertEqual(spec.expected_status(instance), "SAT")
        self.assertEqual(result.status, "SAT")
        self.assertEqual(len(decoded["bits"]), 30)

        spec, instance, result, _decoded = solve_and_decode("random_3sat", {"variables": 30, "ratio": 2, "mode": "forced_unsat", "seed": 4})
        self.assertEqual(spec.expected_status(instance), "UNSAT")
        self.assertEqual(result.status, "UNSAT")

    def test_clause_shape_and_determinism(self):
        first = build_problem("random_3sat", {"variables": 20, "ratio": 4.26, "mode": "random", "seed": 9})
        second = build_problem("random_3sat", {"variables": 20, "ratio": 4.26, "mode": "random", "seed": 9})

        self.assertEqual(first.clauses, second.clauses)
        self.assertEqual(len(first.clauses), round(20 * 4.26))
        self.assertTrue(all(len({abs(lit) for lit in clause}) == 3 for clause in first.clauses))

    def test_mixed_mode_uses_sat_share(self):
        selected = [
            build_problem("random_3sat", {"variables": 20, "ratio": 4, "mode": "mixed", "sat_percent": 70, "seed": seed}).metadata["selected_mode"]
            for seed in range(1, 201)
        ]
        share = selected.count("planted") / len(selected)

        self.assertGreater(share, 0.55)
        self.assertLess(share, 0.85)
        self.assertTrue(all(build_problem("random_3sat", {"variables": 20, "ratio": 4, "mode": "mixed", "sat_percent": 100, "seed": s}).metadata["selected_mode"] == "planted" for s in range(1, 10)))

    def test_forced_unsat_needs_eight_clauses(self):
        with self.assertRaises(ParamError):
            get_problem("random_3sat").parse({"variables": 3, "ratio": 2, "mode": "forced_unsat"})


class DimacsInputTests(unittest.TestCase):
    def test_parse_errors_point_to_the_field(self):
        with self.assertRaises(ParamError) as context:
            get_problem("dimacs").parse({"cnf": "p cnf 2 1\n1 two 0\n"})
        self.assertIn("line 2", context.exception.errors["cnf"])

    def test_assignment_uses_declared_variables(self):
        spec, instance, result, decoded = solve_and_decode("dimacs", {"cnf": {"name": "f.cnf", "text": "p cnf 5 1\n1 -2 0\n"}})

        self.assertEqual(instance.name, "f.cnf")
        self.assertEqual(decoded["variables"], 5)
        self.assertEqual(len(decoded["bits"]), 5)


if __name__ == "__main__":
    unittest.main()
