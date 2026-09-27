from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable


Decoder = Callable[[dict[int, bool]], Any]

# Public run statuses. SAT/UNSAT are proofs; UNKNOWN means an incomplete
# solver (or a conflict limit) stopped without a conclusion.
STATUS_SAT = "SAT"
STATUS_UNSAT = "UNSAT"
STATUS_UNKNOWN = "UNKNOWN"
STATUS_TIMEOUT = "TIMEOUT"
STATUS_CANCELLED = "CANCELLED"
STATUS_SKIPPED = "SKIPPED"
STATUS_ERROR = "ERROR"
STATUSES = (
    STATUS_SAT,
    STATUS_UNSAT,
    STATUS_UNKNOWN,
    STATUS_TIMEOUT,
    STATUS_CANCELLED,
    STATUS_SKIPPED,
    STATUS_ERROR,
)


@dataclass
class ProblemInstance:
    """
    A CNF formula plus everything needed to explain it.

    problem_type is the registry key of the problem (for example
    "graph_coloring"). params are the validated parameters the instance was
    built from, so the same instance can be rebuilt later. metadata holds
    JSON-friendly facts produced while encoding (edge counts, the effective
    seed, ...). decoder turns a SAT model back into a problem answer.
    """

    name: str
    problem_type: str
    clauses: list[list[int]]
    metadata: dict[str, Any] = field(default_factory=dict)
    decoder: Decoder | None = None
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def variable_count(self) -> int:
        return len({abs(lit) for clause in self.clauses for lit in clause})

    @property
    def max_variable(self) -> int:
        variables = [abs(lit) for clause in self.clauses for lit in clause]
        return max(variables) if variables else 0

    @property
    def clause_count(self) -> int:
        return len(self.clauses)

    @property
    def size_variables(self) -> int:
        """
        Variable count used by benchmark limit rules.

        Generators with a declared size (n for Random 3-SAT, the header count
        for DIMACS) store it in metadata["variables"]; otherwise the number of
        distinct CNF variables is used.
        """

        declared = self.metadata.get("variables")
        if isinstance(declared, int) and declared > 0:
            return declared
        return self.variable_count

    def decode_solution(self, solution: dict[int, bool] | None) -> Any:
        if solution is None:
            return None
        if self.decoder is None:
            return None
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
    error: str | None = None


@dataclass
class BenchmarkRow:
    """One solver run inside a benchmark."""

    index: int
    case_index: int
    problem: str
    case_label: str
    params: dict[str, Any]
    repeat: int
    solver: str
    solver_label: str
    status: str
    elapsed: float
    variables: int
    clauses: int
    size_variables: int = 0
    expected: str | None = None
    verified: bool | None = None
    check_errors: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    timeout: float | None = None
    rule: str | None = None
    error: str | None = None
    decoded: Any = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BenchmarkRow":
        known = {name for name in cls.__dataclass_fields__}
        return cls(**{key: value for key, value in data.items() if key in known})
