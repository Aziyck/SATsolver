"""Helpers for problems whose answer is a plain truth assignment."""

from __future__ import annotations

from typing import Any


MAX_ASSIGNMENT_BITS = 200_000


def assignment_bits(solution: dict[int, bool], variables: int) -> dict[str, Any]:
    """
    Compact model for variables 1..variables.

    bits[i] is "1" when variable i+1 is true. Unassigned variables (possible
    for complete solvers when a variable no longer matters) are shown as 0.
    """

    true_count = sum(1 for variable, value in solution.items() if value and 1 <= variable <= variables)
    data: dict[str, Any] = {"variables": variables, "true_count": true_count}
    if variables <= MAX_ASSIGNMENT_BITS:
        data["bits"] = "".join("1" if solution.get(variable) else "0" for variable in range(1, variables + 1))
    return data
