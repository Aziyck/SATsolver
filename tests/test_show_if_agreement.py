"""
show_if is evaluated on the server (ParamField.visible, expand_params) and
twice in the frontend (isVisible, isVisibleSweep). The cases in
tests/fixtures/show_if_cases.json are run by this file and by
frontend/src/lib/visibility.test.ts, so the two sides cannot drift apart.
"""

import json
import unittest
from pathlib import Path

from problems import all_problems
from sat_core.params import Choice, ParamField, expand_params
from sat_core.solver_registry import all_solvers

SHARED = json.loads((Path(__file__).parent / "fixtures" / "show_if_cases.json").read_text(encoding="utf-8"))


def field_from_json(data: dict) -> ParamField:
    return ParamField(
        data["name"],
        data["name"],
        data["kind"],
        default=data.get("default"),
        choices=tuple(Choice(choice["value"], choice["label"]) for choice in data.get("choices", [])),
        optional=data.get("optional", False),
        sweepable=data.get("sweepable", False),
        show_if=tuple((other, tuple(allowed)) for other, allowed in data.get("show_if", {}).items()),
    )


FIELDS = tuple(field_from_json(data) for data in SHARED["fields"])


class ShowIfAgreementTests(unittest.TestCase):
    def test_fixture_fields_survive_the_catalog_format(self):
        # The frontend receives show_if as to_dict() writes it; the fixture must be in that shape.
        for data, field in zip(SHARED["fields"], FIELDS):
            self.assertEqual(field.to_dict()["show_if"], data.get("show_if", {}), data["name"])

    def test_single_values(self):
        for case in SHARED["single"]:
            with self.subTest(case["name"]):
                visible = [field.name for field in FIELDS if field.visible(case["values"])]
                self.assertEqual(visible, case["visible"])

    def test_sweeps(self):
        # A field counts as visible in a sweep when at least one expanded case shows it.
        for case in SHARED["sweep"]:
            with self.subTest(case["name"]):
                expanded = expand_params(FIELDS, case["values"], allow_sweep=True)
                visible = [field.name for field in FIELDS if any(field.visible(values) for values in expanded)]
                self.assertEqual(visible, case["visible"])

    def test_no_registered_field_depends_on_a_conditional_field(self):
        # The two sides agree only for direct conditions (audit item A21): the server gives a
        # hidden field its default, the frontend keeps reading the value the form still holds.
        chains = []
        for owner in [*all_problems(), *all_solvers()]:
            by_name = {field.name: field for field in owner.fields}
            for field in owner.fields:
                chains.extend(f"{owner.key}.{field.name} -> {other}" for other, _allowed in field.show_if if by_name[other].show_if)
        self.assertEqual(chains, [])


if __name__ == "__main__":
    unittest.main()
