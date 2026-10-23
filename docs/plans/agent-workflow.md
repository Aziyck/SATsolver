# Plan: a workflow for agent-driven fixes and features

- **Status:** draft, under discussion (nothing decided yet)
- **Written:** 2026-10-23, against commit `189c2bf`
- **Related:** [2026-10-16 audit](../reviews/2026-10-16-audit.md),
  [solver optimisations](solver-optimisations.md),
  [PyPy runner and run metadata](pypy-solver-runner-and-run-metadata.md),
  [memory measurement](memory-measurement.md)

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

## Proposed order of repo changes

- [ ] Add "done when" tests, "needs decision" flags and difficulty/model hints
  to the review items.
- [ ] Remove the duplicates between the audit and the plans (one owner per
  item, a link from the other place).
- [ ] Add a short "what's next" index (order, dependencies).
- [ ] Split the steps that are too big for one session.
- [ ] Write the closing rule next to "Before you finish" in `AGENTS.md`.
- [ ] SessionStart hook: install `requirements-dev.txt` and the frontend
  packages, and make the API tests impossible to skip silently.
- [ ] Write the two skills.

## Open questions (2026-10-23)

To settle before changing anything; record each decision here.

1. Adopt a `GLOSSARY.md` and ADRs (as in Matt Pocock's workflow), or keep an own
   lighter workflow?
2. Work on branches or worktrees (superpowers), or keep committing to `main`?
3. Copy Matt Pocock's `writing-for-agents` (with `SKILL-MECHANICS.md`) into the
   repo before writing our own skills?
4. Rules for subagents (another repo burned tokens on 3 parallel subagents)?
5. "Done when" tests: written by the agent first, or present before the task
   starts?
6. "Needs decision" tag: agreed in principle; define its format.
7. A skill that turns an audit into plans? Where are the duplicates exactly?
8. A plan index with status and a "blocked" tag?
9. How to split big plans: more plans, or more detailed tasks inside a plan?
10. Closing rule and statuses (done, dropped, needs a stronger model).
11. Rewrite plans with function names and behaviour instead of line numbers;
    include code snippets or not?
12. Difficulty tag to choose between Sonnet and a stronger model.
13. SessionStart hook, rule that the API tests must run, `ruff`,
    `pyproject.toml`, a type checker.
14. Docs volume: restructure, shorten, mark human-only docs?
15. Frontend tests first, even before A1-A3?
16. More inspiration for `/do-plan-step` (Matt's `implement`); split skills into
    smaller ones (like `implement` calling `code-review`)?

## Sources

- https://github.com/mattpocock/skills (read 2026-10-23, commit `5beb35b`)
- https://github.com/obra/superpowers (read 2026-10-23, commit `2ce8aa1`)
- https://code.claude.com/docs/en/skills
