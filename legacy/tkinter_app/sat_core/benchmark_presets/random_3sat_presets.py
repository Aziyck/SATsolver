from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable


# Add new Random 3-SAT benchmark presets in this file, near the bottom.
# For the common case, create one Random3SATPreset with a Random3SATPresetSpec:
#
# register_random_3sat_preset(
#     Random3SATPreset(
#         name="Preset D: Small Smoke SAT",
#         spec=Random3SATPresetSpec(
#             variables=(20, 50),
#             ratios=(3.5, 4.25),
#             seeds=range_seeds(1, 5),  # inclusive helper: 1,2,3,4,5
#             formula_mode="Planted SAT",
#         ),
#         default_solvers=("CDCL", "DPLL", "WalkSAT", "ProbSAT"),
#         ui_values=Random3SATPresetUiValues(
#             variables="20,50",
#             ratios="3.5,4.25",
#             seed="1",
#             formula_mode="Planted SAT",
#             sat_percentage="",
#         ),
#         summary="20 cases, default solvers: CDCL, DPLL, WalkSAT, ProbSAT.",
#     )
# )
#
# Use case_builder only when the preset cannot be described as a simple matrix,
# for example when seed ranges depend on the variable count.
#
# Solver timeout/skip policy for presets:
# - CDCL, WalkSAT, and ProbSAT use the UI benchmark timeout unchanged.
# - DPLL can be skipped or capped per preset below.
# - A skipped DPLL row is exported as SKIPPED; it is not executed.
# - A capped DPLL row is executed, but with min(UI timeout, preset cap).

RANDOM_3SAT_PRESET_CUSTOM = "Custom"
RANDOM_3SAT_PRESET_A = "Preset A: Planted SAT"
RANDOM_3SAT_PRESET_B = "Preset B: Forced UNSAT"
RANDOM_3SAT_PRESET_C = "Preset C: Mixed SAT/UNSAT"

# Fallback policy used by presets that do not have a more specific DPLL rule.
DPLL_TIMEOUT_CAP_MIN_VARIABLES = 200
DPLL_TIMEOUT_CAP_SECONDS = 10.0
DPLL_SKIP_ABOVE_VARIABLES: int | None = None

PRESET_A_VARIABLES = (50, 100, 150, 200, 300)
PRESET_A_RATIOS = (2.5, 3.5, 4.25, 5.5)
PRESET_A_RATIOS_FOR_300 = (3.5, 4.25, 5.5)
PRESET_A_DPLL_SKIP_MIN_VARIABLES = 200

PRESET_B_VARIABLES = (50, 100, 150, 200)
PRESET_B_RATIOS = (3.5, 4.25, 5.5)
PRESET_B_RATIOS_FROM_150 = (4.25, 5.5)
PRESET_B_DPLL_TIMEOUT_MIN_VARIABLES = 150
PRESET_B_DPLL_TIMEOUT_SECONDS = 10.0
PRESET_B_DPLL_SKIP_MIN_VARIABLES = 200


PRESET_C_LOCAL_SEARCH_TIMEOUT_SECONDS = 1
PRESET_C_LOCAL_SEARCH_SOLVERS = {"WalkSAT", "ProbSAT"}

@dataclass(frozen=True)
class Random3SATPresetCase:
    """One concrete generated formula before it is sent to each solver."""

    variable_count: int
    ratio: float
    clause_count: int
    seed: int
    formula_mode: str
    sat_percentage: float | None
    sat_fraction: float | str

    def as_dict(self) -> dict:
        return {
            "variable_count": self.variable_count,
            "ratio": self.ratio,
            "clause_count": self.clause_count,
            "seed": self.seed,
            "formula_mode": self.formula_mode,
            "sat_percentage": self.sat_percentage,
            "sat_fraction": self.sat_fraction,
        }


