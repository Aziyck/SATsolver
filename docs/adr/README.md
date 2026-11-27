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
| [0003](0003-legacy-is-a-frozen-archive.md) | `legacy/` is a frozen archive; its tests are not kept passing |
| [0004](0004-where-the-run-environment-is-read.md) | The server reads the machine once; each job reads its interpreter and git |
| [0005](0005-one-item-skill-model-by-difficulty.md) | One item skill, `/do-item`; the difficulty picks the model, and hard is set by triggers |
| [0006](0006-the-solver-child-ends-with-its-stdin.md) | The solver child ends when its stdin reaches its end; the parent keeps it open for the run |
| [0007](0007-each-job-chooses-its-interpreter.md) | Each solve or benchmark job chooses Python or PyPy; the server finds PyPy, the browser never names a path |
| [0008](0008-work-items-are-github-issues.md) | Work items are GitHub issues; plans are design docs reviewed in a pull request |
