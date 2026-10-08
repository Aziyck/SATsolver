"""
FastAPI application: REST endpoints, the WebSocket event stream and the
static frontend.

All endpoints live under /api. Validation errors come back as HTTP 422 with
{"message": ..., "errors": {field: message}} so the UI can show them next to
the right input. See docs/guide/api.md for the full reference.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from problems import all_problems, get_problem
from problems.base import MAX_CLAUSES, ProblemSpec
from sat_core.benchmark import DEFAULT_TIMEOUT, DPLL_FALLBACK_RULE, MAX_BENCHMARK_RUNS, max_workers, parse_request, rows_to_csv
from sat_core.dimacs import clauses_to_dimacs, app_header_comment
from sat_core.jobs import DEFAULT_SOLVE_TIMEOUT, instance_payload
from sat_core.params import ParamError
from sat_core.presets import all_presets
from sat_core.solver_registry import LOG_LEVELS, all_solvers, get_solver
from sat_web.config import Settings
from sat_web.manager import Job, JobManager
from sat_web.store import Store


VERSION = "2.0.0"
DOWNLOADABLE_FILES = ("instance.cnf", "model.txt")


class JobBody(BaseModel):
    kind: Literal["solve", "generate", "benchmark"]
    request: dict[str, Any] = Field(default_factory=dict)
    title: str | None = None


class ParamsBody(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)


class PlanBody(BaseModel):
    request: dict[str, Any] = Field(default_factory=dict)


class ClearBody(BaseModel):
    kinds: list[str] | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _problem(key: str | None) -> ProblemSpec:
    try:
        return get_problem(key or "")
    except ValueError as exc:
        raise ParamError({"problem": str(exc)}) from None


def visible_params(spec: ProblemSpec, params: dict[str, Any]) -> dict[str, Any]:
    return {field.name: params[field.name] for field in spec.fields if field.visible(params) and field.name in params}


def _timeout(value: Any) -> float | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        raise ParamError({"timeout": "must be a number of seconds"}) from None
    if timeout < 0:
        raise ParamError({"timeout": "must not be negative"})
    return timeout


def validate_job(kind: str, request: dict[str, Any], title: str | None) -> tuple[dict[str, Any], str]:
    """Check a job request and return (normalized request, title)."""

    if kind in ("solve", "generate"):
        spec = _problem(request.get("problem"))
        params = spec.resolve_seed(spec.parse(request.get("params")))
        spec.check_size(params)
        label = spec.case_label(params)
        normalized: dict[str, Any] = {"problem": spec.key, "params": visible_params(spec, params)}
        if kind == "generate":
            return normalized, title or f"Encode {spec.title}: {label}".strip()
        try:
            solver = get_solver(request.get("solver") or "cdcl")
        except ValueError as exc:
            raise ParamError({"solver": str(exc)}) from None
        try:
            options = solver.parse_options(request.get("options"))
        except ParamError as exc:
            raise ParamError({f"options.{name}": message for name, message in exc.errors.items()}) from None
        log_level = request.get("log_level") or "normal"
        if log_level not in LOG_LEVELS:
            raise ParamError({"log_level": f"must be one of {', '.join(LOG_LEVELS)}"})
        normalized.update(
            solver=solver.key,
            options=options,
            timeout=_timeout(request.get("timeout", DEFAULT_SOLVE_TIMEOUT)),
            log_level=log_level,
        )
        return normalized, title or f"{spec.title}: {label} ({solver.title})"

    plan = parse_request(request)
    titles = " + ".join(get_problem(key).title for key in plan.problems)
    default_title = f"{titles}: {len(plan.cases)} cases x {len(plan.solvers)} solvers"
    return plan.normalized, title or plan.title or default_title


class CnfLineIndex:
    """Byte offsets of line starts, cached per file, for paging big CNF files."""

    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, list[int]]] = {}

    def lines(self, path: Path, offset: int, limit: int) -> tuple[list[str], int]:
        stat = path.stat()
        cached = self._cache.get(str(path))
        if cached is None or cached[0] != stat.st_mtime:
            offsets = [0]
            with path.open("rb") as handle:
                data = handle.read()
            position = data.find(b"\n")
            while position != -1:
                offsets.append(position + 1)
                position = data.find(b"\n", position + 1)
            if offsets[-1] >= len(data):
                offsets.pop()
            cached = (stat.st_mtime, offsets)
            self._cache[str(path)] = cached
        offsets = cached[1]
        total = len(offsets)
        if offset >= total:
            return [], total
        end = min(total, offset + limit)
        with path.open("rb") as handle:
            handle.seek(offsets[offset])
            size = (offsets[end] - offsets[offset]) if end < total else -1
            chunk = handle.read(size)
        return chunk.decode("utf-8", errors="replace").splitlines(), total


def catalog() -> dict[str, Any]:
    return {
        "version": VERSION,
        "problems": [spec.to_dict() for spec in all_problems()],
        "solvers": [spec.to_dict() for spec in all_solvers()],
        "presets": [preset.to_dict() for preset in all_presets()],
        "log_levels": list(LOG_LEVELS),
        "limits": {"max_clauses": MAX_CLAUSES, "max_benchmark_runs": MAX_BENCHMARK_RUNS, "max_workers": max_workers()},
        "defaults": {
            "solve_timeout": DEFAULT_SOLVE_TIMEOUT,
            "benchmark_timeout": DEFAULT_TIMEOUT,
            "benchmark_rules": [DPLL_FALLBACK_RULE],
        },
    }


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.ensure_dirs()
        store = Store(settings.db_path)
        manager = JobManager(settings, store)
        manager.attach_loop(asyncio.get_running_loop())
        app.state.manager = manager
        flusher = asyncio.create_task(manager.flush_summaries())
        try:
            yield
        finally:
            flusher.cancel()
            await run_in_threadpool(manager.shutdown)
            store.close()

    app = FastAPI(title="WizSAT", version=VERSION, lifespan=lifespan)
    app.state.settings = settings
    cnf_index = CnfLineIndex()
    catalog_cache: dict[str, Any] = {}

    def manager_of(request: Request | WebSocket) -> JobManager:
        return request.app.state.manager

    def job_or_404(request: Request, job_id: int) -> Job:
        try:
            return manager_of(request).get(job_id)
        except KeyError:
            raise HTTPException(404, f"Job {job_id} not found") from None

    @app.exception_handler(ParamError)
    async def param_error_handler(_request: Request, exc: ParamError):
        return JSONResponse(status_code=422, content={"message": str(exc), "errors": exc.errors})

    # -- catalog & previews ---------------------------------------------------

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {"ok": True, "version": VERSION}

    @app.get("/api/catalog")
    async def get_catalog() -> dict[str, Any]:
        if not catalog_cache:
            catalog_cache.update(await run_in_threadpool(catalog))
        return catalog_cache

    @app.post("/api/problems/{key}/preview")
    async def preview(key: str, body: ParamsBody) -> dict[str, Any]:
        def work() -> dict[str, Any]:
            spec = _problem(key)
            params = spec.parse(body.params)
            try:
                estimate = spec.estimate(params)
            except ParamError:
                estimate = None
            return {
                "label": spec.case_label(params),
                "estimate": estimate,
                "too_large": bool(estimate and estimate["clauses"] > MAX_CLAUSES),
                "preview": spec.preview(params),
            }

        return await run_in_threadpool(work)

    @app.post("/api/benchmarks/plan")
    async def plan_benchmark(body: PlanBody) -> dict[str, Any]:
        return await run_in_threadpool(lambda: parse_request(body.request).summary())

    # -- jobs -----------------------------------------------------------------

    @app.get("/api/jobs")
    async def list_jobs(request: Request) -> dict[str, Any]:
        return {"jobs": manager_of(request).summaries()}

    @app.post("/api/jobs", status_code=201)
    async def create_job(request: Request, body: JobBody) -> dict[str, Any]:
        normalized, title = await run_in_threadpool(validate_job, body.kind, body.request, body.title)
        manager = manager_of(request)
        return manager.summary(manager.submit(body.kind, normalized, title))

    @app.get("/api/jobs/{job_id}")
    async def get_job(request: Request, job_id: int) -> dict[str, Any]:
        return manager_of(request).detail(job_or_404(request, job_id))

    @app.get("/api/jobs/{job_id}/rows")
    async def get_rows(request: Request, job_id: int) -> dict[str, Any]:
        job = job_or_404(request, job_id)
        rows = await run_in_threadpool(manager_of(request).rows, job)
        return {"job_id": job_id, "label": job.label, "rows": rows}

    @app.get("/api/jobs/{job_id}/logs")
    async def get_logs(request: Request, job_id: int) -> dict[str, Any]:
        job = job_or_404(request, job_id)
        with manager_of(request).lock:
            logs = list(job.logs)
        return {"job_id": job_id, "logs": logs}

    @app.post("/api/jobs/{job_id}/cancel")
    async def cancel_job(request: Request, job_id: int) -> dict[str, Any]:
        job_or_404(request, job_id)
        manager = manager_of(request)
        return manager.summary(manager.cancel(job_id))

    @app.post("/api/jobs/{job_id}/skip")
    async def skip_case(request: Request, job_id: int) -> dict[str, Any]:
        job_or_404(request, job_id)
        manager = manager_of(request)
        return manager.summary(manager.skip(job_id))

    @app.post("/api/jobs/{job_id}/rerun", status_code=201)
    async def rerun_job(request: Request, job_id: int) -> dict[str, Any]:
        job = job_or_404(request, job_id)
        normalized, title = await run_in_threadpool(validate_job, job.kind, job.request, job.title)
        manager = manager_of(request)
        return manager.summary(manager.submit(job.kind, normalized, title))

    @app.delete("/api/jobs/{job_id}", status_code=204)
    async def delete_job(request: Request, job_id: int) -> Response:
        job_or_404(request, job_id)
        try:
            await run_in_threadpool(manager_of(request).delete, job_id)
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from None
        return Response(status_code=204)

    @app.post("/api/jobs/clear")
    async def clear_jobs(request: Request, body: ClearBody) -> dict[str, Any]:
        deleted = await run_in_threadpool(manager_of(request).clear_finished, body.kinds)
        return {"deleted": deleted}

    @app.post("/api/jobs/reset-numbering", status_code=204)
    async def reset_numbering(request: Request) -> Response:
        try:
            await run_in_threadpool(manager_of(request).reset_numbering)
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from None
        return Response(status_code=204)

    @app.get("/api/jobs/{job_id}/files/{name}")
    async def download_file(request: Request, job_id: int, name: str) -> FileResponse:
        job = job_or_404(request, job_id)
        path = job.workdir / name
        if name not in DOWNLOADABLE_FILES or not path.is_file():
            raise HTTPException(404, "File not found")
        return FileResponse(path, filename=f"{job.label}_{name}", media_type="text/plain")

    @app.get("/api/jobs/{job_id}/cnf")
    async def cnf_lines(
        request: Request,
        job_id: int,
        offset: int = Query(0, ge=0),
        limit: int = Query(500, ge=1, le=5000),
    ) -> dict[str, Any]:
        job = job_or_404(request, job_id)
        path = job.workdir / "instance.cnf"
        if not path.is_file():
            raise HTTPException(404, "This job has no CNF file")
        lines, total = await run_in_threadpool(cnf_index.lines, path, offset, limit)
        return {"offset": offset, "lines": lines, "total": total}

    @app.get("/api/jobs/{job_id}/export.csv")
    async def export_job(request: Request, job_id: int) -> PlainTextResponse:
        job = job_or_404(request, job_id)
        rows = await run_in_threadpool(manager_of(request).rows, job)
        return _csv_response(rows_to_csv(rows, run_label=job.label), f"{job.label}_benchmark.csv")

    @app.get("/api/export.csv")
    async def export_jobs(request: Request, jobs: str = Query(..., description="Comma-separated job ids")) -> PlainTextResponse:
        combined: list[dict[str, Any]] = []
        labels = []
        for raw_id in jobs.split(","):
            if not raw_id.strip():
                continue
            try:
                job_id = int(raw_id)
            except ValueError:
                raise HTTPException(400, f"Not a job id: {raw_id.strip()}") from None
            job = job_or_404(request, job_id)
            labels.append(job.label)
            for row in await run_in_threadpool(manager_of(request).rows, job):
                combined.append({**row, "run_label": job.label})
        return _csv_response(rows_to_csv(combined), f"benchmark_{'_'.join(labels) or 'empty'}.csv")

    def _rebuild_case(job: Job, index: int, rows: list[dict[str, Any]]):
        if job.kind != "benchmark":
            raise HTTPException(400, "Only benchmark rows can be rebuilt")
        row = next((row for row in rows if row["index"] == index), None)
        if row is None:
            raise HTTPException(404, "Row not found")
        plan = parse_request(job.request)
        case = plan.cases[row["case_index"]]
        spec = get_problem(case.problem)
        instance = spec.build(case.params)
        return row, case, spec, instance

    @app.get("/api/jobs/{job_id}/rows/{index}/case")
    async def row_case(request: Request, job_id: int, index: int) -> dict[str, Any]:
        job = job_or_404(request, job_id)
        rows = await run_in_threadpool(manager_of(request).rows, job)

        def work() -> dict[str, Any]:
            row, case, spec, instance = _rebuild_case(job, index, rows)
            return {
                "row": row,
                "problem": spec.key,
                "params": visible_params(spec, case.params),
                "instance": instance_payload(spec, instance, 0.0, None),
            }

        return await run_in_threadpool(work)

    @app.get("/api/jobs/{job_id}/rows/{index}/cnf")
    async def row_cnf(request: Request, job_id: int, index: int) -> PlainTextResponse:
        job = job_or_404(request, job_id)
        rows = await run_in_threadpool(manager_of(request).rows, job)

        def work() -> str:
            _row, case, spec, instance = _rebuild_case(job, index, rows)
            comments = [instance.name]
            if spec.key != "dimacs":
                comments.append(app_header_comment(spec.key, visible_params(spec, case.params)))
            return clauses_to_dimacs(instance.clauses, comments)

        text = await run_in_threadpool(work)
        return PlainTextResponse(
            text,
            headers={"Content-Disposition": f'attachment; filename="{job.label}_case{index + 1}.cnf"'},
        )

    # -- live events ----------------------------------------------------------

    @app.websocket("/api/ws")
    async def events(websocket: WebSocket) -> None:
        await websocket.accept()
        manager = manager_of(websocket)
        subscriber = manager.subscribe()
        try:
            await websocket.send_json({"type": "hello", "version": VERSION, "jobs": manager.summaries()})
            while True:
                message = await subscriber.get()
                batch = [message]
                while not subscriber.empty() and len(batch) < 500:
                    batch.append(subscriber.get_nowait())
                await websocket.send_json({"type": "batch", "events": batch})
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            manager.unsubscribe(subscriber)

    # -- static files ---------------------------------------------------------

    if settings.assets_dir.is_dir():
        app.mount("/media", StaticFiles(directory=settings.assets_dir), name="media")
    if settings.visualisations_dir.is_dir():
        app.mount("/visualisations", StaticFiles(directory=settings.visualisations_dir, html=True), name="visualisations")

    dist = settings.frontend_dist
    index_file = dist / "index.html"
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="frontend-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def frontend(full_path: str) -> Response:
        if full_path.startswith("api/"):
            raise HTTPException(404, "Not found")
        if not index_file.is_file():
            return HTMLResponse(NOT_BUILT_PAGE, status_code=503)
        candidate = (dist / full_path).resolve()
        if full_path and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index_file)

    return app


def _csv_response(text: str, filename: str) -> PlainTextResponse:
    return PlainTextResponse(
        text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


NOT_BUILT_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>WizSAT</title>
<style>body{font-family:system-ui,sans-serif;max-width:40rem;margin:4rem auto;padding:0 1rem;line-height:1.5}
code{background:#eee;padding:.1rem .3rem;border-radius:4px}</style></head>
<body><h1>WizSAT server is running</h1>
<p>The web interface has not been built yet. Stop the server and start it with</p>
<p><code>python -m sat_web</code></p>
<p>which builds the interface automatically (Node.js 20+ is required), or build it yourself with
<code>cd frontend</code>, <code>npm install</code>, <code>npm run build</code>.</p>
<p>The API is available under <code>/api</code>; see <a href="/docs">/docs</a>.</p>
</body></html>
"""

