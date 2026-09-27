import unittest

from sat_core.params import (
    Choice,
    ParamError,
    ParamField,
    check_field_order,
    expand_params,
    parse_edge_list,
    parse_number_list,
    parse_params,
    parse_sudoku_grid,
)


FIELDS = (
    ParamField("mode", "Mode", "choice", default="a", choices=(Choice("a", "A"), Choice("b", "B"))),
    ParamField("n", "N", "int", default=5, minimum=1, maximum=100, sweepable=True),
    ParamField("p", "P", "float", default=0.5, minimum=0, maximum=1, sweepable=True, show_if=(("mode", ("a",)),)),
    ParamField("seed", "Seed", "seed", default=None, optional=True, sweepable=True),
    ParamField("flag", "Flag", "bool", default=False),
)


class ParseParamsTests(unittest.TestCase):
    def test_defaults_and_coercion(self):
        params = parse_params(FIELDS, {"n": "7", "p": "0.25", "seed": "", "flag": "true"})

        self.assertEqual(params, {"mode": "a", "n": 7, "p": 0.25, "seed": None, "flag": True})

    def test_errors_are_collected_per_field(self):
        with self.assertRaises(ParamError) as context:
            parse_params(FIELDS, {"n": "0", "p": "x", "mode": "c", "extra": 1})

        self.assertEqual(set(context.exception.errors), {"extra"})
        with self.assertRaises(ParamError) as context:
            parse_params(FIELDS, {"n": "0", "p": "x", "mode": "c"})
        self.assertEqual(set(context.exception.errors), {"n", "mode", "p"})

    def test_hidden_fields_are_not_validated(self):
        params = parse_params(FIELDS, {"mode": "b", "p": "not a number"})

        self.assertEqual(params["p"], 0.5)

    def test_lists_need_sweep_mode(self):
        with self.assertRaises(ParamError):
            parse_params(FIELDS, {"n": [1, 2]})

    def test_whole_numbers(self):
        self.assertEqual(parse_params(FIELDS, {"n": 3.0})["n"], 3)
        with self.assertRaises(ParamError):
            parse_params(FIELDS, {"n": 2.5})
        with self.assertRaises(ParamError):
            parse_params(FIELDS, {"n": True})


class SweepTests(unittest.TestCase):
    def test_number_lists_and_ranges(self):
        self.assertEqual(parse_number_list("10, 20; 30", True), [10, 20, 30])
        self.assertEqual(parse_number_list("1..4", True), [1, 2, 3, 4])
        self.assertEqual(parse_number_list("1 .. 3, 10", True), [1, 2, 3, 10])
        self.assertEqual(parse_number_list("0.1..0.3:0.1", False), [0.1, 0.2, 0.3])
        with self.assertRaises(ValueError):
            parse_number_list("5..1", True)
        with self.assertRaises(ValueError):
            parse_number_list("1..3:0", True)

    def test_cartesian_product_in_field_order(self):
        cases = expand_params(FIELDS, {"n": "1,2", "p": [0.1, 0.9], "seed": "1..2"}, allow_sweep=True)

        self.assertEqual(len(cases), 8)
        self.assertEqual([(c["n"], c["p"], c["seed"]) for c in cases[:3]], [(1, 0.1, 1), (1, 0.1, 2), (1, 0.9, 1)])

    def test_visibility_is_evaluated_per_case(self):
        fields = (
            ParamField("mode", "Mode", "choice", default="a", choices=(Choice("a", "A"), Choice("b", "B")), sweepable=True),
            ParamField("p", "P", "float", default=0.5, sweepable=True, show_if=(("mode", ("a",)),)),
        )
        cases = expand_params(fields, {"mode": "a,b", "p": "0.1, 0.2"}, allow_sweep=True)

        self.assertEqual(cases, [{"mode": "a", "p": 0.1}, {"mode": "a", "p": 0.2}, {"mode": "b", "p": 0.5}])

    def test_non_sweepable_field_rejects_lists(self):
        with self.assertRaises(ParamError):
            expand_params(FIELDS, {"flag": [True, False]}, allow_sweep=True)

    def test_field_order_is_checked(self):
        with self.assertRaises(ValueError):
            check_field_order((ParamField("p", "P", "float", show_if=(("mode", ("a",)),)),))


class StructuredValueTests(unittest.TestCase):
    def test_edge_lists(self):
        self.assertEqual(parse_edge_list("1-2, 3 2\n2-1"), [(1, 2), (2, 3)])
        self.assertEqual(parse_edge_list([[4, 1], [1, 4]]), [(1, 4)])
        for bad in ("1-1", "0-2", "1-2-3", "a-b"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_edge_list(bad)

    def test_sudoku_grids(self):
        grid = parse_sudoku_grid("1..4 .4.. ..2. 3..1")
        self.assertEqual(grid[0], [1, 0, 0, 4])
        self.assertEqual(parse_sudoku_grid([[1, None, "", 0]] * 4)[0], [1, 0, 0, 0])
        with self.assertRaises(ValueError):
            parse_sudoku_grid([[1, 2, 3]] * 3)
        with self.assertRaises(ValueError):
            parse_sudoku_grid([[5, 0, 0, 0]] * 4)

    def test_field_to_dict_is_json_friendly(self):
        data = FIELDS[2].to_dict()

        self.assertEqual(data["show_if"], {"mode": ["a"]})
        self.assertTrue(data["sweepable"])


if __name__ == "__main__":
    unittest.main()
