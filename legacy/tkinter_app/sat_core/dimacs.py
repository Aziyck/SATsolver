from __future__ import annotations

from pathlib import Path


def clause_stats(clauses: list[list[int]]) -> tuple[int, int]:
    variables = {abs(lit) for clause in clauses for lit in clause}
    max_var = max(variables) if variables else 0
    return max_var, len(clauses)


def clauses_to_dimacs(clauses: list[list[int]], comments: list[str] | None = None) -> str:
    max_var, clause_count = clause_stats(clauses)
    lines = []

    for comment in comments or []:
        lines.append(f"c {comment}")

    lines.append(f"p cnf {max_var} {clause_count}")

    for clause in clauses:
        lines.append(" ".join(str(lit) for lit in clause) + " 0")

    return "\n".join(lines) + "\n"


def parse_dimacs_text(text: str) -> list[list[int]]:
    clauses = []

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if not line or line.startswith("c") or line.startswith("p"):
            continue

        numbers = [int(part) for part in line.split()]
        clause = [number for number in numbers if number != 0]
        clauses.append(clause)

    return clauses


def save_dimacs(path: str | Path, clauses: list[list[int]], comments: list[str] | None = None) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(clauses_to_dimacs(clauses, comments), encoding="utf-8")


def load_dimacs(path: str | Path) -> list[list[int]]:
    return parse_dimacs_text(Path(path).read_text(encoding="utf-8"))
