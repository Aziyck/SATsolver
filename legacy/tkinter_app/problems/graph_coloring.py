from __future__ import annotations

import random

from sat_core.models import ProblemInstance
from utils.graph_utils import (
    decode_coloring,
    generate_coloring_clauses,
    generate_random_graph,
    generate_random_graph_exact_edges,
    graph_edges,
)


Graph = dict[int, list[int]]


def normalize_graph(node_count: int, edges: list[tuple[int, int]]) -> Graph:
    if node_count <= 0:
        raise ValueError("Node count must be positive")

    graph = {node: [] for node in range(1, node_count + 1)}

    for u, v in edges:
        if u == v:
            raise ValueError("Self loops are not supported")
        if u < 1 or u > node_count or v < 1 or v > node_count:
            raise ValueError(f"Edge {u}-{v} is outside the node range 1..{node_count}")

        if v not in graph[u]:
            graph[u].append(v)
        if u not in graph[v]:
            graph[v].append(u)

    return graph


def parse_edge_list(text: str) -> list[tuple[int, int]]:
    edges = []

    for raw_edge in text.replace("\n", ",").split(","):
        item = raw_edge.strip()
        if not item:
            continue

        if "-" in item:
            left, right = item.split("-", 1)
        else:
            parts = item.split()
            if len(parts) != 2:
                raise ValueError(f"Invalid edge: {item}")
            left, right = parts

        edges.append((int(left.strip()), int(right.strip())))

    return edges


def edge_count(graph: Graph) -> int:
    return sum(len(neighbours) for neighbours in graph.values()) // 2


def graph_coloring_problem(graph: Graph, colors: int, name: str | None = None) -> ProblemInstance:
    if colors <= 0:
        raise ValueError("Color count must be positive")

    clauses = generate_coloring_clauses(graph, colors)
    nodes = len(graph)
    edges = edge_count(graph)

    return ProblemInstance(
        name=name or f"Graph Coloring n{nodes}_e{edges}_k{colors}",
        problem_type="Graph Coloring",
        clauses=clauses,
        metadata={"nodes": nodes, "edges": edges, "graph_edges": graph_edges(graph), "colors": colors},
        decoder=lambda solution: decode_coloring(solution, colors),
    )


def manual_graph_coloring_problem(node_count: int, colors: int, edge_text: str) -> ProblemInstance:
    edges = parse_edge_list(edge_text)
    graph = normalize_graph(node_count, edges)
    problem = graph_coloring_problem(graph, colors, name=f"Graph Coloring manual n{node_count}_k{colors}")
    problem.metadata.update({"mode": "manual"})
    return problem


def random_graph_coloring_problem(
    node_count: int,
    probability: float,
    colors: int,
    seed: int | None = None,
) -> ProblemInstance:
    if probability < 0 or probability > 1:
        raise ValueError("Edge probability must be between 0 and 1")

    rng = random.Random(seed) if seed is not None else random
    graph = generate_random_graph(node_count, probability, rng=rng)
    name = f"Graph Coloring n{node_count}_p{int(probability * 100)}_k{colors}"
    problem = graph_coloring_problem(graph, colors, name=name)
    problem.metadata.update({"mode": "probability", "probability": probability, "seed": seed})
    return problem


def edge_count_from_average_degree(node_count: int, average_degree: float) -> int:
    if node_count <= 0:
        raise ValueError("Node count must be positive")
    if average_degree < 0:
        raise ValueError("Average degree must not be negative")

    max_edges = node_count * (node_count - 1) // 2
    requested_edges = round(node_count * average_degree / 2)
    return min(requested_edges, max_edges)


def exact_edges_graph_coloring_problem(
    node_count: int,
    edge_count: int,
    colors: int,
    seed: int | None = None,
) -> ProblemInstance:
    max_edges = node_count * (node_count - 1) // 2
    if edge_count < 0:
        raise ValueError("Edge count must not be negative")

    rng = random.Random(seed) if seed is not None else random
    graph = generate_random_graph_exact_edges(node_count, edge_count, rng=rng)
    name = f"Graph Coloring n{node_count}_m{edge_count}_k{colors}"
    problem = graph_coloring_problem(graph, colors, name=name)
    problem.metadata.update({
        "mode": "exact_edges",
        "requested_edges": edge_count,
        "max_edges": max_edges,
        "edge_request_clamped": edge_count > max_edges,
        "seed": seed,
    })
    return problem


def average_degree_graph_coloring_problem(
    node_count: int,
    average_degree: float,
    colors: int,
    seed: int | None = None,
) -> ProblemInstance:
    if average_degree < 0:
        raise ValueError("Average degree must not be negative")

    max_edges = node_count * (node_count - 1) // 2
    requested_edges = round(node_count * average_degree / 2)
    edge_count = edge_count_from_average_degree(node_count, average_degree)
    rng = random.Random(seed) if seed is not None else random
    graph = generate_random_graph_exact_edges(node_count, edge_count, rng=rng)
    name = f"Graph Coloring n{node_count}_d{average_degree:g}_k{colors}"
    problem = graph_coloring_problem(graph, colors, name=name)
    problem.metadata.update({
        "mode": "average_degree",
        "average_degree": average_degree,
        "requested_edges": requested_edges,
        "max_edges": max_edges,
        "edge_request_clamped": requested_edges > max_edges,
        "seed": seed,
    })
    return problem
