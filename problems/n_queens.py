"""
N-Queens: place n queens on an n x n board with no two attacking.

Variable x(r, c) = "a queen stands on row r, column c", numbered
readable_pair_var(r, c, n).

Clauses:
- every row has at least one queen, and at most one;
- every column has at most one queen (with n queens in n rows this forces
  exactly one per column);
- no two queens share a diagonal.
"""

from __future__ import annotations

from typing import Any

from problems.base import ProblemSpec, fact, register_problem
from problems.encoding import comb2, readable_pair_var
from sat_core.models import STATUS_SAT, STATUS_UNSAT, ProblemInstance
from sat_core.params import ParamField


def n_queens_var(row: int, col: int, size: int) -> int:
    return readable_pair_var(row, col, size)


def n_queens_clauses(size: int) -> list[list[int]]:
    clauses = []
    for row in range(1, size + 1):
        clauses.append([n_queens_var(row, col, size) for col in range(1, size + 1)])
        for c1 in range(1, size + 1):
            for c2 in range(c1 + 1, size + 1):
                clauses.append([-n_queens_var(row, c1, size), -n_queens_var(row, c2, size)])
    for col in range(1, size + 1):
        for r1 in range(1, size + 1):
            for r2 in range(r1 + 1, size + 1):
                clauses.append([-n_queens_var(r1, col, size), -n_queens_var(r2, col, size)])
    for r1 in range(1, size + 1):
        for c1 in range(1, size + 1):
            for r2 in range(r1 + 1, size + 1):
                delta = r2 - r1
                for c2 in (c1 - delta, c1 + delta):
                    if 1 <= c2 <= size:
                        clauses.append([-n_queens_var(r1, c1, size), -n_queens_var(r2, c2, size)])
    return clauses


def diagonal_pairs(size: int) -> int:
    """Pairs of cells sharing a diagonal, over both diagonal directions."""

    one_direction = comb2(size) + 2 * sum(comb2(length) for length in range(1, size))
    return 2 * one_direction


def decode_queens(solution: dict[int, bool], size: int) -> dict[str, Any]:
    queens = []
    for row in range(1, size + 1):
        for col in range(1, size + 1):
            if solution.get(n_queens_var(row, col, size)):
                queens.append([row, col])
                break
    return {"queens": queens}


@register_problem
class NQueens(ProblemSpec):
    key = "n_queens"
    title = "N-Queens"
    summary = "Place n queens on an n x n board so that no two attack each other."
    description = (
        "Variables x(r,c) mean a queen stands on (r,c). Every row gets exactly one queen, every "
        "column at most one, and no diagonal holds two."
    )
    category = "puzzle"
    image = "n_queens.jpg"
    result_view = "queens"
    fields = (
        ParamField("size", "Board size n", "int", default=8, minimum=1, maximum=300, sweepable=True, short="n"),
    )

    def estimate(self, params: dict[str, Any]) -> dict[str, int]:
        n = params["size"]
        return {"variables": n * n, "clauses": n + 2 * n * comb2(n) + diagonal_pairs(n)}

    def encode(self, params: dict[str, Any]) -> ProblemInstance:
        size = params["size"]
        return ProblemInstance(
            name=self.instance_name(params),
            problem_type=self.key,
            clauses=n_queens_clauses(size),
            metadata={"size": size},
            decoder=lambda solution: decode_queens(solution, size),
        )

    def expected_status(self, instance: ProblemInstance) -> str | None:
        return STATUS_UNSAT if instance.metadata["size"] in (2, 3) else STATUS_SAT

    def check(self, instance: ProblemInstance, decoded: Any) -> list[str]:
        size = instance.metadata["size"]
        queens = decoded["queens"]
        errors = []
        if len(queens) != size:
            errors.append(f"expected {size} queens, found {len(queens)}")
        for index, (r1, c1) in enumerate(queens):
            for r2, c2 in queens[index + 1:]:
                if r1 == r2 or c1 == c2 or abs(r1 - r2) == abs(c1 - c2):
                    errors.append(f"queens at ({r1},{c1}) and ({r2},{c2}) attack each other")
        return errors[:20]

    def describe(self, instance: ProblemInstance) -> list[dict[str, Any]]:
        size = instance.metadata["size"]
        return [fact("Board", f"{size}x{size}"), fact("Queens", size)]

    def visual(self, instance: ProblemInstance) -> dict[str, Any]:
        return {"size": instance.metadata["size"]}

    def preview(self, params: dict[str, Any]) -> dict[str, Any] | None:
        return {"size": params["size"]}
