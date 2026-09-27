@AGENTS.md

## Notes for Claude Code

- Read the relevant guide before larger changes: `docs/guide/architecture.md`
  for server or job changes, `docs/guide/adding-a-problem.md` for new problems
  or solvers, `docs/guide/benchmarking.md` for the benchmark engine.
- Python API tests start real worker processes; they need
  `pip install -r requirements-dev.txt` and take a few seconds.
- When you start the server in the background, pass `--no-browser`, and
  `--strict-port` if something else will connect to a fixed port. Stop it by
  PID. Do not `pkill -f` a pattern that also appears in your own command line.
- A fresh `WIZSAT_DATA_DIR` (a temp folder) keeps experiments out of the
  user's `output/wizsat.db`.
- The frontend build is what `python -m sat_web` serves. After changing
  `frontend/src`, rebuild (`npm run build`) before testing through the
  Python server, or use `npm run dev`.
- Playwright is pinned in `frontend/package.json`; if the environment has
  preinstalled browsers, keep the pin matching them instead of downloading new
  ones.
