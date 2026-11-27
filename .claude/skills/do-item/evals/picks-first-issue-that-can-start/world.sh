#!/usr/bin/env bash
# Offline fixture for the do-item evals: a tiny repository whose open work
# is GitHub issues (saved as the JSON `gh` would print, in .gh/) plus one
# file item, as between MIG-2 and MIG-5.
#
# The source is evals/_fixture/world.sh; each case holds a copy, because
# `claude plugin eval` runs a scaffold only from inside its case folder.
# Edit the source, then copy it into every case (tests/test_eval_fixtures.py
# fails while a copy differs).
set -euo pipefail
PY=$(command -v python3 || command -v python)
mkdir -p .gh docs/plans docs/reviews tests

cat > .gh/README.md <<'EOF'
# gh, offline

`gh` is not installed here. The output of each `gh` call is saved in this
folder; read the file instead of running the command. A file that does not
exist means the call returned an empty list.

| Call | File |
|---|---|
| `gh issue view N ...` | `issue-N.json` |
| `gh api repos/{owner}/{repo}/issues/N/dependencies/blocked_by` | `blocked_by-N.json` |
| `gh api repos/{owner}/{repo}/issues/N/sub_issues` | `sub_issues-N.json` |
| `gh issue list --state open ...` | `issue-list.json` |

A call that writes (`gh issue edit`, `gh issue create`, `gh pr create`,
`gh api` with `-f` or `-F`) is not run: say in your reply what you would
have run.
EOF

cat > CLAUDE.md <<'EOF'
# Fixture repo

| Difficulty | Built by | Review |
|---|---|---|
| easy | `/do-item` (Sonnet) | the checks in "Before you finish" |
| medium | `/do-item` (Sonnet) | plus the `reviewer` agent at level `medium` |
| hard | `/do-item-hard` (Opus) | plus the `reviewer` agent at level `high` |
EOF

cat > AGENTS.md <<'EOF'
# Fixture repo

## Before you finish

1. `python -m unittest discover -s tests` passes.
2. The item is closed as `docs/plans/README.md` describes.
EOF

cat > docs/plans/README.md <<'EOF'
# Plans and the work queue

## Order of work

1. **Features:** [widgets.md](widgets.md).

Free to do at any point: the open `type: fix` issues and the open items in
[`findings.md`](../reviews/findings.md).

## Difficulty

| Level | Means |
|---|---|
| easy | A local change, covered by tests, no hard trigger. |
| medium | Several files or new tests, no hard trigger. |
| hard | Matches a hard trigger, or has an open design question. |

**Hard triggers:** `server/locks.py`; any lock, thread or process.

## Statuses and closing an item

A file item is closed in its file: `- [x] **F1. Title** - Done <date>.`
An issue is closed by its pull request (`Fixes #N`).
EOF

cat > docs/plans/widgets.md <<'EOF'
# Plan: widgets

- **Written:** 2026-11-20
- **Issues:** #20

## Problem statement

Widgets are parsed by hand. The result needed: a parser, a cache and a
size limit.

## Requirements

### MUST

- `parse_widget("a=1")` returns `{"a": 1}`.
- A parsed widget is cached by its text.
- A widget over 1 KB is refused.
EOF

cat > docs/reviews/findings.md <<'EOF'
# Findings made while working

- [ ] **F1. The size limit is read twice**
  - **Difficulty:** easy
  - **Blocked by:** F2
  - **Problem:** `limit()` reads the setting on every call.
  - **Done when:** the setting is read once per process.

- [ ] **F2. The setting has no default**
  - **Difficulty:** easy
  - **Problem:** a missing setting raises KeyError.
  - **Done when:** a missing setting gives 1024.
EOF

cat > widgets.py <<'EOF'
def parse_widget(text):
    """W-1 (#21, closed): "a=1,b=2" -> {"a": 1, "b": 2}."""
    pairs = (item.split("=", 1) for item in text.split(",") if item)
    return {key: int(value) for key, value in pairs}
