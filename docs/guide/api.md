# HTTP API

The web UI talks to the Python server through a small JSON API under `/api`,
plus one WebSocket for live updates. You can use the same API from scripts.
The server listens on `http://127.0.0.1:8000` by default (see the launcher
options in the README).

FastAPI also serves interactive documentation of the REST endpoints at
`/docs` while the server is running.

The TypeScript types in `frontend/src/api/types.ts` mirror every JSON shape
below and are the most precise reference.

## Conventions

- Request and response bodies are JSON.
- Validation errors return **422** with one message per field:

  ```json
  {
    "message": "variables: must be at least 3; ratio: 'x' is not a number",
    "errors": {"variables": "must be at least 3", "ratio": "'x' is not a number"}
  }
  ```

  Field names are paths for nested requests: `segments.0.nodes`,
  `solvers.1.options.noise`, `rules.0.seconds`. The key `_` holds errors that
  belong to no single field (for example "instance too large").
- Unknown jobs or rows return **404**; deleting a running job returns
  **409**.

## Catalog

### `GET /api/health`

`{"ok": true, "version": "2.0.0"}`

### `GET /api/catalog`

Everything the UI needs to draw its forms:

```json
{
  "version": "2.0.0",
  "problems": [ProblemSpec, ...],
  "solvers": [SolverSpec, ...],
  "presets": [Preset, ...],
  "log_levels": ["normal", "periodic", "debug"],
  "limits": {"max_clauses": 2000000, "max_benchmark_runs": 200000, "max_workers": 4},
  "defaults": {
    "solve_timeout": 60,
    "benchmark_timeout": 30,
    "benchmark_rules": [{"solver": "dpll", "action": "cap", "min_variables": 200, "seconds": 10.0}]
  }
}
```

A `ProblemSpec` has `key`, `title`, `summary`, `description`, `category`,
`image`, `result_view` (`sudoku`, `queens`, `graph` or `assignment`),
`graph_based` and `fields`. A `SolverSpec` has `key`, `title`, `complete`,
`summary`, `description` and `fields`. Each field:

```json
{
  "name": "probability", "label": "Edge probability p", "kind": "float",
  "default": 0.3, "help": "...", "min": 0, "max": 1, "step": 0.05,
  "choices": [], "optional": false, "sweepable": true, "group": "",
  "show_if": {"graph_mode": ["gnp"]}, "placeholder": "", "unit": "",
  "advanced": false, "short": "p"
}
```

`kind` is one of `int`, `float`, `bool`, `choice`, `text`, `seed`, `edges`,
`sudoku_grid`, `cnf`. A preset is `{key, title, description, tags, request,
cases, runs, rules}`, where `request` is a benchmark request (below).

### `POST /api/problems/{key}/preview`

Body: `{"params": {...}}`. Validates the parameters without encoding:

```json
{
  "label": "n=10 p=0.3 seed=2 k=3",
  "estimate": {"variables": 30, "clauses": 357},
  "too_large": false,
  "preview": {"nodes": [...], "edges": [[1, 2], ...]}
}
```

`preview` depends on the problem (a graph, a board size, a sample of clauses)
and may be `null`.

### `POST /api/benchmarks/plan`

Body: `{"request": BenchmarkRequest}`. Expands the plan without running it:

```json
{
  "cases": 260, "runs": 260, "solvers": ["CDCL"],
  "rules": ["cap DPLL at 10 s when variables >= 200"],
  "largest": {"variables": 50, "clauses": 300},
  "total_clauses": 45000,
  "sample": [{"problem": "random_3sat", "label": "n=30 r=3 Random seed=1", "repeat": 1, "estimate": {...}}],
  "seed": 1,
  "workers": 1
}
```

## Jobs

A job is one solve, one encoding (`generate`) or one benchmark. Jobs run in
background worker processes; at most `WIZSAT_MAX_JOBS` run at once and the
rest are `queued`.

Job statuses: `queued`, `running`, `cancelling`, `done`, `failed`,
`cancelled`, `interrupted` (the server stopped while it ran).

