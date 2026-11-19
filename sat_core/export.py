"""
CSV export of benchmark rows.

One format for every problem: base columns, one column per parameter, then
the statistics the catalog marks for the CSV (sat_core.solver_registry).
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Iterable

from sat_core.models import BenchmarkRow
from sat_core.solver_registry import STAT_SPECS


STAT_COLUMNS = tuple(spec.key for spec in STAT_SPECS if spec.csv)
BASE_COLUMNS = (
    "run",
    "case",
    "problem",
    "case_label",
    "repeat",
    "solver",
    "solver_label",
    "status",
    "expected",
    "verified",
    "elapsed",
    "cnf_variables",
    "cnf_clauses",
    "size_variables",
    "timeout",
    "rule",
)


def csv_columns(rows: Iterable[BenchmarkRow | dict[str, Any]]) -> tuple[list[str], list[str]]:
    """Parameter columns (in first-seen order) and all columns."""

    param_names: list[str] = []
    for row in rows:
        params = row.params if isinstance(row, BenchmarkRow) else row.get("params", {})
        for name in params:
            if name not in param_names:
                param_names.append(name)
    reserved = set(BASE_COLUMNS) | set(STAT_COLUMNS) | {"error"}
    headers = [f"param_{name}" if name in reserved else name for name in param_names]
    columns = list(BASE_COLUMNS[:4]) + headers + list(BASE_COLUMNS[4:]) + list(STAT_COLUMNS) + ["error"]
    return param_names, columns


def rows_to_csv(rows: list[BenchmarkRow | dict[str, Any]], run_label: str = "") -> str:
    """One CSV format for every problem: base columns, one column per parameter, stats."""

    param_names, columns = csv_columns(rows)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        data = row.to_dict() if isinstance(row, BenchmarkRow) else row
        label = data.get("run_label", run_label)
        params = data.get("params", {})
        stats = data.get("stats", {})
        values = [label, data["case_index"] + 1, data["problem"], data["case_label"]]
        values += [_csv_value(params.get(name, "")) for name in param_names]
        values += [
            data["repeat"],
            data["solver"],
            data["solver_label"],
            data["status"],
            data.get("expected") or "",
            "" if data.get("verified") is None else data["verified"],
            f"{data['elapsed']:.6f}",
            data["variables"],
            data["clauses"],
            data.get("size_variables", ""),
            "" if data.get("timeout") is None else data["timeout"],
            data.get("rule") or "",
        ]
        values += [stats.get(name, "") for name in STAT_COLUMNS]
        values.append(data.get("error") or "")
        writer.writerow(values)
    return buffer.getvalue()


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, separators=(",", ":"))
    if value is None:
        return ""
    return value
