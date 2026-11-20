"""The CSV export, pinned byte for byte on fixed rows.

The timings of a real benchmark change on every run, so this test feeds
rows_to_csv fixed rows: both row forms, a parameter named like a reserved
column, list and dict parameters, and the empty-value cases. After a
deliberate format change, rerun with WIZSAT_RECORD_GOLDEN=1 to rewrite the
file.
"""

import csv
import io
import os
import unittest
from pathlib import Path

from sat_core import benchmark
from sat_core.export import rows_to_csv
from sat_core.models import BenchmarkRow

GOLDEN = Path(__file__).parent / "fixtures" / "export_rows.golden.csv"

MACHINE_COLUMNS = ["python", "cpu", "cores", "ram_gb", "os", "wizsat_commit"]
# What sat_core.environment.run_environment() reports, as it is stored on a job.
ENVIRONMENT = {
    "python_implementation": "CPython",
    "python_version": "3.11.15",
    "os": "Linux 6.8 (x86_64)",
    "cpu_model": "AMD Ryzen 7 5800U",
    "cpu_logical_cores": 16,
    "cpu_physical_cores": 8,
    "ram_total_gb": 15.5,
    "wizsat_version": "2.0.0",
    "git_commit": "9e11958",
    "git_dirty": False,
}
OTHER_ENVIRONMENT = {
    **ENVIRONMENT,
    "python_implementation": "PyPy",
    "python_version": "3.10.14",
    "cpu_model": "Apple M2",
    "git_dirty": True,
}


def fixed_rows() -> list:
    objects = [
        BenchmarkRow(
            index=0,
            case_index=0,
            problem="n_queens",
            case_label="size=4",
            params={"size": 4, "status": "x", "edges": [[1, 2], [2, 3]], "note": None},
            repeat=1,
            solver="cdcl",
            solver_label="CDCL",
            status="SAT",
            elapsed=0.0123456789,
            variables=16,
            clauses=80,
            size_variables=16,
            expected="SAT",
            verified=True,
            stats={"decisions": 5, "conflicts": 2, "propagations": 40},
            timeout=30.0,
            rule="cap CDCL at 10 s",
        ),
        BenchmarkRow(
            index=1,
            case_index=0,
            problem="n_queens",
            case_label="size=4",
            params={"size": 4, "status": "x", "edges": [[1, 2], [2, 3]], "note": None},
            repeat=1,
            solver="walksat",
            solver_label="WalkSAT",
            status="UNKNOWN",
            elapsed=1.5,
            variables=16,
            clauses=80,
            verified=None,
            stats={"tries": 3, "flips": 900, "best_unsatisfied": 1},
            error='gave up, "no luck"\nsecond line',
        ),
    ]
    dicts = [
        {
            "run_label": "J7",
            "case_index": 2,
            "problem": "clique",
            "case_label": "nodes=3",
            "params": {"nodes": 3, "error": "e", "layout": {"a": 1}},
            "repeat": 2,
            "solver": "dpll",
            "solver_label": "DPLL",
            "status": "TIMEOUT",
            "elapsed": 30.0,
            "variables": 6,
            "clauses": 20,
            "verified": False,
            "timeout": None,
            "environment": OTHER_ENVIRONMENT,
        },
    ]
    return objects + dicts


class ExportTests(unittest.TestCase):
    def test_fixed_rows_give_the_recorded_csv(self):
        text = rows_to_csv(fixed_rows(), run_label="J1", environment=ENVIRONMENT)
        if os.environ.get("WIZSAT_RECORD_GOLDEN") == "1":
            GOLDEN.write_text(text, encoding="utf-8", newline="")
        self.assertEqual(text, GOLDEN.read_text(encoding="utf-8"))

    def test_every_row_carries_the_machine_it_ran_on(self):
        table = list(csv.DictReader(io.StringIO(rows_to_csv(fixed_rows()[:2], environment=ENVIRONMENT))))

        self.assertEqual(len(table), 2)
        for row in table:
            self.assertEqual(
                [row[name] for name in MACHINE_COLUMNS],
                ["CPython 3.11.15", "AMD Ryzen 7 5800U", "16", "15.5", "Linux 6.8 (x86_64)", "9e11958"],
            )

    def test_a_row_that_carries_its_environment_keeps_it_in_a_combined_export(self):
        # /api/export.csv?jobs=... joins benchmarks from different machines: each row says its own.
        first, second = fixed_rows()[0], fixed_rows()[2]
        first = {**first.to_dict(), "run_label": "J1", "environment": ENVIRONMENT}
        second = {**second, "run_label": "J2"}  # carries OTHER_ENVIRONMENT
        table = list(csv.DictReader(io.StringIO(rows_to_csv([first, second]))))

        self.assertEqual([row["python"] for row in table], ["CPython 3.11.15", "PyPy 3.10.14"])
        self.assertEqual([row["cpu"] for row in table], ["AMD Ryzen 7 5800U", "Apple M2"])

    def test_a_tree_with_uncommitted_changes_is_marked_in_the_commit(self):
        # A timing from changed code is not the timing of that commit.
        table = list(csv.DictReader(io.StringIO(rows_to_csv(fixed_rows()[:1], environment=OTHER_ENVIRONMENT))))

        self.assertEqual(table[0]["wizsat_commit"], "9e11958-dirty")

    def test_a_benchmark_without_an_environment_gets_empty_machine_cells(self):
        # A benchmark stored before META-2 has no environment; so does one whose facts could not be read.
        unreadable = {key: None for key in ENVIRONMENT}
        for environment in (None, {}, unreadable):
            with self.subTest(environment=environment):
                table = list(csv.DictReader(io.StringIO(rows_to_csv(fixed_rows()[:2], environment=environment))))
                self.assertEqual(len(table), 2)
                for row in table:
                    self.assertEqual([row[name] for name in MACHINE_COLUMNS], [""] * len(MACHINE_COLUMNS))

    def test_a_missing_fact_leaves_only_its_cell_empty(self):
        partial = {**ENVIRONMENT, "cpu_model": None, "git_commit": None, "python_version": None}
        row = next(csv.DictReader(io.StringIO(rows_to_csv(fixed_rows()[:1], environment=partial))))

        self.assertEqual(row["python"], "CPython")
        self.assertEqual(row["cpu"], "")
        self.assertEqual(row["wizsat_commit"], "")
        self.assertEqual(row["cores"], "16")

    def test_a_parameter_named_like_a_machine_column_is_prefixed(self):
        rows = [{**fixed_rows()[2], "params": {"os": "x", "cores": 4}}]
        row = next(csv.DictReader(io.StringIO(rows_to_csv(rows))))

        self.assertEqual((row["param_os"], row["param_cores"]), ("x", "4"))
        self.assertEqual(row["os"], "Linux 6.8 (x86_64)")

    def test_the_machine_columns_come_after_every_older_column(self):
        # A reader that finds columns by position keeps working.
        header = next(csv.reader(io.StringIO(rows_to_csv(fixed_rows()))))

        self.assertEqual(header[-len(MACHINE_COLUMNS) :], MACHINE_COLUMNS)
        self.assertEqual(header[-len(MACHINE_COLUMNS) - 1], "error")

    def test_the_benchmark_engine_has_no_csv_code(self):
        for name in ("rows_to_csv", "csv_columns", "STAT_COLUMNS", "BASE_COLUMNS", "csv", "io"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(benchmark, name))


if __name__ == "__main__":
    unittest.main()