### `POST /api/jobs` -> 201

```json
{"kind": "solve", "title": "optional", "request": SolveRequest}
{"kind": "generate", "request": {"problem": "sudoku", "params": {...}}}
{"kind": "benchmark", "request": BenchmarkRequest}
```

A **SolveRequest**:

```json
{
  "problem": "graph_coloring",
  "params": {"graph_mode": "gnp", "nodes": 10, "probability": 0.3, "seed": 2, "colors": 3},
  "solver": "cdcl",
  "options": {"branching": "vsids", "restarts": true},
  "timeout": 60,
  "log_level": "normal"
}
```

Missing parameters and options take their defaults. A blank seed is replaced
by a fresh one before the job is queued, so the stored request always
reproduces the instance.

A **BenchmarkRequest**:

```json
{
  "problems": ["random_3sat"],
  "segments": [{"variables": "50, 100", "ratio": "3..6:0.5", "mode": ["random"], "seed": "1..10"}],
  "solvers": [{"solver": "cdcl", "options": {}, "label": "CDCL"}, {"solver": "dpll"}],
  "repeats": 1,
  "timeout": 30,
  "rules": [{"solver": "dpll", "action": "cap", "min_variables": 200, "seconds": 10}],
  "seed": 1,
  "log_level": "normal",
  "title": "optional",
  "workers": 1
}
```

