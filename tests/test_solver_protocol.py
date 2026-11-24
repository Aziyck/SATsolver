"""
The child protocol's message shapes and the parser, without a process.

sat_core.solver_protocol holds what the child writes (log_message,
result_message) and what the parent accepts (parse_line). The same broken
lines go through a real child too, three of them (not JSON, a model with
an UNSAT status, a deeply nested line), in tests/test_solver_process.py.
"""

import json
import unittest

from sat_core.solver_protocol import RESULT_FIELDS, BrokenLine, log_message, parse_line, result_message, stopped_result


def result_line(**fields):
    """A result line as the child writes it, with some fields replaced."""

    line = {"type": "result", "status": "SAT", "solution": {"1": True}, "stats": {}, "error": None, "elapsed": 0.01}
    line.update(fields)
    return json.dumps(line)


class ParseLineTests(unittest.TestCase):
    def test_a_log_line_is_returned_as_it_came(self):
        line = json.dumps({"type": "log", "message": "started"})

        self.assertEqual(parse_line(line), {"type": "log", "message": "started"})

    def test_a_good_result_line_is_accepted_and_the_model_gets_int_keys(self):
        message = parse_line(result_line(solution={"1": True, "12": False}, stats={"conflicts": 3, "name": "x", "ok": None}))

        self.assertEqual(message["type"], "result")
        self.assertEqual(message["status"], "SAT")
        self.assertEqual(message["solution"], {1: True, 12: False})
        self.assertEqual(message["stats"], {"conflicts": 3, "name": "x", "ok": None})

    def test_a_result_without_a_model_keeps_none(self):
        self.assertIsNone(parse_line(result_line(status="UNSAT", solution=None))["solution"])

    def test_a_killed_field_from_the_child_is_dropped(self):
        # Only the parent marks a run as killed; a child must not fake it.
        self.assertNotIn("killed", parse_line(result_line(killed="token")))

    def test_every_broken_line_is_rejected(self):
        broken_lines = {
            "not JSON": "not json at all",
            "an empty line": "",
            "JSON that is not an object": "[1, 2]",
            "an unknown type": json.dumps({"type": "progress"}),
            "no type": json.dumps({"message": "hi"}),
            "a log line without its message": json.dumps({"type": "log"}),
            "a log message that is not a string": json.dumps({"type": "log", "message": 5}),
            "a result without its fields": json.dumps({"type": "result", "status": "SAT"}),
            "a result with an unknown status": result_line(status="MAYBE", solution=None),
            "a model with a variable that is not a number": result_line(solution={"x": True}),
            "a model with variable 0": result_line(solution={"0": True}),
            "a model with a negative variable": result_line(solution={"-1": True}),
            "a model with a value that is not a boolean": result_line(solution={"1": "yes"}),
            "a model that is not an object": result_line(solution=[1]),
            "a model with an UNSAT status": result_line(status="UNSAT", solution={"1": True}),
            "an elapsed time that is NaN": result_line(elapsed=float("nan")),
            "an elapsed time that is infinite": result_line(elapsed=float("inf")),
            "an elapsed time that is a boolean": result_line(elapsed=True),
            "an elapsed time that is a string": result_line(elapsed="0.1"),
            "an error that is not a string": result_line(error={"x": 1}),
            "stats that are not an object": result_line(stats=[1]),
            "a statistic that is not a scalar": result_line(stats={"conflicts": [1, 2]}),
            "a statistic that is NaN": result_line(stats={"conflicts": float("nan")}),
            "a line nested too deeply": "[" * 100000 + "]" * 100000,
        }
        for name, line in broken_lines.items():
            with self.subTest(name):
                with self.assertRaises(BrokenLine) as caught:
                    parse_line(line)
                self.assertEqual(caught.exception.line, line)

    def test_each_result_field_is_required(self):
        for field in RESULT_FIELDS:
            with self.subTest(field):
                line = json.loads(result_line())
                del line[field]
                with self.assertRaises(BrokenLine):
                    parse_line(json.dumps(line))


class MessageShapeTests(unittest.TestCase):
    def test_what_the_child_writes_is_what_the_parser_accepts(self):
        self.assertEqual(parse_line(json.dumps(log_message("hello")))["message"], "hello")
        written = result_message("SAT", {3: True, 4: False}, {"conflicts": 2}, None, 0.5)

        parsed = parse_line(json.dumps(written))

        self.assertEqual(parsed["solution"], {3: True, 4: False})
        self.assertEqual((parsed["status"], parsed["stats"], parsed["error"], parsed["elapsed"]), ("SAT", {"conflicts": 2}, None, 0.5))

    def test_a_result_message_has_exactly_the_protocol_fields(self):
        written = result_message("UNSAT", None, {}, None, 0.1)

        self.assertEqual(written["type"], "result")
        self.assertEqual(set(written) - {"type"}, set(RESULT_FIELDS))

    def test_a_stopped_result_has_no_model_or_stats_and_says_who_killed(self):
        made = stopped_result("CANCELLED", 1.5, "token")

        self.assertEqual(made["status"], "CANCELLED")
        self.assertIsNone(made["solution"])
        self.assertEqual(made["stats"], {})
        self.assertIsNone(made["error"])
        self.assertEqual((made["elapsed"], made["killed"]), (1.5, "token"))


if __name__ == "__main__":
    unittest.main()
