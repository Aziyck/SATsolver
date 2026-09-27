"""
Random 3-SAT formulas.

A formula has n variables and m = round(n * ratio) clauses of three distinct
variables with random signs. Around ratio 4.26 random formulas switch from
mostly satisfiable to mostly unsatisfiable, and are hardest to decide there.

Modes:
- planted: pick a hidden assignment first and keep only clauses it
  satisfies, so the formula is guaranteed SAT;
- forced_unsat: add all 8 sign patterns over 3 variables (a tiny
  unsatisfiable core), so the formula is guaranteed UNSAT;
- mixed: each formula is planted with probability "SAT share", otherwise
  forced UNSAT (useful for mixed benchmarks with a known answer);
- random: plain random clauses; the answer is unknown in advance.
"""

from __future__ import annotations

from typing import Any

from problems.assignment import assignment_bits
from problems.base import ProblemSpec, fact, register_problem
from sat_core.models import STATUS_SAT, STATUS_UNSAT, ProblemInstance
from sat_core.params import Choice, ParamError, ParamField, format_value
from sat_core.seeds import rng_for


MODES = (
    Choice("planted", "Planted SAT", "Satisfiable by construction."),
    Choice("forced_unsat", "Forced UNSAT", "Contains an 8-clause unsatisfiable core."),
    Choice("mixed", "Mixed SAT/UNSAT", "Planted with probability SAT share, otherwise forced UNSAT."),
    Choice("random", "Random", "Unconstrained random clauses; SAT or UNSAT is not known in advance."),
)
MODE_LABELS = {choice.value: choice.label for choice in MODES}


def clause_count(variables: int, ratio: float) -> int:
    return max(1, round(variables * ratio))


def _random_clause(rng, variables: int) -> list[int]:
    chosen = rng.sample(range(1, variables + 1), 3)
    return [variable if rng.random() < 0.5 else -variable for variable in chosen]


def _satisfied(clause: list[int], assignment: dict[int, bool]) -> bool:
    return any(assignment[abs(lit)] == (lit > 0) for lit in clause)


def unsat_core(variables: list[int]) -> list[list[int]]:
    a, b, c = variables
    return [
        [a * sa, b * sb, c * sc]
        for sa in (1, -1)
        for sb in (1, -1)
        for sc in (1, -1)
    ]


def generate_formula(
    variables: int,
    ratio: float,
    mode: str,
    sat_percent: float,
    seed: int,
    limit: int | None = None,
) -> tuple[list[list[int]], dict[str, Any]]:
    """Generate the formula; limit stops early (the first clauses are identical either way)."""

    clauses_wanted = clause_count(variables, ratio)
    target = clauses_wanted if limit is None else min(limit, clauses_wanted)
    rng = rng_for("3sat", variables, clauses_wanted, mode, sat_percent if mode == "mixed" else None, seed)
    selected = mode
    if mode == "mixed":
        selected = "planted" if rng.random() < sat_percent / 100 else "forced_unsat"

    planted = {variable: rng.random() < 0.5 for variable in range(1, variables + 1)}
    clauses: list[list[int]] = []
    if selected == "forced_unsat":
        clauses.extend(unsat_core(rng.sample(range(1, variables + 1), 3)))
    while len(clauses) < target:
        clause = _random_clause(rng, variables)
        if selected != "planted" or _satisfied(clause, planted):
            clauses.append(clause)

    metadata = {
        "variables": variables,
        "clauses_requested": clauses_wanted,
        "ratio": ratio,
        "mode": mode,
        "selected_mode": selected,
        "sat_percent": sat_percent if mode == "mixed" else None,
        "seed": seed,
    }
    return clauses, metadata