@dataclass(frozen=True)
class Random3SATPresetSpec:
    """Compact description of a preset built from Cartesian products."""

    variables: tuple[int, ...]
    ratios: Iterable[float] | Callable[[int], Iterable[float]]
    seeds: Iterable[int] | Callable[[int], Iterable[int]]
    formula_mode: str
    sat_fractions: tuple[float | str, ...] = ("auto",)

    def __post_init__(self) -> None:
        object.__setattr__(self, "variables", tuple(self.variables))
        if not callable(self.ratios):
            object.__setattr__(self, "ratios", tuple(self.ratios))
        object.__setattr__(self, "sat_fractions", tuple(self.sat_fractions))
        if not callable(self.seeds):
            object.__setattr__(self, "seeds", tuple(self.seeds))


@dataclass(frozen=True)
class Random3SATPresetUiValues:
    """Preview values shown in the benchmark form after Apply Preset."""

    variables: str
    ratios: str
    seed: str
    formula_mode: str
    sat_percentage: str


@dataclass(frozen=True)
class Random3SATPreset:
    """Registered preset used by the UI and the benchmark runner."""

    name: str
    default_solvers: tuple[str, ...]
    summary: str
    ui_values: Random3SATPresetUiValues | None = None
    spec: Random3SATPresetSpec | None = None
    case_builder: Callable[[], Iterable[Random3SATPresetCase | dict]] | None = None

    def cases(self) -> list[Random3SATPresetCase]:
        if self.case_builder is not None:
            return [_case_from_value(case) for case in self.case_builder()]
        if self.spec is not None:
            return matrix_cases(self.spec)
        return []


_PRESET_REGISTRY: dict[str, Random3SATPreset] = {}


def range_seeds(start: int, stop: int) -> range:
    """Inclusive seed range helper, so range_seeds(1, 5) means 1..5."""

    return range(start, stop + 1)


def _seeds_for_variable(spec: Random3SATPresetSpec, variable_count: int) -> Iterable[int]:
    if callable(spec.seeds):
        return spec.seeds(variable_count)
    return spec.seeds


def _ratios_for_variable(spec: Random3SATPresetSpec, variable_count: int) -> Iterable[float]:
    if callable(spec.ratios):
        return spec.ratios(variable_count)
    return spec.ratios


def _case_from_value(value: Random3SATPresetCase | dict) -> Random3SATPresetCase:
    if isinstance(value, Random3SATPresetCase):
        return value
    return Random3SATPresetCase(
        variable_count=int(value["variable_count"]),
        ratio=float(value["ratio"]),
        clause_count=int(value["clause_count"]),
        seed=int(value["seed"]),
        formula_mode=str(value["formula_mode"]),
        sat_percentage=value.get("sat_percentage"),
        sat_fraction=value.get("sat_fraction", ""),
    )


def _sat_values_for_mode(formula_mode: str, sat_fraction: float | str) -> tuple[float | None, float | str]:
    if formula_mode == "Planted SAT":
        return None, 1.0
    if formula_mode == "Forced UNSAT":
        return None, 0.0
    if formula_mode == "Random" and sat_fraction != "auto":
        return float(sat_fraction) * 100, float(sat_fraction)
    return None, ""


def matrix_cases(spec: Random3SATPresetSpec) -> list[Random3SATPresetCase]:
    """Expand variables x ratios x SAT fractions x seeds into preset cases.

    ratios and seeds may be fixed tuples or callables that receive n_vars.
    Use callables when one variable size needs different ratios or seed counts.
    """

    cases = []
    for variable_count in spec.variables:
        for ratio in _ratios_for_variable(spec, variable_count):
            for sat_fraction in spec.sat_fractions:
                sat_percentage, exported_sat_fraction = _sat_values_for_mode(spec.formula_mode, sat_fraction)
                for seed in _seeds_for_variable(spec, variable_count):
                    cases.append(
                        Random3SATPresetCase(
                            variable_count=variable_count,
                            ratio=ratio,
                            clause_count=round(variable_count * ratio),
                            seed=seed,
                            formula_mode=spec.formula_mode,
                            sat_percentage=sat_percentage,
                            sat_fraction=exported_sat_fraction,
                        )
                    )
    return cases


def register_random_3sat_preset(preset: Random3SATPreset) -> Random3SATPreset:
    """Add a preset to the UI/runner registry and return it for reuse in tests."""

    global RANDOM_3SAT_PRESETS
    if not preset.name:
        raise ValueError("Random 3-SAT preset name cannot be empty")
    if preset.name == RANDOM_3SAT_PRESET_CUSTOM:
        raise ValueError("Custom is reserved for manual Random 3-SAT sweeps")
    _PRESET_REGISTRY[preset.name] = preset
    RANDOM_3SAT_PRESETS = random_3sat_preset_names()
    return preset


