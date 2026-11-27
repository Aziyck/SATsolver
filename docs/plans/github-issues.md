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
  difficulty, area and type as labels, and its "done when" in the body.
- Each migrated item's line in its file becomes
  `- [x] **A4. Title** - Moved to #N (date).`, so a search for an old ID
  still leads to its issue.
- "Blocked by" between issues uses GitHub's issue dependencies. A plan's
  tasks are sub-issues of one parent issue per plan; the open items of the
  2026-10-16 audit are sub-issues of one parent issue for the audit.
- A plan's header shows its status (`Draft`, `Accepted`, `In progress`,
  `Done`), so an accepted plan whose issues are not made yet can be seen,
  and, from `In progress` on, the link to its parent issue.
- A new plan is a design doc in `docs/plans/` with the required sections
  (see "Design doc format"), opened as a pull request with status `Draft`.
  Its issues are created only after that pull request is merged.
- `/do-item` takes an issue (`#N`), reads the plan section the issue links
  to, and closes the issue through `Fixes #N` in the pull request.
- A finding met while working is created as an issue at once and named in
  the pull request body and the report to the owner.
- Every label has a GitHub description, and `ISSUE-FORMAT.md` says what each
  label means and when it is set.
- A cloud session can read, create and comment on issues, and close them
  through its pull request, as a local session can. Opening pull requests
  already works there through the Claude GitHub app; reading and writing
  issues is the new need.

### SHOULD

- `/write-plan review <PR#>` answers the owner's comments on a design doc
  pull request: replies to questions, edits the doc, resolves the threads it
  handled.
- The order of work stays readable in git, in `docs/plans/README.md`.
- The `do-item` evals keep checking the same behaviours, offline.

### NICE TO HAVE

- The issues of a plan are created on their own when its design doc pull
  request merges (a GitHub Action running `/to-issues`), instead of by a
  session started by hand. Filed as a follow-up by MIG-5, not built here.

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
| A plan's or an audit's progress | its parent issue (sub-issue list, filled by GitHub) | a sub-issue closes |
| The order of work | "Order of work" in `docs/plans/README.md` | the owner reorders |
| What a label means | the label's description; `ISSUE-FORMAT.md` | a label is added |
| Difficulty levels and hard triggers | "Difficulty" in `docs/plans/README.md` | unchanged by this plan |

### Skills and their files

| Skill | Job | Reads |
|---|---|---|
| `write-plan` | grill the owner, write the design doc, open its pull request; `/write-plan review <PR#>` answers comments; after merge, call `to-issues` | `write-plan/DESIGN-DOC-FORMAT.md` |
| `to-issues` (new) | turn an accepted design doc, an audit, or a list of findings into issues: labels, dependencies, parent issue; for a plan, set its status to `In progress` and add the parent link to its header. Mechanical, so it pins Sonnet in its frontmatter; it gets no difficulty, since it is a skill step, not an item | `to-issues/ISSUE-FORMAT.md` |
| `do-item`, `do-item-hard` | build one issue | the issue, the plan section it links |
| `write-pr` | commit subject and pull request body with `Fixes #N` | the issue |
| `retro` | look back on finished work; files findings through `to-issues` | issues, pull requests, past sessions |

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
  | `type:` | `fix`, `feature` | `fix`: existing code is wrong or worse than it should be (a bug, a risk, a clean-up); the work starts from a reproduction or from reading the code. `feature`: part of a plan that builds something new; the work starts from the design |
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
- **Parent issue:** groups the issues of one plan or one audit: one sentence
  on what it delivers, the link to its file (`docs/plans/<name>.md`, or the
  archived audit file), and its sub-issues. Nothing copied from the file.
- **A finding met while working:** a standalone `type: fix` issue with
  `Found while #N`.
  It becomes a sub-issue of a plan only when the plan cannot finish without
  it, and then it also blocks the task it holds up.

### Design doc format

Adapted from lecture 10 ("Engineering Design Documents, RFCs, and ADRs") of
the system design course; written down in `write-plan/DESIGN-DOC-FORMAT.md`.

| Section | Required | Content |
|---|---|---|
| Header | yes | the bullet list at the top of the file: `Status` (`Draft`, `Accepted`, `In progress`, `Done`), `Written`, `Related`, and from `In progress` on `Issues: #N`, the link to the plan's parent issue and so to its progress |
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

**Status rule:**

| Status | Means | Set by |
|---|---|---|
| `Draft` | its pull request is open; the design is under review | `write-plan` |
| `Accepted` | merged, but its issues are not made yet | the last commit before the merge (an open question that blocks the decision must be closed first) |
| `In progress` | its issues exist; the header links the parent issue | `to-issues`, in a docs-only commit to `main` |
| `Done` | its last sub-issue is closed; the file is in `done/` | the pull request that closes the last sub-issue |

`/do-item` with no argument names an `Accepted` plan, since its issues are
still to be made.

## Main flow and failures

### A new plan

1. `/write-plan <idea>` grills the owner section by section, writes
   `docs/plans/<name>.md` as `Draft` on branch `plan/<name>`, opens a pull
   request, and stops.
2. The owner comments on lines of the doc. `/write-plan review <PR#>` answers
   questions in the threads, edits the doc for changes, pushes, and resolves
   what it handled. Repeat until the owner has no comments.
