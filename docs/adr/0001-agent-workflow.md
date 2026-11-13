# 0001. Work is tracked as items; code changes go through a branch and a pull request

- **Status:** Accepted (2026-11-13)
- **Decided by:** the repository owner, after the research recorded in
  `docs/plans/agent-workflow.md`

## Context

Most changes to this repository are made by coding agents in separate
sessions that share no memory. Open work lived in a review and three plans
whose items had no test for "done", no marked open decisions, no difficulty,
stale line numbers and duplicates. Work was committed straight to `main`, so
CI ran only after a change had landed. A cheaper model is good enough for
well-specified items, but nothing said which items those are.

## Decision

1. Open work is a list of **items** in `docs/reviews/` (findings about
   existing code) and `docs/plans/` (features not built yet). The format,
   the difficulty levels, the statuses and the closing rule are defined once,
   in `docs/plans/README.md`.
2. Every item states **done when** as observable behaviour. The session that
   takes the item writes that as a test first and watches it fail.
3. An open choice is marked **Needs decision**; work on the item stops there
   until the owner decides.
4. Every item has a **difficulty** (easy, medium, hard). `CLAUDE.md` maps it
   to a model and a review level.
5. **Code changes are made on a branch and merged through a pull request**, so
   CI runs before `main` changes. Documentation-only changes may go to `main`
   directly. One item (or a few small related ones) per branch.
6. Two repository skills drive the work: `/fix-item` for review items and bug
   reports, `/do-plan-step` for plan tasks. Implementation happens in the main
   session, one item at a time; subagents are for read-only research or when
   the owner asks.
7. Shared vocabulary lives in `GLOSSARY.md`; decisions from now on get an ADR.

## Alternatives considered

- **Adopting Matt Pocock's engineering skills or obra/superpowers as they
  are:** they assume an issue tracker with triage labels, specs and tickets,
  or worktrees and per-task subagents. That is more machinery than a
  one-person project needs, and a second set of conventions for agents to
  reconcile. Their ideas were borrowed instead (a red-capable reproduction
  first, fresh verification before any claim, rulings instead of stalls), and
  `writing-for-agents` was copied as a reference skill.
- **GitHub Issues as the tracker:** the plans and reviews already hold the
  design context next to the tasks, and they travel with the code. Revisit if
  other people start reporting bugs.
- **Worktrees:** only useful for several agents working at once.
- **Committing everything to `main`:** simplest, but a failed attempt lands in
  history and CI is only a report after the fact.
- **One skill for everything:** fixing starts from a reproduction, plan steps
  start from a design and often a measurement. One skill would put the wrong
  first step in front of the model half of the time.

## Consequences

- An item can be handed to a mid-tier model with little supervision when it is
  easy or medium and its "done when" is clear.
- Writing an item takes longer: it needs a "done when", a difficulty and any
  open decision spelled out.
- Each code change costs a branch and a pull request.
- `docs/plans/README.md` is a single point of truth that the skills, `AGENTS.md`
  and the items all rely on; keep it short and current.
