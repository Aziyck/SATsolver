# Plan: work items as GitHub issues, plans as design docs

- **Status:** Draft (under review in its pull request)
- **Written:** 2026-11-27, against commit `a27533b`
- **Related:** [ADR 0001](../adr/0001-agent-workflow.md) (the file-based
  workflow this replaces; its "GitHub Issues" alternative is revisited here),
  [ADR 0005](../adr/0005-one-item-skill-model-by-difficulty.md),
  [agent workflow](done/agent-workflow.md),
  [PyPy solver runner](done/pypy-solver-runner.md) (RUNNER-5, the case that
  motivates design review before tasks)
- Item format, difficulty and closing rule (for the tasks below, until the
  switch): [README.md](README.md)

This is the first plan written in the new design-doc form it describes. It is
also the last one that keeps its tasks in the file: `to-issues` does not
exist until MIG-1, and by the time the switch (MIG-5) runs every task here is
closed, so the file moves straight to `done/`.

## Problem statement

Open work is 60 items spread over four files (`docs/reviews/2026-10-16-audit.md`,
`docs/reviews/findings.md`, `docs/plans/memory-measurement.md`,
`docs/plans/solver-optimisations.md`), plus 80 closed ones in the same files.
Finding, ordering and closing an item means editing Markdown by hand, and a
plan mixes two things that change at different speeds: the design, which
should be settled before work starts, and the task list, which changes with
every commit.

The design part is also too thin. The PyPy runner plan described the happy
path and the protocol, but not what happens to the solver child when its
parent dies. The RUNNER-3 review found the gap; RUNNER-5 then built a pid
watchdog (`7b052db`) and replaced it a few hours later with the stdin
lifeline (`917e8ae`, [ADR 0006](../adr/0006-the-solver-child-ends-with-its-stdin.md)).
A design that had to show its failure paths and compare two solutions would
have raised that question before any code.

**The result needed:** tasks and findings live in GitHub issues on
`Aziyck/SATsolver`; a plan is an engineering design document (after lecture
10 of the system design course) that the owner reviews and accepts in a pull
request before its tasks exist.

## Requirements

### MUST

- Every open item (60 on 2026-11-27) becomes one GitHub issue with its
  difficulty, area and kind as labels, and its "done when" in the body.
- Each migrated item's line in its file becomes
  `- [x] **A4. Title** - Moved to #N (date).`, so a search for an old ID
  still leads to its issue.
- "Blocked by" between issues uses GitHub's issue dependencies; a plan's
  tasks are sub-issues of one parent issue per plan.
- A new plan is a design doc in `docs/plans/` with the required sections
  (see "Design doc format"), opened as a pull request with status `Draft`.
  Its issues are created only after that pull request is merged.
- `/do-item` takes an issue (`#N`), reads the plan section the issue links
  to, and closes the issue through `Fixes #N` in the pull request.
- A finding met while working is created as an issue at once and named in
  the pull request body and the report to the owner.
- Every label has a GitHub description, and `ISSUE-FORMAT.md` says what each
  label means and when it is set.
- The skills keep working in cloud sessions: `gh` is installed and logged in
  there.

### SHOULD

- `/write-plan review <PR#>` answers the owner's comments on a design doc
  pull request: replies to questions, edits the doc, resolves the threads it
  handled.
- The order of work stays readable in git, in `docs/plans/README.md`.
- The `do-item` evals keep checking the same behaviours, offline.

### MUST NOT

- Keep a task's text in two places (plan file and issue).
- Copy a plan's text into its parent issue.
- Migrate closed items, or edit `legacy/` or `docs/report/`.
- Leave a half-migrated state: an item is marked `Moved to #N` only after
  issue `#N` exists.

## Non-goals

- A GitHub Project board, milestones or any second tracking tool.
- Rewriting the two open plans (`memory-measurement`, `solver-optimisations`)
  into the new format: only their tasks move. A plan written from now on uses
  the new format.
- Offline access to open work, and a record of open work inside the clone
  (accepted by the owner; closed work stays in the archived files).
- Changing how an item is built, tested or reviewed once it is picked.

## Architecture and contracts

### Where each thing lives

