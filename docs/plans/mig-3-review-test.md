# Plan: test document for /write-plan review (MIG-3)

- **Written:** 2026-11-27
- **Related:** [github-issues](github-issues.md)
- **Issues:** none yet

Throwaway document on a throwaway pull request. It is closed unmerged.

## Problem statement

A solver run that hits its timeout is shown as `TIMEOUT`, and the table gives
no hint of how close the run was to finishing.

## Requirements

- MUST: a `TIMEOUT` row shows the elapsed time next to the status.
- MUST NOT: change how a timeout is detected.

## Main flow and failures

1. The run ends at the limit; the row is stored with status `TIMEOUT`.
2. The table shows the status and the elapsed time. Success point: both are
   visible without opening the row.

Failure path: if the worker dies before storing the row, no row exists and
nothing is shown.

## Solutions and decision

| Solution | How | Cost |
|---|---|---|
| A. Show elapsed time in the table | a column in the results table | one more column |
| B. Show it only in a tooltip | tooltip on the status tag | hidden on touch screens |

**Decision: A.** The deciding reason is that the number is visible at a glance.
The downside: one more column, which a narrow screen has to collapse (see the
risks table).

## Risks and open questions

| Risk | Effect | Response | Blocks decision |
|---|---|---|---|
| A wide table on small screens | the column is cut | collapse it below a width | no |
