# Plan: component tests for the result and settings screens

- **Status:** done (2026-11-15)
- **Written:** 2026-11-13
- **Related:** [run metadata](../run-metadata.md),
  [memory measurement](../memory-measurement.md) (both change these screens)
- Item format, difficulty and closing rule: [README.md](../README.md)

## Goal

The screens that the next features change are protected by fast tests, so a
change that breaks how settings, statistics or benchmark set-ups are shown is
caught by `npm test` instead of by eye.

## Where things stand

- 23 unit tests (`src/lib/lib.test.ts`, `src/api/live.test.ts`) cover pure
  helpers and the live-update merge. No test renders a component.
- 10 end-to-end tests cover whole flows through the real server; they are slow
  and cannot check every state of a table.
- vitest already runs with the `jsdom` environment and includes
  `src/**/*.test.tsx`. Only a rendering helper is missing.

## Non-goals

- A coverage target. Tests are aimed at behaviour that the next plans touch.
- Charts (ECharts draws to a canvas; the table view next to each chart is the
  testable part) and the graph view (Cytoscape).
- Replacing the end-to-end tests.

## Tasks

- [x] **FE-1. Components can be rendered in tests** - Done 2026-11-14.
  - **Difficulty:** easy
  - **How:** add `@testing-library/react` (and `@testing-library/user-event`
    if clicks need it) as dev dependencies, plus a small `renderWithApp()`
    helper that wraps a component in the Mantine provider and a React Query
    client.
  - **Done when:** one test renders `StatsTable` with two statistics and finds
    both labels; `npm test` and `npm run typecheck` pass in CI.

- [x] **FE-2. Solver settings and statistics tables** - Done 2026-11-14.
  - **Difficulty:** easy
  - **Blocked by:** FE-1
  - **Done when:** tests of `SolverSettingsTable` and `StatsTable` show that
    - a changed option is marked "changed" and shows its default;
    - an option hidden by another option (restart schedule and interval while
      restarts are off) is not listed. (First written as "restart interval
      while the schedule is Luby"; the interval is the unit of the Luby
      schedule and stays visible there.)
    - an option the solver no longer has (ProbSAT `noise`) is listed as no
      longer an option;
    - a blank optional value shows its placeholder ("automatic");
    - `elapsed` is shown as a time and unknown statistic keys get a readable
      label.

- [x] **FE-3. Parameter forms: reset buttons and compact help** - Done 2026-11-15.
  - **Difficulty:** medium
  - **Blocked by:** FE-1
  - **Done when:** tests of `ParamForm` show that
    - a changed field gets a reset control that restores the default, and
      `ResetToDefaults` restores all of them and then disappears;
    - the advanced section reports how many hidden fields are changed;
    - inside `CompactHelp` the help text is not shown as a line under the
      field, and short numeric fields share a row;
    - a field with `show_if` appears and disappears with the field it depends
      on.

- [x] **FE-4. Benchmark set-up** - Done 2026-11-15.
  - **Difficulty:** easy
  - **Blocked by:** FE-1
  - **Done when:** tests show that `BenchmarkSetup` lists every solver entry
    with its label and options, shows "None" for an empty rule list, and that
    `entryForRow` maps row indices to solver entries for one, two and three
    entries.

- [x] **FE-5. Result panel states** - Done 2026-11-15.
  - **Difficulty:** medium
  - **Blocked by:** FE-1
  - **Done when:** tests of `SolveResultPanel` with a stubbed job show the
    right state for a running job (progress, Stop), a SAT result (Verified), a
    failed verification (alert), UNKNOWN (not shown as UNSAT) and a failed job
    (error message), and that the Settings tab exists only for jobs with a
    solver.