| Thing | Lives in | Changes when |
|---|---|---|
| A plan's design (problem, requirements, failures, solutions, risks) | `docs/plans/<name>.md` | the design changes, in a reviewed pull request |
| A task or a finding, its status, its dependencies | a GitHub issue | the work moves |
| A plan's progress | its parent issue (sub-issue list, filled by GitHub) | a sub-issue closes |
| The order of work | "Order of work" in `docs/plans/README.md` | the owner reorders |
| What a label means | the label's description; `ISSUE-FORMAT.md` | a label is added |
| Difficulty levels and hard triggers | "Difficulty" in `docs/plans/README.md` | unchanged by this plan |

### Skills and their files

| Skill | Job | Reads |
|---|---|---|
| `write-plan` | grill the owner, write the design doc, open its pull request; `/write-plan review <PR#>` answers comments; after merge, call `to-issues` | `write-plan/DESIGN-DOC-FORMAT.md` |
| `to-issues` (new) | turn an accepted design doc, or a list of findings, into issues: labels, dependencies, parent issue | `to-issues/ISSUE-FORMAT.md` |
| `do-item`, `do-item-hard` | build one issue | the issue, the plan section it links |
| `write-pr` | commit subject and pull request body with `Fixes #N` | the issue |
| `retro` | look back on finished work; files findings through `to-issues` | issues, pull requests |

`to-issues` replaces the item format in `docs/plans/README.md` and the
filing steps that `retro` and `do-item` do by hand today, so it is a
replacement under the skill rule in `AGENTS.md`, not an addition.

### Issue contract

- **Title:** a migrated item keeps its ID as a prefix (`A4. A large DIMACS
  file's text is sent and kept everywhere`); a new issue has only its
  number.
- **Body:** the item's fields as today (`Problem` or `What`, `Fix` or `How`,
  `Done when`, `Not hard` when rated below a trigger), where it came from
  (`From the 2026-10-16 audit`, `Found while #N`), and for a plan task the
  link to its section of the plan.
- **Labels:**

  | Group | Values | Means |
  |---|---|---|
  | `difficulty:` | `easy`, `medium`, `hard` | as defined in `docs/plans/README.md`; sets the model and the review |
  | `area:` | `solvers`, `problems`, `sat_core`, `sat_web`, `frontend`, `workflow`, `docs` | the folder the fix touches most |
  | `kind:` | `finding`, `task` | a fix to existing code (starts from a reproduction) or a plan task (starts from the design) |
  | `needs-decision` | - | an owner question is open; work stops |

  GitHub's nine default labels are deleted.
- **Statuses:**

  | Status | On GitHub |
  |---|---|
  | open | open issue |
  | waiting | open, with a `blocked by` dependency or `needs-decision` |
  | done | closed as completed, by the merged pull request's `Fixes #N` |
  | dropped | closed as not planned, with the reason in a closing comment |

- **Needs decision:** the question, the options and the recommendation sit
  in the body under `Needs decision`, with the label. The owner answers in a
  comment; the next session rewrites it as `Decided (date): ...` and removes
  the label.
- **Commit subject:** `A4 (#N): ...` for a migrated item, `#N: ...` for a new
  one.
- **Parent issue:** one sentence on what the plan delivers, the link to
  `docs/plans/<name>.md`, and its sub-issues. Nothing copied from the plan.
- **A finding met while working:** a standalone issue with `Found while #N`.
  It becomes a sub-issue of a plan only when the plan cannot finish without
  it, and then it also blocks the task it holds up.

### Design doc format

Adapted from lecture 10 ("Engineering Design Documents, RFCs, and ADRs") of
the system design course; written down in `write-plan/DESIGN-DOC-FORMAT.md`.

| Section | Required | Content |
|---|---|---|
| Header | yes | `Status` (`Draft`, `Accepted`, `Done`), `Written`, `Related`, link to the parent issue once it exists |
| Problem statement | yes | the problem and the result needed, in a paragraph |
| Requirements | yes | `MUST`, `SHOULD`, `MUST NOT`: observable behaviour; the issues' "done when" come from these |
| Non-goals | yes | excluded scope |
| Quality targets | no | measure, target, condition (for speed or memory work) |
| Architecture and contracts | no | only the views the change needs: modules, data, JSON shapes, settings |
| Main flow and failures | yes | the main sequence, its success point, and at least one failure path |
| Solutions and decision | yes | at least two viable solutions at the same depth, the deciding reason, and one downside of the chosen one; an ADR when the choice is hard to reverse |
| Risks and open questions | yes | each with its effect, a response or next action, and whether it blocks the decision |

