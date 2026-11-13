# Architecture decision records

An ADR is a short note of one decision that shapes the project: what the
situation was, what was decided, and what follows from it. Its job is to stop
a settled question from being reopened by someone (a person or an agent) who
does not know why it was settled.

## Rules

- One decision per file, named `NNNN-short-title.md`, numbered from `0001`.
- An ADR is never edited after it is accepted, apart from its status line. A
  decision that changes gets a new ADR that says which one it replaces, and
  the old one's status becomes `Superseded by NNNN`.
- Write one when a decision is hard to reverse, was chosen over a real
  alternative, or would surprise a newcomer. Routine choices do not need one.
- A `Needs decision` item in a plan or review that turns out to be a big
  choice becomes an ADR when it is decided. When a plan is finished, its
  "Considered and rejected" section is the raw material for one.
- Decisions made before 2026-11 have no ADR. Their reasons are in `AGENTS.md`,
  the guides and the "Considered and rejected" sections of the plans; write an
  ADR for an old decision only when it is questioned.

## Template

```markdown
# NNNN. Title of the decision

- **Status:** Accepted (YYYY-MM-DD) | Superseded by NNNN
- **Decided by:** who

## Context

The situation and the forces at play, in a few sentences.

## Decision

What we do, stated as a rule.

## Alternatives considered

Each option that was set aside, with the reason.

## Consequences

What becomes easier, what becomes harder, what to watch.
```

## Index

| ADR | Decision |
|---|---|
| [0001](0001-agent-workflow.md) | Work is tracked as items in reviews and plans; code changes go through a branch and a pull request |
| [0002](0002-origin-and-host-checks.md) | The server accepts only local `Host` and `Origin` values, and needs no token |