EOF
cat > tests/test_widgets.py <<'EOF'
import unittest

from widgets import parse_widget


class ParseWidgetTests(unittest.TestCase):
    def test_one_pair(self):
        self.assertEqual(parse_widget("a=1"), {"a": 1})
EOF

cat > calc.py <<'EOF'
def add(a, b):
    return a - b
EOF
cat > tests/__init__.py <<'EOF'
EOF
cat > tests/test_calc.py <<'EOF'
import unittest

import calc


class AddTests(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(calc.add(0, 0), 0)
EOF

issue() { # number, state, title, labels(json), body
  printf '{"number":%s,"state":"%s","title":"%s","labels":%s,"body":%s,"comments":[]}\n' \
    "$1" "$2" "$3" "$4" "$(printf '%s' "$5" | "$PY" -c 'import json,sys;print(json.dumps(sys.stdin.read()))')" > ".gh/issue-$1.json"
}
L() { printf '[%s]' "$(printf '{"name":"%s"},' "$@" | sed 's/,$//')"; }

issue 20 OPEN "Plan: widgets" "$(L 'area: sat_core')" "Delivers the widget parser, cache and size limit. Plan: [docs/plans/widgets.md](docs/plans/widgets.md)."
issue 21 CLOSED "W-1. Parse a widget" "$(L 'difficulty: easy' 'area: sat_core' 'type: feature')" "From plan widgets, section Requirements.
- **How:** \`parse_widget\` in \`widgets.py\`.
- **Done when:** \`parse_widget(\"a=1\")\` returns \`{\"a\": 1}\`."
issue 22 OPEN "W-2. Cache parsed widgets" "$(L 'difficulty: medium' 'area: sat_core' 'type: feature')" "From plan widgets, section Requirements.
- **How:** an LRU cache keyed by the text.
- **Done when:** parsing the same text twice calls the parser once."
issue 23 OPEN "W-3. Refuse a widget over 1 KB" "$(L 'difficulty: medium' 'area: sat_core' 'type: feature')" "From plan widgets, section Requirements.
- **How:** check the length in \`parse_widget\`.
- **Done when:** a 1025-byte widget raises ValueError; a 1024-byte one parses."
issue 30 OPEN "A second start runs two servers" "$(L 'difficulty: medium' 'area: sat_web' 'type: fix' 'needs-decision')" "- **Needs decision:** what a second start does when the app already answers on the port. Options: open the browser at the running server and exit; start on another port; refuse with an error. Recommendation: open the browser at the running server and exit.
- **Problem:** starting the app twice runs two servers on the same data.
- **Done when:** a second start does what was decided."
issue 31 OPEN "Stop can be lost between two locks" "$(L 'difficulty: hard' 'area: sat_web' 'type: fix')" "- **Problem:** a Stop that lands while \`server/locks.py\` swaps the job lock is lost.
- **Fix:** take both locks in one place.
- **Done when:** a test that stops a job during the swap sees it end cancelled."
issue 40 OPEN "add() subtracts" "$(L 'difficulty: easy' 'area: sat_core' 'type: fix')" "- **Problem:** \`calc.add(2, 3)\` returns -1.
- **Fix:** return the sum.
- **Done when:** \`calc.add(2, 3)\` is 5, tested in \`tests/test_calc.py\`."

echo '[{"number":21,"state":"closed"},{"number":22,"state":"open"},{"number":23,"state":"open"}]' > .gh/sub_issues-20.json
echo '[{"number":23,"state":"open"}]' > .gh/blocked_by-22.json
for n in 20 21 23 30 31 40; do echo '[]' > ".gh/blocked_by-$n.json"; done
"$PY" - <<'EOF'
import json, glob
rows = [json.load(open(p)) for p in sorted(glob.glob(".gh/issue-*.json"))]
open_ = [{k: r[k] for k in ("number", "title", "labels")} for r in rows if r["state"] == "OPEN"]
json.dump(open_, open(".gh/issue-list.json", "w"))
EOF