def random_3sat_preset_names() -> tuple[str, ...]:
    return (RANDOM_3SAT_PRESET_CUSTOM, *tuple(_PRESET_REGISTRY))


def random_3sat_preset_cases(preset_name: str) -> list[dict]:
    if preset_name == RANDOM_3SAT_PRESET_CUSTOM:
        return []
    try:
        preset = _PRESET_REGISTRY[preset_name]
    except KeyError as exc:
        raise ValueError(f"Unknown Random 3-SAT preset: {preset_name}") from exc
    return [case.as_dict() for case in preset.cases()]


def random_3sat_preset_case_count(preset_name: str) -> int:
    return len(random_3sat_preset_cases(preset_name))


def random_3sat_preset_default_solvers(preset_name: str) -> tuple[str, ...]:
    if preset_name == RANDOM_3SAT_PRESET_CUSTOM:
        return ()
    try:
        return _PRESET_REGISTRY[preset_name].default_solvers
    except KeyError as exc:
        raise ValueError(f"Unknown Random 3-SAT preset: {preset_name}") from exc


def random_3sat_preset_ui_values(preset_name: str) -> Random3SATPresetUiValues | None:
    if preset_name == RANDOM_3SAT_PRESET_CUSTOM:
        return None
    try:
        return _PRESET_REGISTRY[preset_name].ui_values
    except KeyError as exc:
        raise ValueError(f"Unknown Random 3-SAT preset: {preset_name}") from exc


def random_3sat_preset_summary(preset_name: str) -> str:
    if preset_name == RANDOM_3SAT_PRESET_CUSTOM:
        return "Custom Random 3-SAT sweep."
    try:
        return _PRESET_REGISTRY[preset_name].summary
    except KeyError as exc:
        raise ValueError(f"Unknown Random 3-SAT preset: {preset_name}") from exc


def random_3sat_preset_solver_timeout(
    solver: str,
    variable_count: int,
    timeout_seconds: float | None,
    preset_name: str | None = None,
) -> float | None:
    """Return the timeout to apply for one preset solver run.

    The UI timeout is the base timeout. Preset-specific caps override the
    fallback cap. For example, Forced UNSAT uses a DPLL cap at n=150 while
    skipping DPLL entirely at n=200.

    Preset C uses a short cap for local-search solvers because WalkSAT and
    ProbSAT are incomplete and should not spend too much time on hard or UNSAT
    instances in the mixed benchmark.
    """

    if (
        preset_name == RANDOM_3SAT_PRESET_C
        and solver in PRESET_C_LOCAL_SEARCH_SOLVERS
    ):
        return (
            PRESET_C_LOCAL_SEARCH_TIMEOUT_SECONDS
            if timeout_seconds is None
            else min(timeout_seconds, PRESET_C_LOCAL_SEARCH_TIMEOUT_SECONDS)
        )

    if (
        solver == "DPLL"
        and preset_name == RANDOM_3SAT_PRESET_B
        and variable_count >= PRESET_B_DPLL_TIMEOUT_MIN_VARIABLES
    ):
        return (
            PRESET_B_DPLL_TIMEOUT_SECONDS
            if timeout_seconds is None
            else min(timeout_seconds, PRESET_B_DPLL_TIMEOUT_SECONDS)
        )

    if solver == "DPLL" and variable_count >= DPLL_TIMEOUT_CAP_MIN_VARIABLES:
        return (
            DPLL_TIMEOUT_CAP_SECONDS
            if timeout_seconds is None
            else min(timeout_seconds, DPLL_TIMEOUT_CAP_SECONDS)
        )

    return timeout_seconds

