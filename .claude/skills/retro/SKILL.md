---
name: retro
description: "Retrospective on finished work: find what made the agents slow or wrong, and turn each fix into a check, a pointer or a finding."
argument-hint: "[empty for this session; a plan, PR numbers or session IDs]"
disable-model-invocation: true
---

Run a retrospective on: $ARGUMENTS (empty: this session).

You improve the **environment** the next agent works in, not the code of
this change. Run it after a plan or a run of items is finished, not after
every item.

## 1. Gather, cheaply

Start with what the repository already records, before any transcript:

- the pull requests' review findings and the owner's comments:
  `gh pr view <n> --comments`, `gh api repos/{owner}/{repo}/pulls/<n>/comments`;
- `Escalate:` lines, and findings filed "found while" an item
  (`grep -rn "Escalate:\|found while" docs/reviews docs/plans`).

Then the sessions. This session is in your context. Earlier sessions of a
local Claude Code are JSONL files in `~/.claude/projects/<repo path with
dashes>/`, kept 30 days by default. Never read one whole: run
`python .claude/skills/retro/digest.py <file.jsonl>`, which prints only the
owner's messages and the tool calls that failed. A cloud session's
transcript stays in its own container: if a session you were asked about is
not on disk, say so and work from the pull requests.

## 2. Look for

- **Navigation:** the agent searched long for a file or a rule. Fix: a
  pointer in the folder's `AGENTS.md` or the guide, not in the root file.
- **Mechanical mistakes:** a pattern, an import, a name, a banned call.
  Fix: a test or a ruff rule. Check `pyproject.toml`, `package.json` and
  `.github/workflows/ci.yml` first: a check that exists but is not wired is
  the finding.
- **Judgement mistakes** the review missed: a line for the `code-review`
  levels the `reviewer` agent runs.
- **No-ops and load:** lines in `AGENTS.md`, `CLAUDE.md` or a skill that did
  not change what the agent did. Fix: delete them. Root `AGENTS.md` only
  shrinks.
- **Expensive steps:** a tool call, a subagent or a check that cost a lot for
  little. Fix: a cheaper command named where the agent looks for it.
- **Missing information:** something the agent needed and could not see
  (a log, a server output). Fix: a way to reach it.

## 3. Report

Candidates ranked by how much they cost, each with the evidence (session,
PR, line) and the fix. A new skill is never the fix unless it replaces one
(root `AGENTS.md`, "Conventions"). For each candidate the owner accepts,
file a finding at the end of `docs/reviews/findings.md` in the item format,
marked `(added <date>, found by retro)`. Fix nothing in this session.
