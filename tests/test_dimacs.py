import tempfile
import unittest
from pathlib import Path

from sat_core.dimacs import (
    DimacsError,
    app_header_comment,
    clauses_to_dimacs,
    load_dimacs,
    parse_dimacs,
    save_dimacs,
)


class DimacsParserTests(unittest.TestCase):
    def test_several_clauses_on_one_line(self):
        self.assertEqual(parse_dimacs("p cnf 3 2\n1 -2 0 3 0\n").clauses, [[1, -2], [3]])

    def test_clause_split_over_lines(self):
        self.assertEqual(parse_dimacs("p cnf 3 1\n1 -2\n3 0\n").clauses, [[1, -2, 3]])

    def test_satlib_end_marker(self):
        formula = parse_dimacs("c uf\np cnf 2 1\n1 2 0\n%\n0\n")

        self.assertEqual(formula.clauses, [[1, 2]])
        self.assertEqual(formula.warnings, [])

    def test_plain_clause_list_without_header(self):
        formula = parse_dimacs("1 2 0\n-1 0\n")

        self.assertEqual(formula.clauses, [[1, 2], [-1]])
        self.assertEqual(formula.variables, 2)

    def test_warnings_for_inconsistent_header_and_missing_terminator(self):
        formula = parse_dimacs("p cnf 2 3\n1 2 0\n-3\n")

        self.assertEqual(formula.clauses, [[1, 2], [-3]])
        self.assertEqual(formula.variables, 2)
        self.assertEqual(len(formula.warnings), 3)

    def test_empty_clause_is_kept(self):
        formula = parse_dimacs("p cnf 1 2\n1 0\n0\n")

        self.assertEqual(formula.clauses, [[1], []])
        self.assertTrue(any("empty clause" in warning for warning in formula.warnings))

    def test_errors_carry_line_numbers(self):
        with self.assertRaises(DimacsError) as context:
            parse_dimacs("p cnf 2 1\n1 x 0\n")
        self.assertEqual(context.exception.line, 2)
        for bad in ("p cnf 2\n", "p dnf 2 1\n", "p cnf 1 1\np cnf 1 1\n"):
            with self.subTest(bad=bad), self.assertRaises(DimacsError):
                parse_dimacs(bad)

    def test_app_header_round_trip(self):
        text = clauses_to_dimacs([[1, -2]], ["demo", app_header_comment("n_queens", {"size": 4})])
        formula = parse_dimacs(text)

        self.assertEqual(formula.app_header, {"problem": "n_queens", "params": {"size": 4}})
        self.assertEqual(formula.clauses, [[1, -2]])

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "nested" / "f.cnf"
            save_dimacs(path, [[1, 2], [-2]], ["multi\nline comment"])

            self.assertEqual(load_dimacs(path), [[1, 2], [-2]])
            self.assertTrue(path.read_text().startswith("c multi\nc line comment\np cnf 2 2\n"))

    def test_example_files_load(self):
        self.assertEqual(len(load_dimacs("input/examples/sudoku_4x4.cnf")) > 0, True)
        self.assertEqual(len(load_dimacs("input/examples/graph_coloring/gc_n10_p10_k2.cnf")) > 0, True)


if __name__ == "__main__":
    unittest.main()
