from __future__ import annotations

from pathlib import Path

from sat_core.dimacs import load_dimacs, parse_dimacs_text
from sat_core.models import ProblemInstance


def dimacs_problem_from_text(
    text: str,
    name: str = "DIMACS input",
    problem_type: str = "DIMACS",
) -> ProblemInstance:
    clauses = parse_dimacs_text(text)

    if not clauses:
        raise ValueError("DIMACS text does not contain any clauses")

    return ProblemInstance(
        name=name,
        problem_type=problem_type,
        clauses=clauses,
        metadata={"source": "text", "loaded_as": problem_type},
    )


def dimacs_problem_from_file(path: str | Path) -> ProblemInstance:
    source = Path(path)
    clauses = load_dimacs(source)

    return ProblemInstance(
        name=source.name,
        problem_type="DIMACS",
        clauses=clauses,
        metadata={"source": str(source)},
    )
