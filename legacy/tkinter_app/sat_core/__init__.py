from sat_core.models import BenchmarkRow, ProblemInstance, SolveResult
from sat_core.runtime import RunEvent, RunToken


def __getattr__(name):
    if name in {"SOLVERS", "solve_clauses", "solve_problem"}:
        from sat_core import solver_runner

        return getattr(solver_runner, name)

    raise AttributeError(f"module 'sat_core' has no attribute {name!r}")

__all__ = [
    "BenchmarkRow",
    "ProblemInstance",
    "RunEvent",
    "RunToken",
    "SOLVERS",
    "SolveResult",
    "solve_clauses",
    "solve_problem",
]
