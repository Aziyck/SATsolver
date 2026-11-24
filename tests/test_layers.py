"""
The import rule of docs/guide/architecture.md: every arrow points down.

Each package may import only the layers listed for it in ALLOWED. Every
import statement is checked, the ones inside functions included. A new
sat_core module has to be put into BASE or ENGINE here, and into the diagram
of the guide.
"""

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ("solvers", "problems", "sat_core", "sat_web")

# The two halves of sat_core, as drawn in the guide.
BASE = {"models", "params", "seeds", "dimacs", "runtime", "verify", "environment", "memory"}
ENGINE = {"answers", "jobs", "benchmark", "solver_registry", "solver_process", "solver_protocol", "parallel", "presets", "export"}

ALLOWED = {
    "base": {"base"},
    "solvers": {"solvers", "base"},
    "problems": {"problems", "base"},
    "engine": {"engine", "problems", "solvers", "base"},
    "web": {"web", "engine", "problems", "base"},
}
# Solvers use one base module only, for events and cancellation.
SOLVERS_BASE_MODULES = {"sat_core.runtime"}


def layer_of(module: str) -> str | None:
    """The layer of a dotted module name; None for modules outside the four packages."""

    parts = module.split(".")
    if parts[0] == "solvers":
        return "solvers"
    if parts[0] == "problems":
        return "problems"
    if parts[0] == "sat_web":
        return "web"
    if parts[0] == "sat_core":
        if len(parts) == 1 or parts[1] in BASE:
            return "base"
        if parts[1] in ENGINE:
            return "engine"
        return "unclassified"
    return None


def module_name(path: Path) -> str:
    parts = list(path.relative_to(ROOT).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def imported_modules(source: str, importer: str, is_package: bool) -> list[tuple[int, str]]:
    """Every module an import statement of `source` names, as (line, dotted name)."""

    found: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                package = importer.split(".")
                package = package[: len(package) - node.level + (1 if is_package else 0)]
                target = ".".join(package + ([node.module] if node.module else []))
            else:
                target = node.module or ""
            found.append((node.lineno, target))
            # "from sat_core import benchmark" names the module sat_core.benchmark.
            found.extend((node.lineno, f"{target}.{alias.name}") for alias in node.names)
    return found


def violations(source: str, importer: str, is_package: bool = False) -> list[str]:
    """The imports of one module that the layer rule does not allow."""

    own = layer_of(importer)
    problems: list[str] = []
    if own == "unclassified":
        return [f"{importer}: put this module into BASE or ENGINE in tests/test_layers.py"]
    reported: set[int] = set()
    for line, target in imported_modules(source, importer, is_package):
        theirs = layer_of(target)
        if theirs is None or line in reported:
            continue
        if theirs == "unclassified":
            # "from sat_core import RunToken" also yields sat_core.RunToken, a name and not a module.
            if (ROOT / Path(*target.split(".")[:2])).with_suffix(".py").is_file():
                problems.append(f"{importer}:{line} imports {target}, which is in neither BASE nor ENGINE")
                reported.add(line)
            continue
        if theirs not in ALLOWED[own]:
            problems.append(f"{importer}:{line} imports {target}: {own} may not import {theirs}")
            reported.add(line)
        elif own == "solvers" and theirs == "base" and not any(
            target == allowed or target.startswith(allowed + ".") for allowed in SOLVERS_BASE_MODULES
        ):
            problems.append(f"{importer}:{line} imports {target}: solvers may use sat_core.runtime only")
            reported.add(line)
    return problems


class LayerRuleTests(unittest.TestCase):
    def test_every_import_points_down(self):
        found: list[str] = []
        for package in PACKAGES:
            for path in sorted((ROOT / package).rglob("*.py")):
                found.extend(violations(path.read_text(encoding="utf-8"), module_name(path), path.name == "__init__.py"))
        self.assertEqual(found, [], "\n" + "\n".join(found))

    def test_sat_core_modules_are_all_classified(self):
        modules = {path.stem for path in (ROOT / "sat_core").glob("*.py")} - {"__init__"}
        self.assertEqual(modules, BASE | ENGINE)

    def test_the_check_catches_upward_imports(self):
        cases = [
            ("solvers.cdcl", "from problems import get_problem"),
            ("solvers.cdcl", "from sat_core.models import SolveResult"),
            ("problems.sudoku", "from sat_core.jobs import run_job"),
            ("problems.sudoku", "import solvers.cdcl"),
            ("sat_core.params", "from sat_core import benchmark"),
            ("sat_core.params", "from .benchmark import parse_request"),
            ("sat_core.jobs", "def run():\n    from sat_web.manager import JobManager"),
            ("sat_web.api", "from solvers.cdcl import cdcl"),
        ]
        for importer, source in cases:
            with self.subTest(importer=importer, source=source):
                self.assertTrue(violations(source, importer))

    def test_the_check_accepts_downward_imports(self):
        cases = [
            ("solvers.cdcl", "from sat_core.runtime import stop_requested"),
            ("problems.sudoku", "from sat_core.params import ParamField\nfrom problems.base import ProblemSpec"),
            ("sat_core.params", "from sat_core.models import ProblemInstance\nimport json"),
            ("sat_core.benchmark", "def run():\n    from sat_core.parallel import run_cases_in_pool"),
            ("sat_web.api", "from sat_core.jobs import run_job\nfrom problems import get_problem"),
        ]
        for importer, source in cases:
            with self.subTest(importer=importer, source=source):
                self.assertEqual(violations(source, importer), [])


if __name__ == "__main__":
    unittest.main()
