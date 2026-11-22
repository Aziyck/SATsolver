---
name: write-pr
description: "Commit message, pull request and owner report for a finished item: the close step of /do-item and /do-item-hard, or a request to write a PR."
argument-hint: "[item ID]"
---

Write the text that closes one item: $ARGUMENTS

You write it in the session that did the work, so the facts are in your
context. The reader is the owner, days later, with the diff open and without
this session. Do not retell the diff; show its shape, prove it works, and
say what it risks.

## 1. Gather

- The item, and for a plan task its plan's Goal:
  `grep -rn "\*\*<ID>\. " docs/reviews docs/plans`.
- `git add -N .`, then `git diff main --stat`. Every file in it belongs to
  this item; delete or leave out a stray file (scratch output, a log).
- From this session: each check run after the last edit with its result
  line; the failure each new test showed before the change; rulings; review
  findings fixed and left; new findings filed; measurements.

## 2. Commit message

Subject `<ID>: <what changed>` (several IDs: `A13, A26: ...`), at most 72
characters. Body wrapped at 72: the cause or reason in one or two
lines; one `Ruling: <what> - <why> - <what it costs if wrong>` per
ruling; measurements; one line of checks.

## 3. Pull request

Title: the commit subject. Terse, fragments fine (`AGENTS.md`,
"Conventions"); terms as in `GLOSSARY.md`. Omit a section that would be
empty.

An **easy** item gets the opening line and `## Evidence`, nothing else.

1. **Opening line**, no heading: `Closes **<ID>** in [<file>](<file>)`, then
   one or two lines: what was wrong or missing, what is true now.
2. `## Shape` (medium and hard): the smallest view of the change. A
   `diff` block of a call tree, file tree or control flow, or pseudocode.
   Five to fifteen lines. Not a list of files.
3. `## Evidence`: before and after, from output you saw. For each new test,
   the failure it showed before the change and that it passes now. Each
   check as its command and result line (`262 tests OK, none skipped`), and
   each check not run with the reason. For a medium or hard item, the
   review's level and what it found.
4. `## Rulings`: one bullet each: the choice, why, the alternatives (one
   line), what it costs if wrong, and where to change it (a file, function
   or constant).
5. `## Merge danger` (medium and hard):
   - **Door:** `two-way` (a revert restores everything) or `one-way` (a
     revert leaves something changed). One-way when the change writes the
     database schema or migrates rows (`sat_web/store.py`), changes a
     format others keep (CSV columns, the JSON API, files in a job folder),
     or changes a solver's search or an encoder's clause order (every
     benchmark number and thesis table moves). Say what a revert cannot undo.
   - **Blast radius:** who sees it if it is wrong (solve page, benchmarks,
     API callers, stored jobs, thesis numbers), in one line.
6. `## Known gaps`: what stays wrong or untested, with the item tracking it.

## 4. Hand over

Write the commit message to `commit.txt` and the body to `pr.md` in the
scratchpad, for `git commit -F` and `gh pr create --body-file` unchanged.
The owner report is short: the pull request link, the door, the choices the
owner may want to change, review findings left and why, new findings filed,
and which item can start next.

**Choices the owner may want to change:** the rulings the owner would want a
say in, at most three; the rest stay in the pull request. One line each:

```text
- <choice>. Why: <reason>. Alternatives: <A>; <B>. To change: <file, function or constant>.
```

A choice the owner overturns becomes a new item.
