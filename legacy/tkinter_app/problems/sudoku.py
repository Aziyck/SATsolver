from __future__ import annotations

import math

from sat_core.models import ProblemInstance
from utils.sudoku_general import decode_sudoku, generate_sudoku_clauses


def validate_sudoku_grid(grid: list[list[int]]) -> None:
    if not grid:
        raise ValueError("Sudoku grid cannot be empty")

    size = len(grid)
    root = int(math.sqrt(size))

    if root * root != size:
        raise ValueError("Sudoku size must have an integer square root")

    for row in grid:
        if len(row) != size:
            raise ValueError("Sudoku grid must be square")
        for value in row:
            if value < 0 or value > size:
                raise ValueError(f"Sudoku values must be between 0 and {size}")


def empty_grid(size: int) -> list[list[int]]:
    return [[0 for _ in range(size)] for _ in range(size)]


def grid_from_text(text: str, size: int) -> list[list[int]]:
    values = []

    for raw in text.replace(",", " ").split():
        values.append(int(raw))

    if len(values) != size * size:
        raise ValueError(f"Expected {size * size} Sudoku values, got {len(values)}")

    return [values[i:i + size] for i in range(0, len(values), size)]


def format_grid(grid: list[list[int]]) -> str:
    return "\n".join(" ".join(str(value) for value in row) for row in grid)


def sudoku_problem(grid: list[list[int]], name: str | None = None) -> ProblemInstance:
    validate_sudoku_grid(grid)
    size = len(grid)
    clauses = generate_sudoku_clauses(grid)

    return ProblemInstance(
        name=name or f"Sudoku {size}x{size}",
        problem_type="Sudoku",
        clauses=clauses,
        metadata={
            "size": size,
            "box_size": int(math.sqrt(size)),
            "givens": sum(1 for row in grid for value in row if value != 0),
            "empty_cells": sum(1 for row in grid for value in row if value == 0),
            "grid": [row[:] for row in grid],
        },
        decoder=lambda solution: decode_sudoku(solution, size),
    )
