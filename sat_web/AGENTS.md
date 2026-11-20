# Rules for `sat_web/`

How jobs, locks and live updates work: `docs/guide/how-it-works.md` ("Jobs",
"Live updates"). The rules code must keep:

- Jobs run in `spawn` worker processes, at most `WIZSAT_MAX_JOBS` at once.
  They are not daemons (a benchmark may start its own pool); they exit with
  the server through `shutdown()` and a parent watchdog.
- Worker processes talk to the server only through `RunEvent`s. They never
  touch the database or sockets.
- The reader thread applies events under `JobManager.lock` and publishes to
  the event loop with `call_soon_threadsafe`. Take snapshots for HTTP replies
  under the lock (`manager.summary(job)`, `manager.detail(job)`).
- Every published job summary carries a `rev` that increases by one each time.
  The frontend drops copies older than the one it has, and merges events that
  arrive while a fetch is in flight (`frontend/src/api/live.ts`).
- Logs are throttled per job; row and summary events are batched.
- Only `instance.cnf` and `model.txt` can be downloaded from a job folder.
- The server binds to `127.0.0.1` by default. Keep it that way.
- The server has no login. The middleware `LocalOnlyGuard`
  (`sat_web/api.py`) refuses a foreign `Host` (400) and a foreign `Origin`
  (403) for every route and the WebSocket, and a cross-site `Sec-Fetch-Site`
  (403) under `/api`; it adds headers that forbid framing by another site
  to every reply. The allowed names are `Settings.allowed_hosts`. Do not add
  a route, a mount or CORS headers that bypass it. Tests reach the app as
  `localhost:8000` (`local_client` in `tests/test_api.py`).
