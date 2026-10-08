# Adding a problem or a solver

Problems and solvers are plug-ins: each one is declared in a single place and
the rest of the app (forms, previews, benchmarks, CSV, API) picks it up from
the declaration. This guide walks through a complete new problem, then a new
solver. Read [Architecture](architecture.md) first if you have not.

## Adding a problem

As an example we add **Vertex Cover**: choose k nodes so that every edge has
at least one chosen end. It is a graph problem, so it reuses the graph inputs
(`G(n,p)`, `G(n,m)`, `G(n,d)`, manual edges), the graph drawing and graph
suites.

### 1. Design the encoding

Write it down before coding. Reuse the slot encoding of Independent Set and
Clique:

- variable `x(s, v)`: "slot s of the cover holds node v", for slots
  `1..k` and nodes `1..n`, numbered `readable_pair_var(s, v, n)`;
- each slot holds exactly one node, and no node fills two slots (so the cover
  has exactly k distinct nodes);
- for every edge `(u, v)`: some slot holds u or some slot holds v, that is
  the clause `x(1,u) or ... or x(k,u) or x(1,v) or ... or x(k,v)`.

Size: `n*k` variables; `k` + `k*C(n,2)` + `n*C(k,2)` + `|E|` clauses. A cover
of size k exists if and only if the formula is satisfiable (a smaller cover
can always be padded with extra nodes).

### 2. Write the module

Create `problems/vertex_cover.py`:

```python
"""
Vertex cover of size k.

Variable x(s, v) = "slot s of the cover holds node v", numbered
readable_pair_var(s, v, n).

Clauses:
- each slot holds exactly one node, and a node fills at most one slot;
- every edge has a chosen end: x(1,u) or ... or x(k,u) or x(1,v) or ... or x(k,v).
"""

from __future__ import annotations

from typing import Any

from problems.base import fact, register_problem
from problems.encoding import comb2
from problems.graph import Graph, GraphProblemSpec, expected_edges, graph_fields
from problems.independent_set import TARGET_FIELD, decode_selection, slot_clauses, slot_var, validate_target
from sat_core.models import ProblemInstance


@register_problem
class VertexCover(GraphProblemSpec):
    key = "vertex_cover"
    title = "Vertex Cover"
    summary = "Choose k nodes so that every edge touches at least one of them."
    description = (
        "Variables x(s,v) mean slot s of the cover holds node v. Each of the k slots holds "
        "exactly one node, no node fills two slots, and every edge has a chosen end."
    )
    fields = graph_fields() + (TARGET_FIELD,)

    def validate(self, params: dict[str, Any]) -> None:
        validate_target(params)

    def estimate(self, params: dict[str, Any]) -> dict[str, int]:
        n, k = params["nodes"], params["target"]
        clauses = k + k * comb2(n) + n * comb2(k) + expected_edges(params)
        return {"variables": n * k, "clauses": int(clauses)}

    def encode_graph(self, graph: Graph, params: dict[str, Any]) -> ProblemInstance:
        nodes, target = graph.nodes, params["target"]
        clauses = slot_clauses(nodes, target)
        for u, v in graph.edges:
            clauses.append(
                [slot_var(slot, u, nodes) for slot in range(1, target + 1)]
                + [slot_var(slot, v, nodes) for slot in range(1, target + 1)]
            )
        return ProblemInstance(
            name=self.title,
            problem_type=self.key,
            clauses=clauses,
            metadata={"target": target},
            decoder=lambda solution: decode_selection(solution, nodes, target),
        )

    def check(self, instance: ProblemInstance, decoded: Any) -> list[str]:
        chosen = set(decoded["selected"])
        errors = []
        if len(chosen) != instance.metadata["target"]:
            errors.append(f"expected {instance.metadata['target']} distinct nodes, got {len(chosen)}")
        for u, v in self.graph_of(instance).edges:
            if u not in chosen and v not in chosen:
                errors.append(f"edge {u}-{v} is not covered")
        return errors[:20]

    def describe(self, instance: ProblemInstance) -> list[dict[str, Any]]:
        return [fact("Target k", instance.metadata["target"])] + super().describe(instance)
```

What each piece does:

