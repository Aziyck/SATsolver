"""
Graph inputs shared by every graph problem.

All graph problems take the same graph fields: a generation mode and the
parameters of that mode. The graph is built from those fields (and the seed)
only, never from problem-specific fields such as the number of colors, so
Graph Coloring with k=3 and Clique with k=4 on the same graph fields and seed
really see the same graph. That is what makes side-by-side benchmarks fair.

Modes:
- gnp: Erdos-Renyi G(n,p), each possible edge appears with probability p;
- gnm: G(n,m), exactly m distinct edges chosen uniformly;
- gnd: average degree d, converted to m = round(n*d/2) and generated as G(n,m);
- manual: an explicit edge list.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from typing import Any

from problems.base import ProblemSpec, fact
from problems.encoding import comb2
from sat_core.models import ProblemInstance
from sat_core.params import Choice, ParamError, ParamField, format_value
from sat_core.seeds import rng_for


MAX_GRAPH_NODES = 2000
MAX_VISUAL_EDGES = 20_000

GRAPH_MODES = (
    Choice("gnp", "G(n,p)", "Each possible edge appears independently with probability p."),
    Choice("gnm", "G(n,m)", "Exactly m edges, chosen uniformly at random."),
    Choice("gnd", "G(n,d)", "Average degree d, converted to m = round(n*d/2) edges."),
    Choice("manual", "Manual", "Type the edges yourself, for example 1-2, 2-3."),
)
RANDOM_MODES = ("gnp", "gnm", "gnd")


def graph_fields(default_mode: str = "gnp", default_nodes: int = 10) -> tuple[ParamField, ...]:
    return (
        ParamField(
            "graph_mode",
            "Graph",
            "choice",
            default=default_mode,
            choices=GRAPH_MODES,
            group="graph",
            help="How the input graph is produced.",
        ),
        ParamField(
            "nodes",
            "Nodes",
            "int",
            default=default_nodes,
            minimum=1,
            maximum=MAX_GRAPH_NODES,
            sweepable=True,
            group="graph",
            short="n",
        ),
        ParamField(
            "edges",
            "Edges",
            "edges",
            default="1-2, 2-3, 3-4, 4-5, 5-1, 1-3, 6-7, 7-8, 8-9, 9-10, 10-6, 5-6",
            group="graph",
            show_if=(("graph_mode", ("manual",)),),
            help="Undirected edges such as 1-2, separated by commas or new lines. Nodes are numbered from 1.",
        ),
        ParamField(
            "probability",
            "Edge probability p",
            "float",
            default=0.3,
            minimum=0.0,
            maximum=1.0,
            step=0.05,
            sweepable=True,
            group="graph",
            show_if=(("graph_mode", ("gnp",)),),
            short="p",
        ),
        ParamField(
            "edge_count",
            "Edges m",
            "int",
            default=15,
            minimum=0,
            sweepable=True,
            group="graph",
            show_if=(("graph_mode", ("gnm",)),),
            short="m",
        ),
        ParamField(
            "average_degree",
            "Average degree d",
            "float",
            default=3.0,
            minimum=0.0,
            step=0.5,
            sweepable=True,
            group="graph",
            show_if=(("graph_mode", ("gnd",)),),
            short="d",
            help="Converted to m = round(n*d/2) edges; capped at the complete graph.",
        ),
        ParamField(
            "seed",
            "Seed",
            "seed",
            default=2,
            optional=True,
            sweepable=True,
            group="graph",
            show_if=(("graph_mode", RANDOM_MODES),),
            placeholder="random",
            short="seed",
            help="Same parameters and seed give the same graph. Leave blank for a random one.",
        ),
    )


@dataclass
class Graph:
    nodes: int
    edges: list[tuple[int, int]]
    meta: dict[str, Any] = field(default_factory=dict)

    def adjacency(self) -> dict[int, set[int]]:
        adjacency = {node: set() for node in range(1, self.nodes + 1)}
        for u, v in self.edges:
            adjacency[u].add(v)
            adjacency[v].add(u)
        return adjacency


def max_edges(nodes: int) -> int:
    return comb2(nodes)


def requested_edge_count(params: dict[str, Any]) -> int:
    mode = params["graph_mode"]
    if mode == "gnm":
        return int(params["edge_count"])
    if mode == "gnd":
        return round(params["nodes"] * params["average_degree"] / 2)
    raise ValueError(mode)


def expected_edges(params: dict[str, Any]) -> float:
    """Edge count used for size estimates (exact except for G(n,p))."""

    nodes = params["nodes"]
    mode = params["graph_mode"]
    if mode == "manual":
        return float(len(params["edges"]))
    if mode == "gnp":
        return params["probability"] * max_edges(nodes)
    return float(min(requested_edge_count(params), max_edges(nodes)))


def _pair_from_index(index: int, nodes: int, row_starts: list[int]) -> tuple[int, int]:
    """Map 0..C(n,2)-1 to the pairs (1,2), (1,3), ..., (n-1,n) without listing them."""

    row = bisect_right(row_starts, index)  # rows are 1-based: row_starts[r-1] is the first index of row r
    first = row
    offset = index - row_starts[row - 1]
    return first, first + 1 + offset


def validate_graph_params(params: dict[str, Any]) -> None:
    if params["graph_mode"] == "manual":
        largest = max((v for _u, v in params["edges"]), default=0)
        if largest > params["nodes"]:
            raise ParamError({"edges": f"edge list uses node {largest}, but the graph has {params['nodes']} nodes"})


def build_graph(params: dict[str, Any]) -> Graph:
    nodes = params["nodes"]
    mode = params["graph_mode"]
    total_pairs = max_edges(nodes)

    if mode == "manual":
        validate_graph_params(params)
        edges = [tuple(edge) for edge in params["edges"]]
        return Graph(nodes, sorted(edges), {"mode": "manual"})

    seed = params["seed"]
    if seed is None:
        raise ValueError("random graphs need a resolved seed")

    if mode == "gnp":
        probability = params["probability"]
        rng = rng_for("gnp", nodes, probability, seed)
        edges = [
            (u, v)
            for u in range(1, nodes + 1)
            for v in range(u + 1, nodes + 1)
            if rng.random() < probability
        ]
        return Graph(nodes, edges, {"mode": "gnp", "probability": probability, "seed": seed})

    requested = requested_edge_count(params)
    count = min(requested, total_pairs)
    rng = rng_for("gnm", nodes, count, seed)
    row_starts = []
    start = 0
    for row in range(1, nodes):
        row_starts.append(start)
        start += nodes - row
    edges = sorted(_pair_from_index(index, nodes, row_starts) for index in rng.sample(range(total_pairs), count))
    meta = {
        "mode": mode,
        "requested_edges": requested,
        "max_edges": total_pairs,
        "edge_request_clamped": requested > total_pairs,
        "seed": seed,
    }
    if mode == "gnd":
        meta["average_degree"] = params["average_degree"]
    return Graph(nodes, edges, meta)


def graph_generation_text(params: dict[str, Any]) -> str:
    mode = params["graph_mode"]
    if mode == "manual":
        return "manual edges"
    if mode == "gnp":
        return f"G(n,p), p={format_value(params['probability'])}"
    if mode == "gnm":
        return f"G(n,m), m={params['edge_count']}"
    return f"G(n,d), d={format_value(params['average_degree'])}"


def graph_visual(nodes: int, edges: list[tuple[int, int]]) -> dict[str, Any]:
    if len(edges) > MAX_VISUAL_EDGES:
        return {"nodes": nodes, "edges": [], "edge_count": len(edges), "too_large": True}
    return {"nodes": nodes, "edges": [list(edge) for edge in edges], "edge_count": len(edges), "too_large": False}


class GraphProblemSpec(ProblemSpec):
    """Base class for problems whose input is an undirected graph."""

    category = "graph"
    result_view = "graph"
    graph_based = True

    def validate(self, params: dict[str, Any]) -> None:
        validate_graph_params(params)

    def encode(self, params: dict[str, Any]) -> ProblemInstance:
        graph = build_graph(params)
        instance = self.encode_graph(graph, params)
        instance.name = self.instance_name(params)
        instance.metadata.update(graph.meta)
        instance.metadata.update(
            {
                "nodes": graph.nodes,
                "edges": len(graph.edges),
                "graph_edges": [list(edge) for edge in graph.edges],
            }
        )
        return instance

    def encode_graph(self, graph: Graph, params: dict[str, Any]) -> ProblemInstance:
        raise NotImplementedError

    def graph_of(self, instance: ProblemInstance) -> Graph:
        edges = [tuple(edge) for edge in instance.metadata.get("graph_edges", [])]
        return Graph(instance.metadata["nodes"], edges)

    def describe(self, instance: ProblemInstance) -> list[dict[str, Any]]:
        metadata = instance.metadata
        nodes = metadata["nodes"]
        edges = metadata["edges"]
        density = (2 * edges / (nodes * (nodes - 1))) if nodes > 1 else 0.0
        facts = [
            fact("Nodes", nodes),
            fact("Edges", edges),
            fact("Density", round(density, 4)),
            fact("Generation", graph_generation_text(instance.params)),
        ]
        if metadata.get("edge_request_clamped"):
            facts.append(
                fact(
                    "Requested edges",
                    metadata.get("requested_edges"),
                    "More than a simple graph can hold, so the complete graph was used.",
                )
            )
        if metadata.get("seed") is not None:
            facts.append(fact("Seed", metadata["seed"]))
        return facts

    def visual(self, instance: ProblemInstance) -> dict[str, Any]:
        graph = self.graph_of(instance)
        return graph_visual(graph.nodes, graph.edges)

    def preview(self, params: dict[str, Any]) -> dict[str, Any] | None:
        params = self.resolve_seed(params)
        graph = build_graph(params)
        data = graph_visual(graph.nodes, graph.edges)
        data["seed"] = params.get("seed") if params["graph_mode"] != "manual" else None
        return data
