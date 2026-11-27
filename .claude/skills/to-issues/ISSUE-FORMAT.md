# Issue format

What an issue of this repository looks like, and what each label means.
[ADR 0008](../../../docs/adr/0008-work-items-are-github-issues.md) records
the decision; the plan is
[github-issues.md](../../../docs/plans/github-issues.md).

## Title and commit subject

- A migrated item keeps its ID as a prefix: `A4. A large DIMACS file's text
  is sent and kept everywhere`. A new issue has only its title.
- The commit subject is `A4 (#N): ...` for a migrated item and `#N: ...` for
  a new one. A `#N` there is always an issue.

## Body

The item's fields, as the file format has them today; leave out a field
with nothing to say:

- `Problem` (a finding) or `What` (a task): what is wrong or missing, with
  the case that shows it.
- `Fix` or `How`: the smallest change that works.
- `Worth it when`: the bar for a speed or memory item, set before measuring.
- `Done when`: behaviour that can be observed and tested.
- `Not hard`: why a matching hard trigger does not apply, only when the
  issue is rated below one.
- `Needs decision`: the question, the options and the recommendation, with
  the label. The owner answers in a comment; the next session rewrites it as
  `Decided (date): ...` and removes the label.
- Where it came from: `From the 2026-10-16 audit (A4)`, `Found while #N`, or
  `From plan <name>, section <heading>` with a relative link to the plan
  file on `main` (`docs/plans/<name>.md#<anchor>`).

Text is copied from the source item unchanged, apart from the `Blocked by`
line (it becomes a dependency) and the checkbox. Names, not line numbers;
snippets only for interfaces.

## Labels

Every issue has one `difficulty:`, one `area:` and one `type:` label.

| Label | Means |
|---|---|
| `difficulty: easy` | a local change covered by existing tests, with a clear "done when" and no hard trigger |
| `difficulty: medium` | several files or new tests, or a behaviour users see, but no hard trigger |
| `difficulty: hard` | matches a hard trigger or has an open design question; sets Opus and the review at level `high` (`docs/plans/README.md`, "Difficulty") |
| `area: solvers` | the fix touches `solvers/` most |
| `area: problems` | `problems/` |
| `area: sat_core` | `sat_core/` |
| `area: sat_web` | `sat_web/` |
| `area: frontend` | `frontend/` |
| `area: workflow` | skills, agents, hooks, CI, `AGENTS.md`, `CLAUDE.md` |
| `area: docs` | documentation only, outside the above |
| `type: fix` | existing code is wrong or worse than it should be (a bug, a risk, a clean-up); the work starts from a reproduction or from reading the code |
| `type: feature` | a task of a plan that builds something new; the work starts from the design |
| `needs-decision` | an owner question is open; work stops |

The area is the folder the fix touches most; when two tie, the one that holds
the behaviour change. The difficulty is copied from the item and re-rated
against the hard triggers: a task whose fix matches a trigger and has no
`Not hard` line gets `difficulty: hard`, and the body says why.

GitHub's nine default labels (`bug`, `enhancement`, ...) are deleted once,
in MIG-5; an agent offered `bug` next to `type: fix` would have to guess.
Each label has a GitHub description, the one-line "Means" above. Colours:
one per group (`difficulty:` green to red by level, `area:` one shared
colour, `type:` one shared colour, `needs-decision` yellow).

## Statuses

| Status | On GitHub |
|---|---|
| open | open issue |
| waiting | open, with a `blocked by` dependency or `needs-decision` |
| done | closed as completed, by the merged pull request's `Fixes #N` |
| dropped | closed as not planned, with the reason in a closing comment |

An issue may start when it is open, every issue it is blocked by is closed,
and it has no `needs-decision` label.

## Dependencies and parents

- "Blocked by" is a GitHub issue dependency. A blocker that is already closed
  or done is left out. A blocker in another plan is a dependency across
  parents.
- A **parent issue** groups the issues of one plan or one audit as
  sub-issues: one sentence on what it delivers, the link to its file
  (`docs/plans/<name>.md`, or the archived audit file), and nothing copied
  from the file. Its title is `Plan: <name>` or `Audit: <date>`. It carries
  no difficulty or type label; it has `area:` only when all its children
  share one.
- A finding met while working is a standalone `type: fix` issue with
  `Found while #N`. It becomes a sub-issue of a plan only when the plan
  cannot finish without it, and then it also blocks the task it holds up.
- The open items of `docs/reviews/findings.md` stay standalone.

## The `gh` calls

Created in this order, so every call has what it needs:

1. Labels (once): `gh label create "difficulty: easy" --description "..." --color ...`.
2. Each issue: `gh issue create --title ... --body-file <file> --label ...`;
   the output is its URL, so its number. The parent comes first.
3. Each child as a sub-issue, right after it is created:
   `gh api repos/{owner}/{repo}/issues/<parent>/sub_issues -F sub_issue_id=<child id>`.
4. Each dependency, once both issues exist:
   `gh api repos/{owner}/{repo}/issues/<blocked>/dependencies/blocked_by -F issue_id=<blocker id>`.

The two `gh api` calls take an issue's **id**
(`gh api repos/{owner}/{repo}/issues/<n> --jq .id`), not its number, as an
integer: `-F`, since `-f` sends a string and gets a 422. A link that already
exists also gets a 422 ("already a sub-issue"); on a rerun that error means
done.

The repository had no issues when this was written, so the two endpoints
are checked on the first real issues (MIG-5): the parent, its first child
and one dependency, before any other issue is created. If one is not
reachable, stop and ask the owner. The fallback is a `Blocked by: #N` line
in the body.
