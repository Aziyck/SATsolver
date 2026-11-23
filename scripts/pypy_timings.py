"""
Time the CPython-versus-PyPy table of docs/guide/performance.md through the app.

Every case goes through run_solver, the path the app uses for solve jobs and
benchmarks, once with WIZSAT_SOLVER_PYTHON unset (the solver runs in this
process) and once with it set to each interpreter named on the command line
(the solver runs in a child of it). Per case it prints, for each setting:

- "solver": the run time the result reports (without the child's start-up);
- "wall": the whole run_solver call (with it);
- the work count (conflicts or flips), which must match across interpreters,
  or the comparison is not like for like.

    python scripts/pypy_timings.py /path/to/pypy3          # 120 s limit per run
    python scripts/pypy_timings.py /path/to/pypy3 --limit 300 --repeat 3

Run it as the only heavy job on the machine, with the server stopped.
"""

from __future__ import annotations

import argparse
import os
import platform
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from problems import build_problem  # noqa: E402
from sat_core.environment import interpreter_facts  # noqa: E402
from sat_core.solver_registry import SOLVER_PYTHON_ENV, run_solver  # noqa: E402

PLANTED = {"mode": "planted", "ratio": 4.2, "seed": 1}
# (label, problem, params, solver, options), the table of the PyPy plan.
CASES = [
    ("CDCL, 3-SAT n=250 r=4.26 seed 2 (UNSAT)", "random_3sat", {"variables": 250, "ratio": 4.26, "mode": "random", "seed": 2}, "cdcl", {}),
    ("CDCL, Sudoku 25x25 40% seed 1", "sudoku", {"source": "generated", "size": 25, "givens": 40, "seed": 1}, "cdcl", {}),
    ("CDCL, 3-SAT n=200 r=4.26 seed 1", "random_3sat", {"variables": 200, "ratio": 4.26, "mode": "random", "seed": 1}, "cdcl", {}),
    ("DPLL, 25-Queens", "n_queens", {"size": 25}, "dpll", {}),
    (
        "WalkSAT, 3-SAT n=60 r=6 (UNSAT), 10 x 100,000 flips",
        "random_3sat",
        {"variables": 60, "ratio": 6, "mode": "random", "seed": 2},
        "walksat",
        {"random_seed": 1, "max_tries": 10, "max_flips": 100000},
    ),
    ("WalkSAT, planted n=5000 r=4.2", "random_3sat", {"variables": 5000, **PLANTED}, "walksat", {"random_seed": 1}),
    ("ProbSAT, planted n=5000 r=4.2", "random_3sat", {"variables": 5000, **PLANTED}, "probsat", {"random_seed": 1}),
    ("CDCL, 3-SAT n=150 r=4.26 seed 3", "random_3sat", {"variables": 150, "ratio": 4.26, "mode": "random", "seed": 3}, "cdcl", {}),
    ("CDCL, Sudoku 16x16 40% seed 1", "sudoku", {"source": "generated", "size": 16, "givens": 40, "seed": 1}, "cdcl", {}),
    ("CDCL, 40-Queens", "n_queens", {"size": 40}, "cdcl", {}),
    ("DPLL, 3-SAT n=100 r=4.26 seed 1", "random_3sat", {"variables": 100, "ratio": 4.26, "mode": "random", "seed": 1}, "dpll", {}),
]


def measure(clauses, solver, options, python: str | None, limit: float, repeat: int):
    """Median solver time and wall time over `repeat` runs, plus status and work count."""

    if python:
        os.environ[SOLVER_PYTHON_ENV] = python
    else:
        os.environ.pop(SOLVER_PYTHON_ENV, None)
    solver_times, wall_times, result = [], [], None
    for _ in range(repeat):
        started = time.perf_counter()
        result = run_solver(clauses, solver, dict(options), timeout=limit)
        wall_times.append(time.perf_counter() - started)
        solver_times.append(result.elapsed)
    work = result.stats.get("conflicts", result.stats.get("flips"))
    return statistics.median(solver_times), statistics.median(wall_times), result.status, work


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("interpreters", nargs="+", help="paths of the interpreters to run the solvers in")
    parser.add_argument("--limit", type=float, default=120.0, help="time limit per run in seconds (default 120)")
    parser.add_argument("--repeat", type=int, default=1, help="runs per case and setting, median reported (default 1)")
    args = parser.parse_args()

    settings = [("CPython (in process)", None)]
    for path in args.interpreters:
        facts = interpreter_facts(path)
        settings.append((f"{facts['python_implementation']} {facts['python_version']} (child)", path))
    print(f"parent: {platform.python_implementation()} {platform.python_version()}, "
          f"limit {args.limit:g} s, median of {args.repeat}")
    for label, case_problem, params, solver, options in CASES:
        clauses = build_problem(case_problem, params).clauses
        print(label, flush=True)
        for name, python in settings:
            solver_time, wall, status, work = measure(clauses, solver, options, python, args.limit, args.repeat)
            print(f"    {name:28} {status:8} solver {solver_time:8.2f} s  wall {wall:8.2f} s  work {work}", flush=True)


if __name__ == "__main__":
    main()
