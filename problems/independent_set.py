"""
Independent set of size k.

Variable x(s, v) = "slot s of the set holds node v", numbered
readable_pair_var(s, v, n). Using k slots turns "at least k nodes" into
"exactly k distinct nodes", which is equivalent for this decision problem.

Clauses:
- each slot holds exactly one node;
- a node fills at most one slot;
- the two ends of an edge are never both chosen.
"""

from __future__ import annotations

from typing import Any

from problems.base import fact, register_problem
from problems.encoding import comb2, readable_pair_var
from problems.graph import Graph, GraphProblemSpec, expected_edges, graph_fields, validate_graph_params
from sat_core.models import ProblemInstance
from sat_core.params import ParamError, ParamField


TARGET_FIELD = ParamField(
    "target",
    "Target size k",
    "int",
    default=3,
    minimum=1,
    maximum=500,
    sweepable=True,
    short="k",
)


def slot_var(slot: int, node: int, nodes: int) -> int:
    return readable_pair_var(slot, node, nodes)


def slot_clauses(nodes: int, target: int) -> list[list[int]]:
    """k slots, each with exactly one node, and no node in two slots."""

    clauses = []
    for slot in range(1, target + 1):
        clauses.append([slot_var(slot, node, nodes) for node in range(1, nodes + 1)])
        for first in range(1, nodes + 1):
            for second in range(first + 1, nodes + 1):
                clauses.append([-slot_var(slot, first, nodes), -slot_var(slot, second, nodes)])
    for node in range(1, nodes + 1):
        for first in range(1, target + 1):
            for second in range(first + 1, target + 1):
                clauses.append([-slot_var(first, node, nodes), -slot_var(second, node, nodes)])
    return clauses


def decode_selection(solution: dict[int, bool], nodes: int, target: int) -> dict[str, Any]:
    selected = []
    for slot in range(1, target + 1):
        for node in range(1, nodes + 1):
            if solution.get(slot_var(slot, node, nodes)):
                selected.append(node)
                break
    return {"selected": sorted(selected)}


def validate_target(params: dict[str, Any]) -> None:
    validate_graph_params(params)
    if params["target"] > params["nodes"]:
        raise ParamError({"target": f"k must be between 1 and the number of nodes ({params['nodes']})"})


@register_problem
class IndependentSet(GraphProblemSpec):
    key = "independent_set"
    title = "Independent Set"
    summary = "Choose k nodes with no edge between any two of them."
    description = (
        "Variables x(s,v) mean slot s of the set holds node v. Each of the k slots holds exactly "
        "one node, no node fills two slots, and the ends of an edge are never both chosen."
    )
    image = "independent_set.jpg"
    fields = graph_fields() + (TARGET_FIELD,)

    def validate(self, params: dict[str, Any]) -> None:
        validate_target(params)

    def estimate(self, params: dict[str, Any]) -> dict[str, int]:
        n, k = params["nodes"], params["target"]
        clauses = k + k * comb2(n) + n * comb2(k) + expected_edges(params) * k * k
        return {"variables": n * k, "clauses": int(clauses)}

    def encode_graph(self, graph: Graph, params: dict[str, Any]) -> ProblemInstance:
        nodes, target = graph.nodes, params["target"]
        clauses = slot_clauses(nodes, target)
        for u, v in graph.edges:
            for first in range(1, target + 1):
                for second in range(1, target + 1):
                    clauses.append([-slot_var(first, u, nodes), -slot_var(second, v, nodes)])
        return ProblemInstance(
            name=self.title,
            problem_type=self.key,
            clauses=clauses,
            metadata={"target": target},
            decoder=lambda solution: decode_selection(solution, nodes, target),
        )

    def check(self, instance: ProblemInstance, decoded: Any) -> list[str]:
        selected = decoded["selected"]
        errors = []
        if len(set(selected)) != instance.metadata["target"]:
            errors.append(f"expected {instance.metadata['target']} distinct nodes, got {len(set(selected))}")
        chosen = set(selected)
        for u, v in self.graph_of(instance).edges:
            if u in chosen and v in chosen:
                errors.append(f"nodes {u} and {v} are adjacent")
        return errors

    def describe(self, instance: ProblemInstance) -> list[dict[str, Any]]:
        return [fact("Target k", instance.metadata["target"])] + super().describe(instance)
