# Plan: a workflow for agent-driven fixes and features

- **Status:** done (2026-11-13). The decisions are recorded in
  [ADR 0001](../adr/0001-agent-workflow.md); the rules live in
  [README.md](README.md), `AGENTS.md` and `CLAUDE.md`.
- **Written:** 2026-10-23, against commit `189c2bf`
- **Related:** [2026-10-16 audit](../reviews/2026-10-16-audit.md),
  [solver optimisations](solver-optimisations.md),
  [PyPy solver runner](pypy-solver-runner.md), [run metadata](run-metadata.md),
  [memory measurement](memory-measurement.md)

This file is kept as the record of the research and of what was decided. The
sections up to "What was done" describe the state on 2026-10-23, before the
changes.

## Goal

Work through the open review items and plans in small, well-specified steps
that a mid-tier model (Sonnet, high effort) can finish reliably, escalating to
a stronger model only for the hard ones. Two repo-specific skills drive the
work; the plans and reviews become precise enough to execute without
re-discussing them.

## What already exists (researched 2026-10-23)

**Installed here:** the built-in skills `code-review` (reviews a diff, can
apply fixes with `--fix`), `security-review`, `simplify`, `run` (starts the
app to check a change), `skill-creator`, `session-start-hook`. None of them
takes an item from our review or plan files and drives it to done. The repo
has no skills yet (`.claude/skills/` does not exist).

**Matt Pocock's skills** (github.com/mattpocock/skills, MIT, 38 skill files):

- `implement` (17 lines): implement from a spec or tickets, typecheck and run
  single tests regularly and the full suite at the end, run `code-review`,
  commit.
- `diagnosing-bugs`: the strongest bug-fixing discipline found. Before
  touching code, build a *tight, red-capable* loop: one command already run
  that fails on this exact bug, fast and deterministically. Then reproduce,
  minimise, rank 3-5 falsifiable hypotheses, write the regression test before
  the fix, clean up the debug output.
- `triage` + `AGENT-BRIEF.md`: how to write a task an unattended agent can
  finish: behaviour and names rather than file paths and line numbers,
  testable acceptance criteria, an explicit out-of-scope list.
- `writing-for-agents` (+ `SKILL-MECHANICS.md`): the theory behind them: every
  step ends on a clear completion criterion, one source of truth per fact,
  prompt the positive instead of prohibitions, user-invoked skills cost no
  context.
- Caveat: the engineering skills assume an issue tracker (GitHub, or local
  markdown under `.scratch/`), a `GLOSSARY.md` and ADRs.

**obra/superpowers** (github.com/obra/superpowers, 15 skills):

- `systematic-debugging`: no fix without the root cause first.
- `verification-before-completion`: no "fixed" or "tests pass" claim without
  fresh command output.
- `executing-plans`: work through a plan without stopping after every task,
  write every judgement call down as a ruling, stop only for destructive,
  security-sensitive or shared-branch actions. It says a fully specified plan
  "runs well on a mid-tier session model", with the strongest model kept for
  the final review.
- Caveat: heavy ("iron laws", worktrees per branch); assumes branches and pull
  requests.

**Claude Code skill mechanics** (code.claude.com/docs/en/skills):

- Frontmatter `model: sonnet` and `effort: high` exist, but apply only to the
  turn that invoked the skill; the session model resumes with the next
  message. `context: fork` runs the skill in a subagent on that model (which
  then cannot ask questions mid-way).
- `disable-model-invocation: true`: only the user can start the skill
  (`/name`); it costs no context otherwise.
- Project skills: `.claude/skills/<name>/SKILL.md`, committed, loaded for every
  session in the repo. Keep `SKILL.md` under 500 lines.

## Gaps in the plans and reviews

1. Audit items have no "done when" test. Example for A1: "a POST with
   `Origin: http://evil.example` gets 403 and a WebSocket from that origin is
   refused".
2. Open design decisions are not marked consistently (B4 is; A1 hosts and
   ports, A4 where Edit gets the CNF text, A8 open or exit are not).
3. Duplicates: audit A2 is also step 4 of the solver-optimisations plan; A11
   contains B14.
4. No single "what's next" list; order and dependencies are spread over prose.
5. Some steps are too big for one session (PyPy runner protocol + cancel +
   timeout + errors in one checkbox; A1 touches HTTP and the WebSocket).
6. No closing rule (done with commit hash, dropped with reason).
7. Line numbers go stale after the first fix; names and behaviour last.
8. No difficulty or model hint per item.

## Repo health findings

- **Risk for unattended runs:** a fresh session has no dependencies, and
  `tests/test_api.py` skips itself when FastAPI is missing, so "OK
  (skipped=1)" can be reported as success.
- No Python linter or type checker in CI; no `pyproject.toml`.
- Docs volume: about 1,400 lines of plans and reviews; `AGENTS.md` (about 290
  lines) is loaded every session; user guide and report docs have no freshness
  check.
- Frontend unit tests are thin: 23 tests for about 6,700 lines; most UI
  behaviour is covered only by 10 end-to-end tests.
- Audit A1-A3 are still open.

## Proposed skills

Both user-invoked (`disable-model-invocation: true`), in `.claude/skills/`, each
well under 100 lines, ending by pointing to "Before you finish" in `AGENTS.md`
rather than repeating it.

