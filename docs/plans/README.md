# Plans and the work queue

Open work lives in two places:

- [`docs/reviews/`](../reviews/): findings about the code as it is. A dated
  file per deliberate review, and [`findings.md`](../reviews/findings.md) for
  findings made while working
  (bugs, risks, clean-ups). Items there are fixes.
- `docs/plans/` (this folder): features that are designed but not built. Each
  plan holds the design, the rejected options and a list of tasks.

Both use the same **item** format, defined below. The skill `/do-item`
(`/do-item-hard` for a hard item) works on one item at a time; `/write-plan`
turns an idea into a new plan, and `/retro` looks back on finished work.
Words such as *item*, *case* or *run* are defined in
[`GLOSSARY.md`](../../GLOSSARY.md); decisions are recorded in
[`docs/adr/`](../adr/).

## Order of work

Take the first open item, going down this list, that is not blocked and has no
undecided `Needs decision`. Statuses are on the items themselves, not here.
Finished work is not listed: closed items stay in their files, and finished
plans move to [`done/`](done/).

1. **Features, in this order:**
   [pypy-solver-runner.md](pypy-solver-runner.md), then
   [memory-measurement.md](memory-measurement.md) (its memory limit, MEM-8,
   last).

Free to do at any point, when there is time or when the code is being
touched anyway:

- the open findings of the [2026-10-16 audit](../reviews/2026-10-16-audit.md),
  whole-repo and solver clean-up alike;
- the open findings in [`findings.md`](../reviews/findings.md);
- [solver-optimisations.md](solver-optimisations.md), once the audit's CDCL
  clean-up items that touch the same code are closed (its first task names
  them in `Blocked by`).

| File | What | Waits on |
|---|---|---|
| [../reviews/2026-10-16-audit.md](../reviews/2026-10-16-audit.md) | the 2026-10-16 review: whole-repo findings, solver simplification | nothing |
| [../reviews/findings.md](../reviews/findings.md) | findings made while working | nothing |
| [pypy-solver-runner.md](pypy-solver-runner.md) | solvers in a child process, optionally under PyPy | nothing |
| [memory-measurement.md](memory-measurement.md) | peak memory and stored literals per run | the solver runner |
| [solver-optimisations.md](solver-optimisations.md) | faster pure-Python CDCL | the audit's CDCL clean-up |

To list every open item, the findings above included: `grep -n "^- \[ \]" docs/reviews/*.md docs/plans/*.md`.

## The item format

```markdown
  - [ ] **ID. Short title that names the symptom or the task**
    - **Difficulty:** easy | medium | hard
    - **Not hard:** why a matching hard trigger does not apply
                                                     (only to rate below one)
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
  tasks use the plan's prefix (META-2, RUNNER-3, MEM-1, OPT-1, ARCH-4).

## Difficulty

Difficulty says how much can go wrong, not how long it takes or how big the
change is. `CLAUDE.md` maps it to a model and a review.

| Level | Means |
|---|---|
| easy | A local change, covered by existing tests, with a clear "done when". Nothing subtle, and no hard trigger. |
| medium | Several files or new tests, or a behaviour users see, but no subtle interaction and no hard trigger. |
| hard | The change matches a hard trigger below, or has an open design question. |

**Hard triggers.** An item is hard when its fix touches any of these, however
small the change. A one-line change in a hard area is hard.

- **Concurrency:** `sat_web/manager.py`, `sat_core/parallel.py`,
  `sat_core/runtime.py`, `frontend/src/api/live.ts`; any lock, thread,
  process or queue; a race between two channels (a REST reply and a
  WebSocket event).
- **Stopping:** how Stop, Skip or a timeout is handled, or which event ends a
  job.
- **Security:** `LocalOnlyGuard`, what the server serves, file downloads.
- **Stored data:** the database schema or a migration (`sat_web/store.py`).
- **Solvers:** a solver's hot loop (propagation, the main search loop,
  flips), or a change meant to alter a solver's search or results. A
  solver change outside the loops that keeps the search, proven by unchanged
  conflict counts, is not hard by this trigger.

An item that matches a trigger is rated lower only with a `Not hard:` line
that says why the trigger does not apply. When unsure between two levels,
take the higher one.

The rating is checked twice: `/do-item` compares the files the fix will
touch with the triggers before starting, and the files in the diff before
the review, and re-rates the item when a trigger matches.

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
  `done (date)`, move decisions worth keeping into an ADR, and move the file
  to `docs/plans/done/` (fix its relative links and the links to it).
- A **new finding** met along the way (a bug, a weak spot, a review finding
  left unfixed) is filed the moment it is found: a new item at the end of
  [`docs/reviews/findings.md`](../reviews/findings.md), next F number, marked
  `(added <date>, found while <ID>)`. It goes into the current change as a
  documentation edit and into the report to the owner; the fix waits for its
  own session.
