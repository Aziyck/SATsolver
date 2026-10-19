# Plan: memory use in the results

- **Status:** proposed, not started
- **Written:** 2026-10-19, against commit `33cdfab`
- **Depends on:** the per-run child process ("solver runner") from
  [PyPy runner and run metadata](pypy-solver-runner-and-run-metadata.md),
  Part 2, and the run metadata from Part 1 of the same plan.
- **Related:** [Benchmarking](../guide/benchmarking.md),
  [audit A2](../reviews/2026-10-16-audit.md) (one huge variable number can
  exhaust memory), `docs/report/table-templates.md` (Table 8 lists "benchmarks
  do not measure memory" as a limitation)

## Goal

Every solver run can report how much memory it needed, next to its time, in
the run details, the Runs table, the charts and the CSV. The numbers must be
honest: the same run gives the same number wherever it sits in a benchmark.

## Non-goals

- Memory of the web server or the browser.
- Exact byte counts of individual Python objects.
- A new dependency (`psutil` would help, but the project avoids runtime
  dependencies).

## Why the obvious ways mislead (measured 2026-10-19)

CPython 3.11 on Linux. Each finding below changes the design.

| Approach | What happened | Problem |
|---|---|---|
| Peak memory of the shared job process (`resource.getrusage(...).ru_maxrss`) | CDCL on 3-SAT n=200 showed 39 MB; after a Sudoku 16x16 run the peak stayed at 116 MB, so the same 3-SAT run again would report 116 MB | The value only ever goes up. In a benchmark every row after a big case reports that case's peak. It also includes the interpreter, the imports and the encoding. |
| The same 3-SAT run alone in a fresh child process | baseline 17 MB, peak 21 MB | Exact for that run. Cost: starting a child with the solver imports took about 0.05 s. |
| `tracemalloc` (Python's allocation tracker) | the same CDCL run took 25.6 s instead of 3.7 s (7x slower); traced Python peak 3.6 MB | Precise, but it ruins the times, and it only sees Python allocations, not the process. |
| A thread sampling the process memory | not measured | Python's allocator keeps freed memory for reuse, so a later run can use a lot without the number moving; short spikes between samples are missed. |

How the numbers above were taken, to repeat them: in one Python process, build
the instances with `problems.build_problem`, call `run_solver` and read
`resource.getrusage(resource.RUSAGE_SELF).ru_maxrss` (kilobytes on Linux)
after each run. For the child, run the same code with `subprocess.run([sys.executable,
"-c", code])` and read the value inside the child.

## The two measures

1. **Peak memory of the run** (process level, real-world).
   - Taken in a process that runs exactly one solver run: a child started by
     the solver runner, or the job process of a solve job (which already runs
     one solve).
   - Record `peak_memory_mb` and `baseline_memory_mb` (measured in the child
     after the imports and after reading the clauses, before the solver
     starts). The UI shows the peak and offers "peak minus baseline" as the
     solver's own share.
   - Reading the peak, standard library only:
     - Linux: `resource.getrusage(resource.RUSAGE_SELF).ru_maxrss` is in
       kilobytes.
     - macOS: the same call returns **bytes**. Convert by platform; this is an
       easy bug.
     - Windows: `GetProcessMemoryInfo` from `psapi.dll` through `ctypes`,
       field `PeakWorkingSetSize` (bytes).
   - Depends on the interpreter: PyPy uses memory differently from CPython, so
     the run metadata (interpreter, machine) must be shown with it.

2. **Peak stored literals** (algorithm level, reproducible).
   - Counted by the solver itself, independent of Python, the interpreter and
     the machine. For comparing algorithms in the thesis this is the cleaner
     number; peak memory is the practical one next to it.
   - CDCL: literals of the input clauses plus learned literals, with the
     running maximum. Update it where `add_clause()` adds a learned clause and
     where `reduce_learned()` deletes; never in the propagation loop.
   - DPLL and WalkSAT/ProbSAT store the formula plus structures proportional to
     it and learn nothing, so their value equals the input literal count. Report
     it anyway, so the column is filled for every solver and the comparison
     shows that only CDCL grows.
   - Stat key `peak_stored_literals`; also `learned_literals_peak` for CDCL if
     the split is useful.

## Design

- **Solve jobs** already run in their own process (one job, one solve), so
  they can report peak memory without the runner:
  - read the baseline after encoding;
  - read the peak after the solver returns.

  The number includes the encoded formula. Say so in the label ("peak memory
  of the job").
- **Benchmarks** need the runner. They run many cases in the same job process
  (or in parallel workers that also run many cases), so the per-run number only
  exists when each run is its own child.
  - New benchmark option "Measure memory" (off by default), shown under Run
    settings next to Parallel cases.
  - When on, every run goes through the solver runner, even on CPython.
  - The help text says what it costs: about 0.05 s per run to start a child,
    which is nothing for long runs but about 2.8 hours on a 200,000-run
    benchmark of tiny cases.
- **Where the numbers live:**
  - Both measures are plain scalar stats, so they flow through `public_stats()`
    in `sat_core/solver_registry.py` into `SolveResult.stats` and
    `BenchmarkRow.stats` without a schema change.
  - Add `peak_memory_mb`, `baseline_memory_mb` and `peak_stored_literals` to
    `STAT_COLUMNS` in `sat_core/benchmark.py` (CSV).
  - Add a label and a one-line explanation for each in `STATS` in
    `frontend/src/lib/format.ts` (AGENTS.md rule).
- **UI:**
  - "Peak memory" in the run drawer and the solve job's Statistics tab.
  - An optional column in the Runs table.
  - "Peak memory" and "Stored literals" as measures in the charts (`METRICS`
    in `frontend/src/lib/stats.ts`).
  - Charts follow the existing dataviz rules: one y-axis. Memory and time are
    separate measures, never a second axis on the same chart.
- **Rows without the measurement** (option off, or older benchmarks): show
  "not measured", never 0.

## Optional later: a memory limit and status MEMOUT

SAT competitions report runs that exceed a memory limit as their own status.
With every run in its own child, a per-run limit becomes possible:

- Linux/macOS: the child sets `resource.setrlimit(resource.RLIMIT_AS, ...)` at
  start; an allocation over the limit raises `MemoryError`, which the child
  catches and reports as `MEMOUT`. If the child is killed instead, the parent
  reports `MEMOUT` when the exit reason says so, else `ERROR`.
- Windows: limits need job objects (`CreateJobObject` with a memory limit),
  noticeably more code; leave it out at first and show the option as
  unavailable there.
- A new status touches several places:
  - the `STATUS_*` constants in `sat_core/models.py`;
  - the "Statuses" section of `AGENTS.md`;
  - the frontend status colours (`frontend/src/lib/status.tsx`, where status colours are
    reserved for statuses);
  - the charts' status shares, CSV counts and docs.
  
  Like `TIMEOUT`, `MEMOUT` is "no answer", never `UNSAT`.
- This also turns audit A2 ("one huge variable number freezes the machine")
  into a clean MEMOUT row instead of a frozen machine.

## Steps

- [ ] 0. Prerequisites from the other plan: run metadata (Part 1) and the
  solver runner (Part 2's child process with JSON pipes, cancel, timeout).
- [ ] 1. A small helper `peak_memory_mb()` / `memory_baseline()` with the three
  platform branches (new module, for example `sat_core/memory.py`; standard
  library only, returns `None` when unsupported).
- [ ] 2. Solve jobs: baseline and peak around the solver call in `solve_job`
  (`sat_core/jobs.py`), stored as stats.
- [ ] 3. The runner reports `baseline_memory_mb` and `peak_memory_mb` with its
  result.
- [ ] 4. Benchmark option "Measure memory" (request field, `ParamField`-style
  validation in `parse_request`, builder control, Setup tab line, preset
  default off).
- [ ] 5. `peak_stored_literals` in CDCL, DPLL and WalkSAT/ProbSAT (a counter,
  not a scan). Check with `scripts/solver_timings.py` that speed is unchanged.
- [ ] 6. CSV columns, `STATS` labels, chart measures, Runs table column, run
  drawer.
- [ ] 7. Docs: `docs/guide/benchmarking.md` (what the numbers mean and cost),
  `docs/guide/performance.md`, `docs/report/table-templates.md` (Table 8 no
  longer a limitation; add a memory column to the result tables).
- [ ] 8. Optional: memory limit and `MEMOUT` (Linux/macOS first).

## Tests

- [ ] The memory helper returns a positive number on the CI platforms (Ubuntu
  and Windows) and `None` instead of raising where unsupported.
- [ ] A benchmark with "Measure memory" on: every row has `peak_memory_mb`
  greater than or equal to `baseline_memory_mb`, and running the same small
  case twice in one benchmark gives similar peaks (the bug this design avoids).
- [ ] `peak_stored_literals` equals the input literal count for DPLL and
  WalkSAT, and is at least that for CDCL.
- [ ] With the option off, rows carry no memory stats and the UI shows "not
  measured".
- [ ] Optional MEMOUT: a child with a tiny limit (for example 64 MB) on a large
  formula reports `MEMOUT` (skip the test on Windows).

## Rules for results (thesis)

- Report peak memory with the interpreter and machine (run metadata). Compare
  memory only between runs on the same interpreter.
- The CPython baseline (about 17 MB with the solvers imported) is in every
  peak. For small instances it dominates, so either report "peak minus
  baseline" or state the baseline.
- For comparing algorithms, prefer peak stored literals; use peak memory for
  "what does this need on a real machine".

## Considered and rejected

- **`tracemalloc`:** 7x slower in the measurement above, so times measured
  in the same run become useless; it also misses non-Python memory.
- **`ru_maxrss` of the shared job process or of the parallel workers:** only
  ever grows, so rows after a big case are wrong (measured above).
- **A sampling thread:** misses short spikes and cannot see memory that
  Python's allocator keeps for reuse.
- **`psutil`:** convenient, but a new runtime dependency for what three short
  standard-library branches can do.
- **Always running every solve in a child (memory on by default):** about
  0.05 s per run is too much for large benchmarks of tiny cases. Opt-in keeps
  the default fast.
