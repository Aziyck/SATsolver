"""
Hamiltonian path in an undirected graph.

Variable x(i, v) = "position i of the path is node v", numbered
readable_pair_var(i, v, n).

Clauses:
- each position holds exactly one node;
- each node appears at exactly one position;
- consecutive positions hold adjacent nodes: for every non-edge (u, v),
  not x(i,u) or not x(i+1,v).
"""

from __future__ import annotations

from typing import Any

from problems.base import register_problem
from problems.encoding import comb2, readable_pair_var
from problems.graph import Graph, GraphProblemSpec, expected_edges, graph_fields
from sat_core.models import ProblemInstance


def hamiltonian_var(position: int, node: int, nodes: int) -> int:
    return readable_pair_var(position, node, nodes)


def hamiltonian_clauses(graph: Graph) -> list[list[int]]:
    n = graph.nodes
    adjacency = graph.adjacency()
    clauses = []
    for position in range(1, n + 1):
        clauses.append([hamiltonian_var(position, node, n) for node in range(1, n + 1)])
        for first in range(1, n + 1):
            for second in range(first + 1, n + 1):
                clauses.append([-hamiltonian_var(position, first, n), -hamiltonian_var(position, second, n)])
    for node in range(1, n + 1):
        clauses.append([hamiltonian_var(position, node, n) for position in range(1, n + 1)])
        for first in range(1, n + 1):
            for second in range(first + 1, n + 1):
                clauses.append([-hamiltonian_var(first, node, n), -hamiltonian_var(second, node, n)])
    for position in range(1, n):
        for u in range(1, n + 1):
            for v in range(1, n + 1):
                if u != v and v not in adjacency[u]:
                    clauses.append([-hamiltonian_var(position, u, n), -hamiltonian_var(position + 1, v, n)])
    return clauses


def decode_path(solution: dict[int, bool], nodes: int) -> dict[str, Any]:
    path = []
    for position in range(1, nodes + 1):
        chosen = 0
        for node in range(1, nodes + 1):
            if solution.get(hamiltonian_var(position, node, nodes)):
                chosen = node
                break
        path.append(chosen)
    return {"path": path}


@register_problem
class HamiltonianPath(GraphProblemSpec):
    key = "hamiltonian_path"
    title = "Hamiltonian Path"
    summary = "Find a path that visits every node exactly once."
    description = (
        "Variables x(i,v) mean node v is at position i of the path. Every position holds exactly "
        "one node, every node appears exactly once, and consecutive positions must be joined by "
        "an edge."
    )
    image = "hamiltonian_path.jpg"
    fields = graph_fields()

    def estimate(self, params: dict[str, Any]) -> dict[str, int]:
        n = params["nodes"]
        non_edge_pairs = n * (n - 1) - 2 * expected_edges(params)
        clauses = 2 * (n + n * comb2(n)) + max(n - 1, 0) * non_edge_pairs
        return {"variables": n * n, "clauses": int(clauses)}

    def encode_graph(self, graph: Graph, params: dict[str, Any]) -> ProblemInstance:
        nodes = graph.nodes
        return ProblemInstance(
            name=self.title,
            problem_type=self.key,
            clauses=hamiltonian_clauses(graph),
            decoder=lambda solution: decode_path(solution, nodes),
        )

    def check(self, instance: ProblemInstance, decoded: Any) -> list[str]:
        graph = self.graph_of(instance)
        path = decoded["path"]
        errors = []
        if sorted(path) != list(range(1, graph.nodes + 1)):
            errors.append("the path does not visit every node exactly once")
        adjacency = graph.adjacency()
        for u, v in zip(path, path[1:]):
            if u and v and v not in adjacency[u]:
                errors.append(f"{u} -> {v} is not an edge")
        return errors
