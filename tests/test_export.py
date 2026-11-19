"""The CSV export, pinned byte for byte on fixed rows.

The timings of a real benchmark change on every run, so this test feeds
rows_to_csv fixed rows: both row forms, a parameter named like a reserved
column, list and dict parameters, and the empty-value cases. After a
deliberate format change, rerun with WIZSAT_RECORD_GOLDEN=1 to rewrite the
file.
"""

import os
import unittest
from pathlib import Path

from sat_core import benchmark
from sat_core.export import rows_to_csv
from sat_core.models import BenchmarkRow

GOLDEN = Path(__file__).parent / "fixtures" / "export_rows.golden.csv"


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
        },
    ]
    return objects + dicts


class ExportTests(unittest.TestCase):
    def test_fixed_rows_give_the_recorded_csv(self):
        text = rows_to_csv(fixed_rows(), run_label="J1")
        if os.environ.get("WIZSAT_RECORD_GOLDEN") == "1":
            GOLDEN.write_text(text, encoding="utf-8", newline="")
        self.assertEqual(text, GOLDEN.read_text(encoding="utf-8"))

    def test_the_benchmark_engine_has_no_csv_code(self):
        for name in ("rows_to_csv", "csv_columns", "STAT_COLUMNS", "BASE_COLUMNS", "csv", "io"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(benchmark, name))


if __name__ == "__main__":
    unittest.main()