A small change may merge sections into a short "focused change note", but
never drops the failure path or the second solution.

**Status rule:** a design doc is `Draft` while its pull request is open,
`Accepted` when it merges (an open question that blocks the decision must be
closed first), and `Done` when its last sub-issue closes; the session that
closes it moves the file to `done/` in the same pull request.

## Main flow and failures

### A new plan

1. `/write-plan <idea>` grills the owner section by section, writes
   `docs/plans/<name>.md` as `Draft` on branch `plan/<name>`, opens a pull
   request, and stops.
2. The owner comments on lines of the doc. `/write-plan review <PR#>` answers
   questions in the threads, edits the doc for changes, pushes, and resolves
   what it handled. Repeat until the owner has no comments.
3. The owner merges. **Success point: the design is accepted.**
4. `to-issues` reads the merged doc and creates the parent issue and one
   sub-issue per task, with labels and dependencies.
5. `/do-item #N` builds a task; its pull request says `Fixes #N`. If building
   shows the design was wrong, the same pull request edits the plan's
   section; a large change stops and goes back to step 1 as a small design
   doc pull request.
6. The pull request that closes the last sub-issue sets `Status: Done` and
   moves the file to `done/`; the parent issue closes on merge.

### The migration (MIG-5)

1. The migration script reads every `- [ ]` item and writes each issue
   (title, body, labels, dependencies, parent) into a folder in the
   scratchpad. Nothing is created yet.
2. The owner reads the drafts.
3. The real run creates the labels, the issues, then the parent issues and
   the dependencies, recording each old ID and its new number.
4. Only then are the file lines rewritten as `Moved to #N`.
   **Success point: every open item has an issue, and every file line points
   to it.**

### Failure paths

- **The run stops half-way** (network, rate limit, a `gh` error). The script
  skips an item whose issue already exists (same title), so a rerun creates
  only what is missing; the file lines are rewritten only from the recorded
  mapping after the run finished, so no line points to an issue that does not
  exist.
- **GitHub's dependency or sub-issue API is not reachable through `gh`.** The
  repository has no issues yet, so this could not be checked while writing
  the plan. MIG-5 checks it first on the first issue it creates; if it fails,
  the session stops and asks the owner (fallback: a `Blocked by: #N` line in
  the body).
- **A cloud session has no `gh` or no login.** `/do-item` cannot find its
  issue. MIG-4 makes `session-start.sh` install `gh` and checks the login;
  `/do-item` stops with a clear message when `gh auth status` fails, instead
  of falling back to the files.
- **The design turns out wrong during a task** (the RUNNER-5 case after
  acceptance): handled by step 5 of "A new plan".

## Solutions and decision