| Member | Used for |
|---|---|
| `key`, `title`, `summary`, `description` | URLs, cards, the (i) help, the catalog |
| `fields` | the form, validation, benchmark sweeps, CSV columns, case labels |
| `validate()` | cross-field checks, raised as `ParamError({field: message})` |
| `estimate()` | the size badge, the plan panel, and the `MAX_CLAUSES` guard; keep it close to the real counts |
| `encode_graph()` / `encode()` | the CNF and a decoder that turns a model into the answer |
| `check()` | an independent check of the decoded answer; an empty list means valid |
| `describe()` | facts listed under the answer |

`GraphProblemSpec` supplies `encode()` (build the graph, then call
`encode_graph`), `visual()` and `preview()` (the graph drawing), and the graph
facts. For a problem that is not a graph, subclass `ProblemSpec` directly and
implement `encode(params)` plus, if useful, `visual()` and `preview()`; see
`problems/n_queens.py` for a small complete example.

Optional hooks:

- `expected_status(instance)`: return `"SAT"` or `"UNSAT"` when the answer is
  known by construction (planted formulas, N-Queens with n = 2 or 3).
  Benchmarks flag answers that contradict it.
- `case_label(params)`: override the automatic label built from the fields'
  `short` names.
- `result_view`: how the answer is drawn. Graph problems use `graph`, which
  highlights `decoded["selected"]` nodes, a `decoded["path"]`, or a
  `decoded["coloring"]`. Other views: `sudoku` (`decoded["grid"]`), `queens`
  (`decoded["queens"]`), `assignment` (`decoded["bits"]`).

### 3. Register it

Add the import to `problems/__init__.py`. The position sets the order of the
cards in the UI:

```python
from problems import clique  # noqa: F401
from problems import vertex_cover  # noqa: F401
from problems import random_3sat  # noqa: F401
```

Optionally add a card picture `assets/vertex_cover.jpg` and set
`image = "vertex_cover.jpg"` on the class.

That is all for the backend. Restart `python -m sat_web` and the problem
appears on the Solve page, in the benchmark builder (and, being a graph
problem, in graph suites with the other graph problems).

### 4. Test it

Add tests to `tests/test_problems.py` (or a new `tests/test_vertex_cover.py`):

```python
import unittest

from problems import build_problem, get_problem
from sat_core.solver_registry import run_solver


class VertexCoverTests(unittest.TestCase):
    def solve(self, params):
        spec = get_problem("vertex_cover")
        instance = build_problem("vertex_cover", params)
        result = run_solver(instance.clauses, "cdcl")
        decoded = spec.decode(instance, result.solution) if result.solution else None
        return spec, instance, result, decoded

    def test_path_graph_needs_two_nodes(self):
        params = {"graph_mode": "manual", "nodes": 4, "edges": "1-2, 2-3, 3-4", "target": 2}
        spec, instance, result, decoded = self.solve(params)
        self.assertEqual(result.status, "SAT")
        self.assertEqual(spec.check(instance, decoded), [])

        spec, instance, result, decoded = self.solve({**params, "target": 1})
        self.assertEqual(result.status, "UNSAT")

    def test_estimate_matches_manual_graph(self):
        params = {"graph_mode": "manual", "nodes": 5, "edges": "1-2, 2-3, 4-5", "target": 2}
        instance = build_problem("vertex_cover", params)
        estimate = get_problem("vertex_cover").estimate(get_problem("vertex_cover").parse(params))
        self.assertEqual(estimate["clauses"], len(instance.clauses))
        self.assertEqual(estimate["variables"], instance.variable_count)

    def test_check_rejects_an_uncovered_edge(self):
        instance = build_problem("vertex_cover", {"graph_mode": "manual", "nodes": 3, "edges": "1-2, 2-3", "target": 1})
        errors = get_problem("vertex_cover").check(instance, {"selected": [1]})
        self.assertIn("edge 2-3 is not covered", errors)
```

Good tests for any encoder:

- a tiny SAT instance and a tiny UNSAT instance, solved with CDCL;
- `check()` accepts the solver's answer and rejects a broken one;
- `estimate()` equals the real counts on a manual input;
- for generators: the same seed gives the same instance.

Then run `python -m unittest discover -s tests`.

### 5. Document it

Add the encoding to [docs/algorithms/encodings.md](../algorithms/encodings.md)
and the problem to the table in the [user guide](user-guide.md).

