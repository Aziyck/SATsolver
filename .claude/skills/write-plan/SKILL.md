---
name: write-plan
description: "Write a design doc for a plan, answer the review comments on its pull request, or make its issues once it is merged. Modes: <idea> | review <PR#> | issues <name>."
argument-hint: "<idea> | review <PR#> | issues <name>"
disable-model-invocation: true
---

Plan: $ARGUMENTS

A plan is a design doc in `docs/plans/<name>.md`, in the form of
[`DESIGN-DOC-FORMAT.md`](DESIGN-DOC-FORMAT.md) (read it first: sections,
the state a plan is in, the rules for writing one). The owner reviews it in a
pull request, and the merge accepts it. Its tasks are issues, made after the
merge. You change docs only: `docs/plans/`, `GLOSSARY.md`, `docs/adr/`.
Never code, and never start a task.

The first word of the arguments picks the mode:

- `review <PR#>`: read [`REVIEW.md`](REVIEW.md) and follow it.
- `issues <name>`: step 5 below.
- anything else is the idea of a new plan: steps 1 to 4.

## 1. Read

`docs/plans/README.md` (order of work, difficulty, hard triggers),
`GLOSSARY.md`, and the problem statement of each plan in `docs/plans/`
(not `done/`). If an open plan already covers the idea, say so. One whose
header says `Issues: none yet` is extended on its own branch `plan/<name>`
and pull request; for one with issues (`Issues: #N`, or an older plan), the
idea gets a new design doc that names it under `Related`.

**Done when** you can say in one sentence what the plan will add and which
plan or files it is closest to.

## 2. Grill

Call the Skill tool for `grilling`, then `domain-modeling`, and follow them,
section by section down the table in `DESIGN-DOC-FORMAT.md`, with these
limits:

- **Look facts up yourself** with Grep and Read. Send a subagent only for a
  search across many folders, and one at a time.
- **No prototype** unless the owner asks for one.
- **Theory the owner cannot settle** (correctness of an encoding, complexity,
  how the custom algorithm should behave, what the thesis needs to show)
  is not guessed. Collect it as open questions for the thesis partner.
- **The failure path and the second solution** are asked for until each is
  real. When the owner has nothing to add, draft them from the code and
  mark them in "Risks and open questions" for the review.
- The owner can say "write it" at any round. What is still open then
  becomes a row of "Risks and open questions" that says whether it blocks
  the decision.

**Done when** every required section has its content, or the owner has said
"write it".

## 3. Write the doc

On a new branch `plan/<name>` from `main` (a clean tree first), create
`docs/plans/<name>.md`:

- the header: `Written` (today), `Related`, and `- **Issues:** none yet`;
  no `Status` field;
- the sections of `DESIGN-DOC-FORMAT.md`, with `Considered and rejected`
  (every option the grilling dropped, with the reason) when the grilling
  dropped any;
- requirements as observable behaviour, since each MUST becomes the "done
  when" of an issue; for speed or memory work, a quality target before any
  measurement.

In the same pull request: ask the owner where the plan goes in "Order of
work" in `README.md`, then add it there and to the table; add an ADR for a
decision that is hard to reverse or was chosen over a real alternative; add
a new term to `GLOSSARY.md`.

If questions for the thesis partner were collected, offer
`/to-questionnaire` for them, and save the questionnaire next to the plan.

**Done when** the doc has the failure path, two solutions with the deciding
reason and the downside of the chosen one, and a risks table whose rows say
whether they block the decision.

## 4. Open the pull request

Commit with the subject `Plan <name>: design doc`, push the branch, and open
a pull request titled `Plan: <name>` with `gh pr create`. Its body: one
sentence on what the plan delivers, the open questions that block the
decision (the owner closes them before the merge), and the line `Review
with line comments, then /write-plan review with this pull request's
number. After the merge: /write-plan issues <name>.` Stop: the merge is the
owner's.

Report the plan's path, the pull request, and what is still open.

## 5. Issues (after the merge)

`/write-plan issues <name>`:

1. Check out `main` and bring it up to date (`git pull --ff-only`), then
   check the acceptance: the pull request of `plan/<name>` is merged
   (`gh pr list --head plan/<name> --state merged`) and the doc on `main`
   says `Issues: none yet`. Otherwise stop and say which of the two fails.
2. Call the Skill tool for `to-issues` with `draft <name>`, and show the
   owner its report.
3. When the owner says to go ahead, call `to-issues` with `<name>`. It
   creates the issues and writes the parent link into the doc's header.

**Done when** `to-issues` reports the parent issue and the header says
`Issues: #<parent>`.
The next step is the owner's: `/clear`, then `/do-item <plan name>` or
`/do-item #<first task>`.
