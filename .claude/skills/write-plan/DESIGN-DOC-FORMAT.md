# Design doc format

The form of a plan in `docs/plans/<name>.md`, adapted from lecture 10
("Engineering Design Documents, RFCs, and ADRs") of the system design
course. [ADR 0008](../../../docs/adr/0008-work-items-are-github-issues.md)
records why a plan is a design doc and its tasks are issues.

A plan holds the design only. Its tasks are GitHub issues made by
`to-issues` after the owner has accepted the doc; the file has no task list.

## Sections

Every section is required unless it says otherwise. A section the change
does not need is cut, never left empty.

| Section | Content |
|---|---|
| Header | the bullet list at the top: `Written` (date), `Related` (ADRs, plans, guides), `Issues` |
| Problem statement | the problem and the result needed, in a paragraph |
| Requirements | `MUST`, `SHOULD`, `NICE TO HAVE`, `MUST NOT`: observable behaviour. The issues' "done when" come from these |
| Non-goals | excluded scope, each with a reason when it is tempting |
| Quality targets (optional) | measure, target, condition: for speed or memory work |
| Architecture and contracts (optional) | only the views the change needs: modules, data, JSON shapes, settings |
| Main flow and failures | the main sequence, its **success point**, and at least one **failure path** |
| Solutions and decision | at least two viable solutions at the same depth, the deciding reason, and one downside of the chosen one; an ADR when the choice is hard to reverse |
| Risks and open questions | each with its effect, a response or next action, and whether it blocks the decision |

A small change may merge sections into a short **focused change note**
(problem, requirements, the flow with its failure, the two solutions, the
risks), and never drops the failure path or the second solution.

Plan-specific sections the old plans had still apply when they carry
weight: `Considered and rejected` (every option the grilling dropped, with
the reason) and, for a plan that adds a term, the glossary change.

## The header and the plan's state

A plan has no `Status` field. Its state follows from facts that change
anyway, so nothing is flipped by hand:

| State | The fact | Written by |
|---|---|---|
| draft | the file exists only on its pull request branch (`plan/<name>`) | `write-plan` opens the pull request |
| accepted | the file is on `main` and its header says `- **Issues:** none yet` | `write-plan` writes `none yet`; the owner's merge accepts |
| in progress | the header says `- **Issues:** #N`, the plan's parent issue | `to-issues` replaces `none yet`, in a docs-only commit to `main` |
| done | the file is in `docs/plans/done/` | the pull request that closes the last sub-issue |

- An open question that blocks the decision is closed before the merge,
  since the merge is the acceptance.
- `/do-item` with no argument names an accepted plan (`Issues: none yet`):
  its issues are still to be made, with `/write-plan issues <name>`.
- Plans written before this format keep their `Status:` line. `to-issues`
  sets it to `in progress` and adds the `Issues:` line when it makes their
  issues.

## Rules for writing one

- **Requirements are behaviour** ("a POST from a foreign Origin gets 403"),
  not activity. Each MUST is a candidate "done when".
- **The failure path is shown, not implied.** Name what dies or stops
  (the parent, the network, the child, the cancel), and what the system
  does then. A flow with only a happy path is unfinished.
- **Two solutions at the same depth.** The second is a real candidate with a
  cost, not a strawman. The decision names the deciding reason and what the
  chosen one costs.
- **Names, not line numbers.** Files, functions, settings, behaviour.
- **Snippets only for interfaces:** a setting, a JSON shape, a function
  signature, a command. No implementation code.
- **One owner for each fact.** Link to a guide or an ADR instead of copying.
- A change to the design found while building a task is made in that task's
  pull request, in the plan's own section; a large one goes back to a new
  design doc pull request.
