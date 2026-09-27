import random

from utils.general_utils import color_var


def _empty_graph(n):
    return {i: [] for i in range(1, n + 1)}


def _add_edge(graph, u, v):
    graph[u].append(v)
    graph[v].append(u)


def _sort_graph(graph):
    for neighbours in graph.values():
        neighbours.sort()
    return graph


def all_possible_edges(n):
    return [(i, j) for i in range(1, n + 1) for j in range(i + 1, n + 1)]


def generate_random_graph(n, p, rng=None):
    if n <= 0:
        raise ValueError("Node count must be positive")
    if p < 0 or p > 1:
        raise ValueError("Edge probability must be between 0 and 1")

    source = rng or random
    graph = _empty_graph(n)

    for i in range(1, n + 1):
        for j in range(i + 1, n + 1):
            if source.random() < p:
                _add_edge(graph, i, j)

    return _sort_graph(graph)


def generate_random_graph_exact_edges(n, m, rng=None):
    if n <= 0:
        raise ValueError("Node count must be positive")
    if m < 0:
        raise ValueError("Edge count must not be negative")

    max_edges = n * (n - 1) // 2
    actual_edge_count = min(m, max_edges)

    source = rng or random
    graph = _empty_graph(n)

    for u, v in source.sample(all_possible_edges(n), actual_edge_count):
        _add_edge(graph, u, v)

    return _sort_graph(graph)


def graph_edges(graph):
    return [(u, v) for u in sorted(graph) for v in graph[u] if u < v]


def generate_coloring_clauses(graph, k):
    clauses = []
    nodes = list(graph.keys())

    for v in nodes:
        clauses.append([color_var(v, c, k) for c in range(1, k + 1)])

    for v in nodes:
        for c1 in range(1, k + 1):
            for c2 in range(c1 + 1, k + 1):
                clauses.append([-color_var(v, c1, k), -color_var(v, c2, k)])

    for u in nodes:
        for v in graph[u]:
            if u < v:
                for c in range(1, k + 1):
                    clauses.append([
                        -color_var(u, c, k),
                        -color_var(v, c, k),
                    ])

    return clauses


def decode_coloring(solution, colors=None):
    coloring = {}
    width = 100
    if colors is not None:
        while colors >= width:
            width *= 10

    for key, value in solution.items():
        if value:
            if colors is None:
                v = key // 100
                c = key % 100
            else:
                v = key // width
                c = key % width
            coloring[v] = c

    return coloring
