# 0005. One item skill; the difficulty picks the model, and hard is set by triggers

- **Status:** Accepted (2026-11-20)
- **Decided by:** the repository owner
- **Replaces:** point 6 of [ADR 0001](0001-agent-workflow.md) (two skills,
  `/fix-item` and `/do-plan-step`)

## Context

Two skills drove the work: `/fix-item` for review items and bug reports,
`/do-plan-step` for plan tasks. Their review and closing steps were word for
word the same, and every workflow change had to be made twice. The order of
work mixes review items and plan tasks, but neither skill took "the next
item" from both.

Both skills were pinned to Sonnet, because a skill's model is fixed before it
has read the item. So hard items, the ones about processes, threads,
cancellation, security, storage and solver loops, were built by the weaker
model and only reviewed by Opus. Medium items were reviewed by Sonnet, the
same model that built them; those reviews reported nits and confirmed no
defect (pull requests #36, #41, #46), while the hard reviews on Opus found
real issues (#35, #49).

Difficulty was also rated by the size of the change rather than by its risk:
A40, a missing lock around one call in a thread, was rated easy although the
definition lists threads as hard. Nothing checked the rating after the item
was written.

## Decision

- One skill, `/do-item`, works on any item: a review finding, a plan task, a
  bug report, or the next item in the order of work. It is pinned to Sonnet.
- `/do-item-hard` runs the same steps, pinned to Opus. `/do-item` stops at a
  hard item and names `/do-item-hard <ID>`. The owner never picks a model.
- Medium and hard items are reviewed by the `reviewer` agent, on Opus, in a
  fresh context, at level `medium` or `high`.
- Hard is defined by **triggers** (files and concepts in
  `docs/plans/README.md`), not by size. An item that matches one is rated
  lower only with a `Not hard:` line saying why. `/do-item` checks the
  rating against the triggers before starting and against the diff before
  the review.

## Alternatives considered

- **Keep two skills and share the common steps through a third file.** It
  removes the duplicated text but keeps two entry points, and still leaves no
  skill that takes the next item from both queues.
- **No model pin; the owner switches to Opus for hard items.** It works, but
  the owner has to remember, and a session left on Opus runs easy items on
  it.
- **Build hard items on Sonnet and rely on the Opus review.** The previous
  rule. A review finds bugs in a diff; it does not replace the judgement that
  produced the diff, which is what hard items need.
- **Path-only triggers, including every file in `solvers/`.** It would make
  every solver clean-up hard, although those are guarded by unchanged
  conflict counts. Solvers trigger only for their hot loops or a change meant
  to alter the search.

## Consequences

- Hard items cost more per item, because they are built on Opus. The
  triggers make more items hard: eight open items were re-rated on
  2026-11-20.
- Medium reviews cost an Opus call each.
- The evals under `.claude/skills/do-item/evals/` name items that are open
  today (A8, A31, A40, MEM-1, RUNNER-3). They go stale as those items close,
  as the previous evals did, and need new targets then.
