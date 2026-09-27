from __future__ import annotations

from sat_core.models import ProblemInstance
from utils.general_utils import readable_pair_var


def n_queens_var(row: int, col: int, size: int) -> int:
    return readable_pair_var(row, col, size)


def decode_n_queens(solution: dict[int, bool], size: int) -> dict:
    positions = []

    for row in range(1, size + 1):
        for col in range(1, size + 1):
            if solution.get(n_queens_var(row, col, size)):
                positions.append((row, col))
                break

    position_set = set(positions)
    board = [
        "".join("Q" if (row, col) in position_set else "." for col in range(1, size + 1))
        for row in range(1, size + 1)
    ]

    return {"positions": positions, "board": board}


def n_queens_problem(size: int, name: str | None = None) -> ProblemInstance:
    if size <= 0:
        raise ValueError("N-Queens size must be positive")

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

    return ProblemInstance(
        name=name or f"N-Queens n{size}",
        problem_type="N-Queens",
        clauses=clauses,
        metadata={"size": size, "queens": size, "board_cells": size * size},
        decoder=lambda solution: decode_n_queens(solution, size),
    )
