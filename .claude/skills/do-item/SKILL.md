---
name: do-item
description: "Work one item: a review finding (A3, B7), a plan task (RUNNER-2), a pasted bug report, or the next item in the work queue. Test-first, reviewed, closed."
argument-hint: "[item ID, plan name or bug report; empty for the next item]"
disable-model-invocation: true
model: sonnet
effort: high
---

Work exactly one item: $ARGUMENTS

The rules live elsewhere and are not repeated here: the order of work, the
item format, the difficulty rules and the closing rule in
`docs/plans/README.md`; branches and the final checks in `AGENTS.md`
("Working on items", "Before you finish"); the model and review for each
difficulty in `CLAUDE.md`. This skill is the order to work in. `/do-item-hard`
runs the same steps on Opus.

## 1. Pick the item

- **An ID:** `grep -rn "\*\*<ID>\. " docs/reviews docs/plans`, then read the
  whole item and the header of its file.
- **A plan name:** its first open task that can start.
- **Nothing:** follow "Order of work" in `docs/plans/README.md` to the first
  open item that can start, a review finding or a plan task alike.
- **A bug report without an ID** (a console error, a traceback, a wrong
  result): the report is the item, and its "done when" is "the reported
  symptom no longer happens". Once step 2 has a reproduction, file it as a new
  item at the end of `docs/reviews/findings.md` (next F number), so it is
  closed like any other.

For a plan task, read the whole plan: Goal, Non-goals, Design and
"Considered and rejected". The plan already did the thinking; the task is
built inside that design, and a rejected option stays rejected.

An item **can start** when it is open, every item in its `Blocked by` is
closed, and it has no undecided `Needs decision`. When it cannot, tell the
owner what it waits for and stop; when nothing in the queue can start, say
what each open item waits for.

Then **re-rate** it. List the files the fix or task will touch and compare
them with the hard triggers in `docs/plans/README.md` ("Difficulty"). When a
trigger matches and the item is not hard and has no `Not hard:` line, change
its difficulty line to `hard (re-rated <date>: <trigger>)`. A small change
in a hard area is hard.

**The model gate.** In `/do-item` (Sonnet), stop at a hard item: tell the
owner "<ID> is hard: run `/do-item-hard <ID>`", and change nothing else. In
`/do-item-hard` (Opus), an easy or medium item belongs to `/do-item`: say
so, and go on only when the owner confirms.

**The fork.** A hard item gets one more read, of the item and for a plan
task its Design: is a choice left open that would need an ADR (hard to
reverse, or chosen over a real alternative)? If so, end your turn with the
question as plain text before going red: two or three options, what each
costs, the recommended one first. Go on only after the owner has chosen; a
follow-up question from the owner is answered, not taken as a choice. For a
choice about how processes or messages flow, also write a mermaid diagram to
a throwaway `.md` in the scratchpad (`mkdir -p` it first) for the owner to
open in the preview, and delete it afterwards. A hard item with no open fork
goes on without asking.

**Done when** you have told the owner which item you are working on, its
"done when" in your own words, its difficulty, and the files you expect to
touch; and for a hard item with an open fork, the owner has chosen.

## 2. Go red

Build a **tight red loop**: one command that fails because of this exact
item, in seconds, with the same verdict on every run. Everything after this
step consumes it.

- **A bug or a finding:** a failing test written from the item's "done
  when" (`tests/` for Python, `frontend/src/**/*.test.ts(x)` for the UI).
  When a test cannot reach the problem: a script against a running server
  (`CLAUDE.md` says how to start one safely), a Playwright script, or a diff
  against a known-good output.
- **A plan task:** turn its "done when" into tests and work in slices: one
  test red, make it pass, then the next. Tests written all at once check an
  imagined design.
- **A refactor, or a plan with measuring rules:** the loop is a
  **baseline**. Run what the plan or item names (usually the solver tests
  and `python scripts/solver_timings.py`) and keep the output before
  touching code.

Before trusting a test, name one wrong implementation it would catch: a
flipped comparison, a skipped case, an answer that is off by one. If none
comes to mind, the assertion is too loose. A test of a checker or a
validator includes an input it must reject.

**Done when** you have seen the command fail for the item's reason (not for
a typo or a missing import), or saved the baseline. If no loop can be built
after a real attempt, say what you tried and what you would need, and stop.

## 3. Find the cause (bugs and findings)

Read the code the loop runs through. The item names a cause and a fix, but
was written against older code: confirm both still hold. If the cause is
different, tell the owner before fixing. When the cause is unclear, write
three ranked guesses, each with the observation that would confirm it, and
test them one at a time.

**Done when** you can point at the lines that produce the symptom. A plan
task skips this step.

## 4. Build

- Make the smallest change that turns the loop green. The fix an item names
  is the default; the interfaces a plan names (settings, JSON shapes,
  modules, functions) are used as written, because later tasks and the docs
  rely on them.
- Typecheck and run the single test file often; the full suite runs once, in
  step 5.
- **Rulings, not stalls.** Where the item is silent on a detail and the
  choice is cheap to undo, decide it and record
  `Ruling: <what> - <why> - <what it costs if wrong>` for the commit message.
- Stop and ask only for: a `Needs decision`; an action that can lose data or
  cannot be undone; anything security-sensitive; something a plan's
  Non-goals exclude; or a design that turns out not to work (say what you
  found).
- Stay inside the item. Each other problem you meet, file now as a new
  finding (`docs/plans/README.md`, "Statuses and closing an item") and
  carry on.

**Done when** the loop is green: every test from step 2 passes, and for a
baseline, the tests pass and the conflicts column matches it.

## 5. Verify

1. **Re-rate from the diff.** `git add -N .`, then `git diff --stat`. If a
   file in it matches a hard trigger and the item is not hard, re-rate it as
   in step 1. In `/do-item`, stop there and hand over to `/do-item-hard`;
   the work stays in the tree for it.
2. **Review** a medium or hard item: dispatch the `reviewer` agent with the
   level (`medium` or `high`, as `CLAUDE.md` gives) and no `model` argument,
   and leave the working tree alone until it replies. Its reply starts with
   the model it ran on; check that it is the one in `CLAUDE.md`. If the
   agent is unavailable, says `REVIEW FAILED`, or ran on another model, ask
   the owner to run `/code-review <level>` on that model and wait for the
   findings. Check each finding against the code: fix the ones that hold,
   file a holding one outside this item as a new finding, and list the rest
   with the reason for `write-pr`.
3. **Checks.** Run every check of "Before you finish" in `AGENTS.md` that
   applies, once, after the last edit, plus the plan's own rules (for a
   "same search" task: the conflicts column matches the baseline).

If the loop will not go green after three different attempts, stop: leave
the item open, and report what was tried and where it failed.

## 6. Close

1. Close the item in its file; for the last task of a plan, set the plan's
   status line to done. Update the docs the item names and those for the
   area (`docs/plans/README.md`, docs table in `AGENTS.md`). Measured
   numbers go where the plan says.
2. Write the commit message, pull request and report with the `write-pr`
   skill.
3. Commit and open the pull request with its files unchanged, as "Working
   on items" in `AGENTS.md` says.
4. Report to the owner: the short report from `write-pr`.
