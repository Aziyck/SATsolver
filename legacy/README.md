# Legacy

Archived code and documents kept for reference. Product code must not import
anything from this folder; if an idea here is useful, port it into the active
packages and add tests.

| Path | What it is |
|---|---|
| `tkinter_app/` | Runnable snapshot of the original Tkinter desktop app, with its own copy of the backend and its tests. See `tkinter_app/README.md`. |
| `walksat_original.py` | The first WalkSAT/ProbSAT implementation: make/break recomputed for every candidate, and a ProbSAT that combined noise with a `(make+1)/(break+1)^2` weight. Replaced by the textbook algorithms in `solvers/walksat.py`. |
| `dpll_recursive.py` | The recursive DPLL solver the web app used before `solvers/dpll.py` became iterative. Same decisions, but it copies the formula at every branch and can hit Python's recursion limit. |
| `docs_ro/` | Original Romanian thesis and report documents. English, updated versions live in `docs/report/` and `docs/guide/`. |
| `generated_graph_coloring_cnf/` | Old generated DIMACS files (graph coloring and Sudoku). They use the old graph-coloring variable numbering `node * 100 + color`. |
| `main.py`, `benchmark.py`, `dpll_debug.py`, ... | Early console scripts from before the app existed. |
| `experiments/` | Early experiments. |
