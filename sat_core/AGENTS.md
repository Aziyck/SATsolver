# Rules for `sat_core/`

Benchmark request format, limit rules, presets and CSV:
`docs/guide/benchmarking.md`. The invariants code must keep:

- Every solver entry of a case runs on the same CNF.
- Row index = `case.index * len(solvers) + position`, so parallel
  (`"workers" > 1`, `sat_core/parallel.py`) and sequential runs give identical
  rows. The frontend relies on the same formula (`entryForRow` in
  `components/BenchmarkSetup.tsx`).
- Code inside `run_case` must work in a worker process (no globals set by the
  job process).
- Workers are `spawn` processes, which re-import the main module: a script
  that runs a parallel benchmark must be a file with an
  `if __name__ == "__main__":` guard (piping it into `python -` fails).
- One CSV format for all problems: base columns, one column per parameter,
  solver statistics.
- Worker processes talk to the server only through `RunEvent`s. They never
  touch the database or sockets.
