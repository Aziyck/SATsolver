# Rules for `problems/`

Follow the walkthrough in `docs/guide/adding-a-problem.md` for a new problem;
it has the checklists and the tests to write. Problem modules never import
`sat_web`, FastAPI or anything UI-related. What the walkthrough cannot show:

- Encoders number variables sparsely on purpose (`sudoku_var(r, c, v) =
  r*10000 + c*100 + v`; `readable_pair_var(a, b, max_b)`, always with
  `max_b`, or large instances collide). No encoder reaches 1,000,000 at the
  default clause limit, above which `run_solver` renumbers. Numbering per
  problem: `docs/algorithms/encodings.md`.
- The order of the clauses an encoder produces is part of its behaviour: it
  changes the solvers' decisions and every benchmark number.
