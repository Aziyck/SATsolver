from __future__ import annotations

import random

from problems.graph_coloring import edge_count, edge_count_from_average_degree, normalize_graph, parse_edge_list
from sat_core.models import ProblemInstance
from utils.general_utils import readable_pair_var
from utils.graph_utils import generate_random_graph, generate_random_graph_exact_edges, graph_edges


Graph = dict[int, list[int]]


def independent_var(slot: int, node: int, node_count: int) -> int:
    return readable_pair_var(slot, node, node_count)


def decode_independent_set(solution: dict[int, bool], node_count: int, target_size: int) -> dict:
    selected = []

    for slot in range(1, target_size + 1):
        for node in range(1, node_count + 1):
            if solution.get(independent_var(slot, node, node_count)):
                selected.append(node)
                break

    return {"selected": selected}


def independent_set_problem(graph: Graph, target_size: int, name: str | None = None) -> ProblemInstance:
    node_count = len(graph)
    if node_count <= 0:
        raise ValueError("Node count must be positive")
    if target_size < 1 or target_size > node_count:
        raise ValueError(f"Independent set target k must be between 1 and {node_count}")

    clauses = []

    for slot in range(1, target_size + 1):
        clauses.append([independent_var(slot, node, node_count) for node in range(1, node_count + 1)])
        for n1 in range(1, node_count + 1):
            for n2 in range(n1 + 1, node_count + 1):
                clauses.append([
                    -independent_var(slot, n1, node_count),
                    -independent_var(slot, n2, node_count),
                ])

    for node in range(1, node_count + 1):
        for s1 in range(1, target_size + 1):
            for s2 in range(s1 + 1, target_size + 1):
                clauses.append([
                    -independent_var(s1, node, node_count),
                    -independent_var(s2, node, node_count),
                ])

    for node in range(1, node_count + 1):
        for neighbour in graph[node]:
            if node >= neighbour:
                continue
            for s1 in range(1, target_size + 1):
                for s2 in range(1, target_size + 1):
                    clauses.append([
                        -independent_var(s1, node, node_count),
                        -independent_var(s2, neighbour, node_count),
                    ])

    edges = edge_count(graph)
    return ProblemInstance(
        name=name or f"Independent Set n{node_count}_e{edges}_k{target_size}",
        problem_type="Independent Set",
        clauses=clauses,
        metadata={"nodes": node_count, "edges": edges, "graph_edges": graph_edges(graph), "target": target_size},
        decoder=lambda solution: decode_independent_set(solution, node_count, target_size),
    )


def manual_independent_set_problem(node_count: int, target_size: int, edge_text: str) -> ProblemInstance:
    graph = normalize_graph(node_count, parse_edge_list(edge_text))
    problem = independent_set_problem(graph, target_size, name=f"Independent Set manual n{node_count}_k{target_size}")
    problem.metadata.update({"mode": "manual"})
    return problem


def random_independent_set_problem(
    node_count: int,
    probability: float,
    target_size: int,
    seed: int | None = None,
) -> ProblemInstance:
    if probability < 0 or probability > 1:
        raise ValueError("Edge probability must be between 0 and 1")

    rng = random.Random(seed) if seed is not None else random
    graph = generate_random_graph(node_count, probability, rng=rng)
    problem = independent_set_problem(graph, target_size, name=f"Independent Set n{node_count}_p{int(probability * 100)}_k{target_size}")
    problem.metadata.update({"mode": "probability", "probability": probability, "seed": seed})
    return problem


def exact_edges_independent_set_problem(
    node_count: int,
    edges: int,
    target_size: int,
    seed: int | None = None,
) -> ProblemInstance:
    max_edges = node_count * (node_count - 1) // 2
    if edges < 0:
        raise ValueError("Edge count must not be negative")

    rng = random.Random(seed) if seed is not None else random
    graph = generate_random_graph_exact_edges(node_count, edges, rng=rng)
    problem = independent_set_problem(graph, target_size, name=f"Independent Set n{node_count}_m{edges}_k{target_size}")
    problem.metadata.update({
        "mode": "exact_edges",
        "requested_edges": edges,
        "max_edges": max_edges,
        "edge_request_clamped": edges > max_edges,
        "seed": seed,
    })
    return problem


def average_degree_independent_set_problem(
    node_count: int,
    average_degree: float,
    target_size: int,
    seed: int | None = None,
) -> ProblemInstance:
    if average_degree < 0:
        raise ValueError("Average degree must not be negative")

    requested_edges = round(node_count * average_degree / 2)
    edges = edge_count_from_average_degree(node_count, average_degree)
    problem = exact_edges_independent_set_problem(node_count, edges, target_size, seed=seed)
    problem.name = f"Independent Set n{node_count}_d{average_degree:g}_k{target_size}"
    problem.metadata.update({
        "mode": "average_degree",
        "average_degree": average_degree,
        "requested_edges": requested_edges,
        "edge_request_clamped": requested_edges > problem.metadata["max_edges"],
    })
    return problem