### A new kind of answer picture

Only needed when none of `sudoku`, `queens`, `graph` or `assignment` fits:

1. add the name to `RESULT_VIEWS` in `problems/base.py`;
2. add it to the `ResultView` type in `frontend/src/api/types.ts`;
3. write a component in `frontend/src/components/views/` that draws
   `visual` (the input, from `ProblemSpec.visual()`) and `decoded` (the
   answer, or `null` before solving);
4. add a `case` for it in `frontend/src/components/views/ProblemViews.tsx`.

## Adding a solver

### 1. Implement it

Put the algorithm in `solvers/<name>.py`. Follow the shape of the existing
solvers:

```python
from sat_core.runtime import EVENT_LOG, cancellation_status, emit, stop_requested


def my_solver(clauses, *, return_stats=False, event_callback=None, cancel_token=None, logging_options=None):
    options = logging_options or {}
    stats = {"status": None, "decisions": 0}
    ...
    for step in ...:
        if stop_requested(cancel_token):          # cancel, skip or timeout
            stats["status"] = cancellation_status(cancel_token)
            return (None, stats) if return_stats else None
        ...
    emit(event_callback, EVENT_LOG, "my_solver: found a model")
    stats["status"] = "SAT"
    return (model, stats) if return_stats else model
```

- Input: a list of clauses, each a list of non-zero ints (DIMACS literals).
- Output: `{variable: bool}` for a model, or `None`.
- Put `status` in the stats when the answer is not plain SAT/UNSAT:
  `TIMEOUT`, `CANCELLED`, `SKIPPED` (from `cancellation_status`), or
  `UNKNOWN` for an incomplete solver that gave up.
- Numeric stats (`decisions`, `conflicts`, `propagations`, `flips`, ...)
  appear in the UI and the CSV; use the existing names where they fit. For a
  new name, add a label and a one-line explanation to `STATS` in
  `frontend/src/lib/format.ts`.
- If you keep arrays indexed by variable, renumber the variables 1..n first:
  the encoders' readable numbers are sparse (see `solvers/walksat.py`).
- Check `stop_requested(cancel_token)` often enough (every few thousand
  steps) that cancel and timeouts react within a fraction of a second.

### 2. Register it

In `sat_core/solver_registry.py`, declare its options and a runner that maps
them to your function's arguments:

```python
MY_FIELDS = (
    ParamField("max_steps", "Max steps", "int", default=100_000, minimum=1, help="Give up after this many steps."),
    ParamField("random_seed", "Random seed", "seed", default=None, optional=True, advanced=True),
)


def _run_my_solver(clauses, options, log_options, event_callback, token):
    solver_options = dict(log_options)
    solver_options.update(options)
    return my_solver(clauses, return_stats=True, event_callback=event_callback,
                     cancel_token=token, logging_options=solver_options)


register_solver(
    SolverSpec(
        key="mysolver",
        title="MySolver",
        complete=False,            # True only if it can prove UNSAT
        summary="One line for the solver picker.",
        description="A few sentences for the help text.",
        fields=MY_FIELDS,
        runner=_run_my_solver,
    )
)
```

`run_solver()` wraps the runner: it applies the time limit, turns exceptions
into `ERROR` results, fills in SAT/UNSAT/UNKNOWN from `complete` when the
stats carry no status, and keeps only scalar stats. The solver now appears in
the Solve page, the benchmark builder, limit rules and the API, and its
options in the job Settings and benchmark Setup tables (with their `help`
text), with reset-to-default buttons in the forms.

### 3. Test it

- Add `tests/test_<name>.py`: small SAT and UNSAT formulas, a formula with
  unit clauses and duplicates, cancellation (a token cancelled up front
  returns `CANCELLED`), and a timeout.
- Add it to `tests/test_solver_agreement.py`: a complete solver must agree
  with brute force on random small formulas; an incomplete one must find a
  model of every satisfiable one and return `UNKNOWN` for the rest (give it a
  small budget there, or the UNSAT cases take long).
- `python scripts/benchmark_cdcl.py` runs every registered solver on the
  example files; check that yours appears and agrees with CDCL.

### 4. Document it

Add a page under `docs/algorithms/` (it shows up on the Learn page) and a
line in the solver table of the [user guide](user-guide.md).
