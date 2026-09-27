"""
Web API tests. They start real worker processes, so each job takes a moment.

Skipped automatically when the web dependencies (fastapi, httpx) are not
installed: python -m pip install -r requirements-dev.txt
"""

import csv
import io
import tempfile
import time
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover
    raise unittest.SkipTest("fastapi/httpx not installed; run pip install -r requirements-dev.txt")

from sat_web.api import create_app
from sat_web.config import Settings


def make_settings(folder: str, dist: Path | None = None) -> Settings:
    return Settings(data_dir=Path(folder), max_parallel_jobs=2, frontend_dist=dist or Path(folder) / "no-dist")


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.client = TestClient(create_app(make_settings(self.folder.name)))
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.folder.cleanup()

    def submit(self, kind, request, status=201):
        response = self.client.post("/api/jobs", json={"kind": kind, "request": request})
        self.assertEqual(response.status_code, status, response.text)
        return response.json()

    def wait(self, job_id, timeout=60):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            job = self.client.get(f"/api/jobs/{job_id}").json()
            if job["status"] in ("done", "failed", "cancelled"):
                return job
            time.sleep(0.1)
        self.fail(f"job {job_id} did not finish")


class CatalogTests(ApiTestCase):
    def test_catalog_lists_problems_solvers_and_presets(self):
        data = self.client.get("/api/catalog").json()

        self.assertEqual(len(data["problems"]), 8)
        self.assertEqual([solver["key"] for solver in data["solvers"]], ["cdcl", "dpll", "walksat", "probsat"])
        presets = {preset["key"]: preset for preset in data["presets"]}
        self.assertEqual(presets["3sat_forced_unsat"]["cases"], 100)
        self.assertEqual(data["defaults"]["benchmark_rules"][0]["seconds"], 10.0)
        graph_fields = next(p for p in data["problems"] if p["key"] == "clique")["fields"]
        self.assertEqual(graph_fields[2]["show_if"], {"graph_mode": ["manual"]})

    def test_preview_and_field_errors(self):
        response = self.client.post("/api/problems/graph_coloring/preview", json={"params": {"nodes": 5, "probability": 1}})
        data = response.json()
        self.assertEqual(len(data["preview"]["edges"]), 10)
        self.assertEqual(data["estimate"]["variables"], 15)

        response = self.client.post("/api/problems/clique/preview", json={"params": {"nodes": 3, "target": 7}})
        self.assertEqual(response.status_code, 422)
        self.assertIn("target", response.json()["errors"])

        response = self.client.post("/api/problems/chess/preview", json={"params": {}})
        self.assertEqual(response.status_code, 422)
        self.assertIn("problem", response.json()["errors"])

    def test_benchmark_plan(self):
        response = self.client.post(
            "/api/benchmarks/plan",
            json={"request": {"problems": ["n_queens"], "segments": [{"size": "4..8"}], "solvers": ["cdcl", "dpll"]}},
        )
        data = response.json()
        self.assertEqual((data["cases"], data["runs"]), (5, 10))
        self.assertEqual(data["largest"]["variables"], 64)

        response = self.client.post("/api/benchmarks/plan", json={"request": {"problems": ["n_queens"], "solvers": []}})
        self.assertEqual(response.status_code, 422)

    def test_frontend_not_built_page_and_api_404(self):
        self.assertEqual(self.client.get("/").status_code, 503)
        self.assertEqual(self.client.get("/api/nothing").status_code, 404)
        self.assertEqual(self.client.get("/media/logo.png").status_code, 200)


