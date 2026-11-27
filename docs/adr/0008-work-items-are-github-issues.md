# 0008. Work items are GitHub issues; plans are design docs reviewed in a pull request

- **Status:** Accepted (2026-11-27)
- **Decided by:** the repository owner
- **Replaces:** point 1 and the "GitHub Issues as the tracker" alternative of
  [ADR 0001](0001-agent-workflow.md), and amends its point 5: a new or
  changed design doc goes through a pull request although it is
  documentation only. Points 2 to 4 and 7 of ADR 0001 stand
- **Plan:** [github-issues.md](../plans/github-issues.md)

## Context

Open work was 60 items in four Markdown files. Finding, ordering and closing
an item meant editing a file by hand, and a plan mixed two things that change
at different speeds: the design, which should be settled before work starts,
and the task list, which changes with every commit.

The design part was also too thin. The PyPy runner plan described the happy
path and the protocol but not what happens to the solver child when its
parent dies. The RUNNER-3 review found the gap; RUNNER-5 then built a pid
watchdog and replaced it hours later with the stdin lifeline
([ADR 0006](0006-the-solver-child-ends-with-its-stdin.md)). A design that
had to show its failure paths and compare two solutions would have raised
the question before any code.

ADR 0001 rejected GitHub Issues because "the plans and reviews already hold
the design context next to the tasks", and said to revisit it if the
workflow outgrew files. It has.

## Decision

1. A **task** or a **finding** is a GitHub issue on `Aziyck/SATsolver`, with
   labels for difficulty, area and type (`fix` or `feature`). "Blocked by"
   is a GitHub issue dependency; the tasks of one plan, and the open items
   of one audit, are sub-issues of one parent issue. The contract is in
   `.claude/skills/to-issues/ISSUE-FORMAT.md`.
2. A **plan** is an engineering design document in `docs/plans/`, in the
   form of `.claude/skills/write-plan/DESIGN-DOC-FORMAT.md` (problem,
   requirements, non-goals, main flow and failures, at least two solutions,
   risks). It is opened as a pull request and the owner reviews it with line
   comments; the merge is the acceptance, so a new or changed design doc
   never goes straight to `main`. Its issues are created only after that
   merge, by the skill `to-issues`.
3. A plan has no status field. Its state follows from facts that change
   anyway: the file exists only on its pull request branch (draft); it is
   on `main` with `Issues: none yet` (accepted); it has `Issues: #N`, the
   link to its parent issue (in progress); it is in `docs/plans/done/`
   (done).
4. A task's text lives in its issue and a plan's text in its file; neither
   is copied into the other, and an issue links the section of the plan it
   builds.
5. The queue's order stays in "Order of work" in `docs/plans/README.md`,
   reviewed in git.
6. A pull request says `Fixes #N`; a commit subject starts with the old ID
   and `#N` for a migrated item (`A4 (#N): ...`), with `#N` alone for a new
   one.
7. Closed items are not migrated; they stay in their files as an archive.

The switch itself (migrating the open items and rewriting the workflow
docs) is task MIG-5 of the plan.

## Alternatives considered

- **Keep the files.** Offline and in the clone, but statuses and order are
  hand-edited, design and tasks stay mixed, and a design gets no review step.
- **Everything on GitHub, the design as a parent issue (a PRD).** One tool
  and a progress bar, but a design that is revised often is hard to review
  and diff in an issue body, has no line comments, and is not in the clone.
- **A GitHub Project board or milestones for the order of work.** A second
  tool to keep in sync for a one-person project.
- **A `Status` field in each plan's header.** It has to be flipped by hand at
  each stage and drifts from the facts (a merged plan still saying `Draft`).

## Consequences

- A design is reviewed and accepted before any task exists, which is the step
  RUNNER-5 lacked.
- Tasks have statuses, dependencies and a progress bar without hand edits.
- A reader needs both the repository and GitHub to see a plan and its
  progress, and an agent needs `gh` (or the Claude GitHub app in a cloud
  session) to find work. Open work is no longer in the clone.
- Issues and pull requests share one number sequence; a `#N` in a commit
  subject is always an issue.
- Whether the dependency and sub-issue API works through `gh` is checked on
  the first issue MIG-5 creates; the fallback is a `Blocked by: #N` line in
  the body.
- Until MIG-5, the file-based workflow of `docs/plans/README.md` is still the
  one in use.
