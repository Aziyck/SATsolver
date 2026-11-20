---
name: write-pr
description: "Commit message, pull request and owner report for a finished item: the close step of /do-item and /do-item-hard, or a request to write a PR."
argument-hint: "[item ID]"
---

Write the text that closes one item: $ARGUMENTS

You write it in the session that did the work, so the facts are in your
context. The reader is the owner opening the pull request days later,
without this session, deciding from the body alone whether to merge.

## 1. Gather

- The item, and for a plan task its plan's Goal:
  `grep -rn "\*\*<ID>\. " docs/reviews docs/plans`.
- The change: `git add -N .` (new files show in the diff, nothing is
  staged), then `git diff main --stat` and `git diff main`. Check the
  stat lists only files this item changed; a stray file (scratch output,
  a log) is deleted or left out of the commit, never committed.
- From this session: each check run after the last edit with its result
  line; the failure each new test showed before the change; rulings;
  review findings fixed and left; new findings filed; measurements.

**Done when** you can say in one sentence why the change exists and what it
unblocks or fixes, and you hold every check's result from output you saw.

## 2. Commit message

Subject `<ID>: <what changed>` (several IDs: `A13, A26: ...`), at most 72
characters. Body wrapped at 72: the cause or reason in one or two
sentences; one `Ruling: <what> - <why> - <what it costs if wrong>` per
ruling; measurements; one line of checks.

## 3. Pull request

Title: the commit subject. The body's depth follows the item's difficulty:
an **easy** item gets the opening paragraph, `## Verified` and any
`## Rulings`, a few lines each; a **medium** or **hard** item gets every
section below. Body in this order; omit a section that would be empty:

1. **Opening paragraph**, no heading: `Closes **<ID>** in [<file>](<file>)`
   and any item filed. Then the plan's goal or the problem in the reader's
   words, what was missing before, what is true after, and what it unblocks.
   A merge-order warning or anything to know before merging follows in bold.
2. `## What`: by file, in the order a reviewer reads (core module, its
   callers, tests, docs). Name each new or changed function, constant,
   column, event or setting in backticks with its concrete values or shape,
   and what an edge case gives (null, old data, an error). Tests: one bullet
   per behaviour asserted.
3. `## Verified`: each check as its command and the result line you saw
   (`262 tests OK, none skipped`); for each new test, the failure it showed
   before the change; each check not run, with the reason; the review's
   level, finding count and what was fixed.
4. `## Rulings`: one bullet each: the choice, why, what it costs if wrong.
5. `## Behaviour changes`: what users, API callers or file readers now see.
6. `## Known gaps`: what stays wrong or untested, with the item tracking it.

PRs #37 and #39 (`gh pr view 37`) show the depth expected for a medium or
hard item.

## 4. Review it as the owner

Reread the body as someone who never saw this session, and revise until
each holds:

- Every file in `--stat` is named in What (a named group counts).
- Every check, number and error message comes from output seen in this
  session.
- Every line is a full sentence; session shorthand (the loop, the baseline,
  "as discussed") is replaced by what it names.
- The body alone answers: why now, what changed, how it is proven, what to
  watch.

**Done when** all four hold.

## 5. Hand over

Write the commit message to `commit.txt` and the body to `pr.md` in the
scratchpad, for `git commit -F` and `gh pr create --body-file` unchanged.
The owner report is short: the pull request link, review findings left and
why, new findings filed, and which item can start next. The pull request
carries the rest.