class JobTests(ApiTestCase):
    def test_solve_job_lifecycle(self):
        job = self.submit("solve", {"problem": "n_queens", "params": {"size": 8}, "solver": "cdcl"})
        self.assertEqual(job["label"], f"J{job['id']}")
        self.assertIn("N-Queens", job["title"])

        detail = self.wait(job["id"])
        self.assertEqual(detail["status"], "done")
        self.assertEqual(detail["result"]["status"], "SAT")
        self.assertTrue(detail["result"]["verified"])
        self.assertEqual(detail["instance"]["visual"], {"size": 8})

        cnf = self.client.get(f"/api/jobs/{job['id']}/cnf", params={"limit": 3}).json()
        self.assertEqual(cnf["lines"][0], "c N-Queens (n=8)")
        self.assertGreater(cnf["total"], 700)
        model = self.client.get(f"/api/jobs/{job['id']}/files/model.txt")
        self.assertTrue(model.text.startswith("s SATISFIABLE"))
        self.assertEqual(self.client.get(f"/api/jobs/{job['id']}/files/secret.db").status_code, 404)

        self.assertEqual(self.client.delete(f"/api/jobs/{job['id']}").status_code, 204)
        self.assertEqual(self.client.get(f"/api/jobs/{job['id']}").status_code, 404)

    def test_blank_seed_is_resolved_before_queueing(self):
        job = self.submit("generate", {"problem": "random_3sat", "params": {"seed": ""}})
        detail = self.client.get(f"/api/jobs/{job['id']}").json()

        self.assertIsInstance(detail["request"]["params"]["seed"], int)
        self.assertNotIn("sat_percent", detail["request"]["params"])
        self.wait(job["id"])

    def test_invalid_jobs_are_rejected_with_field_errors(self):
        response = self.client.post("/api/jobs", json={"kind": "solve", "request": {"problem": "n_queens", "params": {"size": 0}}})
        self.assertEqual(response.status_code, 422)
        self.assertIn("size", response.json()["errors"])

        response = self.client.post("/api/jobs", json={"kind": "solve", "request": {"problem": "n_queens", "solver": "cdcl", "options": {"noise": 1}}})
        self.assertIn("options.noise", response.json()["errors"])

        response = self.client.post("/api/jobs", json={"kind": "benchmark", "request": {"problems": ["hamiltonian_path"], "segments": [{"nodes": 400, "probability": 0.1}], "solvers": ["cdcl"]}})
        self.assertEqual(response.status_code, 201)

    def test_benchmark_rows_export_and_case_rebuild(self):
        job = self.submit(
            "benchmark",
            {"problems": ["random_3sat"], "segments": [{"variables": 20, "ratio": "3, 5", "seed": 1}], "solvers": ["cdcl", "walksat"], "repeats": 1},
        )
        detail = self.wait(job["id"])
        self.assertEqual(detail["row_count"], 4)

        rows = self.client.get(f"/api/jobs/{job['id']}/rows").json()["rows"]
        self.assertEqual([row["solver"] for row in rows], ["cdcl", "walksat", "cdcl", "walksat"])

        table = list(csv.DictReader(io.StringIO(self.client.get(f"/api/jobs/{job['id']}/export.csv").text)))
        self.assertEqual(len(table), 4)
        self.assertEqual(table[0]["run"], job["label"])

        case = self.client.get(f"/api/jobs/{job['id']}/rows/2/case").json()
        self.assertEqual(case["params"]["ratio"], 5.0)
        self.assertEqual(case["instance"]["clauses"], 100)
        cnf = self.client.get(f"/api/jobs/{job['id']}/rows/2/cnf").text
        self.assertIn("p cnf 20 100", cnf)

        rerun = self.client.post(f"/api/jobs/{job['id']}/rerun").json()
        self.assertEqual(self.wait(rerun["id"])["row_count"], 4)
        combined = self.client.get("/api/export.csv", params={"jobs": f"{job['id']},{rerun['id']}"}).text
        self.assertEqual(len(combined.strip().splitlines()), 9)
        self.assertEqual(self.client.get("/api/export.csv", params={"jobs": "1,x"}).status_code, 400)

    def test_cancel_a_running_job(self):
        job = self.submit(
            "solve",
            {"problem": "random_3sat", "params": {"variables": 250, "ratio": 4.26, "mode": "random", "seed": 3}, "solver": "dpll", "timeout": None},
        )
        deadline = time.monotonic() + 30
        while self.client.get(f"/api/jobs/{job['id']}").json()["status"] != "running" and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertEqual(self.client.delete(f"/api/jobs/{job['id']}").status_code, 409)

        self.client.post(f"/api/jobs/{job['id']}/cancel")
        self.assertEqual(self.wait(job["id"], timeout=15)["status"], "cancelled")

    def test_queue_respects_parallel_limit_and_clear(self):
        jobs = [self.submit("solve", {"problem": "n_queens", "params": {"size": 6}, "solver": "cdcl"}) for _ in range(3)]
        statuses = [job["status"] for job in self.client.get("/api/jobs").json()["jobs"]]
        self.assertLessEqual(statuses.count("running"), 2)

        for job in jobs:
            self.wait(job["id"])
        deleted = self.client.post("/api/jobs/clear", json={}).json()["deleted"]
        self.assertEqual(sorted(deleted), sorted(job["id"] for job in jobs))

    def test_websocket_streams_job_events(self):
        with self.client.websocket_connect("/api/ws") as socket:
            hello = socket.receive_json()
            self.assertEqual(hello["type"], "hello")
            job = self.submit("solve", {"problem": "n_queens", "params": {"size": 5}, "solver": "cdcl"})
            seen = set()
            revs = []
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                message = socket.receive_json()
                for event in message["events"]:
                    seen.add(event["type"])
                    if event["type"] == "job" and event["job"]["id"] == job["id"]:
                        revs.append(event["job"]["rev"])
                        if event["job"]["status"] == "done":
                            deadline = 0
            self.assertTrue({"job", "log", "instance", "result"} <= seen)
            # Every published summary is newer than the last, so clients can drop stale copies.
            self.assertEqual(revs, sorted(set(revs)))
            self.assertIn(job["rev"], revs)
            self.assertEqual(self.client.get(f"/api/jobs/{job['id']}").json()["rev"], revs[-1])


