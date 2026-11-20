# Rules for `solvers/`

Solvers know nothing about problems, files or the web. They take
`list[list[int]]` clauses and return `(solution | None, stats)`.

- Keep the `dpll()`, `cdcl()` and `walksat()` signatures backward compatible
  unless the registry, tests and docs change with them.
- Solver hot loops are performance-sensitive (`docs/guide/performance.md`):
  check the cancel token every few thousand steps, not on every step; avoid
  scanning all clauses or variables per conflict or decision; measure with
  `scripts/solver_timings.py` before and after. Its conflicts column must not
  move for a change that claims to keep the search.
- Variable numbers can be sparse (encoders number them on purpose, see
  `problems/AGENTS.md`). A solver that keeps per-variable arrays renumbers
  1..n internally and maps the model back (see `solvers/walksat.py`). For
  CDCL and DPLL, `run_solver` renumbers formulas whose largest number is
  above 1,000,000 and mostly unused.
- Every solver is in `tests/test_solver_agreement.py`: complete solvers must
  agree with brute force; incomplete ones must find every model and never
  claim one for an UNSAT formula (give them a small budget there).
- Every new stat key is declared once as a `StatSpec` in `STAT_SPECS`
  (`sat_core/solver_registry.py`): label, log name, one-line explanation, CSV
  and chart flags. The frontend reads them from `GET /api/catalog`; it keeps
  no list of statistic keys, so nothing else needs an entry.
- A new solver: follow `docs/guide/adding-a-problem.md`.
