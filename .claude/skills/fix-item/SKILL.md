---
name: fix-item
description: "Fix one review item (A3, B7) or one reported bug: reproduce it red, fix it, verify, close the item."
argument-hint: "[item ID such as A3, or a pasted bug report]"
disable-model-invocation: true
---

Fix exactly one item: $ARGUMENTS

The rules live elsewhere and are not repeated here: the item format,
difficulty and closing rule in `docs/plans/README.md`; branches and the final
checks in `AGENTS.md` ("Working on items", "Before you finish"); the model
for each difficulty in `CLAUDE.md`. This skill is the order to work in.

## 1. Locate the item

- **An ID:** `grep -rn "\*\*<ID>\. " docs/reviews docs/plans`, then read the
  whole item and the header of its file.
- **A bug report without an ID** (a console error, a traceback, a wrong
  result): the report is the item, and its "done when" is "the reported
  symptom no longer happens". Once step 2 has a reproduction, file it as a new
  item at the end of the newest file in `docs/reviews/` (next free ID), so it
  gets closed like any other.

Ask the owner instead of starting when the item is already closed, has an
undecided `Needs decision`, is `Blocked by` an open item, or has a difficulty
above what `CLAUDE.md` allows for this session's model.

**Done when** you have told the owner, in two sentences, what is wrong and
which observable behaviour will prove it fixed.

## 2. Go red

Build a **tight red loop**: one command that fails because of this exact
problem, in seconds, with the same verdict on every run. Everything after
this step consumes it; without it a fix is a guess.

- Default: a failing test written from the item's "done when"
  (`tests/` for Python, `frontend/src/**/*.test.ts(x)` for the UI).
- When a test cannot reach the problem: a script against a running server
  (`CLAUDE.md` says how to start one safely), a Playwright script, or a diff
  against a known-good output.
- A pure refactor (most B items) cannot go red. Its loop is a **baseline**:
  run the solver tests and `python scripts/solver_timings.py` and keep the
  output, before touching code.

**Done when** you have run the command and seen it fail for the item's reason
(not for a typo or a missing import), or, for a refactor, saved the baseline.
If no loop can be built after a real attempt, say what you tried and what you
would need, and stop.

## 3. Find the cause

Read the code the loop runs through. The item names a cause and a fix, but it
was written against older code: confirm both still hold. If the cause is
different from what the item says, tell the owner before fixing.

When the cause is not clear, write down three ranked guesses, each with the
observation that would confirm it ("if X, then changing Y makes the loop go
green"), and test them one at a time.

**Done when** you can point at the lines that produce the symptom.

## 4. Fix

Make the smallest change that turns the loop green; the fix named in the item
is the default. Where the item leaves a detail open and the choice is cheap to
undo, decide it and record a **ruling** for the commit message:
`Ruling: <what> - <why> - <what it costs if wrong>`.

Stay inside the item. Something else you notice becomes a new item, not an
extra edit.

**Done when** the loop is green (for a refactor: tests pass and the conflicts
column matches the baseline).

## 5. Verify

Run every check of "Before you finish" in `AGENTS.md` that applies, after the
last edit. For a medium or hard item, also run `/code-review` on the diff and
fix what it confirms.

If the loop will not go green after three different attempts, stop: write the
`Escalate:` line on the item, leave it open, and report what was tried.

## 6. Close

1. Close the item in its file and update the docs for the area, as
   `docs/plans/README.md` and the docs table in `AGENTS.md` describe.
2. Commit with the ID first in the subject (`A3: reopen old ProbSAT
   benchmarks`). The body states the cause in one sentence and lists any
   rulings.
3. Branch and pull request as "Working on items" in `AGENTS.md` says.
4. Report to the owner: what was wrong, what changed, each check with its
   result, rulings, and any new items you filed.