class PersistenceTests(unittest.TestCase):
    def test_jobs_survive_a_restart_and_running_jobs_become_interrupted(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = make_settings(folder)
            with TestClient(create_app(settings)) as client:
                job = client.post("/api/jobs", json={"kind": "benchmark", "request": {"problems": ["n_queens"], "segments": [{"size": "4,5"}], "solvers": ["cdcl"]}}).json()
                deadline = time.monotonic() + 60
                while client.get(f"/api/jobs/{job['id']}").json()["status"] != "done" and time.monotonic() < deadline:
                    time.sleep(0.1)

            from sat_web.store import Store

            store = Store(settings.db_path)
            store.insert_job({"kind": "solve", "title": "ghost", "status": "running", "request": {}})
            store.close()

            with TestClient(create_app(make_settings(folder))) as client:
                jobs = {item["title"]: item for item in client.get("/api/jobs").json()["jobs"]}
                self.assertEqual(jobs["ghost"]["status"], "interrupted")
                restored = client.get(f"/api/jobs/{job['id']}/rows").json()["rows"]
                self.assertEqual(len(restored), 2)


class FrontendServingTests(unittest.TestCase):
    def test_spa_fallback_serves_index_for_client_routes(self):
        with tempfile.TemporaryDirectory() as folder:
            dist = Path(folder) / "dist"
            (dist / "assets").mkdir(parents=True)
            (dist / "index.html").write_text("<html>app</html>")
            (dist / "assets" / "app.js").write_text("console.log(1)")
            (dist / "favicon.png").write_bytes(b"png")
            with TestClient(create_app(make_settings(folder, dist))) as client:
                self.assertIn("app", client.get("/benchmarks/results").text)
                self.assertEqual(client.get("/assets/app.js").text, "console.log(1)")
                self.assertEqual(client.get("/favicon.png").content, b"png")
                self.assertEqual(client.get("/api/missing").status_code, 404)


if __name__ == "__main__":
    unittest.main()
