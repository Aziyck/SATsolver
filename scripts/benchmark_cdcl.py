"""
Command-line smoke benchmark.

Runs every registered solver on the example DIMACS files and on a few
generated instances, and prints one line per run. Useful after changing a
solver or the DIMACS code:

    python scripts/benchmark_cdcl.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from problems import build_problem  # noqa: E402
from sat_core.dimacs import load_dimacs  # noqa: E402
from sat_core.solver_registry import all_solvers, run_solver  # noqa: E402
from sat_core.verify import check_assignment  # noqa: E402


FILES = [
    "input/examples/sudoku_4x4.cnf",
    "input/examples/graph_coloring/gc_n10_p10_k2.cnf",
]
GENERATED = [
    ("n_queens", {"size": 12}),
    ("random_3sat", {"variables": 50, "ratio": 4.26, "mode": "planted", "seed": 1}),
    ("graph_coloring", {"graph_mode": "gnd", "nodes": 30, "average_degree": 4, "colors": 3, "seed": 1}),
]
TIMEOUT = 10.0


def cases():
    for path in FILES:
        yield path, load_dimacs(ROOT / path)
    for key, params in GENERATED:
        instance = build_problem(key, params)
        yield instance.name, instance.clauses


def main() -> None:
    print(f"{'CASE':58} {'SOLVER':8} {'STATUS':8} {'TIME':>10}  VERIFIED  STATS")
    for name, clauses in cases():
        for spec in all_solvers():
            options = {"random_seed": 1} if any(field.name == "random_seed" for field in spec.fields) else None
            result = run_solver(clauses, spec.key, options, timeout=TIMEOUT)
            verified = "yes" if result.status == "SAT" and check_assignment(clauses, result.solution) else "-"
            stats = ", ".join(
                f"{key}={result.stats[key]}"
                for key in ("decisions", "conflicts", "flips")
                if key in result.stats
            )
            print(f"{name[:58]:58} {spec.title:8} {result.status:8} {result.elapsed:9.4f}s  {verified:8}  {stats}")


if __name__ == "__main__":
    main()
