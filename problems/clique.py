"""
Clique of size k.

Same slot encoding as Independent Set, with the edge rule reversed: two
nodes that are not adjacent can never both be chosen.
"""

from __future__ import annotations

from typing import Any

from problems.base import fact, register_problem
from problems.encoding import comb2
from problems.graph import Graph, GraphProblemSpec, expected_edges, graph_fields
from problems.independent_set import TARGET_FIELD, decode_selection, slot_clauses, slot_var, validate_target
from sat_core.models import ProblemInstance


@register_problem
class Clique(GraphProblemSpec):
    key = "clique"
    title = "Clique"
    summary = "Choose k nodes that are all connected to each other."
    description = (
        "Variables x(s,v) mean slot s of the clique holds node v. Each of the k slots holds "
        "exactly one node, no node fills two slots, and two nodes without an edge between them "
        "are never both chosen."
    )
    image = "clique.jpg"
    fields = graph_fields(default_mode="gnp") + (TARGET_FIELD,)

    def validate(self, params: dict[str, Any]) -> None:
        validate_target(params)

    def estimate(self, params: dict[str, Any]) -> dict[str, int]:
        n, k = params["nodes"], params["target"]
        non_edges = comb2(n) - expected_edges(params)
        clauses = k + k * comb2(n) + n * comb2(k) + non_edges * k * (k - 1)
        return {"variables": n * k, "clauses": int(clauses)}

    def encode_graph(self, graph: Graph, params: dict[str, Any]) -> ProblemInstance:
        nodes, target = graph.nodes, params["target"]
        adjacency = graph.adjacency()
        clauses = slot_clauses(nodes, target)
        for u in range(1, nodes + 1):
            for v in range(u + 1, nodes + 1):
                if v in adjacency[u]:
                    continue
                for first in range(1, target + 1):
                    for second in range(1, target + 1):
                        if first != second:
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
        adjacency = self.graph_of(instance).adjacency()
        for index, u in enumerate(selected):
            for v in selected[index + 1:]:
                if v not in adjacency[u]:
                    errors.append(f"nodes {u} and {v} are not adjacent")
        return errors

    def describe(self, instance: ProblemInstance) -> list[dict[str, Any]]:
        return [fact("Target k", instance.metadata["target"])] + super().describe(instance)
