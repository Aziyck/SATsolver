"""
Time the solvers on a fixed set of instances.

Prints one line per run: status, time, conflicts and conflicts per second.
Run it before and after changing a solver to see the effect:

    python scripts/solver_timings.py            # 60 s limit per run
    python scripts/solver_timings.py 10         # 10 s limit per run

The numbers in docs/guide/performance.md come from this script.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from problems import build_problem  # noqa: E402
from sat_core.solver_registry import run_solver  # noqa: E402

CASES = [
    ("3-SAT n=150 ratio 4.26", "random_3sat", {"variables": 150, "ratio": 4.26, "mode": "random", "seed": 3}, "cdcl", {}),
    ("3-SAT n=200 ratio 4.26", "random_3sat", {"variables": 200, "ratio": 4.26, "mode": "random", "seed": 1}, "cdcl", {}),
    ("3-SAT n=250 ratio 4.26", "random_3sat", {"variables": 250, "ratio": 4.26, "mode": "random", "seed": 2}, "cdcl", {}),
    ("3-SAT n=120 ratio 5.5", "random_3sat", {"variables": 120, "ratio": 5.5, "mode": "random", "seed": 4}, "cdcl", {}),
    ("Sudoku 16x16, 40% givens", "sudoku", {"source": "generated", "size": 16, "givens": 40, "seed": 1}, "cdcl", {}),
    ("Sudoku 25x25, 40% givens", "sudoku", {"source": "generated", "size": 25, "givens": 40, "seed": 1}, "cdcl", {}),
    ("40-Queens", "n_queens", {"size": 40}, "cdcl", {}),
    ("60-Queens", "n_queens", {"size": 60}, "cdcl", {}),
    ("3-coloring G(60, d=4.5)", "graph_coloring", {"graph_mode": "gnd", "nodes": 60, "average_degree": 4.5, "colors": 3, "seed": 2}, "cdcl", {}),
    ("3-SAT n=100, CDCL DLIS", "random_3sat", {"variables": 100, "ratio": 4.26, "mode": "random", "seed": 1}, "cdcl", {"branching": "dlis"}),
    ("3-SAT n=100, DPLL", "random_3sat", {"variables": 100, "ratio": 4.26, "mode": "random", "seed": 1}, "dpll", {}),
    ("25-Queens, DPLL", "n_queens", {"size": 25}, "dpll", {}),
]


def main() -> None:
    timeout = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
    print(f"{'instance':28} {'solver':6} {'status':8} {'time':>9} {'conflicts':>10} {'per second':>11}")
    for label, problem, params, solver, options in CASES:
        instance = build_problem(problem, params)
        result = run_solver(instance.clauses, solver, options, timeout=timeout)
        conflicts = result.stats.get("conflicts") or 0
        rate = conflicts / result.elapsed if result.elapsed else 0.0
        print(f"{label:28} {solver:6} {result.status:8} {result.elapsed:8.2f}s {conflicts:10} {rate:11.0f}", flush=True)


if __name__ == "__main__":
    main()
