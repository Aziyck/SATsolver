"""
CSV export of benchmark rows.

One format for every problem: base columns, one column per parameter, the
statistics the catalog marks for the CSV (sat_core.solver_registry), the error
message and last the machine the run happened on.
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
# After "error", so no column that was there before moves. One set of cells per
# row, not header comments: the file stays a valid CSV, and benchmarks from
# different machines can share it (docs/plans/done/run-metadata.md).
MACHINE_COLUMNS = ("python", "cpu", "cores", "ram_gb", "os", "wizsat_commit")


def csv_columns(rows: Iterable[BenchmarkRow | dict[str, Any]]) -> tuple[list[str], list[str]]:
    """Parameter columns (in first-seen order) and all columns."""

    param_names: list[str] = []
    for row in rows:
        params = row.params if isinstance(row, BenchmarkRow) else row.get("params", {})
        for name in params:
            if name not in param_names:
                param_names.append(name)
    reserved = set(BASE_COLUMNS) | set(STAT_COLUMNS) | set(MACHINE_COLUMNS) | {"error"}
    headers = [f"param_{name}" if name in reserved else name for name in param_names]
    columns = list(BASE_COLUMNS[:4]) + headers + list(BASE_COLUMNS[4:]) + list(STAT_COLUMNS) + ["error"] + list(MACHINE_COLUMNS)
    return param_names, columns


def rows_to_csv(
    rows: list[BenchmarkRow | dict[str, Any]], run_label: str = "", environment: dict[str, Any] | None = None
) -> str:
    """One CSV format for every problem: base columns, one column per parameter, stats, machine.

    `run_label` and `environment` (a job's run_environment()) apply to every row
    that does not carry its own "run_label" or "environment" key; a combined
    export of several jobs sets them per row.
    """

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
        values += machine_cells(data.get("environment", environment))
        writer.writerow(values)
    return buffer.getvalue()


def machine_cells(environment: dict[str, Any] | None) -> list[Any]:
    """The MACHINE_COLUMNS cells of a job's environment; a fact that is not there is an empty cell.

    `environment` is None for a benchmark stored before the environment was
    recorded, and a fact inside it is None when it could not be read.
    """

    env = environment or {}
    interpreter = " ".join(str(env[key]) for key in ("python_implementation", "python_version") if env.get(key))
    commit = env.get("git_commit")
    if commit and env.get("git_dirty"):
        # A timing from changed code is not the timing of that commit.
        commit += "-dirty"
    cells = [
        interpreter,
        env.get("cpu_model"),
        env.get("cpu_logical_cores"),
        env.get("ram_total_gb"),
        env.get("os"),
        commit,
    ]
    return ["" if cell is None else cell for cell in cells]


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, separators=(",", ":"))
    if value is None:
        return ""
    return value
