"""
Graph k-coloring.

Variable x(v, c) = "node v has color c", numbered color_var(v, c, k).

Clauses:
- every node has at least one color:        x(v,1) or ... or x(v,k)
- every node has at most one color:         not x(v,a) or not x(v,b)
- adjacent nodes never share a color:       not x(u,c) or not x(v,c)
"""

from __future__ import annotations

from typing import Any

from problems.base import fact, register_problem
from problems.encoding import color_var, comb2
from problems.graph import Graph, GraphProblemSpec, expected_edges, graph_fields
from sat_core.models import ProblemInstance
from sat_core.params import ParamField


def coloring_clauses(graph: Graph, colors: int) -> list[list[int]]:
    clauses = []
    for node in range(1, graph.nodes + 1):
        clauses.append([color_var(node, color, colors) for color in range(1, colors + 1)])
    for node in range(1, graph.nodes + 1):
        for first in range(1, colors + 1):
            for second in range(first + 1, colors + 1):
                clauses.append([-color_var(node, first, colors), -color_var(node, second, colors)])
    for u, v in graph.edges:
        for color in range(1, colors + 1):
            clauses.append([-color_var(u, color, colors), -color_var(v, color, colors)])
    return clauses


def decode_coloring(solution: dict[int, bool], nodes: int, colors: int) -> dict[str, Any]:
    coloring = []
    for node in range(1, nodes + 1):
        chosen = 0
        for color in range(1, colors + 1):
            if solution.get(color_var(node, color, colors)):
                chosen = color
                break
        coloring.append(chosen)
    return {"coloring": coloring, "colors_used": len({color for color in coloring if color})}


@register_problem
class GraphColoring(GraphProblemSpec):
    key = "graph_coloring"
    title = "Graph Coloring"
    summary = "Color every node with one of k colors so that adjacent nodes differ."
    description = (
        "Variables x(v,c) mean node v has color c. Each node gets at least one and at most one "
        "color, and the two ends of every edge get different colors. SAT means the graph is "
        "k-colorable."
    )
    image = "graph_coloring.jpg"
    fields = graph_fields() + (
        ParamField("colors", "Colors k", "int", default=3, minimum=1, maximum=64, sweepable=True, short="k"),
    )

    def estimate(self, params: dict[str, Any]) -> dict[str, int]:
        nodes, colors = params["nodes"], params["colors"]
        clauses = nodes + nodes * comb2(colors) + expected_edges(params) * colors
        return {"variables": nodes * colors, "clauses": int(clauses)}

    def encode_graph(self, graph: Graph, params: dict[str, Any]) -> ProblemInstance:
        colors = params["colors"]
        nodes = graph.nodes
        return ProblemInstance(
            name=self.title,
            problem_type=self.key,
            clauses=coloring_clauses(graph, colors),
            metadata={"colors": colors},
            decoder=lambda solution: decode_coloring(solution, nodes, colors),
        )

    def check(self, instance: ProblemInstance, decoded: Any) -> list[str]:
        coloring = decoded["coloring"]
        errors = [f"node {index} has no color" for index, color in enumerate(coloring, start=1) if not color]
        for u, v in self.graph_of(instance).edges:
            if coloring[u - 1] and coloring[u - 1] == coloring[v - 1]:
                errors.append(f"edge {u}-{v} joins two nodes of color {coloring[u - 1]}")
        return errors

    def describe(self, instance: ProblemInstance) -> list[dict[str, Any]]:
        return [fact("Colors k", instance.metadata["colors"])] + super().describe(instance)
