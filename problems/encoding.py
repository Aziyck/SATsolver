"""
Readable variable numbering shared by the encoders.

Variables are numbered so that a DIMACS file stays readable by eye: the
digits of a variable spell out what it means. For example the Sudoku
variable 10203 is "row 1, column 2 holds value 3", and graph-coloring
variable 203 is "node 2 has color 3".

The numbers are sparse (Sudoku 9x9 uses values up to 90909 for 729
variables). Solvers index arrays by variable number, so a compact
renumbering inside the solver layer is a possible later optimisation; the
encodings themselves stay readable.
"""

from __future__ import annotations


def sudoku_var(row: int, col: int, value: int) -> int:
    """Row r, column c holds value v: r*10000 + c*100 + v (sizes up to 99)."""

    return row * 10_000 + col * 100 + value


def readable_pair_var(first: int, second: int, max_second: int) -> int:
    """
    Encode a (first, second) pair as a decimal number.

    The second part takes two digits, or more when max_second needs them:
    (2, 3, 10) -> 203 and (2, 101, 101) -> 2101.
    """

    width = 100
    while max_second >= width:
        width *= 10
    return first * width + second


def color_var(node: int, color: int, colors: int) -> int:
    """Graph coloring: node has color."""

    return readable_pair_var(node, color, colors)


def pairwise_at_most_one(literals: list[int]) -> list[list[int]]:
    """Naive at-most-one constraint: forbid every pair."""

    return [
        [-literals[i], -literals[j]]
        for i in range(len(literals))
        for j in range(i + 1, len(literals))
    ]


def comb2(n: int) -> int:
    return n * (n - 1) // 2 if n > 1 else 0