3. The owner merges. **Success point: the design is accepted.**
4. `/write-plan issues <name>` runs `to-issues`: it reads the merged doc,
   creates the parent issue and one sub-issue per task with labels and
   dependencies, and sets the doc to `In progress` with the parent link.
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
3. The real run creates the labels, the issues, then the parent issues (one
   per open plan, one for the 2026-10-16 audit; the items of `findings.md`
   stay standalone) and the dependencies, recording each old ID and its new
   number.
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
- **A cloud session cannot read or write issues.** Its GitHub access (the
  Claude GitHub app) is known to push and open pull requests; whether it
  also reaches issues is not known. If it does not, `/do-item` cannot find
  its issue. MIG-4 finds out in a real cloud session and adds only what is
  missing (for example `gh` in `session-start.sh`); `/do-item` stops with a
  clear message when it cannot read the issue, instead of falling back to
  the files.
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
| Whether a cloud session reaches issues cannot be checked from a local session | cloud sessions cannot find work | MIG-4's "done when" is seen in a real cloud session |
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
    issues and the `gh` commands to a folder without running them, and pins
    Sonnet in its frontmatter. Read the `writing-for-agents` skill first.
  - **Done when:** `to-issues` in draft mode, run on
    `docs/plans/memory-measurement.md`, writes a parent issue and one
    `type: feature` issue per open MEM task with the right labels, MEM-8's
    dependencies, and the link to the plan, plus the header change to
    `In progress`; on the 2026-10-16 audit, a parent issue with its open
    items as `type: fix` sub-issues; and on two findings from
    `findings.md`, two standalone `type: fix` issues. No issue is created.

- [ ] **MIG-2. `do-item`, `do-item-hard` and `write-pr` work from issues**
  - **Difficulty:** medium
  - **Blocked by:** MIG-1
  - **How:** `do-item #N` reads the issue (`gh issue view`), the plan section
    it links, its dependencies and its `needs-decision` label; with no
    argument it follows "Order of work" through `gh issue list`, and names
    any plan that is `Accepted` but has no issues yet. It files a
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

- [ ] **MIG-4. Cloud sessions reach issues**
  - **Difficulty:** medium
  - **How:** in a cloud session, find out how it can read, create and
    comment on an issue with the access it already has (the Claude GitHub
    app that pushes and opens its pull requests). Add only what is missing,
    for example `gh` and its login in `.claude/hooks/session-start.sh`.
    Write down in `CLAUDE.md` ("Notes for Claude Code") how a cloud session
    reaches issues. `do-item` stops with a clear message when it cannot read
    the issue.
  - **Done when:** in a Claude Code cloud session on this repository, the
    session lists the open issues, creates a test issue, comments on it and
    closes it as not planned (seen by the owner, since a local session
    cannot start one).

- [ ] **MIG-5. The switch: migrate the open items and rewrite the workflow docs**
  - **Difficulty:** medium
  - **Blocked by:** MIG-2, MIG-3, MIG-4
  - **How:** follow "The migration" above with a one-off script that is not
    committed. First, on the first created issue, check that dependencies and
    sub-issues work through `gh` (stop and ask if not). Create the labels with
    their descriptions and delete the defaults; parent issues for
    `memory-measurement` and `solver-optimisations`, with their tasks as
    sub-issues, and one for the 2026-10-16 audit, with its open items as
    sub-issues; dependencies from every `Blocked by`; set both plans to
    `In progress` with their `Issues:` link. File the follow-up issue
    "Create a plan's issues when its design doc pull request merges" (the
    NICE TO HAVE above: a GitHub Action running `/to-issues` with
    `anthropics/claude-code-action`), `type: feature`, `area: workflow`,
    standalone. Rewrite the file lines
    as `Moved to #N`, delete the two plans' `## Tasks` sections (replaced by
    the parent-issue link), and give `findings.md` and the audit file the
    header "Closed archive. Open findings are GitHub issues (`type: fix`)."
    Then rewrite `docs/plans/README.md` (order of work in
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
    their `blocked by` dependencies on GitHub; the three parent issues show
    their sub-issues; `/do-item` with no argument
    names the first unblocked issue in the order of work.

### Glossary changes (applied in MIG-5)

Written here and not in `GLOSSARY.md` yet, because they are false until the
switch:

- **item:** one unit of work as a GitHub issue, about one commit; its type
  is `fix` or `feature`.
- **finding:** a problem noticed in the existing code (a bug, a risk, a
  clean-up). Its issue has type `fix`.
- **fix / feature:** the two types of item. A `fix` changes existing code
  that is wrong or worse than it should be and starts from a reproduction or
  the code; a `feature` is a task of a plan and starts from the design.
- **plan:** the engineering design doc of a feature (`docs/plans/`); its
  tasks are issues. Its status is `Draft` (under review in its pull
  request), `Accepted` (merged, issues not made yet), `In progress` (issues
  made) or `Done`.
- **parent issue:** the issue that groups the items of one plan or one
  audit as sub-issues and links its file.
- **status of an item:** open, waiting (blocked or needs decision), done
  (closed as completed) or dropped (closed as not planned). Not the same as
  a run's status.
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
  `type: fix` would have to guess.
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
- **`kind: finding` / `kind: task`:** the names did not say what kind of
  work an issue is. **`bug` / `plan-task`:** many findings are not bugs
  (dead code, duplication). **No type label, derived from having a plan
  parent:** breaks once a finding is a plan's sub-issue or an audit has a
  parent.
- **The audit's items as standalone issues:** a parent issue shows how much
  of the audit is left, at no cost, and a future audit works the same way.
- **No status between `Accepted` and `Done`:** an accepted plan without
  issues would look the same as one being built.
- **A cron job that polls for accepted plans:** a GitHub Action on the merge
  fires on the event itself; both wait until the switch works by hand.
- **Installing and logging in `gh` in cloud sessions in any case:** cloud
  sessions already push and open pull requests through the Claude GitHub
  app; MIG-4 adds only what reading and writing issues turns out to need.
