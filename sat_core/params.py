"""
Declarative parameter schemas.

Problems and solvers describe their inputs as a tuple of ParamField objects.
The same description is used to:

- validate and coerce raw values coming from the web UI or from tests;
- expand benchmark sweeps, where a sweepable field may hold a list or a
  range such as "1..20" instead of a single value;
- render forms in the frontend (see ParamField.to_dict).

Fields can depend on earlier fields through show_if. A hidden field is not
validated and falls back to its default, so for example the probability of a
G(n,p) graph is ignored while the graph mode is "manual".
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Iterable


SCALAR_KINDS = {"int", "float", "bool", "choice", "text", "seed"}
STRUCTURED_KINDS = {"edges", "sudoku_grid", "cnf"}
KINDS = SCALAR_KINDS | STRUCTURED_KINDS

MAX_SWEEP_VALUES = 10_000
MAX_CASES = 100_000


class ParamError(ValueError):
    """Validation error with one message per field name."""

    def __init__(self, errors: dict[str, str]):
        self.errors = dict(errors)
        super().__init__("; ".join(f"{name}: {message}" for name, message in self.errors.items()))


@dataclass(frozen=True)
class Choice:
    value: str
    label: str
    help: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"value": self.value, "label": self.label, "help": self.help}


@dataclass(frozen=True)
class ParamField:
    """
    One input parameter.

    kind is one of:
    - int, float, bool, choice, text
    - seed: optional non-negative integer used for random generation
    - edges: undirected edge list, "1-2, 2-3" or [[1, 2], [2, 3]]
    - sudoku_grid: square grid of ints, 0 means empty
    - cnf: DIMACS text, or {"name": ..., "text": ...}
    """

    name: str
    label: str
    kind: str
    default: Any = None
    help: str = ""
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    choices: tuple[Choice, ...] = ()
    optional: bool = False
    sweepable: bool = False
    group: str = ""
    show_if: tuple[tuple[str, tuple[Any, ...]], ...] = ()
    placeholder: str = ""
    unit: str = ""
    advanced: bool = False
    short: str = ""

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"Unknown parameter kind {self.kind!r} for {self.name}")
        if self.kind == "choice" and not self.choices:
            raise ValueError(f"Choice parameter {self.name} needs choices")

    def visible(self, values: dict[str, Any]) -> bool:
        return all(values.get(other) in allowed for other, allowed in self.show_if)

    def choice_values(self) -> tuple[str, ...]:
        return tuple(choice.value for choice in self.choices)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "kind": self.kind,
            "default": _json_default(self.default),
            "help": self.help,
            "min": self.minimum,
            "max": self.maximum,
            "step": self.step,
            "choices": [choice.to_dict() for choice in self.choices],
            "optional": self.optional,
            "sweepable": self.sweepable,
            "group": self.group,
            "show_if": {other: list(allowed) for other, allowed in self.show_if},
            "placeholder": self.placeholder,
            "unit": self.unit,
            "advanced": self.advanced,
            "short": self.short,
        }


def _json_default(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_json_default(item) for item in value]
    return value


def check_field_order(fields: Iterable[ParamField]) -> None:
    """show_if may only reference fields declared earlier (keeps expansion simple)."""

    seen: set[str] = set()
    for field in fields:
        for other, _allowed in field.show_if:
            if other not in seen:
                raise ValueError(f"{field.name} depends on {other}, which must be declared before it")
        if field.name in seen:
            raise ValueError(f"Duplicate parameter name {field.name}")
        seen.add(field.name)


# ---------------------------------------------------------------------------
# Scalar coercion
# ---------------------------------------------------------------------------

def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _check_range(field: ParamField, number: float) -> None:
    if field.minimum is not None and number < field.minimum:
        raise ValueError(f"must be at least {_fmt(field.minimum)}")
    if field.maximum is not None and number > field.maximum:
        raise ValueError(f"must be at most {_fmt(field.maximum)}")


def _fmt(number: float) -> str:
    return f"{number:g}" if isinstance(number, float) else str(number)


def _to_int(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("must be a whole number")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError("must be a whole number")
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        try:
            return int(text)
        except ValueError:
            try:
                number = float(text)
            except ValueError:
                raise ValueError(f"{text!r} is not a whole number") from None
            if not number.is_integer():
                raise ValueError(f"{text!r} is not a whole number") from None
            return int(number)
    raise ValueError("must be a whole number")


def _to_float(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("must be a number")
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError:
            raise ValueError(f"{value.strip()!r} is not a number") from None
    else:
        raise ValueError("must be a number")
    if not math.isfinite(number):
        raise ValueError("must be a finite number")
    return number


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("true", "yes", "on", "1"):
            return True
        if text in ("false", "no", "off", "0"):
            return False
    raise ValueError("must be true or false")


def parse_edge_list(value: Any) -> list[tuple[int, int]]:
    """Parse "1-2, 2-3", "1 2\\n2 3" or [[1, 2], [2, 3]] into sorted unique pairs."""

    pairs: list[tuple[int, int]] = []
    if isinstance(value, str):
        for raw in re.split(r"[,;\n]+", value):
            item = raw.strip()
            if not item:
                continue
            parts = re.split(r"\s*-\s*|\s+", item)
            parts = [part for part in parts if part]
            if len(parts) != 2:
                raise ValueError(f"invalid edge {item!r}; use pairs like 1-2")
            pairs.append((_to_int(parts[0]), _to_int(parts[1])))
    elif isinstance(value, (list, tuple)):
        for item in value:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                raise ValueError(f"invalid edge {item!r}; use pairs like [1, 2]")
            pairs.append((_to_int(item[0]), _to_int(item[1])))
    else:
        raise ValueError("must be an edge list")

    edges = set()
    for u, v in pairs:
        if u < 1 or v < 1:
            raise ValueError(f"edge {u}-{v}: nodes are numbered from 1")
        if u == v:
            raise ValueError(f"edge {u}-{v}: self loops are not supported")
        edges.add((min(u, v), max(u, v)))
    return sorted(edges)


def parse_sudoku_grid(value: Any) -> list[list[int]]:
    """Accept a list of rows or a string of digits/dots (4x4 or 9x9 only)."""

    if isinstance(value, str):
        cells = [char for char in value if not char.isspace() and char not in ",|"]
        size = int(round(math.sqrt(len(cells))))
        if size * size != len(cells) or size not in (4, 9):
            raise ValueError("a text puzzle needs 16 or 81 cells (digits, 0 or . for empty)")
        grid = []
        for row in range(size):
            row_values = []
            for char in cells[row * size:(row + 1) * size]:
                if char in ".0_":
                    row_values.append(0)
                elif char.isdigit():
                    row_values.append(int(char))
                else:
                    raise ValueError(f"invalid cell {char!r}")
            grid.append(row_values)
        value = grid

    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("must be a square grid")
    size = len(value)
    root = int(round(math.sqrt(size)))
    if root * root != size:
        raise ValueError("grid size must be a perfect square (4, 9, 16, 25)")
    grid = []
    for row in value:
        if not isinstance(row, (list, tuple)) or len(row) != size:
            raise ValueError("grid must be square")
        row_values = []
        for cell in row:
            number = 0 if _is_blank(cell) else _to_int(cell)
            if number < 0 or number > size:
                raise ValueError(f"cell values must be between 0 and {size}")
            row_values.append(number)
        grid.append(row_values)
    return grid


def parse_cnf_value(value: Any) -> dict[str, str]:
    if isinstance(value, str):
        return {"name": "", "text": value}
    if isinstance(value, dict) and isinstance(value.get("text"), str):
        return {"name": str(value.get("name") or ""), "text": value["text"]}
    raise ValueError("must be DIMACS text")


def coerce(field: ParamField, value: Any) -> Any:
    """Validate one (non-list) value for a field and return its canonical form."""

    if _is_blank(value) and field.kind not in ("text", "cnf"):
        if field.optional or field.kind == "seed":
            return None
        raise ValueError("is required")

    kind = field.kind
    if kind == "int":
        number = _to_int(value)
        _check_range(field, number)
        if field.choices and str(number) not in field.choice_values():
            raise ValueError(f"must be one of: {', '.join(field.choice_values())}")
        return number
    if kind == "seed":
        number = _to_int(value)
        if number < 0:
            raise ValueError("must be a non-negative integer")
        return number
    if kind == "float":
        number = _to_float(value)
        _check_range(field, number)
        return number
    if kind == "bool":
        return _to_bool(value)
    if kind == "choice":
        text = str(value)
        if text not in field.choice_values():
            options = ", ".join(field.choice_values())
            raise ValueError(f"must be one of: {options}")
        return text
    if kind == "text":
        return "" if value is None else str(value)
    if kind == "edges":
        return parse_edge_list("" if value is None else value)
    if kind == "sudoku_grid":
        return parse_sudoku_grid(value)
    if kind == "cnf":
        return parse_cnf_value("" if value is None else value)
    raise ValueError(f"unsupported kind {kind}")


# ---------------------------------------------------------------------------
# Sweep values
# ---------------------------------------------------------------------------

_RANGE_RE = re.compile(r"^\s*(-?[\d.eE+-]+)\s*\.\.\s*(-?[\d.eE+-]+)\s*(?::\s*(-?[\d.eE+-]+))?\s*$")


def parse_number_list(text: str, integer: bool) -> list[float | int]:
    """
    Parse "10, 20, 30", "1..20" (inclusive) or "0.1..0.5:0.1" into numbers.

    Items may be mixed: "1..3, 10" gives [1, 2, 3, 10].
    """

    values: list[float | int] = []
    normalized = re.sub(r"\s*(\.\.|:)\s*", r"\1", text.strip())
    for item in re.split(r"[,;\s]+", normalized):
        item = item.strip()
        if not item:
            continue
        match = _RANGE_RE.match(item)
        if match:
            start_text, stop_text, step_text = match.groups()
            if integer:
                start, stop = _to_int(start_text), _to_int(stop_text)
                step = _to_int(step_text) if step_text else 1
            else:
                start, stop = _to_float(start_text), _to_float(stop_text)
                step = _to_float(step_text) if step_text else 1.0
            if step <= 0:
                raise ValueError(f"range {item!r} needs a positive step")
            if stop < start:
                raise ValueError(f"range {item!r} ends before it starts")
            count = int(math.floor((stop - start) / step + 1e-9)) + 1
            if len(values) + count > MAX_SWEEP_VALUES:
                raise ValueError(f"too many values (limit {MAX_SWEEP_VALUES})")
            for index in range(count):
                number = start + index * step
                values.append(int(number) if integer else round(number, 10))
        else:
            values.append(_to_int(item) if integer else _to_float(item))
        if len(values) > MAX_SWEEP_VALUES:
            raise ValueError(f"too many values (limit {MAX_SWEEP_VALUES})")
    return values


def sweep_candidates(field: ParamField, raw: Any, allow_sweep: bool) -> list[Any]:
    """Return the list of candidate values for a field (one item when not swept)."""

    if isinstance(raw, (list, tuple)) and field.kind not in ("edges", "sudoku_grid"):
        if not allow_sweep:
            raise ValueError("needs a single value")
        if not field.sweepable:
            raise ValueError("cannot be swept")
        items = list(raw)
        if not items:
            raise ValueError("needs at least one value")
        if len(items) > MAX_SWEEP_VALUES:
            raise ValueError(f"too many values (limit {MAX_SWEEP_VALUES})")
        expanded: list[Any] = []
        for item in items:
            if isinstance(item, str) and field.kind in ("int", "float", "seed") and ".." in item:
                expanded.extend(parse_number_list(item, field.kind != "float"))
            else:
                expanded.append(item)
        return [coerce(field, item) for item in expanded]

    if (
        allow_sweep
        and field.sweepable
        and isinstance(raw, str)
        and field.kind in ("int", "float", "seed")
        and re.search(r"[,;]|\.\.", raw)
    ):
        numbers = parse_number_list(raw, field.kind != "float")
        if not numbers:
            raise ValueError("needs at least one value")
        return [coerce(field, number) for number in numbers]

    if (
        allow_sweep
        and field.sweepable
        and isinstance(raw, str)
        and field.kind == "choice"
        and "," in raw
    ):
        return [coerce(field, item.strip()) for item in raw.split(",") if item.strip()]

    return [coerce(field, raw)]


def expand_params(
    fields: Iterable[ParamField],
    raw: dict[str, Any] | None,
    *,
    allow_sweep: bool = False,
) -> list[dict[str, Any]]:
    """
    Validate raw values and expand sweeps into concrete parameter dicts.

    Every returned dict contains every field. Hidden fields get their
    default. The cartesian product is taken in field order, so earlier
    fields vary slowest.
    """

    fields = tuple(fields)
    raw = dict(raw or {})
    known = {field.name for field in fields}
    unknown = [name for name in raw if name not in known]
    if unknown:
        raise ParamError({name: "unknown parameter" for name in unknown})

    errors: dict[str, str] = {}
    cache: dict[str, list[Any]] = {}

    def candidates(field: ParamField) -> list[Any]:
        if field.name not in cache:
            value = raw.get(field.name, field.default)
            try:
                cache[field.name] = sweep_candidates(field, value, allow_sweep)
            except ValueError as exc:
                errors[field.name] = str(exc)
                cache[field.name] = []
        return cache[field.name]

    cases: list[dict[str, Any]] = [{}]
    for field in fields:
        next_cases: list[dict[str, Any]] = []
        for case in cases:
            if not field.visible(case):
                next_cases.append({**case, field.name: _json_default(field.default)})
                continue
            values = candidates(field)
            if not values:
                # Invalid input: keep going with the default so that errors in
                # later fields are reported too (the ParamError is raised below).
                values = [_json_default(field.default)]
            for value in values:
                next_cases.append({**case, field.name: value})
        cases = next_cases
        if len(cases) > MAX_CASES:
            raise ParamError({field.name: f"sweep produces more than {MAX_CASES} cases"})

    if errors:
        raise ParamError(errors)
    return cases


def parse_params(fields: Iterable[ParamField], raw: dict[str, Any] | None) -> dict[str, Any]:
    """Validate a single parameter set (no sweeps)."""

    return expand_params(fields, raw, allow_sweep=False)[0]


def product_size(lists: Iterable[list[Any]]) -> int:
    total = 1
    for values in lists:
        total *= len(values)
    return total


def format_value(value: Any) -> str:
    """Short human-readable form of a parameter value (for labels)."""

    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if value is None:
        return "-"
    return str(value)


__all__ = [
    "Choice",
    "ParamError",
    "ParamField",
    "check_field_order",
    "coerce",
    "expand_params",
    "format_value",
    "parse_edge_list",
    "parse_number_list",
    "parse_params",
    "parse_sudoku_grid",
    "product_size",
]
