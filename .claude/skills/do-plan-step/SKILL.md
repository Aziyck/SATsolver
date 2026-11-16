---
name: do-plan-step
description: "Build one task of a plan in docs/plans (the next open one, or a named one such as RUNNER-2), test-first, and close it."
argument-hint: "[plan file name or task ID; empty for the next task in the work queue]"
disable-model-invocation: true
model: sonnet
effort: high
---

Build exactly one plan task: $ARGUMENTS

The rules live elsewhere and are not repeated here: the order of work, the
item format, difficulty and closing rule in `docs/plans/README.md`; branches
and the final checks in `AGENTS.md` ("Working on items", "Before you
finish"); the model for each difficulty in `CLAUDE.md`. This skill is the
order to work in.

## 1. Pick the task

- A task ID: that task.
- A plan name: its first open task that can start.
- Nothing: follow "Order of work" in `docs/plans/README.md` to the first open
  task that can start.

A task **can start** when every item in its `Blocked by` is closed and it has
no undecided `Needs decision`.

Read the whole plan, not only the task: Goal, Non-goals, Design and
"Considered and rejected". The plan already did the thinking. The task is
built inside that design, and a rejected option is not reopened.

Ask the owner instead of starting when no task can start (say what each open
one waits for), or when the task's difficulty is above what `CLAUDE.md`
allows for this session's model.

**Done when** you have told the owner which task you are building, its "done
when" in your own words, and the files you expect to touch.

## 2. Baseline

Only when the plan has measuring rules or the task touches a solver: run what
the plan names (usually the solver tests and `python
scripts/solver_timings.py`) and keep the output, before changing code.

## 3. Go red

Turn the task's "done when" into tests and watch them fail for the right
reason. With several bullets, work in slices: one test, make it pass, then
the next. Tests written all at once check an imagined design.

**Done when** the first test is red because the behaviour is missing.

## 4. Build

- Use the interfaces the plan names (setting names, JSON shapes, module and
  function names) as written; later tasks and the docs rely on them.
- Typecheck and run the single test file often; run the full suite once, at
  the end.
- **Rulings, not stalls.** Where the plan is silent on a detail and the choice
  is cheap to undo, decide it and record a ruling for the commit message:
  `Ruling: <what> - <why> - <what it costs if wrong>`.
- Stop and ask only for: a `Needs decision`; an action that can lose data or
  cannot be undone; anything security-sensitive; something the Non-goals
  exclude; or a design that turns out not to work (say what you found).
- Build this task only. Later tasks stay untouched, even when they look
  close. Each other problem you meet, file now as a new finding
  (`docs/plans/README.md`, "Statuses and closing an item") and carry on.

**Done when** every test from step 3 is green.

## 5. Verify

For a medium or hard task, first run `/code-review` on the diff, at `medium`
for a medium task and `high` for a hard one, and fix what it confirms; a
confirmed finding outside this task is filed as a new finding instead. Then
run every check of "Before you finish" in `AGENTS.md` that applies, once,
after the last edit, plus the plan's own rules (for a "same search" task: the
conflicts column matches the baseline).

If the tests will not go green after three different attempts, stop: write
the `Escalate:` line on the task, leave it open, and report what was tried.

## 6. Close

1. Close the task in the plan; if it was the last one, set the plan's status
   line to done. Update the docs the task names and those for the area
   (`docs/plans/README.md`, docs table in `AGENTS.md`). Measured numbers go
   where the plan says.
2. Hand the writing to the `pr-writer` agent (`.claude/agents/pr-writer.md`).
   Its brief: the task ID, the branch, each check with its result, rulings,
   measurements, review findings left and why, new findings filed, and which
   task can start next.
3. Commit and open the pull request with its `COMMIT` and `PR BODY` text
   unchanged, as "Working on items" in `AGENTS.md` says.
4. Report to the owner: its `REPORT` text, with the pull request link.