| Solution | How | Benefit | Cost or risk |
|---|---|---|---|
| A. Keep the files (today) | items in Markdown, `grep` to find them | offline, in the clone, no new tool | hand-edited statuses and order; design and tasks mixed; no review step for a design |
| B. Everything on GitHub (Matt Pocock's flow) | the design is a parent issue (a PRD); tasks are sub-issues | one tool; progress bar | a design that is revised often is hard to review and diff in an issue body; no line comments; not in the clone |
| C. Design docs in files, tasks in issues (chosen) | the design is a file reviewed in a pull request; tasks are issues linked to its sections | the design gets line comments, history and diffs; tasks get statuses, dependencies and a progress bar; nothing lives in two places | two tools: the design is in git, the work is on GitHub; open work is not offline |

**Decision: C.** The deciding reason is the review step: a design doc pull
request gives the owner line comments and an explicit acceptance (the merge)
before any task exists, which is what RUNNER-5 lacked. **Downside:** a reader
needs both the repo and GitHub to see a plan and its progress, and an agent
needs `gh` to find work.

This is hard to reverse and supersedes part of ADR 0001, so MIG-1 records it
as ADR 0008.

## Risks and open questions

| Risk | Effect | Response |
|---|---|---|
| The dependency or sub-issue API does not work through `gh` | "blocked by" is not machine-readable; `do-item` could pick a blocked issue | checked first in MIG-5; fallback is a text line, decided by the owner then |
| `gh` in cloud sessions cannot be checked from a local session | cloud sessions cannot find work | MIG-4's "done when" is seen in a real cloud session |
| `do-item` changes before the items move (MIG-2 before MIG-5) | sessions in between cannot find file items | MIG-2 keeps the file-ID path; MIG-5 removes it |
| Issues and pull requests share one number sequence | `#N` in a commit could be read as a pull request | the commit subject's `#N` is always an issue; `Fixes #N` makes GitHub link it |
| Findings filed during MIG-1 to MIG-4 | they would land in `findings.md` and be missed | they are still open file items at MIG-5, so the migration takes them along |

No open question blocks the decision.

## Tasks

Until MIG-5, these tasks follow the item format in [README.md](README.md),
and findings met along the way are still filed in `docs/reviews/findings.md`.

- [ ] **MIG-1. ADR 0008, the design doc format and the `to-issues` skill**
  - **Difficulty:** medium
  - **How:** ADR 0008 ("Work items are GitHub issues; plans are design docs
    reviewed in a pull request"), superseding point 1 and the "GitHub Issues"
    alternative of ADR 0001; `write-plan/DESIGN-DOC-FORMAT.md` from "Design
    doc format" above; a new skill `to-issues` with `ISSUE-FORMAT.md` from
    "Issue contract" above. `to-issues` has a draft mode that writes the
    issues and the `gh` commands to a folder without running them. Read the
    `writing-for-agents` skill first.
  - **Done when:** `to-issues` in draft mode, run on
    `docs/plans/memory-measurement.md`, writes a parent issue and one issue
    per open MEM task with the right labels, MEM-8's dependencies, and the
    link to the plan; and on two findings from `findings.md`, two standalone
    `kind: finding` issues. No issue is created.

- [ ] **MIG-2. `do-item`, `do-item-hard` and `write-pr` work from issues**
  - **Difficulty:** medium
  - **Blocked by:** MIG-1
  - **How:** `do-item #N` reads the issue (`gh issue view`), the plan section
    it links, its dependencies and its `needs-decision` label; with no
    argument it follows "Order of work" through `gh issue list`. It files a
    finding through `to-issues`. A file ID still works until MIG-5. `write-pr`
    writes `A4 (#N): ...` or `#N: ...` and `Fixes #N`. A task that closes a
    plan's last sub-issue sets the plan's status to `Done` and moves it to
    `done/`. The five evals in `.claude/skills/do-item/evals/` get fixture
    issue bodies instead of the plan files.
  - **Done when:** the five evals, rewritten with fixtures, pass under the
    same runner as today (refuses a blocked issue, stops at
    `needs-decision`, hands a hard issue to `/do-item-hard`, picks the first
    issue that can start, writes the test first); and `do-item A4` still
    finds the file item.

- [ ] **MIG-3. `write-plan` writes design docs; `retro` files through `to-issues`**
  - **Difficulty:** medium
  - **Blocked by:** MIG-1
  - **How:** `write-plan` grills section by section against
    `DESIGN-DOC-FORMAT.md` (the failure path and the second solution are
    never skipped), writes the doc as `Draft` on `plan/<name>`, and opens a
    pull request. `/write-plan review <PR#>` reads the unresolved review
    comments, replies or edits, pushes, and resolves the threads it handled.
    After the merge, `/write-plan issues <name>` calls `to-issues`. `retro`
    files findings through `to-issues`.
  - **Done when:** on a throwaway branch, `/write-plan review` run on a test
    pull request with one question comment and one change comment replies to
    the first, edits the doc for the second, and resolves both threads; the
    test pull request is closed unmerged afterwards.

- [ ] **MIG-4. `gh` works in cloud sessions**
  - **Difficulty:** medium
  - **How:** `.claude/hooks/session-start.sh` installs `gh` when it is
    missing and runs `gh auth status`; when no login is available it prints
    how to provide one. `do-item` stops with that message when `gh auth
    status` fails.
  - **Done when:** in a Claude Code cloud session on this repository,
    `gh issue list --repo Aziyck/SATsolver` runs without error after the
    hook (seen by the owner, since a local session cannot start one).

- [ ] **MIG-5. The switch: migrate the open items and rewrite the workflow docs**
  - **Difficulty:** medium
  - **Blocked by:** MIG-2, MIG-3, MIG-4
  - **How:** follow "The migration" above with a one-off script that is not
    committed. First, on the first created issue, check that dependencies and
    sub-issues work through `gh` (stop and ask if not). Create the labels with
    their descriptions and delete the defaults; parent issues for
    `memory-measurement` and `solver-optimisations`, with their tasks as
    sub-issues; dependencies from every `Blocked by`. Rewrite the file lines
    as `Moved to #N`, delete the two plans' `## Tasks` sections (replaced by
    the parent-issue link), and give `findings.md` and the audit file the
    header "Closed archive. Open findings are GitHub issues (`kind:
    finding`)." Then rewrite `docs/plans/README.md` (order of work in
    issues, statuses, no item format), `AGENTS.md` ("Working on items", the
    branches rule: "Documentation-only changes may go straight to `main`,
    except a new or changed design doc in `docs/plans/`, which goes through
    a pull request"), `CLAUDE.md`, and `GLOSSARY.md` (below). Remove
    `do-item`'s file-ID path. Close this plan: `Status: Done`, move to
    `done/`.
  - **Done when:** `gh issue list --state open` shows as many issues as there
    were open `- [ ]` items before the run; `grep -n "^- \[ \]"
    docs/reviews/*.md docs/plans/*.md` finds nothing; every `Moved to #N`
    names an issue whose title starts with that ID; MEM-8 and OPT-1 show
    their `blocked by` dependencies on GitHub; `/do-item` with no argument
    names the first unblocked issue in the order of work.

### Glossary changes (applied in MIG-5)

Written here and not in `GLOSSARY.md` yet, because they are false until the
switch:

- **item:** one finding or task, as a GitHub issue labelled `kind: finding`
  or `kind: task`; the unit of work, about one commit.
- **plan:** the engineering design doc of a feature (`docs/plans/`); its
  tasks are issues.
- **parent issue:** the issue that links a plan and holds its tasks as
  sub-issues.
- **review:** a check of a change before it merges: the `reviewer` agent's on
  a diff, the owner's on a design doc pull request.
- **audit:** a deliberate pass over the whole repository; it produces
  issues.
- **blocked:** an issue with an open `blocked by` dependency.
- **needs decision:** an issue with the `needs-decision` label.

## Considered and rejected

- **A GitHub Project board or milestones for the order of work:** a second
  tool to keep in sync, for a one-person project; the order stays in the
  README, where a change to it is reviewed in git.
- **Copying the plan into its parent issue:** the copy drifts after the first
  revision of the doc.
- **Keeping the tasks in the plan as well as in issues:** every closed task
  would mean editing two places.
- **Deleting the "docs-only may go to `main`" rule:** every typo fix would
  cost a pull request and a CI run; only design docs need review.
- **Drafting each new finding for the owner's approval before it is
  created:** interrupts every session; a wrong issue is closed in one click.
- **Rewriting the two open plans into the new format:** their design is
  settled; rewriting it is separate work.
- **Deleting the `do-item` evals, or leaving them broken:** the behaviours
  they check still matter; fixtures keep them offline.
- **Labels for where an item came from (`audit-2026-10-16`, `found-while`):**
  that goes in the body; labels stay for what selects and routes work.
- **GitHub's default labels next to ours:** an agent offered `bug` and
  `kind: finding` would have to guess.
- **Committing the migration script:** it runs once.
- **Making issues as a mode of `write-plan`:** plans are one of three sources
  of issues (plans, `retro`, review findings); a skill of its own serves all
  three.
- **A separate skill for answering design doc comments:** it is the same job
  as the grilling (shaping a design), so it is a second entry of
  `write-plan`.
- **Writing this plan in the old format:** using the new format here tests
  it on a real case.
- **Migrating closed items:** they stay in the files as an archive; nothing
  needs their status changed.