def random_3sat_preset_should_skip_solver(
    solver: str,
    variable_count: int,
    preset_name: str | None = None,
) -> bool:
    """Return True when a preset row should be emitted as SKIPPED, not solved."""

    if solver != "DPLL":
        return False
    if preset_name == RANDOM_3SAT_PRESET_A and variable_count >= PRESET_A_DPLL_SKIP_MIN_VARIABLES:
        return True
    if preset_name == RANDOM_3SAT_PRESET_B and variable_count >= PRESET_B_DPLL_SKIP_MIN_VARIABLES:
        return True
    return DPLL_SKIP_ABOVE_VARIABLES is not None and variable_count > DPLL_SKIP_ABOVE_VARIABLES


def _preset_a_seeds(variable_count: int) -> range:
    # Preset A is larger at n=300, so it uses fewer seeds to stay practical.
    return range_seeds(1, 10) if variable_count == 300 else range_seeds(1, 20)


def _preset_a_ratios(variable_count: int) -> tuple[float, ...]:
    # n=300 uses fewer ratios to keep Preset A practical.
    return PRESET_A_RATIOS_FOR_300 if variable_count == 300 else PRESET_A_RATIOS


def _preset_b_ratios(variable_count: int) -> tuple[float, ...]:
    # Forced UNSAT skips ratio 3.5 from n=150 upward.
    return PRESET_B_RATIOS_FROM_150 if variable_count >= 150 else PRESET_B_RATIOS


# Built-in presets. The order of these register calls is the order shown in the UI.
register_random_3sat_preset(
    Random3SATPreset(
        name=RANDOM_3SAT_PRESET_A,
        spec=Random3SATPresetSpec(
            variables=PRESET_A_VARIABLES,
            ratios=_preset_a_ratios,
            seeds=_preset_a_seeds,
            formula_mode="Planted SAT",
        ),
        default_solvers=("CDCL", "DPLL", "WalkSAT", "ProbSAT"),
        ui_values=Random3SATPresetUiValues(
            variables="50,100,150,200,300",
            ratios="2.5,3.5,4.25,5.5",
            seed="1",
            formula_mode="Planted SAT",
            sat_percentage="",
        ),
        summary=(
            "350 cases, default solvers: CDCL, DPLL, WalkSAT, ProbSAT. "
            "DPLL is skipped for n>=200. n=300 uses ratios 3.5, 4.25, 5.5. "
            "seeds 1..20 for n<=200, 1..10 for n=300. "
            "Fields are read-only while the preset is active."
        ),
    )
)

register_random_3sat_preset(
    Random3SATPreset(
        name=RANDOM_3SAT_PRESET_B,
        spec=Random3SATPresetSpec(
            variables=PRESET_B_VARIABLES,
            ratios=_preset_b_ratios,
            seeds=range_seeds(1, 10),
            formula_mode="Forced UNSAT",
        ),
        default_solvers=("CDCL", "DPLL"),
        ui_values=Random3SATPresetUiValues(
            variables="50,100,150,200",
            ratios="3.5,4.25,5.5",
            seed="1",
            formula_mode="Forced UNSAT",
            sat_percentage="",
        ),
        summary=(
            "100 cases, default solvers: CDCL, DPLL. "
            "n>=150 uses ratios 4.25, 5.5; DPLL is capped at n=150 and skipped at n=200. "
            "seeds 1..10. "
            "Fields are read-only while the preset is active."
        ),
    )
)

register_random_3sat_preset(
    Random3SATPreset(
        name=RANDOM_3SAT_PRESET_C,
        spec=Random3SATPresetSpec(
            variables=(100, 150, 200),
            ratios=(4.25,),
            seeds=range_seeds(1, 30),
            formula_mode="Random",
            sat_fractions=(0.3, 0.5, 0.7),
        ),
        default_solvers=("CDCL", "DPLL", "WalkSAT", "ProbSAT"),
        ui_values=Random3SATPresetUiValues(
            variables="100,150,200",
            ratios="4.25",
            seed="1",
            formula_mode="Random",
            sat_percentage="30,50,70",
        ),
        summary=(
            "270 cases, default solvers: CDCL, DPLL, WalkSAT, ProbSAT. "
        "SAT fractions 0.3, 0.5, 0.7; seeds 1..30. "
        "WalkSAT and ProbSAT are capped at 1 second per run. "
        "Fields are read-only while the preset is active."
        ),
    )
)


RANDOM_3SAT_PRESETS = random_3sat_preset_names()
