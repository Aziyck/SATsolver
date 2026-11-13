# Plans and the work queue

Open work lives in two places:

- [`docs/reviews/`](../reviews/): dated findings about the code as it is
  (bugs, risks, clean-ups). Items there are fixes.
- `docs/plans/` (this folder): features that are designed but not built. Each
  plan holds the design, the rejected options and a list of tasks.

Both use the same **item** format, defined below. The skills `/fix-item` and
`/do-plan-step` work on one item at a time. Words such as *item*, *case* or
*run* are defined in [`GLOSSARY.md`](../../GLOSSARY.md); decisions are recorded
in [`docs/adr/`](../adr/).

## Order of work

Take the first open item, going down this list, that is not blocked and has no
undecided `Needs decision`. Statuses are on the items themselves, not here.

1. **Must-fix findings:** [audit](../reviews/2026-10-16-audit.md) A1, A2, A3.
   They are bugs in what already ships (security, a machine-freezing input,
   old results that cannot be opened).
2. **Frontend tests:** [frontend-tests.md](frontend-tests.md), aimed at the
   screens the features below will change.
3. **Features, in this order:**
   [run-metadata.md](run-metadata.md), then
   [pypy-solver-runner.md](pypy-solver-runner.md), then
   [memory-measurement.md](memory-measurement.md) (its memory limit, MEM-8,
   last).

Free to do at any point after step 1, when there is time or when the code is
being touched anyway:

- the remaining audit findings A4-A12;
- the solver clean-up B1-B17 in the same audit;
- [solver-optimisations.md](solver-optimisations.md), after the CDCL clean-up
  items B6-B9 that touch the same code.

| File | What | Waits on |
|---|---|---|
| [../reviews/2026-10-16-audit.md](../reviews/2026-10-16-audit.md) | A1-A12 whole-repo findings, B1-B17 solver simplification | nothing |
| [frontend-tests.md](frontend-tests.md) | component tests for the result and settings screens | nothing |
| [run-metadata.md](run-metadata.md) | machine and interpreter recorded with every run | nothing |
| [pypy-solver-runner.md](pypy-solver-runner.md) | solvers in a child process, optionally under PyPy | run-metadata for one task |
| [memory-measurement.md](memory-measurement.md) | peak memory and stored literals per run | the solver runner |
| [solver-optimisations.md](solver-optimisations.md) | faster pure-Python CDCL | audit B6-B9 |
| [agent-workflow.md](agent-workflow.md) | how this workflow was chosen (done) | - |

To list every open item: `grep -n "^- \[ \]" docs/reviews/*.md docs/plans/*.md`.

## The item format

```markdown
  - [ ] **ID. Short title that names the symptom or the task**
    - **Difficulty:** easy | medium | hard
    - **Blocked by:** A2, META-1                    (only if it must wait)
    - **Needs decision:** the question. The options. The recommendation.
                                                     (only while it is open)
    - **Problem:** what is wrong, with the concrete case that shows it.
      (plans use **What:** or go straight to **How:**)
    - **Fix:** the smallest change that works.       (plans: **How:**)
    - **Done when:** behaviour that can be observed and tested.
```

(Shown indented; a real item starts at the left margin, like the ones in the
audit.)

Rules for writing one:

- **One commit, one session.** An item that needs more is split, or moved into
  a plan with the review keeping a one-line pointer to it.
- **One owner.** A piece of work is described in one place; other places link
  to it by ID.
- **Done when** is behaviour ("a POST from a foreign Origin gets 403"), not an
  activity ("add a check"). The session that takes the item writes it as a
  test first and watches it fail. For a pure refactor it is "the existing
  tests pass, and the conflict counts of `scripts/solver_timings.py` are
  unchanged".
- **Names, not line numbers.** Refer to files, functions, settings and
  behaviour. Line numbers are stale after the first edit.
- **Snippets only for interfaces:** a setting name, a JSON shape, a function
  signature, a command to run. No implementation code: it goes stale and gets
  copied even when wrong.
- IDs are stable. Review items keep their letter and number (A3, B7); plan
  tasks use the plan's prefix (META-2, RUNNER-3, MEM-1, OPT-1, FE-2).

## Difficulty

Difficulty says how much can go wrong, not how long it takes. `CLAUDE.md` maps
it to a model and a review level.

| Level | Means |
|---|---|
| easy | A local change, covered by existing tests, with a clear "done when". Nothing subtle. |
| medium | Several files or new tests, or a behaviour users see, but no subtle interaction. |
| hard | Any of: security; processes, threads, cancellation or timeouts; a solver's hot loop or anything that can change a solver's search or results; data migration; an open design question. |

When unsure between two levels, take the higher one.

## Statuses and closing an item

An item is open until it is closed in the file it lives in, in the same change
as the work.

| Status | How it is written |
|---|---|
| open | `- [ ] **A3. Title**` |
| done | `- [x] **A3. Title** - Done 2026-11-20.` The commit subject starts with the ID (`A3: ...`), so `git log --grep "^A3:"` finds the change. |
| dropped | `- [x] **A3. Title** - Dropped 2026-11-20: the reason.` |
| needs a stronger model | stays `- [ ]`, with a line `- **Escalate:** 2026-11-20, what was tried and where it failed.` |
| waiting | stays `- [ ]`, with its `Blocked by:` or `Needs decision:` line |

- A `Blocked by:` item may start once every item it names is closed (done or
  dropped).
- A `Needs decision:` line is answered by the owner and then rewritten as
  `- **Decided (2026-11-20):** the choice.` A choice that shapes the project
  also gets an ADR.
- After three failed attempts to make the "done when" test pass, stop, write
  the `Escalate:` line and leave the item open. A wrong fix that looks done
  costs more than an open item.
- When every task of a plan is closed, set its status line to
  `done (date)` and move decisions worth keeping into an ADR.
- A new finding met along the way becomes a new item (next free ID in the
  newest review); it is not fixed inside another item's change.
