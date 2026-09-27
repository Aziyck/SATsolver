"""
Benchmark presets.

A preset is just a benchmark request (see sat_core.benchmark) with a name.
The UI loads a preset into the benchmark builder, where every value (grids,
seeds, solvers, timeouts and limit rules) stays editable. Case counts and
summaries are computed from the request itself, so they cannot drift from
what actually runs.

To add a preset, append a BenchmarkPreset to PRESETS.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sat_core.benchmark import DPLL_FALLBACK_RULE, parse_request


ALL_SOLVERS = [{"solver": "cdcl"}, {"solver": "dpll"}, {"solver": "walksat"}, {"solver": "probsat"}]


@dataclass(frozen=True)
class BenchmarkPreset:
    key: str
    title: str
    description: str
    request: dict[str, Any]
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        plan = parse_request(self.request)
        return {
            "key": self.key,
            "title": self.title,
            "description": self.description,
            "tags": list(self.tags),
            "request": self.request,
            "cases": len(plan.cases),
            "runs": plan.total_runs,
            "rules": [rule.describe() for rule in plan.rules],
        }


PRESETS: list[BenchmarkPreset] = [
    BenchmarkPreset(
        key="3sat_planted",
        title="Random 3-SAT A: Planted SAT",
        description=(
            "Satisfiable-by-construction formulas across sizes and densities. Compares complete "
            "and local-search solvers where every answer should be SAT."
        ),
        tags=("random 3-sat", "report"),
        request={
            "problems": ["random_3sat"],
            "segments": [
                {"variables": "50, 100, 150, 200", "ratio": "2.5, 3.5, 4.25, 5.5", "mode": "planted", "seed": "1..20"},
                {"variables": "300", "ratio": "3.5, 4.25, 5.5", "mode": "planted", "seed": "1..10"},
            ],
            "solvers": ALL_SOLVERS,
            "repeats": 1,
            "timeout": 30,
            "rules": [
                {"solver": "dpll", "action": "skip", "min_variables": 200},
                DPLL_FALLBACK_RULE,
            ],
            "seed": 1,
        },
    ),
    BenchmarkPreset(
        key="3sat_forced_unsat",
        title="Random 3-SAT B: Forced UNSAT",
        description=(
            "Formulas with a small unsatisfiable core. Only complete solvers can prove UNSAT, so "
            "this compares CDCL with the DPLL baseline."
        ),
        tags=("random 3-sat", "report"),
        request={
            "problems": ["random_3sat"],
            "segments": [
                {"variables": "50, 100", "ratio": "3.5, 4.25, 5.5", "mode": "forced_unsat", "seed": "1..10"},
                {"variables": "150, 200", "ratio": "4.25, 5.5", "mode": "forced_unsat", "seed": "1..10"},
            ],
            "solvers": [{"solver": "cdcl"}, {"solver": "dpll"}],
            "repeats": 1,
            "timeout": 30,
            "rules": [
                {"solver": "dpll", "action": "cap", "min_variables": 150, "seconds": 10},
                {"solver": "dpll", "action": "skip", "min_variables": 200},
                DPLL_FALLBACK_RULE,
            ],
            "seed": 1,
        },
    ),
    BenchmarkPreset(
        key="3sat_mixed",
        title="Random 3-SAT C: Mixed SAT/UNSAT",
        description=(
            "At the phase transition (ratio 4.25), each formula is planted SAT with the given "
            "probability and forced UNSAT otherwise. Local search is capped at 1 s because it "
            "cannot finish on UNSAT formulas."
        ),
        tags=("random 3-sat", "report"),
        request={
            "problems": ["random_3sat"],
            "segments": [
                {"variables": "100, 150, 200", "ratio": "4.25", "mode": "mixed", "sat_percent": "30, 50, 70", "seed": "1..30"},
            ],
            "solvers": ALL_SOLVERS,
            "repeats": 1,
            "timeout": 30,
            "rules": [
                {"solver": "walksat", "action": "cap", "min_variables": 0, "seconds": 1},
                {"solver": "probsat", "action": "cap", "min_variables": 0, "seconds": 1},
                DPLL_FALLBACK_RULE,
            ],
            "seed": 1,
        },
    ),
    BenchmarkPreset(
        key="3sat_phase_transition",
        title="Random 3-SAT phase transition",
        description=(
            "Plain random formulas from ratio 3 to 6. Plot the SAT share and the median time "
            "against the ratio to see the easy-hard-easy pattern peaking near 4.26."
        ),
        tags=("random 3-sat", "classic"),
        request={
            "problems": ["random_3sat"],
            "segments": [{"variables": "30, 50", "ratio": "3..6:0.25", "mode": "random", "seed": "1..10"}],
            "solvers": [{"solver": "cdcl"}],
            "repeats": 1,
            "timeout": 30,
            "rules": [DPLL_FALLBACK_RULE],
            "seed": 1,
        },
    ),
    BenchmarkPreset(
        key="cdcl_heuristics",
        title="CDCL branching heuristics",
        description="The same hard random formulas solved by CDCL with four branching heuristics.",
        tags=("solvers",),
        request={
            "problems": ["random_3sat"],
            "segments": [{"variables": "60", "ratio": "4.26", "mode": "random", "seed": "1..10"}],
            "solvers": [
                {"solver": "cdcl", "options": {"branching": "vsids"}, "label": "CDCL VSIDS"},
                {"solver": "cdcl", "options": {"branching": "moms"}, "label": "CDCL MOMS"},
                {"solver": "cdcl", "options": {"branching": "dlis"}, "label": "CDCL DLIS"},
                {"solver": "cdcl", "options": {"branching": "random", "random_seed": 1}, "label": "CDCL random"},
            ],
            "repeats": 1,
            "timeout": 30,
            "rules": [DPLL_FALLBACK_RULE],
            "seed": 1,
        },
    ),
    BenchmarkPreset(
        key="graph_suite",
        title="Graph suite: Clique vs Independent Set",
        description="Clique and Independent Set on exactly the same random graphs, for two target sizes.",
        tags=("graphs",),
        request={
            "problems": ["clique", "independent_set"],
            "segments": [{"graph_mode": "gnp", "nodes": "10, 20, 30", "probability": "0.3, 0.5", "target": "3, 4", "seed": "1..5"}],
            "solvers": [{"solver": "cdcl"}],
            "repeats": 1,
            "timeout": 30,
            "rules": [DPLL_FALLBACK_RULE],
            "seed": 1,
        },
    ),
    BenchmarkPreset(
        key="coloring_threshold",
        title="3-coloring threshold",
        description=(
            "Graph 3-coloring on G(n,d) graphs with growing average degree; random graphs stop "
            "being 3-colorable around d = 4.7."
        ),
        tags=("graphs", "classic"),
        request={
            "problems": ["graph_coloring"],
            "segments": [{"graph_mode": "gnd", "nodes": "20, 40", "average_degree": "2..6:0.5", "colors": 3, "seed": "1..5"}],
            "solvers": [{"solver": "cdcl"}],
            "repeats": 1,
            "timeout": 30,
            "rules": [DPLL_FALLBACK_RULE],
            "seed": 1,
        },
    ),
    BenchmarkPreset(
        key="sudoku_sizes",
        title="Sudoku sizes",
        description="Generated puzzles of growing size with fewer or more givens, CDCL against DPLL.",
        tags=("puzzles",),
        request={
            "problems": ["sudoku"],
            "segments": [{"source": "generated", "size": "4, 9, 16", "givens": "30, 50", "seed": "1..3"}],
            "solvers": [{"solver": "cdcl"}, {"solver": "dpll"}],
            "repeats": 1,
            "timeout": 30,
            "rules": [DPLL_FALLBACK_RULE],
            "seed": 1,
        },
    ),
]


def all_presets() -> list[BenchmarkPreset]:
    return list(PRESETS)


def get_preset(key: str) -> BenchmarkPreset:
    for preset in PRESETS:
        if preset.key == key:
            return preset
    raise ValueError(f"Unknown preset: {key}")
