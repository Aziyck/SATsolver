"""
Measure how well the tests catch bugs: break the code on purpose, one small
change at a time, and see whether a test fails.

Each mutant flips one comparison (== and !=, < and <=, in and not in, ...),
swaps `and` and `or`, adds 1 to an integer or flips True and False. A mutant
is "killed" when the tests fail and "survives" when they all pass. A
survivor is either a missing test or an equivalent change (one that cannot
alter behaviour, such as `n > 1` to `n >= 1` in `n * (n - 1) // 2`): read
each one before acting on it.

    python scripts/mutation_sample.py problems/n_queens.py sat_core/verify.py
    python scripts/mutation_sample.py sat_core/*.py --per-module 20 --seed 3

A mutant runs only the test files that import its module, so the first pass
is fast; every survivor is then rerun against the whole suite before it is
reported. Coverage cannot replace this: a function every test calls is fully
covered even when no test checks its answer.

The source file is restored after each mutant, also on Ctrl+C. Run it on a
clean working tree, alone (it starts many test processes), and check
`git status` afterwards.
"""

import argparse
import ast
import random
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SWAPS = {
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
    ast.Lt: ast.LtE, ast.LtE: ast.Lt,
    ast.Gt: ast.GtE, ast.GtE: ast.Gt,
    ast.In: ast.NotIn, ast.NotIn: ast.In,
    ast.Is: ast.IsNot, ast.IsNot: ast.Is,
}


def mutation_sites(tree):
    """Every place one mutant can be made: (kind, line, column, index)."""

    sites = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for index, op in enumerate(node.ops):
                if type(op) in SWAPS:
                    sites.append(("compare", node.lineno, node.col_offset, index))
        elif isinstance(node, ast.BoolOp):
            sites.append(("and/or", node.lineno, node.col_offset, 0))
        elif isinstance(node, ast.Constant) and type(node.value) is int:
            sites.append(("int+1", node.lineno, node.col_offset, 0))
        elif isinstance(node, ast.Constant) and type(node.value) is bool:
            sites.append(("bool", node.lineno, node.col_offset, 0))
    return sites


def mutate(source, site):
    """Return the source with one site changed."""

    kind, line, column, index = site
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if getattr(node, "lineno", None) != line or getattr(node, "col_offset", None) != column:
            continue
        if kind == "compare" and isinstance(node, ast.Compare):
            node.ops[index] = SWAPS[type(node.ops[index])]()
        elif kind == "and/or" and isinstance(node, ast.BoolOp):
            node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
        elif kind == "int+1" and isinstance(node, ast.Constant) and type(node.value) is int:
            node.value += 1
        elif kind == "bool" and isinstance(node, ast.Constant) and type(node.value) is bool:
            node.value = not node.value
        else:
            continue
        return ast.unparse(tree)
    raise ValueError(f"site not found: {site}")


def tests_importing(module_path):
    """Test modules whose source names the module (import or from-import)."""

    dotted = ".".join(module_path.with_suffix("").parts)
    package, _, name = dotted.rpartition(".")
    pattern = re.compile(rf"\b{re.escape(dotted)}\b|from {re.escape(package)} import [^\n]*\b{re.escape(name)}\b")
    return sorted(
        f"tests.{path.stem}"
        for path in (ROOT / "tests").glob("test_*.py")
        if pattern.search(path.read_text(encoding="utf-8"))
    )


def tests_fail(test_modules, timeout):
    command = [sys.executable, "-m", "unittest"]
    command += test_modules if test_modules else ["discover", "-s", "tests"]
    try:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return True
    return result.returncode != 0


def run_mutant(path, source, site, test_modules, timeout):
    path.write_text(mutate(source, site), encoding="utf-8")
    try:
        return tests_fail(test_modules, timeout)
    finally:
        path.write_text(source, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Sample mutants of the given modules and run the tests against each.")
    parser.add_argument("modules", nargs="+", help="source files, relative to the repository root")
    parser.add_argument("--per-module", type=int, default=12, help="mutants per module (default 12)")
    parser.add_argument("--seed", type=int, default=1, help="which sites are sampled (default 1)")
    parser.add_argument("--timeout", type=int, default=300, help="seconds per test run; a timeout counts as killed")
    args = parser.parse_args()

    killed = survived = 0
    for name in args.modules:
        relative = Path(name)
        path = ROOT / relative
        source = path.read_text(encoding="utf-8")
        sites = mutation_sites(ast.parse(source))
        random.Random(args.seed).shuffle(sites)
        test_modules = tests_importing(relative)
        lines = source.splitlines()
        for site in sites[:args.per_module]:
            caught = run_mutant(path, source, site, test_modules, args.timeout)
            if not caught and test_modules:
                caught = run_mutant(path, source, site, [], args.timeout)
            killed += caught
            survived += not caught
            label = "killed  " if caught else "SURVIVED"
            print(f"{label} {relative}:{site[1]} {site[0]:8} {lines[site[1] - 1].strip()[:90]}", flush=True)

    total = killed + survived
    if total:
        print(f"\n{killed} of {total} mutants killed ({100 * killed // total}%), {survived} survived")


if __name__ == "__main__":
    main()
