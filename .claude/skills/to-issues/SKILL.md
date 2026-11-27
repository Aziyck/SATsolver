---
name: to-issues
description: "Issues from a source: an accepted design doc (Issues: none yet), an audit's open items, or a finding met while working. Sets labels, dependencies and a parent issue. `draft` writes them to a folder and creates nothing."
argument-hint: "[draft] <plan name | audit file | findings>"
model: sonnet
effort: high
---

Make issues from: $ARGUMENTS

Model-invoked on purpose: `write-plan`, `retro` and `do-item` file their
issues through this skill, and a user-invoked skill cannot be reached by
another skill.

Read [`ISSUE-FORMAT.md`](ISSUE-FORMAT.md) first: the issue, its labels and
the `gh` calls. Your output is issues and the header of one plan file.

Two modes. With `draft` first in the arguments you are in **draft mode**: you
only write files into a folder, and every `gh` call you run is a read:
`gh label list`, `gh issue list`, `gh issue view`, and `gh api` with no
`-f`, `-F`, `--field`, `--raw-field`, `--input`, and no `-X` other than
`GET`. Without it you
create the issues, once the owner has seen the drafts of this source or has
said to go ahead.

## 1. Pick the source

- **A plan name:** `docs/plans/<name>.md`.
  - A plan in the design doc form
    ([`DESIGN-DOC-FORMAT.md`](../write-plan/DESIGN-DOC-FORMAT.md)) whose header
    says `Issues: none yet` has no task list: cut its Requirements into tasks
    (step 2).
  - An older plan has its tasks in `## Tasks`: take each `- [ ]` item. A
    `- [x]` item is closed; skip it.
  - A plan whose header already has `Issues: #N` or a link to a parent issue
    has its issues: stop and say so.
- **An audit file** (`docs/reviews/<date>-audit.md`): each `- [ ]` item.
- **Findings:** the IDs or titles named, from `docs/reviews/findings.md` or
  from the conversation. Standalone: no parent.

The folder for the drafts: the scratchpad when the system prompt names one,
`mkdir -p` first.

**Done when** you can list the source's open items (or, for a new plan, its
requirements) and their IDs.

## 2. Slice (new design doc only)

An item of an older source is already one commit. For a design doc, cut the
MUST and SHOULD requirements into **tasks**: each is one commit and one
session, ends on observable behaviour, and cuts through the layers it needs
rather than doing one layer of everything. Test the slice: could a session
that has read only this issue and the plan section finish it? If not, split
it or give it the missing link.

Name a task `<PREFIX>-<n>. Title` with a short prefix for the plan. A
requirement becomes the task's `Done when`; a failure path or a quality target
that the design names must be one task's `Done when` too, so nothing the
design promises is left without an issue.

**Done when** every MUST of the doc is the `Done when` of at least one task.

## 3. Write one draft per issue

For each item, in order, write `NN-<ID or slug>.md` in the folder:

```markdown
---
title: "A5. A big DIMACS file is parsed three times per encode"
labels: ["difficulty: easy", "area: problems", "type: fix"]
parent: "Audit: 2026-10-16"         # or "Plan: memory-measurement"; none for a standalone issue
blocked_by: ["MEM-4"]               # IDs or titles of open issues only
---
<body: the fields of ISSUE-FORMAT.md, copied from the source>
```

Rules, in this order:

1. **Copy, do not rewrite.** The body is the source's fields, dedented to
   the left margin, with the checkbox, the `Difficulty` line and the
   `Blocked by` line removed (labels and dependencies carry them), plus the
   "where it came from" line. A note after the title
   (`(added 2026-11-13, found while A2)`) goes into that line:
   `From docs/reviews/findings.md (A23; added 2026-11-13, found while A2).`
   A reference to text elsewhere in the source ("see 'Optional later'
   above", "the shared checks above") becomes a link to that section of
   the file on `main`. For a plan task, link the plan's section it builds;
   for an older plan, its `## Tasks` section and the task ID.
2. **Difficulty.** Copy it, then compare the files the fix names with the
   hard triggers in `docs/plans/README.md` ("Difficulty"). A match with no
   `Not hard` line becomes `difficulty: hard`, with one line in the body:
   `Re-rated (<date>): <trigger>`. A parenthetical after the difficulty
   (`hard (solver code; speed must not change)`) goes into the body as
   `Rated hard: solver code; speed must not change.`
3. **Area and type** as in `ISSUE-FORMAT.md`: plan task is `type: feature`,
   audit or finding is `type: fix`.
4. **Needs decision:** an open one gets the `needs-decision` label and stays
   in the body. A `Decided (date)` line stays as text, with no label.
5. **Dependencies.** `Blocked by` names that are closed in the source, or
   that are not open items, are dropped; the others go in `blocked_by`. A
   name that cannot be found is a stop: ask the owner.

Then the parent, when the source has one: `00-parent.md` with its title, one
sentence on what it delivers, and the link to the source file by its path
on `main` (`docs/reviews/2026-10-16-audit.md`). Nothing copied from the
file.

**Done when** every open item has one draft, every `blocked_by` names a
draft in the folder or an issue that already exists, and no draft has two
`difficulty:`, `area:` or `type:` labels.

## 4. Plan header

For a plan, write `header.md` in the folder: the exact change to the plan's
header, not applied in draft mode.

- A design doc: `- **Issues:** none yet` becomes `- **Issues:** #<parent>`.
- An older plan: the status word of its `- **Status:**` line becomes
  `in progress`, keeping any note after it (`in progress (MEM-1 to MEM-3
  done 2026-11-23)`), and a line `- **Issues:** #<parent>` is added under
  `Written`.

## 5. The commands

Write `commands.sh` in the folder: the labels that do not exist yet
(`gh label list` is a read, run it), then the `gh issue create` calls in
file order, the sub-issue calls and the dependency calls, in the order of
`ISSUE-FORMAT.md`. A number or id that only exists after a call is a shell
variable set from the previous call's output. `--body-file` gets the draft
without its front matter (everything after the second `---` line).

In draft mode, stop here: report the folder, the count of issues by source,
and any decision you took (an area chosen between two, a re-rating). The
owner reads the drafts.

## 6. Create (without `draft`)

1. Run `commands.sh` step by step. Create the parent and the first child,
   link them as sub-issue, and add one dependency (or, for a source without
   one, check the `blocked_by` endpoint with a read) before any other issue;
   if a call fails, stop and ask the owner (the fallback is a
   `Blocked by: #N` line in the body).
2. A rerun skips an issue whose title already exists
   (`gh issue list --state all --search "<title> in:title" --json number,id,title`),
   and sets its number and id variables from that output, so the later
   calls still have them. A sub-issue or dependency call that answers
   "already" is done. A run that stopped half-way is finished, not
   duplicated.
3. Apply `header.md` to the plan file and commit it to `main` on its own,
   docs only, with the subject `Plan <name>: issues created (#<parent>)`.
4. Report the parent's URL and the issues made, as a list of `#N title`.

**Done when** every draft has an issue, the plan's header links its parent
issue, and the report lists them.
