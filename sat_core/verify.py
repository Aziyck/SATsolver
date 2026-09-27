"""
Certificate checking.

Finding a model can be hard; checking one is easy: evaluate every clause. The
app verifies each SAT answer this way before showing it, which is the
"search vs verification" asymmetry behind NP in miniature.
"""

from __future__ import annotations


def first_unsatisfied_clause(clauses: list[list[int]], solution: dict[int, bool]) -> int | None:
    """
    Return the index of the first clause the model falsifies, or None.

    Variables missing from the model are treated as False. Complete solvers
    may leave variables unassigned when every clause is already satisfied,
    and any value works for those.
    """

    for index, clause in enumerate(clauses):
        for lit in clause:
            value = solution.get(abs(lit), False)
            if value == (lit > 0):
                break
        else:
            return index
    return None


def check_assignment(clauses: list[list[int]], solution: dict[int, bool] | None) -> bool:
    if solution is None:
        return False
    return first_unsatisfied_clause(clauses, solution) is None
