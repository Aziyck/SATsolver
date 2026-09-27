from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


Decoder = Callable[[dict[int, bool]], Any]


@dataclass
class ProblemInstance:
    name: str
    problem_type: str
    clauses: list[list[int]]
    metadata: dict[str, Any] = field(default_factory=dict)
    decoder: Decoder | None = None

    @property
    def variable_count(self) -> int:
        variables = {abs(lit) for clause in self.clauses for lit in clause}
        return len(variables)

    @property
    def max_variable(self) -> int:
        variables = [abs(lit) for clause in self.clauses for lit in clause]
        return max(variables) if variables else 0

    @property
    def clause_count(self) -> int:
        return len(self.clauses)

    def decode_solution(self, solution: dict[int, bool] | None) -> Any:
        if solution is None:
            return None
        if self.decoder is None:
            return solution
        return self.decoder(solution)


@dataclass
class SolveResult:
    solver: str
    status: str
    elapsed: float
    solution: dict[int, bool] | None
    decoded: Any = None
    stats: dict[str, Any] = field(default_factory=dict)
    clauses: int = 0
    variables: int = 0


@dataclass
class BenchmarkRow:
    case_name: str
    problem_type: str
    solver: str
    status: str
    elapsed: float
    clauses: int
    variables: int
    repeat: int
    detail: str = ""
    conflicts: int | str = "-"
    decisions: int | str = "-"
    propagations: int | str = "-"
    learned_clauses: int | str = "-"
    generation_mode: str = ""
    edge_count: int | str = "-"
    node_count: int | str = "-"
    graph_edges: list[tuple[int, int]] = field(default_factory=list)
    decoded: Any = None
    seed: int | str | None = "-"
    solver_options: str = ""
    problem_metadata: dict[str, Any] = field(default_factory=dict)
    problem_clauses: list[list[int]] = field(default_factory=list)
    run_label: str = ""
    flips: int | str = "-"
    tries: int | str = "-"
    best_unsatisfied: int | str = "-"
    timeout: float | str = "-"

    def as_csv_row(self) -> list[Any]:
        return [
            self.run_label,
            self.case_name,
            self.problem_type,
            self.detail,
            self.solver,
            self.status,
            f"{self.elapsed:.8f}",
            self.clauses,
            self.variables,
            self.repeat,
            self.conflicts,
            self.decisions,
            self.propagations,
            self.learned_clauses,
            self.generation_mode,
            self.edge_count,
            self.solver_options,
        ]


BENCHMARK_HEADERS = [
    "run",
    "case_name",
    "problem_type",
    "detail",
    "solver",
    "status",
    "elapsed",
    "clauses",
    "variables",
    "repeat",
    "conflicts",
    "decisions",
    "propagations",
    "learned_clauses",
    "generation_mode",
    "edge_count",
    "solver_options",
]
