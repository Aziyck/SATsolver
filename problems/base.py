"""
Problem registry and the ProblemSpec base class.

A problem is declared once, as a ProblemSpec subclass registered with
@register_problem. The spec owns everything problem-specific:

- fields: the parameter schema (validation, benchmark sweeps, UI forms);
- build(): encode validated parameters into a CNF ProblemInstance;
- decode/check: turn a SAT model back into an answer and double-check it;
- describe/visual/preview: data the web UI shows before and after solving;
- estimate(): size of the CNF, computed without building it.

Solvers, jobs, benchmarks and the web server only talk to this interface, so
adding a problem means adding one module under problems/ (and a frontend
renderer only if it needs a new kind of picture).
"""

from __future__ import annotations

import os
from typing import Any

from sat_core.models import ProblemInstance
from sat_core.params import ParamError, ParamField, check_field_order, expand_params, format_value, parse_params
from sat_core.seeds import fresh_seed


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


# Encoding more clauses than this is refused before any work is done: Python
# lists of clauses need a few hundred bytes per clause.
MAX_CLAUSES = _env_int("WIZSAT_MAX_CLAUSES", 2_000_000)

RESULT_VIEWS = ("sudoku", "queens", "graph", "assignment")


class ProblemSpec:
    key: str = ""
    title: str = ""
    summary: str = ""
    description: str = ""
    category: str = "puzzle"
    image: str | None = None
    result_view: str = "assignment"
    fields: tuple[ParamField, ...] = ()
    graph_based: bool = False

    # -- parameters ---------------------------------------------------------

    def parse(self, raw: dict[str, Any] | None) -> dict[str, Any]:
        params = parse_params(self.fields, raw)
        self.validate(params)
        return params

    def expand(self, raw: dict[str, Any] | None) -> list[dict[str, Any]]:
        cases = expand_params(self.fields, raw, allow_sweep=True)
        for params in cases:
            self.validate(params)
        return cases

    def validate(self, params: dict[str, Any]) -> None:
        """Cross-field checks; raise ParamError({field: message})."""

    def field(self, name: str) -> ParamField:
        for field in self.fields:
            if field.name == name:
                return field
        raise KeyError(name)

    def has_visible_seed(self, params: dict[str, Any]) -> bool:
        return any(field.name == "seed" and field.visible(params) for field in self.fields)

    def resolve_seed(self, params: dict[str, Any]) -> dict[str, Any]:
        """Replace a blank seed by a fresh one, so the instance stays reproducible."""

        if self.has_visible_seed(params) and params.get("seed") is None:
            return {**params, "seed": fresh_seed()}
        return params

    # -- encoding -------------------------------------------------------------

    def estimate(self, params: dict[str, Any]) -> dict[str, int] | None:
        """Approximate {"variables", "clauses"} of the CNF, or None if unknown."""

        return None

    def check_size(self, params: dict[str, Any]) -> None:
        estimate = self.estimate(params)
        if estimate and estimate["clauses"] > MAX_CLAUSES:
            raise ParamError(
                {
                    "_": (
                        f"This instance would need about {estimate['clauses']:,} clauses, above the "
                        f"limit of {MAX_CLAUSES:,}. Use smaller parameters (or raise "
                        "WIZSAT_MAX_CLAUSES if you have the memory)."
                    )
                }
            )

    def build(self, params: dict[str, Any]) -> ProblemInstance:
        params = self.resolve_seed(params)
        self.validate(params)
        self.check_size(params)
        instance = self.encode(params)
        instance.problem_type = self.key
        instance.params = dict(params)
        return instance

    def encode(self, params: dict[str, Any]) -> ProblemInstance:
        raise NotImplementedError

    # -- answers --------------------------------------------------------------

    def decode(self, instance: ProblemInstance, solution: dict[int, bool] | None) -> Any:
        return instance.decode_solution(solution)

    def check(self, instance: ProblemInstance, decoded: Any) -> list[str]:
        """Problem-level validation of a decoded answer; empty list means valid."""

        return []

    def expected_status(self, instance: ProblemInstance) -> str | None:
        """SAT/UNSAT when the generator guarantees it (planted formulas...)."""

        return None

    # -- presentation ---------------------------------------------------------

    def case_label(self, params: dict[str, Any]) -> str:
        parts = []
        for field in self.fields:
            if not field.short or not field.visible(params):
                continue
            value = params.get(field.name)
            if field.kind == "choice":
                parts.append(next((c.label for c in field.choices if c.value == value), str(value)))
            else:
                parts.append(f"{field.short}={format_value(value)}")
        return " ".join(parts)

    def instance_name(self, params: dict[str, Any]) -> str:
        label = self.case_label(params)
        return f"{self.title} ({label})" if label else self.title

    def describe(self, instance: ProblemInstance) -> list[dict[str, Any]]:
        """Key facts shown next to an instance, as [{"label", "value"}]."""

        return []

    def visual(self, instance: ProblemInstance) -> dict[str, Any]:
        """Input data for the frontend renderer (graph edges, givens, ...)."""

        return {}

    def preview(self, params: dict[str, Any]) -> dict[str, Any] | None:
        """Cheap picture of the input before encoding (None when not useful)."""

        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "summary": self.summary,
            "description": self.description,
            "category": self.category,
            "image": self.image,
            "result_view": self.result_view,
            "graph_based": self.graph_based,
            "fields": [field.to_dict() for field in self.fields],
        }


def fact(label: str, value: Any, hint: str = "") -> dict[str, Any]:
    item = {"label": label, "value": value}
    if hint:
        item["hint"] = hint
    return item


_REGISTRY: dict[str, ProblemSpec] = {}


def register_problem(cls: type[ProblemSpec]) -> type[ProblemSpec]:
    spec = cls()
    if not spec.key or not spec.title:
        raise ValueError(f"{cls.__name__} needs a key and a title")
    if spec.key in _REGISTRY:
        raise ValueError(f"Problem {spec.key} is already registered")
    if spec.result_view not in RESULT_VIEWS:
        raise ValueError(f"{spec.key}: unknown result view {spec.result_view}")
    check_field_order(spec.fields)
    _REGISTRY[spec.key] = spec
    return cls


def get_problem(key: str) -> ProblemSpec:
    try:
        return _REGISTRY[key]
    except KeyError:
        raise ValueError(f"Unknown problem: {key}") from None


def all_problems() -> list[ProblemSpec]:
    return list(_REGISTRY.values())
