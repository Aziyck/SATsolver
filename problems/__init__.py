"""
Problem encoders.

Importing this package registers every problem. The import order below is
the order problems appear in the UI. To add a problem, create a module with a
@register_problem ProblemSpec subclass and import it here.
"""

from problems.base import ProblemSpec, all_problems, get_problem, register_problem
from problems import sudoku  # noqa: F401  (registers the problem)
from problems import n_queens  # noqa: F401
from problems import graph_coloring  # noqa: F401
from problems import hamiltonian_path  # noqa: F401
from problems import independent_set  # noqa: F401
from problems import clique  # noqa: F401
from problems import random_3sat  # noqa: F401
from problems import dimacs_input  # noqa: F401


def build_problem(key: str, raw_params: dict | None = None):
    """Validate raw parameters and build the CNF instance in one call."""

    spec = get_problem(key)
    return spec.build(spec.parse(raw_params))


__all__ = ["ProblemSpec", "all_problems", "build_problem", "get_problem", "register_problem"]
