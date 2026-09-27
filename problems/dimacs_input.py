"""
Raw CNF formulas in DIMACS format.

The formula is solved as-is; the answer is the truth assignment. Files that
were exported by this app carry a "c wizsat {...}" header, which the UI can
use to reopen the formula as the problem it was generated from.
"""

from __future__ import annotations

from typing import Any

from problems.assignment import assignment_bits
from problems.base import ProblemSpec, fact, register_problem
from sat_core.dimacs import DimacsError, parse_dimacs
from sat_core.models import ProblemInstance
from sat_core.params import ParamError, ParamField


EXAMPLE_CNF = """c A small example: (x1 or x2) and (not x1 or x2) and (not x2 or x3)
p cnf 3 3
1 2 0
-1 2 0
-2 3 0
"""


@register_problem
class DimacsInput(ProblemSpec):
    key = "dimacs"
    title = "DIMACS / CNF"
    summary = "Paste or upload any CNF formula in DIMACS format and solve it directly."
    description = (
        "Standard DIMACS: an optional 'p cnf <variables> <clauses>' header, then clauses as "
        "integers ending in 0. Comments start with 'c'. SATLIB files (ending in %) are accepted."
    )
    category = "cnf"
    image = None
    result_view = "assignment"
    fields = (
        ParamField(
            "cnf",
            "Formula",
            "cnf",
            default={"name": "example.cnf", "text": EXAMPLE_CNF},
            sweepable=True,
            help="Paste DIMACS text or drop .cnf files. In benchmarks, each file is one case.",
        ),
    )

    def parse_formula(self, params: dict[str, Any]):
        try:
            return parse_dimacs(params["cnf"]["text"])
        except DimacsError as exc:
            raise ParamError({"cnf": str(exc)}) from None

    def validate(self, params: dict[str, Any]) -> None:
        formula = self.parse_formula(params)
        if not formula.clauses:
            raise ParamError({"cnf": "the formula has no clauses"})

    def case_label(self, params: dict[str, Any]) -> str:
        return params["cnf"].get("name") or "DIMACS input"

    def instance_name(self, params: dict[str, Any]) -> str:
        return params["cnf"].get("name") or "DIMACS input"

    def estimate(self, params: dict[str, Any]) -> dict[str, int] | None:
        formula = self.parse_formula(params)
        return {"variables": formula.variables, "clauses": len(formula.clauses)}

    def encode(self, params: dict[str, Any]) -> ProblemInstance:
        formula = self.parse_formula(params)
        variables = formula.variables
        return ProblemInstance(
            name=self.instance_name(params),
            problem_type=self.key,
            clauses=formula.clauses,
            metadata={
                "variables": variables,
                "declared_clauses": formula.declared_clauses,
                "source": params["cnf"].get("name") or "",
                "warnings": formula.warnings,
                "app_header": formula.app_header,
            },
            decoder=lambda solution: assignment_bits(solution, variables),
        )

    def describe(self, instance: ProblemInstance) -> list[dict[str, Any]]:
        metadata = instance.metadata
        facts = [fact("Variables", metadata["variables"]), fact("Clauses", len(instance.clauses))]
        if metadata.get("source"):
            facts.insert(0, fact("File", metadata["source"]))
        for warning in metadata.get("warnings", [])[:3]:
            facts.append(fact("Warning", warning))
        return facts

    def visual(self, instance: ProblemInstance) -> dict[str, Any]:
        return {
            "variables": instance.metadata["variables"],
            "clauses": len(instance.clauses),
            "sample": instance.clauses[:12],
            "warnings": instance.metadata.get("warnings", []),
            "app_header": instance.metadata.get("app_header"),
        }

    def preview(self, params: dict[str, Any]) -> dict[str, Any] | None:
        formula = self.parse_formula(params)
        return {
            "variables": formula.variables,
            "clauses": len(formula.clauses),
            "sample": formula.clauses[:12],
            "warnings": formula.warnings,
            "app_header": formula.app_header,
        }
