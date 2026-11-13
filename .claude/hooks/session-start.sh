#!/bin/bash
# SessionStart hook for Claude Code cloud sessions: install what the tests and
# linters need, so a fresh container can run the checks in AGENTS.md
# ("Before you finish"). Local sessions are left alone: your own Python
# environment and node_modules are yours to manage (see the README).
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}"

# Python: FastAPI, httpx and ruff go into the system Python, which has no
# git-ignored folder to keep a marker in, so this runs every time (a few
# seconds when everything is already installed).
python3 -m pip install --quiet --disable-pip-version-check --root-user-action=ignore -r requirements-dev.txt

# Frontend: install only when the manifests changed since the last successful
# install. The marker lives in node_modules, so it disappears with the packages.
hashes=frontend/node_modules/.session-start.sha256
if ! sha256sum --check --status "$hashes" 2>/dev/null; then
  rm -f "$hashes"
  (cd frontend && npm install --no-audit --no-fund)
  sha256sum .claude/hooks/session-start.sh frontend/package.json frontend/package-lock.json > "$hashes" || rm -f "$hashes"
fi

# Make a missing FastAPI fail the API tests instead of skipping them.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo 'export WIZSAT_REQUIRE_API_TESTS=1' >> "$CLAUDE_ENV_FILE"
fi
