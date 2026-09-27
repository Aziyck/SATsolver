"""
Sudoku of size n x n (n = 4, 9, 16 or 25).

Variable x(r, c, v) = "cell (r, c) holds v", numbered sudoku_var(r, c, v),
so 10203 reads as row 1, column 2, value 3.

Clauses:
- every cell holds at least one value, and at most one;
- every value appears at most once per row, column and box;
- the givens are unit clauses.

Puzzles are typed in the editor, or generated: a random valid solution
(a shuffled canonical grid) with a chosen percentage of cells kept as givens.
Generated puzzles are always satisfiable but may have several solutions.
"""

from __future__ import annotations

import math
from typing import Any

from problems.base import ProblemSpec, fact, register_problem
from problems.encoding import comb2, sudoku_var
from sat_core.models import STATUS_SAT, STATUS_UNSAT, ProblemInstance
from sat_core.params import Choice, ParamError, ParamField
from sat_core.seeds import rng_for


SUDOKU_SIZES = (4, 9, 16, 25)

EXAMPLE_PUZZLE = [
    [5, 3, 0, 0, 7, 0, 0, 0, 0],
    [6, 0, 0, 1, 9, 5, 0, 0, 0],
    [0, 9, 8, 0, 0, 0, 0, 6, 0],
    [8, 0, 0, 0, 6, 0, 0, 0, 3],
    [4, 0, 0, 8, 0, 3, 0, 0, 1],
    [7, 0, 0, 0, 2, 0, 0, 0, 6],
    [0, 6, 0, 0, 0, 0, 2, 8, 0],
    [0, 0, 0, 4, 1, 9, 0, 0, 5],
    [0, 0, 0, 0, 8, 0, 0, 7, 9],
]


def box_size(size: int) -> int:
    return int(math.isqrt(size))


def sudoku_clauses(grid: list[list[int]]) -> list[list[int]]:
    n = len(grid)
    k = box_size(n)
    clauses = []

    for r in range(1, n + 1):
        for c in range(1, n + 1):
            clauses.append([sudoku_var(r, c, value) for value in range(1, n + 1)])
            for v1 in range(1, n + 1):
                for v2 in range(v1 + 1, n + 1):
                    clauses.append([-sudoku_var(r, c, v1), -sudoku_var(r, c, v2)])

    for value in range(1, n + 1):
        for r in range(1, n + 1):
            for c1 in range(1, n + 1):
                for c2 in range(c1 + 1, n + 1):
                    clauses.append([-sudoku_var(r, c1, value), -sudoku_var(r, c2, value)])
        for c in range(1, n + 1):
            for r1 in range(1, n + 1):
                for r2 in range(r1 + 1, n + 1):
                    clauses.append([-sudoku_var(r1, c, value), -sudoku_var(r2, c, value)])
        for box_row in range(k):
            for box_col in range(k):
                cells = [
                    (r, c)
                    for r in range(box_row * k + 1, (box_row + 1) * k + 1)
                    for c in range(box_col * k + 1, (box_col + 1) * k + 1)
                ]
                for i in range(len(cells)):
                    for j in range(i + 1, len(cells)):
                        (r1, c1), (r2, c2) = cells[i], cells[j]
                        clauses.append([-sudoku_var(r1, c1, value), -sudoku_var(r2, c2, value)])

    for r in range(n):
        for c in range(n):
            if grid[r][c]:
                clauses.append([sudoku_var(r + 1, c + 1, grid[r][c])])
    return clauses


def decode_grid(solution: dict[int, bool], size: int) -> dict[str, Any]:
    grid = [[0] * size for _ in range(size)]
    for variable, value in solution.items():
        if not value:
            continue
        r, c, v = variable // 10_000, (variable // 100) % 100, variable % 100
        if 1 <= r <= size and 1 <= c <= size and 1 <= v <= size:
            grid[r - 1][c - 1] = v
    return {"grid": grid}


