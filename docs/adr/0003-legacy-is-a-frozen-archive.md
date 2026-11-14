# 0003. `legacy/` is a frozen archive; its tests are not kept passing

- **Status:** Accepted (2026-11-15)
- **Decided by:** the repository owner

## Context

`legacy/` holds the original Tkinter app (with its own copy of the backend
and four test files in `legacy/tkinter_app/tests/`), early console scripts and
the Romanian thesis documents. `AGENTS.md` said not to edit it "except to keep
its own tests passing", but no CI step and no documented command ran those
tests: CI runs `python -m unittest discover -s tests`, which only looks in
`tests/`. The promise was not being kept, and nobody would have noticed a
failure.

## Decision

`legacy/` is a frozen archive, read for reference only. Nothing outside it
imports from it, nothing edits it, and its tests are not run or maintained;
they may stop passing as Python and the dependencies move on. An idea worth
keeping is ported into the active packages with new tests.

## Alternatives considered

- **Run the legacy tests in CI** (`python -m unittest discover -s
  legacy/tkinter_app/tests`). Set aside: it keeps a second copy of the
  backend alive for no product use, and the Tkinter tests may need a display
  on the Ubuntu runners.

## Consequences

- No CI time or upkeep goes to code the web app does not use.
- Code in `legacy/` may stop running. The one documented use,
  `from legacy.dpll_recursive import dpll` in `docs/algorithms/dpll.md` (a
  comparison with the recursive DPLL), is best effort.
- Bringing an old idea back means porting it, not importing it.
