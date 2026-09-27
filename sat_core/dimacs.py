"""
DIMACS CNF reading and writing.

The parser is token based, as the format requires: a clause is a run of
integers terminated by 0 and may span lines, and one line may hold several
clauses. It also accepts:

- comment lines starting with "c";
- an optional "p cnf <variables> <clauses>" header (plain clause lists work);
- the "%" end marker used by SATLIB benchmark files;
- a final clause without its terminating 0 (recorded as a warning).

Files written by this app carry a "c wizsat {...}" comment with the problem
key and parameters, so a CNF can be reopened as the problem it came from.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any


APP_HEADER_PREFIX = "wizsat "


class DimacsError(ValueError):
    def __init__(self, message: str, line: int | None = None):
        self.line = line
        super().__init__(f"line {line}: {message}" if line is not None else message)


@dataclass
class DimacsFormula:
    clauses: list[list[int]]
    declared_variables: int | None = None
    declared_clauses: int | None = None
    comments: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    app_header: dict[str, Any] | None = None

    @property
    def variables(self) -> int:
        """Declared variable count, or the largest variable used."""

        if self.declared_variables is not None:
            return self.declared_variables
        return max((abs(lit) for clause in self.clauses for lit in clause), default=0)


def parse_dimacs(text: str) -> DimacsFormula:
    clauses: list[list[int]] = []
    comments: list[str] = []
    warnings: list[str] = []
    declared_variables = None
    declared_clauses = None
    app_header = None
    current: list[int] = []
    current_start = None

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("c"):
            comment = line[1:].strip()
            comments.append(comment)
            if comment.startswith(APP_HEADER_PREFIX) and app_header is None:
                try:
                    header = json.loads(comment[len(APP_HEADER_PREFIX):])
                    if isinstance(header, dict):
                        app_header = header
                except json.JSONDecodeError:
                    warnings.append(f"line {line_number}: ignored unreadable wizsat header")
            continue
        if line.startswith("%"):
            break
        if line.startswith("p"):
            parts = line.split()
            if len(parts) != 4 or parts[1].lower() != "cnf":
                raise DimacsError("header must look like 'p cnf <variables> <clauses>'", line_number)
            if declared_variables is not None:
                raise DimacsError("duplicate 'p cnf' header", line_number)
            try:
                declared_variables = int(parts[2])
                declared_clauses = int(parts[3])
            except ValueError:
                raise DimacsError("header counts must be integers", line_number) from None
            if declared_variables < 0 or declared_clauses < 0:
                raise DimacsError("header counts must not be negative", line_number)
            continue

        for token in line.split():
            try:
                literal = int(token)
            except ValueError:
                raise DimacsError(f"unexpected token {token!r}", line_number) from None
            if literal == 0:
                clauses.append(current)
                current = []
                current_start = None
            else:
                if current_start is None:
                    current_start = line_number
                current.append(literal)

    if current:
        warnings.append(f"line {current_start}: last clause has no terminating 0")
        clauses.append(current)

    if declared_clauses is not None and declared_clauses != len(clauses):
        warnings.append(f"header declares {declared_clauses} clauses, found {len(clauses)}")
    if declared_variables is not None:
        largest = max((abs(lit) for clause in clauses for lit in clause), default=0)
        if largest > declared_variables:
            warnings.append(f"header declares {declared_variables} variables, but variable {largest} is used")
    empty = sum(1 for clause in clauses if not clause)
    if empty:
        warnings.append(f"{empty} empty clause(s): the formula is trivially UNSAT")

    return DimacsFormula(
        clauses=clauses,
        declared_variables=declared_variables,
        declared_clauses=declared_clauses,
        comments=comments,
        warnings=warnings,
        app_header=app_header,
    )


def parse_dimacs_text(text: str) -> list[list[int]]:
    return parse_dimacs(text).clauses


def clause_stats(clauses: list[list[int]]) -> tuple[int, int]:
    max_var = max((abs(lit) for clause in clauses for lit in clause), default=0)
    return max_var, len(clauses)


def app_header_comment(problem: str, params: dict[str, Any]) -> str:
    return APP_HEADER_PREFIX + json.dumps({"problem": problem, "params": params}, separators=(",", ":"))


def dimacs_lines(clauses: list[list[int]], comments: list[str] | None = None, variables: int | None = None):
    """Yield DIMACS lines; handy for streaming large formulas to a file."""

    max_var, clause_count = clause_stats(clauses)
    for comment in comments or []:
        for part in str(comment).splitlines() or [""]:
            yield f"c {part}".rstrip()
    yield f"p cnf {max(max_var, variables or 0)} {clause_count}"
    for clause in clauses:
        yield " ".join(str(lit) for lit in clause) + " 0"


def clauses_to_dimacs(clauses: list[list[int]], comments: list[str] | None = None, variables: int | None = None) -> str:
    return "\n".join(dimacs_lines(clauses, comments, variables)) + "\n"


def save_dimacs(path: str | Path, clauses: list[list[int]], comments: list[str] | None = None, variables: int | None = None) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        for line in dimacs_lines(clauses, comments, variables):
            handle.write(line + "\n")


def load_dimacs(path: str | Path) -> list[list[int]]:
    return parse_dimacs(Path(path).read_text(encoding="utf-8")).clauses