Sweepable fields take a single value, a list, or a string with lists and
ranges (see [Benchmarking](benchmarking.md#writing-parameter-values)).
`rules[].solver` may be `"*"` for any solver; `action` is `cap` (needs
`seconds`) or `skip`. `workers` (default 1, at most `limits.max_workers`,
the number of CPU cores) is how many cases are solved at the same time; see
[Benchmarking](benchmarking.md#parallel-runs).

The response is the job summary.

### Job summary

```json
{
  "id": 12, "rev": 5, "label": "J12", "kind": "solve",
  "title": "Graph Coloring: n=10 p=0.3 seed=2 k=3 (CDCL)",
  "status": "done",
  "created_at": "2026-09-27T19:24:20.419+00:00",
  "started_at": "...", "finished_at": "...",
  "progress": {"current": null, "total": null, "message": ""},
  "row_count": 0,
  "problems": ["graph_coloring"], "solver": "cdcl",
  "result_status": "SAT", "verified": true, "elapsed": 0.0012,
  "error": null
}
```

`rev` grows by one every time the server publishes a new version of the
summary. When you combine polling and the WebSocket, keep the copy with the
higher `rev`.

### `GET /api/jobs`

`{"jobs": [JobSummary, ...]}`, all jobs.

### `GET /api/jobs/{id}`

The summary plus:

| Key | Content |
|---|---|
| `request` | the normalized request |
| `instance` | the encoded instance (solve and generate jobs): `name`, `problem`, `params`, `variables`, `clauses`, `size_variables`, `facts`, `visual`, `expected`, `encode_seconds`, `cnf_file` |
| `result` | the solver result (solve jobs): `solver`, `solver_label`, `options`, `status`, `elapsed`, `stats`, `decoded`, `verified`, `check_errors`, `expected`, `timeout`, `error`, `model_file` |
| `errors` | field errors if the job failed validation inside the worker |
| `logs` | the last 400 log lines as `[time, text]` pairs |
| `log_count` | total log lines kept |

`decoded` is the answer in the problem's own terms, for example
`{"coloring": [...], "colors_used": 3}`, `{"path": [...]}`,
`{"queens": [[1, 2], ...]}`, `{"grid": [[...]]}` or, for Random 3-SAT and
DIMACS, `{"variables": n, "true_count": k, "bits": "0110..."}`.

### `GET /api/jobs/{id}/rows`

Benchmark rows: `{"job_id", "label", "rows": [BenchmarkRow, ...]}`. A row has
`index`, `case_index`, `problem`, `case_label`, `params`, `repeat`, `solver`,
`solver_label`, `status`, `elapsed`, `variables`, `clauses`,
`size_variables`, `expected`, `verified`, `check_errors`, `stats`, `timeout`,
`rule`, `error` and `decoded`.

### `GET /api/jobs/{id}/logs`

`{"job_id", "logs": [[time, text], ...]}`, every kept line.

### Actions

| Request | Effect |
|---|---|
| `POST /api/jobs/{id}/cancel` | stop a queued or running job (cooperative first, forced after 3 s) |
| `POST /api/jobs/{id}/skip` | benchmarks: mark the current run SKIPPED and continue |
| `POST /api/jobs/{id}/rerun` -> 201 | submit the same request as a new job |
| `DELETE /api/jobs/{id}` -> 204 | delete a finished job and its files (409 while it runs) |
| `POST /api/jobs/clear` | body `{"kinds": ["solve", ...]}` or `{}`: delete all finished jobs of those kinds; returns `{"deleted": [ids]}` |

Cancel, skip and rerun return a job summary.

## Files and exports

| Request | Returns |
|---|---|
| `GET /api/jobs/{id}/files/instance.cnf` | the job's DIMACS file |
| `GET /api/jobs/{id}/files/model.txt` | the SAT model as `s SATISFIABLE` and `v` lines |
| `GET /api/jobs/{id}/cnf?offset=0&limit=500` | a page of CNF lines: `{"offset", "lines", "total"}` (limit up to 5000) |
| `GET /api/jobs/{id}/export.csv` | the benchmark as CSV |
| `GET /api/export.csv?jobs=3,4,5` | several benchmarks in one CSV (the `run` column tells them apart) |
| `GET /api/jobs/{id}/rows/{index}/case` | rebuilds one benchmark case: `{"row", "problem", "params", "instance"}` |
| `GET /api/jobs/{id}/rows/{index}/cnf` | the DIMACS file of one benchmark case |

Only `instance.cnf` and `model.txt` can be downloaded from a job folder. The
CSV format is described in [Benchmarking](benchmarking.md#csv-columns).

## Live events: `WS /api/ws`

Connect a WebSocket to `/api/ws`. The server first sends

```json
{"type": "hello", "version": "2.0.0", "jobs": [JobSummary, ...]}
```

and then batches of events:

```json
{"type": "batch", "events": [Event, ...]}
```

| Event | Sent when |
|---|---|
| `{"type": "job", "job": JobSummary}` | a job is created, starts, finishes, or its progress changes (throttled to about 5 per second) |
| `{"type": "log", "job_id", "line": [time, text]}` | a log line; at most 60 per second per job are streamed, the rest are summarised in a synthetic line and kept in the job log |
| `{"type": "instance", "job_id", "instance": {...}}` | a solve or generate job finished encoding |
| `{"type": "result", "job_id", "result": {...}}` | a solve job has its answer |
| `{"type": "row", "job_id", "row": BenchmarkRow}` | a benchmark run finished |
| `{"type": "deleted", "job_id"}` | a job was deleted |
| `{"type": "resync"}` | this client fell behind and events were dropped; fetch the state again |

The socket is read-only; actions go through the REST endpoints. After a
reconnect, refetch what you display, since events sent while you were
disconnected are not replayed.

An event can arrive while a `GET` for the same job is in flight, and the
`GET` reply can be older than the event. The web UI handles this with `rev`
for summaries and by merging instance, result and row events into the reply
(see `frontend/src/api/live.ts`).

## Example: solve from Python

```python
import json, time, urllib.request

BASE = "http://127.0.0.1:8000/api"

def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(BASE + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read() or "null")

job = call("POST", "/jobs", {"kind": "solve", "request": {
    "problem": "n_queens", "params": {"size": 12}, "solver": "cdcl"}})
while (detail := call("GET", f"/jobs/{job['id']}"))["status"] not in ("done", "failed", "cancelled"):
    time.sleep(0.2)
print(detail["result"]["status"], detail["result"]["decoded"]["queens"])
```