@register_problem
class Random3SAT(ProblemSpec):
    key = "random_3sat"
    title = "Random 3-SAT"
    summary = "Random formulas with three literals per clause; hardest near 4.26 clauses per variable."
    description = (
        "m = round(n x ratio) clauses, each over three distinct variables with random signs. "
        "Planted formulas are SAT by construction and forced ones UNSAT; plain random formulas "
        "show the SAT/UNSAT phase transition around ratio 4.26."
    )
    category = "logic"
    image = "3sat.jpg"
    result_view = "assignment"
    fields = (
        ParamField("variables", "Variables n", "int", default=50, minimum=3, maximum=100_000, sweepable=True, short="n"),
        ParamField(
            "ratio",
            "Clauses per variable",
            "float",
            default=4.26,
            minimum=0.01,
            maximum=20.0,
            step=0.05,
            sweepable=True,
            short="r",
            help="m = round(n x ratio). The phase transition is near 4.26.",
        ),
        ParamField("mode", "Formula", "choice", default="planted", choices=MODES, sweepable=True, short="mode"),
        ParamField(
            "sat_percent",
            "SAT share",
            "float",
            default=50.0,
            minimum=0.0,
            maximum=100.0,
            step=5.0,
            unit="%",
            sweepable=True,
            show_if=(("mode", ("mixed",)),),
            short="sat",
            help="Probability that a formula is planted SAT (otherwise forced UNSAT).",
        ),
        ParamField(
            "seed",
            "Seed",
            "seed",
            default=1,
            optional=True,
            sweepable=True,
            placeholder="random",
            short="seed",
            help="Same parameters and seed give the same formula.",
        ),
    )

    def validate(self, params: dict[str, Any]) -> None:
        clauses = clause_count(params["variables"], params["ratio"])
        needs_core = params["mode"] == "forced_unsat" or (params["mode"] == "mixed" and params["sat_percent"] < 100)
        if needs_core and clauses < 8:
            raise ParamError({"ratio": f"forced UNSAT formulas need at least 8 clauses (currently {clauses})"})

    def estimate(self, params: dict[str, Any]) -> dict[str, int]:
        return {"variables": params["variables"], "clauses": clause_count(params["variables"], params["ratio"])}

    def case_label(self, params: dict[str, Any]) -> str:
        parts = [f"n={params['variables']}", f"r={format_value(params['ratio'])}", MODE_LABELS[params["mode"]]]
        if params["mode"] == "mixed":
            parts.append(f"sat={format_value(params['sat_percent'])}%")
        parts.append(f"seed={format_value(params.get('seed'))}")
        return " ".join(parts)

    def encode(self, params: dict[str, Any]) -> ProblemInstance:
        variables = params["variables"]
        clauses, metadata = generate_formula(variables, params["ratio"], params["mode"], params["sat_percent"], params["seed"])
        return ProblemInstance(
            name=self.instance_name(params),
            problem_type=self.key,
            clauses=clauses,
            metadata=metadata,
            decoder=lambda solution: assignment_bits(solution, variables),
        )

    def expected_status(self, instance: ProblemInstance) -> str | None:
        selected = instance.metadata["selected_mode"]
        if selected == "planted":
            return STATUS_SAT
        if selected == "forced_unsat":
            return STATUS_UNSAT
        return None

    def describe(self, instance: ProblemInstance) -> list[dict[str, Any]]:
        metadata = instance.metadata
        facts = [
            fact("Variables n", metadata["variables"]),
            fact("Clauses m", len(instance.clauses)),
            fact("Ratio m/n", round(len(instance.clauses) / metadata["variables"], 3)),
            fact("Formula", MODE_LABELS[metadata["mode"]]),
        ]
        if metadata["mode"] == "mixed":
            facts.append(fact("SAT share", f"{metadata['sat_percent']:g}%"))
            facts.append(fact("This formula", MODE_LABELS[metadata["selected_mode"]]))
        facts.append(fact("Seed", metadata["seed"]))
        return facts

    def preview(self, params: dict[str, Any]) -> dict[str, Any] | None:
        params = self.resolve_seed(params)
        sample, metadata = generate_formula(
            params["variables"], params["ratio"], params["mode"], params["sat_percent"], params["seed"], limit=12
        )
        clauses = metadata["clauses_requested"]
        return {
            "variables": params["variables"],
            "clauses": clauses,
            "ratio": clauses / params["variables"],
            "sample": sample,
            "selected_mode": metadata["selected_mode"],
            "seed": params["seed"],
        }

    def visual(self, instance: ProblemInstance) -> dict[str, Any]:
        return {
            "variables": instance.metadata["variables"],
            "clauses": len(instance.clauses),
            "ratio": len(instance.clauses) / instance.metadata["variables"],
            "sample": instance.clauses[:12],
        }