1. **`/fix-item <ID or bug report>`:** locate the item by ID; restate it; build
   a tight red-capable reproduction (for pure refactors: agreement tests,
   unchanged conflict counts, unchanged timings); minimal fix plus regression
   test; fresh verification including the API tests; tick the item with the
   commit hash; one commit per item; stop on "needs decision"; after three
   failed verification attempts stop and report (the escalation point).
2. **`/do-plan-step <plan>`:** take the first unchecked step whose dependencies
   are done; implement test-first; measure when the plan says so; update
   checkboxes, status line and docs; record judgement calls as rulings in the
   commit message.

Possible later: `/triage-bug` (raw report to a review item with a reproduction
and a done-when test), only if that is done by hand often.

## What was done (2026-11-13)

- [x] **WF-1. Item format with "done when", "needs decision", "blocked by" and difficulty** - Done 2026-11-13. Defined in [README.md](README.md); applied to the audit and every plan.
- [x] **WF-2. One owner per item** - Done 2026-11-13. Audit A2 owns the renumbering (OPT-4 points to it); A11 owns `cdcl_debug` (B14 points to it).
- [x] **WF-3. A "what's next" index** - Done 2026-11-13. "Order of work" in [README.md](README.md).
- [x] **WF-4. Steps sized to one commit** - Done 2026-11-13. The runner is RUNNER-1 to RUNNER-10; the run metadata became its own plan (META-1 to META-5).
- [x] **WF-5. Closing rule and statuses** - Done 2026-11-13. In [README.md](README.md); "Before you finish" in `AGENTS.md` points to it.
- [x] **WF-6. Names instead of line numbers** - Done 2026-11-13. The audit was rewritten; the rule is in [README.md](README.md).
- [x] **WF-7. Tooling** - Done 2026-11-13. SessionStart hook for cloud sessions, `WIZSAT_REQUIRE_API_TESTS`, `ruff` with `pyproject.toml`, both in CI.
- [x] **WF-8. Glossary and ADRs** - Done 2026-11-13. `GLOSSARY.md`; `docs/adr/` with a template and ADR 0001.
- [x] **WF-9. Leaner `AGENTS.md` and a code-to-docs table** - Done 2026-11-13.
- [x] **WF-10. Skills** - Done 2026-11-13. `/fix-item`, `/do-plan-step` and a copy of `writing-for-agents` in `.claude/skills/`.
- [x] **WF-11. A type checker for Python** - Dropped 2026-11-13: the code is not annotated enough for mypy to give a useful signal yet. Revisit after the solver clean-up.

## Decisions on the open questions (2026-11-13)

1. **Glossary and ADRs:** a `GLOSSARY.md` now, including the solver terms.
   ADRs from now on only; no ADRs for old decisions unless one is questioned.
   Matt Pocock's wider workflow is not adopted; start small and iterate.
2. **Branches:** code changes go on a branch and through a pull request, one
   item (or a few small related ones) per branch; documentation-only changes
   may go to `main`. No worktrees.
3. **`writing-for-agents`:** copied into `.claude/skills/` (MIT, with licence
   and source commit).
4. **Subagents:** implementation in the main session, one item at a time;
   subagents only for read-only research or when asked; never several at once
   unless asked. Rule in `CLAUDE.md`.
5. **"Done when" tests:** the item states the behaviour; the session that
   takes the item writes the test first.
6. **Needs decision:** `Needs decision:` with question, options and
   recommendation; rewritten as `Decided (date):` once answered.
7. **Audit to plans:** no skill; a rule instead (an item bigger than one
   commit moves into a plan, the review keeps a pointer).
8. **Index:** `docs/plans/README.md` holds the order and the dependencies;
   statuses stay on the items; `Blocked by:` on the item.
9. **Splitting plans:** one file per feature with a shared design; tasks of
   one commit each with their own ID; a new file only for a part that ships on
   its own (run metadata).
10. **Closing rule:** done with date and the ID in the commit subject; dropped
    with a reason; `Escalate:` after three failed attempts.
11. **Line numbers:** names and behaviour instead; snippets only for
    interfaces.
12. **Difficulty:** easy, medium, hard, defined in `README.md`; the mapping to
    a model is in `CLAUDE.md`.
13. **Tooling:** hook, `WIZSAT_REQUIRE_API_TESTS`, `ruff`, `pyproject.toml`
    now; a type checker later.
14. **Docs volume:** `AGENTS.md` trimmed to rules and pointers, details moved
    to the guides; a table says which doc belongs to which code area; the
    report folder is edited only on request.
15. **Order:** must-fix findings A1-A3, then frontend tests, then features.
    Recorded in `README.md`.
16. **Skills:** `/do-plan-step` borrows the rhythm of Matt Pocock's
    `implement` and the rulings and stop conditions of superpowers'
    `executing-plans`; both skills call the built-in `code-review` rather
    than a skill of our own; no further splitting until two skills share a
    multi-step procedure.

## Sources

- https://github.com/mattpocock/skills (read 2026-10-23, commit `5beb35b`)
- https://github.com/obra/superpowers (read 2026-10-23, commit `2ce8aa1`)
- https://code.claude.com/docs/en/skills
