from __future__ import annotations

import random

from problems.graph_coloring import edge_count, edge_count_from_average_degree, normalize_graph, parse_edge_list
from sat_core.models import ProblemInstance
from utils.general_utils import readable_pair_var
from utils.graph_utils import generate_random_graph, generate_random_graph_exact_edges, graph_edges


Graph = dict[int, list[int]]


def hamiltonian_var(position: int, node: int, node_count: int) -> int:
    return readable_pair_var(position, node, node_count)


def decode_hamiltonian_path(solution: dict[int, bool], node_count: int) -> dict:
    path = []

    for position in range(1, node_count + 1):
        node_at_position = 0
        for node in range(1, node_count + 1):
            if solution.get(hamiltonian_var(position, node, node_count)):
                node_at_position = node
                break
        path.append(node_at_position)

    return {"path": path}


def hamiltonian_path_problem(graph: Graph, name: str | None = None) -> ProblemInstance:
    node_count = len(graph)
    if node_count <= 0:
        raise ValueError("Node count must be positive")

    clauses = []

    for position in range(1, node_count + 1):
        clauses.append([hamiltonian_var(position, node, node_count) for node in range(1, node_count + 1)])
        for n1 in range(1, node_count + 1):
            for n2 in range(n1 + 1, node_count + 1):
                clauses.append([
                    -hamiltonian_var(position, n1, node_count),
                    -hamiltonian_var(position, n2, node_count),
                ])

    for node in range(1, node_count + 1):
        clauses.append([hamiltonian_var(position, node, node_count) for position in range(1, node_count + 1)])
        for p1 in range(1, node_count + 1):
            for p2 in range(p1 + 1, node_count + 1):
                clauses.append([
                    -hamiltonian_var(p1, node, node_count),
                    -hamiltonian_var(p2, node, node_count),
                ])

    for position in range(1, node_count):
        for n1 in range(1, node_count + 1):
            for n2 in range(1, node_count + 1):
                if n1 == n2 or n2 in graph[n1]:
                    continue
                clauses.append([
                    -hamiltonian_var(position, n1, node_count),
                    -hamiltonian_var(position + 1, n2, node_count),
                ])

    edges = edge_count(graph)
    return ProblemInstance(
        name=name or f"Hamiltonian Path n{node_count}_e{edges}",
        problem_type="Hamiltonian Path",
        clauses=clauses,
        metadata={"nodes": node_count, "edges": edges, "graph_edges": graph_edges(graph)},
        decoder=lambda solution: decode_hamiltonian_path(solution, node_count),
    )


def manual_hamiltonian_path_problem(node_count: int, edge_text: str) -> ProblemInstance:
    graph = normalize_graph(node_count, parse_edge_list(edge_text))
    problem = hamiltonian_path_problem(graph, name=f"Hamiltonian Path manual n{node_count}")
    problem.metadata.update({"mode": "manual"})
    return problem


def random_hamiltonian_path_problem(
    node_count: int,
    probability: float,
    seed: int | None = None,
) -> ProblemInstance:
    if probability < 0 or probability > 1:
        raise ValueError("Edge probability must be between 0 and 1")

    rng = random.Random(seed) if seed is not None else random
    graph = generate_random_graph(node_count, probability, rng=rng)
    problem = hamiltonian_path_problem(graph, name=f"Hamiltonian Path n{node_count}_p{int(probability * 100)}")
    problem.metadata.update({"mode": "probability", "probability": probability, "seed": seed})
    return problem


def exact_edges_hamiltonian_path_problem(
    node_count: int,
    edges: int,
    seed: int | None = None,
) -> ProblemInstance:
    max_edges = node_count * (node_count - 1) // 2
    if edges < 0:
        raise ValueError("Edge count must not be negative")

    rng = random.Random(seed) if seed is not None else random
    graph = generate_random_graph_exact_edges(node_count, edges, rng=rng)
    problem = hamiltonian_path_problem(graph, name=f"Hamiltonian Path n{node_count}_m{edges}")
    problem.metadata.update({
        "mode": "exact_edges",
        "requested_edges": edges,
        "max_edges": max_edges,
        "edge_request_clamped": edges > max_edges,
        "seed": seed,
    })
    return problem


def average_degree_hamiltonian_path_problem(
    node_count: int,
    average_degree: float,
    seed: int | None = None,
) -> ProblemInstance:
    if average_degree < 0:
        raise ValueError("Average degree must not be negative")

    requested_edges = round(node_count * average_degree / 2)
    edges = edge_count_from_average_degree(node_count, average_degree)
    problem = exact_edges_hamiltonian_path_problem(node_count, edges, seed=seed)
    problem.name = f"Hamiltonian Path n{node_count}_d{average_degree:g}"
    problem.metadata.update({
        "mode": "average_degree",
        "average_degree": average_degree,
        "requested_edges": requested_edges,
        "edge_request_clamped": requested_edges > problem.metadata["max_edges"],
    })
    return problem
