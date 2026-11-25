---
name: write-plan
description: "Turn an idea into a plan in docs/plans/: grill the owner, sharpen the terms, write the plan and its tasks. Stops before any code."
argument-hint: "[the idea, or the plan to extend]"
disable-model-invocation: true
---

Plan this: $ARGUMENTS

The output is one plan file that `/do-item` can work from in a fresh
session. You change docs only: `docs/plans/`, `GLOSSARY.md`, `docs/adr/`.
Never code, and never start a task.

## 1. Read

`docs/plans/README.md` (item format, difficulty, hard triggers),
`GLOSSARY.md`, and the Goal of each open plan. If an open plan already covers
the idea, say so: extend it instead of writing a second one.

**Done when** you can say in one sentence what the plan will add and which
plan or files it is closest to.

## 2. Grill

Call the Skill tool for `grilling`, then `domain-modeling`, and follow them,
with these limits:

- **Look facts up yourself** with Grep and Read. Send a subagent only for a
  search across many folders, and one at a time.
- **No prototype** unless the owner asks for one.
- **Theory the owner cannot settle** (correctness of an encoding, complexity,
  how the custom algorithm should behave, what the thesis needs to show)
  is not guessed. Collect it as open questions for the thesis partner.
- The owner can say "write it" at any round. What is still open then
  becomes a `Needs decision` line on the task it blocks.

**Done when** the grilling frontier is empty or the owner has said "write it".

## 3. Write the plan

Create `docs/plans/<name>.md` in the form of the existing plans:

- a header: `Status` (proposed), `Written` (today), `Related`, and the link
  to `README.md` for the item format;
- `## Goal`, `## Why`, `## Non-goals`, `## Design`, `## Tasks`,
  `## Considered and rejected` (every option the grilling dropped, with the
  reason);
- tasks in the item format with a new prefix (`NAME-1`, `NAME-2`), each one
  session and one commit, rated by the hard triggers, with `Blocked by`, a
  testable "done when", and for a speed or memory task a `Worth it when:`
  bar.

Ask the owner where the plan goes in "Order of work" in `README.md`, then add
it there and to the table.

If questions for the thesis partner were collected, offer `/to-questionnaire`
for them, and save the questionnaire next to the plan.

## 4. Stop

Report the plan's path, its tasks with difficulty, and what is still open.
The next step is the owner's: `/clear`, then `/do-item <first task ID>`.