def units(size: int):
    """Every row, column and box as a list of (row, col) cells (0-based)."""

    k = box_size(size)
    for r in range(size):
        yield "row", r + 1, [(r, c) for c in range(size)]
    for c in range(size):
        yield "column", c + 1, [(r, c) for r in range(size)]
    for box in range(size):
        top, left = (box // k) * k, (box % k) * k
        yield "box", box + 1, [(r, c) for r in range(top, top + k) for c in range(left, left + k)]


def givens_conflicts(grid: list[list[int]]) -> list[str]:
    conflicts = []
    for unit, number, cells in units(len(grid)):
        seen: dict[int, int] = {}
        for r, c in cells:
            value = grid[r][c]
            if value:
                seen[value] = seen.get(value, 0) + 1
        for value, count in seen.items():
            if count > 1:
                conflicts.append(f"{unit} {number} contains {value} {count} times")
    return conflicts


def solved_grid(size: int, rng) -> list[list[int]]:
    """A random valid solution: shuffle a canonical grid by symmetry moves."""

    k = box_size(size)
    base = [[(r * k + r // k + c) % size + 1 for c in range(size)] for r in range(size)]
    bands = rng.sample(range(k), k)
    rows = [band * k + inner for band in bands for inner in rng.sample(range(k), k)]
    stacks = rng.sample(range(k), k)
    cols = [stack * k + inner for stack in stacks for inner in rng.sample(range(k), k)]
    digits = [0] + rng.sample(range(1, size + 1), size)
    return [[digits[base[r][c]] for c in cols] for r in rows]


def generated_puzzle(size: int, givens_percent: float, seed: int) -> tuple[list[list[int]], list[list[int]]]:
    rng = rng_for("sudoku", size, givens_percent, seed)
    solution = solved_grid(size, rng)
    cells = [(r, c) for r in range(size) for c in range(size)]
    keep = set(rng.sample(cells, round(len(cells) * givens_percent / 100)))
    puzzle = [[solution[r][c] if (r, c) in keep else 0 for c in range(size)] for r in range(size)]
    return puzzle, solution


@register_problem
class Sudoku(ProblemSpec):
    key = "sudoku"
    title = "Sudoku"
    summary = "Fill the grid so every row, column and box holds each value exactly once."
    description = (
        "Variables x(r,c,v) mean cell (r,c) holds value v. Each cell holds exactly one value, each "
        "value appears once per row, column and box, and the givens are fixed with unit clauses."
    )
    category = "puzzle"
    image = "sudoku.jpg"
    result_view = "sudoku"
    fields = (
        ParamField(
            "source",
            "Puzzle",
            "choice",
            default="manual",
            choices=(
                Choice("manual", "Enter a puzzle", "Type the givens into the grid."),
                Choice("generated", "Generate", "A random valid solution with a share of cells kept as givens."),
            ),
        ),
        ParamField(
            "size",
            "Size",
            "int",
            default=9,
            choices=tuple(Choice(str(size), f"{size}x{size}") for size in SUDOKU_SIZES),
            sweepable=True,
            short="size",
        ),
        ParamField(
            "grid",
            "Givens",
            "sudoku_grid",
            default=EXAMPLE_PUZZLE,
            show_if=(("source", ("manual",)),),
            help="Leave a cell empty (or 0) when it is unknown.",
        ),
        ParamField(
            "givens",
            "Givens",
            "float",
            default=40.0,
            minimum=0.0,
            maximum=100.0,
            step=5.0,
            unit="%",
            sweepable=True,
            show_if=(("source", ("generated",)),),
            short="givens",
            help="Share of cells revealed. Fewer givens usually means more search.",
        ),
        ParamField(
            "seed",
            "Seed",
            "seed",
            default=1,
            optional=True,
            sweepable=True,
            show_if=(("source", ("generated",)),),
            placeholder="random",
            short="seed",
        ),
    )

    def validate(self, params: dict[str, Any]) -> None:
        if params["source"] == "manual" and len(params["grid"]) != params["size"]:
            raise ParamError({"grid": f"the grid is {len(params['grid'])}x{len(params['grid'])} but size is {params['size']}"})

    def estimate(self, params: dict[str, Any]) -> dict[str, int]:
        n = params["size"]
        if params["source"] == "manual":
            givens = sum(1 for row in params["grid"] for value in row if value)
        else:
            givens = round(n * n * params["givens"] / 100)
        return {"variables": n ** 3, "clauses": n * n + 4 * n * n * comb2(n) + givens}

    def case_label(self, params: dict[str, Any]) -> str:
        size = params["size"]
        if params["source"] == "manual":
            givens = sum(1 for row in params["grid"] for value in row if value)
            return f"{size}x{size} manual, {givens} givens"
        seed = params.get("seed")
        return f"{size}x{size} givens={params['givens']:g}% seed={'-' if seed is None else seed}"

    def puzzle_for(self, params: dict[str, Any]) -> tuple[list[list[int]], list[list[int]] | None]:
        if params["source"] == "manual":
            return [row[:] for row in params["grid"]], None
        return generated_puzzle(params["size"], params["givens"], params["seed"])

    def encode(self, params: dict[str, Any]) -> ProblemInstance:
        grid, _solution = self.puzzle_for(params)
        size = len(grid)
        givens = sum(1 for row in grid for value in row if value)
        return ProblemInstance(
            name=self.instance_name(params),
            problem_type=self.key,
            clauses=sudoku_clauses(grid),
            metadata={
                "size": size,
                "box_size": box_size(size),
                "givens": givens,
                "empty_cells": size * size - givens,
                "grid": grid,
                "conflicts": givens_conflicts(grid),
                "seed": params.get("seed") if params["source"] == "generated" else None,
            },
            decoder=lambda solution: decode_grid(solution, size),
        )

    def expected_status(self, instance: ProblemInstance) -> str | None:
        if instance.metadata["conflicts"]:
            return STATUS_UNSAT
        if instance.params.get("source") == "generated":
            return STATUS_SAT
        return None

    def check(self, instance: ProblemInstance, decoded: Any) -> list[str]:
        grid = decoded["grid"]
        size = len(grid)
        errors = []
        for unit, number, cells in units(size):
            values = sorted(grid[r][c] for r, c in cells)
            if values != list(range(1, size + 1)):
                errors.append(f"{unit} {number} is not a permutation of 1..{size}")
        givens = instance.metadata["grid"]
        for r in range(size):
            for c in range(size):
                if givens[r][c] and givens[r][c] != grid[r][c]:
                    errors.append(f"cell ({r + 1},{c + 1}) changed a given")
        return errors[:20]

    def describe(self, instance: ProblemInstance) -> list[dict[str, Any]]:
        metadata = instance.metadata
        facts = [
            fact("Size", f"{metadata['size']}x{metadata['size']}"),
            fact("Givens", metadata["givens"]),
            fact("Empty cells", metadata["empty_cells"]),
        ]
        if metadata.get("seed") is not None:
            facts.append(fact("Seed", metadata["seed"]))
        if metadata["conflicts"]:
            facts.append(fact("Conflicting givens", "; ".join(metadata["conflicts"][:3]), "The puzzle cannot be solved."))
        return facts

    def visual(self, instance: ProblemInstance) -> dict[str, Any]:
        return {"size": instance.metadata["size"], "givens": instance.metadata["grid"]}

    def preview(self, params: dict[str, Any]) -> dict[str, Any] | None:
        params = self.resolve_seed(params)
        grid, _solution = self.puzzle_for(params)
        return {"size": len(grid), "givens": grid, "seed": params.get("seed"), "conflicts": givens_conflicts(grid)}
