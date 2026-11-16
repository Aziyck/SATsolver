"""
Judging a SAT answer.

A solver's model is only a claim. judge_answer checks it against the clauses,
decodes it into the problem's own answer and runs the problem's check, so a
solve job and a benchmark run mean the same thing by "verified".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from problems.base import ProblemSpec
from sat_core.models import STATUS_SAT, ProblemInstance, SolveResult
from sat_core.verify import check_assignment


@dataclass(frozen=True)
class Verdict:
    verified: bool | None  # None when there is no model to check
    decoded: Any
    errors: list[str]


def judge_answer(spec: ProblemSpec, instance: ProblemInstance, result: SolveResult) -> Verdict:
    """Judge a result; only a SAT status with a model is judged, anything else gets no verdict."""

    if result.status != STATUS_SAT or result.solution is None:
        return Verdict(verified=None, decoded=None, errors=[])

    errors: list[str] = []
    satisfied = check_assignment(instance.clauses, result.solution)
    if not satisfied:
        errors.append("the model does not satisfy every clause")
    decoded = None
    try:
        decoded = spec.decode(instance, result.solution)
        if decoded is not None:
            errors.extend(spec.check(instance, decoded))
    except Exception as exc:  # noqa: BLE001 - a broken decoder is a failed verification, not a crash
        errors.append(f"decoding failed: {exc}")
    return Verdict(verified=satisfied and not errors, decoded=decoded, errors=errors)
