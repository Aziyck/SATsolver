"""
Measure what running the solvers in a child process costs.

With WIZSAT_SOLVER_PYTHON set, every run starts a child interpreter and sends
it the formula as JSON (sat_core/solver_process.py). This script times two
things, with the setting off (the solver runs in this process) and on (a
child of each interpreter named on the command line):

- start-up per run: a 4x4 Sudoku solved with CDCL, many times. The solve
  itself takes about a millisecond, so the difference is the child's cost.
- a formula at the clause limit: MAX_CLAUSES random clauses (three literals
  each, or --width), cancelled at its first log line, so the solver does no
  work. What is left is counting the variables, encoding the request,
  sending it and parsing it in the child.

Per run, "wall" is the whole run_solver call and "first line" the time from
the call to the first log line. For a child, "window" runs from starting the
child to its first log line (written once the child has parsed the request
and counted the variables): the start-up that START_UP_SECONDS in
sat_core/solver_process.py has to cover.

    python scripts/child_cost.py                     # this interpreter as the child
    python scripts/child_cost.py /path/to/pypy3      # one or more other interpreters
    python scripts/child_cost.py --runs 50 --big-runs 5 --width 10

Run it as the only heavy job on the machine. The numbers in
docs/guide/performance.md ("The solver child process") come from this script.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import random
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from problems.base import MAX_CLAUSES  # noqa: E402
from sat_core import solver_process  # noqa: E402
from sat_core.dimacs import parse_dimacs_text  # noqa: E402
from sat_core.runtime import EVENT_LOG, RunToken  # noqa: E402
from sat_core.solver_registry import SOLVER_PYTHON_ENV, run_solver  # noqa: E402

SMALL = ROOT / "input" / "examples" / "sudoku_4x4.cnf"
RATIO = 4.26  # variables = clauses / RATIO, as random 3-SAT at its threshold

_child_started: list[float] = []
_real_popen = subprocess.Popen


class _TimedPopen(_real_popen):
    """subprocess.Popen that notes when run_in_child starts its child (the start of its start-up window)."""

    def __init__(self, args, *rest, **kwargs):
        if "sat_core.solver_process" in args:  # not the version probe, or any other process
            _child_started.append(time.perf_counter())
        super().__init__(args, *rest, **kwargs)


def timed_run(clauses, python, stop_at_first_line=False):
    """(wall, first line, window or None, status) of one run_solver call, in seconds."""

    if python:
        os.environ[SOLVER_PYTHON_ENV] = python
    else:
        os.environ.pop(SOLVER_PYTHON_ENV, None)
    _child_started.clear()
    first = []
    token = RunToken()

    def on_event(event):
        if event.type == EVENT_LOG and not first:
            first.append(time.perf_counter())
            if stop_at_first_line:
                token.cancel()

    # No timeout: run_solver checks a timeout before it starts a child, and
    # one shorter than counting the variables would end the run there.
    started = time.perf_counter()
    result = run_solver(clauses, "cdcl", event_callback=on_event, cancel_token=token)
    ended = time.perf_counter()
    first_line = first[0] if first else float("nan")
    window = first_line - _child_started[0] if _child_started else None
    return ended - started, first_line - started, window, result.status


def interpreter_name(python):
    if not python:
        return f"in-process ({platform.python_implementation()} {platform.python_version()})"
    code = "import platform; print(platform.python_implementation(), platform.python_version())"
    try:
        answer = subprocess.run([python, "-c", code], capture_output=True, text=True, timeout=30).stdout.strip()
    except OSError as exc:
        answer = f"cannot start: {exc}"
    return f"child: {answer or python}"


def report(samples):
    """One line: median and max of each measure, and the statuses."""

    def spread(name, values):
        return f"  {name} {statistics.median(values):6.3f}s (max {max(values):6.3f}s)"

    line = spread("wall", [s[0] for s in samples]) + spread("first line", [s[1] for s in samples])
    if samples[0][2] is not None:
        line += spread("window", [s[2] for s in samples])
    statuses = sorted({s[3] for s in samples})
    print(f"{line}  [{len(samples)} runs, {', '.join(statuses)}]", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("interpreters", nargs="*", help="child interpreters (default: this one)")
    parser.add_argument("--runs", type=int, default=20, help="runs of the small formula per interpreter")
    parser.add_argument("--big-runs", type=int, default=3, help="runs of the formula at the clause limit")
    parser.add_argument("--width", type=int, default=3, help="literals per clause of the formula at the limit")
    args = parser.parse_args()
    if min(args.runs, args.big_runs, args.width) < 1:
        parser.error("--runs, --big-runs and --width must be at least 1")
    pythons = [None] + (args.interpreters or [sys.executable])
    solver_process.subprocess.Popen = _TimedPopen

    print(
        f"{platform.platform()}, {os.cpu_count()} logical CPUs, "
        f"parent {platform.python_implementation()} {platform.python_version()}"
    )

    small = parse_dimacs_text(SMALL.read_text(encoding="utf-8"))
    print(f"\nStart-up per run: {SMALL.name}, {len(small)} clauses, CDCL")
    for python in pythons:
        print(f" {interpreter_name(python)}")
        timed_run(small, python)  # warms the file cache; not counted
        report([timed_run(small, python) for _ in range(args.runs)])

    # Built here: the random_3sat problem stops at 100,000 variables, and a
    # DIMACS file near the limit has no such bound.
    variables = round(MAX_CLAUSES / RATIO)
    rng = random.Random(1)
    big = [
        [v if rng.random() < 0.5 else -v for v in rng.sample(range(1, variables + 1), args.width)]
        for _ in range(MAX_CLAUSES)
    ]
    # Parts of the run, each timed alone once.
    started = time.perf_counter()
    len({abs(lit) for clause in big for lit in clause})
    counted = time.perf_counter() - started
    started = time.perf_counter()
    text = json.dumps({"clauses": big})
    encoded = time.perf_counter() - started
    started = time.perf_counter()
    json.loads(text)
    decoded = time.perf_counter() - started
    print(
        f"\nAt the clause limit: {len(big):,} clauses of {args.width} literals, {variables:,} variables, "
        f"request {len(text) / 1e6:.1f} MB; cancelled at the first log line.\n"
        f" Alone in this process: counting the variables {counted:.2f}s, json.dumps {encoded:.2f}s, "
        f"json.loads {decoded:.2f}s"
    )
    del text
    for python in pythons:
        print(f" {interpreter_name(python)}")
        report([timed_run(big, python, stop_at_first_line=True) for _ in range(args.big_runs)])
    os.environ.pop(SOLVER_PYTHON_ENV, None)


if __name__ == "__main__":
    main()
