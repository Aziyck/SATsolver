@AGENTS.md

## Notes for Claude Code

- Read the relevant guide before larger changes: `docs/guide/architecture.md`
  for server or job changes, `docs/guide/adding-a-problem.md` for new problems
  or solvers, `docs/guide/benchmarking.md` for the benchmark engine.
- Python API tests start real worker processes; they need
  `pip install -r requirements-dev.txt` and take a few seconds.
- Cloud sessions get their dependencies from `.claude/hooks/session-start.sh`
  (pip packages, `frontend/node_modules`, `WIZSAT_REQUIRE_API_TESTS=1`). If a
  check fails because a package is missing, run that script instead of
  working around the missing package.
- When you start the server in the background, pass `--no-browser`, and
  `--strict-port` if something else will connect to a fixed port. Stop it by
  PID. Do not `pkill -f` a pattern that also appears in your own command line.
- A fresh `WIZSAT_DATA_DIR` (a temp folder) keeps experiments out of the
  user's `output/wizsat.db`.
- The frontend build is what `python -m sat_web` serves. After changing
  `frontend/src`, rebuild (`npm run build`) before testing through the
  Python server, or use `npm run dev`.
- Playwright is pinned in `frontend/package.json`; if the environment has
  preinstalled browsers, keep the pin matching them instead of downloading new
  ones.
- To check a UI change by eye: start the server on a temp data dir, create
  jobs with `curl -X POST localhost:<port>/api/jobs` (same body as the UI),
  and screenshot with a small Playwright script that imports
  `frontend/node_modules/playwright/index.mjs`. Mantine's SegmentedControl
  and Switch hide their inputs: click `label[for$="-<value>"]`, or the
  switch role with `{ force: true }`.
- A push to `main` starts two workflows: "CI" (the tests) and "pages build
  and deployment". Check "CI".

## Difficulty and models

Every item carries a difficulty (`docs/plans/README.md` defines the levels).
This is the one place that maps it to a model, so a model change is a
one-line edit:

| Difficulty | Model | Review before the item is closed |
|---|---|---|
| easy | Sonnet, high effort | the checks in "Before you finish" |
| medium | Sonnet, high effort | plus `/code-review` on the diff; fix what it confirms |
| hard | the strongest model available (Opus), or Sonnet followed by a `/code-review` run on the stronger model | plus, for solver items, unchanged conflict counts and timings |

- If the session's model is below the item's level, say so before starting
  and let the owner choose: switch model, or proceed with the stronger review.
- After three failed attempts at an item's "done when", stop and write the
  `Escalate:` line (`docs/plans/README.md`). Do not keep trying variations.

## Subagents

- Implement in the main session, one item at a time. A subagent starts with
  no context and re-reads the codebase, so parallel implementers multiply the
  token cost without making a one-item change faster.
- Use a subagent for read-only research, for the long wait described below,
  or when the owner asks for one. One at a time unless the owner asks for
  more.

## Long-running work

Benchmarks, `scripts/solver_timings.py`, local-search runs on UNSAT
formulas, the e2e suite and waiting for CI take minutes. Don't block on them:

- Waiting only: run the command with Bash `run_in_background` (or an
  `until` loop that exits when the condition holds). It costs nothing while
  it waits, and you are notified when it ends.
- Waiting plus judgment (read the output, rerun a failure once, summarise a
  large table): hand it to a background subagent on a cheaper model. Give it
  the exact command, the data dir and the port, and ask for a short report
  (statuses and times per case, failures with their message), not the raw
  log. Keep working on something else meanwhile.
- Timings you will report must run alone: builds, test suites or a second
  benchmark running at the same time make them noisy. Run them as the only
  heavy job, with `workers` at 1.
