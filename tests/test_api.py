"""
Web API tests. They start real worker processes, so each job takes a moment.

Skipped when the web dependencies (fastapi, httpx) are not installed:
python -m pip install -r requirements-dev.txt

A skipped module looks like a pass ("OK (skipped=1)"), so CI and agent
sessions set WIZSAT_REQUIRE_API_TESTS=1, which turns the skip into a failure.
"""

import csv
import io
import json
import os
import platform
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

try:
    from fastapi.testclient import TestClient
    import starlette.testclient
    from starlette.websockets import WebSocketDisconnect
except ImportError as exc:  # pragma: no cover
    install_hint = "fastapi/httpx not installed; run: python -m pip install -r requirements-dev.txt"
    if os.environ.get("WIZSAT_REQUIRE_API_TESTS", "").lower() not in ("", "0", "false"):
        raise ImportError(f"WIZSAT_REQUIRE_API_TESTS is set, but {install_hint}") from exc
    raise unittest.SkipTest(install_hint) from None

from sat_web.api import create_app
from sat_web.config import Settings


def make_settings(folder: str, dist: Path | None = None) -> Settings:
    return Settings(data_dir=Path(folder), max_parallel_jobs=2, frontend_dist=dist or Path(folder) / "no-dist")


# The server only answers for its own names; TestClient's default host is "testserver".
LOCAL = "localhost:8000"


def local_client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings), base_url=f"http://{LOCAL}")


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.client = local_client(make_settings(self.folder.name, self.make_dist(Path(self.folder.name))))
        self.client.__enter__()

    def make_dist(self, folder: Path) -> Path | None:
        """A built frontend to serve, for tests that need the page; none by default."""
        return None

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

    def test_catalog_declares_the_statistics(self):
        stats = {entry["key"]: entry for entry in self.client.get("/api/catalog").json()["stats"]}

        self.assertEqual(
            stats["learned_clauses"],
            {
                "key": "learned_clauses",
                "label": "Learned clauses",
                "short": "learned",
                "help": "Clauses CDCL derived from conflicts so it never repeats the same mistake.",
                "unit": "",
                "csv": True,
                "chart": True,
            },
        )
        self.assertFalse(stats["flip_break_total"]["csv"])

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

    def test_a_finished_job_reports_the_environment_it_ran_in(self):
        job = self.submit("solve", {"problem": "n_queens", "params": {"size": 5}, "solver": "cdcl"})
        detail = self.wait(job["id"])

        # Reported by the worker process, which is this interpreter (META-2).
        self.assertEqual(detail["environment"]["python_implementation"], platform.python_implementation())
        self.assertEqual(detail["environment"]["wizsat_version"], self.client.get("/api/health").json()["version"])
        # Only the detail carries it, not the job list or the live summaries.
        listed = next(item for item in self.client.get("/api/jobs").json()["jobs"] if item["id"] == job["id"])
        self.assertNotIn("environment", listed)

    def test_the_server_reads_the_machine_once_and_hands_it_to_each_job(self):
        # A worker is a fresh process: it can only know this CPU name from the server (A39).
        server_machine = {"os": "Server OS", "cpu_model": "Read by the server", "cpu_logical_cores": 2, "cpu_physical_cores": 1, "ram_total_gb": 4.0}
        with mock.patch("sat_web.manager.machine_facts", return_value=server_machine) as read:
            with local_client(make_settings(str(Path(self.folder.name) / "machine"))) as client:
                ids = [client.post("/api/jobs", json={"kind": "solve", "request": {"problem": "n_queens", "params": {"size": 4}}}).json()["id"] for _ in range(2)]
                deadline = time.monotonic() + 60
                while any(client.get(f"/api/jobs/{job_id}").json()["status"] not in ("done", "failed") for job_id in ids) and time.monotonic() < deadline:
                    time.sleep(0.1)
                details = [client.get(f"/api/jobs/{job_id}").json() for job_id in ids]
        self.assertEqual(read.call_count, 1)
        for detail in details:
            self.assertEqual(detail["status"], "done", detail["error"])
            self.assertEqual({key: detail["environment"][key] for key in server_machine}, server_machine)
            self.assertEqual(detail["environment"]["python_implementation"], platform.python_implementation())

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

    def test_a_worker_that_dies_without_reporting_fails_its_job(self):
        # For example killed for memory: no final event ever arrives (audit item A7).
        job = self.submit(
            "benchmark",
            {
                "problems": ["random_3sat"],
                "segments": [{"variables": 250, "ratio": 4.26, "mode": "random", "seed": 3}],
                "solvers": ["dpll"],
                "timeout": None,
            },
        )
        manager = self.client.app.state.manager
        deadline = time.monotonic() + 30
        while (manager.get(job["id"]).process is None or not manager.get(job["id"]).process.is_alive()) and time.monotonic() < deadline:
            time.sleep(0.05)
        manager.get(job["id"]).process.kill()

        finished = self.wait(job["id"], timeout=15)
        self.assertEqual(finished["status"], "failed")
        self.assertIn("stopped unexpectedly", finished["error"])
        # The slot is free again: the next job runs.
        self.assertEqual(self.wait(self.submit("solve", {"problem": "n_queens", "params": {"size": 5}, "solver": "cdcl"})["id"])["status"], "done")

    def test_parallel_benchmark_job_runs_and_cancels(self):
        job = self.submit(
            "benchmark",
            {"problems": ["n_queens"], "segments": [{"size": "4..9"}], "solvers": ["cdcl", "dpll"], "workers": 2},
        )
        detail = self.wait(job["id"])
        self.assertEqual(detail["status"], "done")
        rows = self.client.get(f"/api/jobs/{job['id']}/rows").json()["rows"]
        self.assertEqual(sorted(row["index"] for row in rows), list(range(12)))

        slow = self.submit(
            "benchmark",
            {
                "problems": ["random_3sat"],
                "segments": [{"variables": 250, "ratio": 4.26, "mode": "random", "seed": "1..20"}],
                "solvers": ["dpll"],
                "timeout": None,
                "rules": [],
                "workers": 2,
            },
        )
        deadline = time.monotonic() + 30
        while self.client.get(f"/api/jobs/{slow['id']}").json()["status"] != "running" and time.monotonic() < deadline:
            time.sleep(0.05)
        time.sleep(1.5)  # let the workers start solving
        self.client.post(f"/api/jobs/{slow['id']}/cancel")
        self.assertEqual(self.wait(slow["id"], timeout=15)["status"], "cancelled")

    def test_queue_respects_parallel_limit_and_clear(self):
        jobs = [self.submit("solve", {"problem": "n_queens", "params": {"size": 6}, "solver": "cdcl"}) for _ in range(3)]
        statuses = [job["status"] for job in self.client.get("/api/jobs").json()["jobs"]]
        self.assertLessEqual(statuses.count("running"), 2)

        for job in jobs:
            self.wait(job["id"])
        deleted = self.client.post("/api/jobs/clear", json={}).json()["deleted"]
        self.assertEqual(sorted(deleted), sorted(job["id"] for job in jobs))

    def test_numbering_restarts_only_when_no_jobs_are_left(self):
        request = {"problem": "n_queens", "params": {"size": 5}, "solver": "cdcl"}
        first = self.submit("solve", request)
        second = self.submit("solve", request)
        self.assertEqual(second["id"], first["id"] + 1)
        self.wait(first["id"])
        self.wait(second["id"])

        # Deleting the newest job does not hand its number out again.
        self.client.delete(f"/api/jobs/{second['id']}")
        self.assertEqual(self.submit("solve", request)["id"], second["id"] + 1)

        # Refused while any job exists.
        response = self.client.post("/api/jobs/reset-numbering")
        self.assertEqual(response.status_code, 409)
        self.assertIn("Delete every job first", response.json()["detail"])

        for job in self.client.get("/api/jobs").json()["jobs"]:
            self.wait(job["id"])
        self.client.post("/api/jobs/clear", json={})
        leftover = Path(self.folder.name) / "jobs" / "1"
        leftover.mkdir(parents=True, exist_ok=True)
        (leftover / "instance.cnf").write_text("stale")

        self.assertEqual(self.client.post("/api/jobs/reset-numbering").status_code, 204)
        restarted = self.submit("solve", request)
        self.assertEqual(restarted["id"], 1)
        self.assertEqual(restarted["label"], "J1")
        detail = self.wait(1)
        self.assertEqual(detail["result"]["status"], "SAT")
        self.assertNotEqual((leftover / "instance.cnf").read_text(), "stale")

    def test_websocket_streams_job_events(self):
        with self.client.websocket_connect(f"ws://{LOCAL}/api/ws") as socket:
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


class OriginAndHostTests(ApiTestCase):
    """Only this machine's own pages may use the API (audit item A1)."""

    request = {"problem": "n_queens", "params": {"size": 5}, "solver": "cdcl"}

    def reset_numbering(self, **headers):
        return self.client.post("/api/jobs/reset-numbering", headers=headers)

    def use_up_job_number_one(self):
        job = self.submit("solve", self.request)
        self.wait(job["id"])
        self.assertEqual(self.client.delete(f"/api/jobs/{job['id']}").status_code, 204)

    def test_foreign_origin_is_refused_and_changes_nothing(self):
        self.use_up_job_number_one()
        for origin in ("http://evil.example", "http://localhost.evil.example:8000", "null", "file://"):
            response = self.reset_numbering(Origin=origin)
            self.assertEqual(response.status_code, 403, origin)
            self.assertIn("Origin", response.json()["detail"])
        # The numbering was not restarted.
        self.assertEqual(self.submit("solve", self.request)["id"], 2)

    def test_foreign_origin_cannot_read_either(self):
        self.assertEqual(self.client.get("/api/jobs", headers={"Origin": "http://evil.example"}).status_code, 403)

    def test_local_origins_and_no_origin_still_work(self):
        # Any port: the Vite dev server sends Origin http://localhost:5173.
        for origin in ("http://localhost:8000", "http://localhost:5173", "http://127.0.0.1:8000", "http://[::1]:8000"):
            self.use_up_job_number_one()
            self.assertEqual(self.reset_numbering(Origin=origin).status_code, 204, origin)
        self.use_up_job_number_one()
        self.assertEqual(self.reset_numbering().status_code, 204)
        self.assertEqual(self.submit("solve", self.request)["id"], 1)

    def test_foreign_host_is_refused(self):
        # DNS rebinding: a hostile name that resolves to 127.0.0.1.
        self.assertEqual(self.client.get("/api/health", headers={"Host": "evil.example"}).status_code, 400)
        self.assertEqual(self.client.get("/", headers={"Host": "evil.example:8000"}).status_code, 400)
        # The refusal names the setting, for someone who reaches the server under a new name.
        self.assertIn("WIZSAT_ALLOWED_HOSTS", self.client.get("/", headers={"Host": "my-pc:8000"}).text)
        for host in ("localhost", "127.0.0.1:8000", "[::1]:8000", "LOCALHOST:8000"):
            self.assertEqual(self.client.get("/api/health", headers={"Host": host}).status_code, 200, host)

    def assert_websocket_refused(self, **headers):
        # Starlette reports a handshake refused with an HTTP response (the Host check) as its own type.
        refused = (WebSocketDisconnect, getattr(starlette.testclient, "WebSocketDenialResponse", WebSocketDisconnect))
        with self.assertRaises(refused):
            with self.client.websocket_connect(f"ws://{LOCAL}/api/ws", headers=headers) as socket:
                self.fail(f"connected and received {socket.receive_json()['type']}")

    def test_websocket_refuses_foreign_origin_and_host_before_hello(self):
        self.assert_websocket_refused(Origin="http://evil.example")
        self.assert_websocket_refused(Host="evil.example")
        with self.client.websocket_connect(f"ws://{LOCAL}/api/ws", headers={"Origin": "http://localhost:5173"}) as socket:
            self.assertEqual(socket.receive_json()["type"], "hello")

    def test_extra_hosts_come_from_the_environment(self):
        with mock.patch.dict(os.environ, {"WIZSAT_ALLOWED_HOSTS": "Wizsat.lan, FE80:0:0:0:0:0:0:1,"}):
            settings = make_settings(self.folder.name)
        self.assertEqual(settings.allowed_hosts, ["localhost", "127.0.0.1", "[::1]", "wizsat.lan", "[fe80::1]"])
        with local_client(settings) as client:
            response = client.post("/api/jobs/reset-numbering", headers={"Host": "wizsat.lan:8000", "Origin": "http://wizsat.lan:8000"})
            self.assertEqual(response.status_code, 204)
            self.assertEqual(client.get("/api/health", headers={"Host": "evil.example"}).status_code, 400)

    def test_host_names_that_could_never_match_are_refused_at_start(self):
        # A port, a URL or a wildcard would be an entry that silently matches nothing (or everything).
        for value in ("192.168.1.20:8000", "http://my-pc", "*.lan", "*", "my pc"):
            with mock.patch.dict(os.environ, {"WIZSAT_ALLOWED_HOSTS": value}):
                with self.assertRaisesRegex(ValueError, "WIZSAT_ALLOWED_HOSTS"):
                    Settings()

    def test_launcher_passes_its_host_to_the_app(self):
        from sat_web.__main__ import allow_host

        with mock.patch.dict(os.environ, {"WIZSAT_ALLOWED_HOSTS": "wizsat.lan"}):
            allow_host("192.168.1.20")
            # "Every interface" is not a name anyone addresses the server by.
            allow_host("0.0.0.0")
            allow_host("::")
            self.assertEqual(Settings().allowed_hosts[3:], ["wizsat.lan", "192.168.1.20"])


class FramingAndFetchSiteTests(ApiTestCase):
    """Another site may neither frame the app nor make the browser call the API (audit item A13)."""

    def make_dist(self, folder):
        dist = folder / "dist"
        dist.mkdir()
        (dist / "index.html").write_text("<html>app</html>")
        return dist

    def assert_not_frameable(self, response):
        self.assertEqual(response.headers.get("content-security-policy"), "frame-ancestors 'self'", response.url)
        self.assertEqual(response.headers.get("x-frame-options"), "SAMEORIGIN", response.url)

    def test_page_and_api_replies_refuse_foreign_frames(self):
        # The Learn page frames /visualisations/ itself, which 'self' allows.
        for path in ("/", "/benchmarks/results", "/api/jobs", "/api/missing", "/visualisations/cdcl/"):
            self.assert_not_frameable(self.client.get(path))
        # Refusals too: a frame showing an error page is still a frame.
        self.assert_not_frameable(self.client.get("/api/jobs", headers={"Origin": "http://evil.example"}))

    def test_cross_site_api_request_is_refused(self):
        # An <img src="http://127.0.0.1:8000/api/..."> on another site sends no Origin, only this.
        response = self.client.get("/api/jobs", headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(response.status_code, 403)
        self.assert_not_frameable(response)
        for site in (None, "same-origin", "same-site", "none"):
            headers = {"Sec-Fetch-Site": site} if site else {}
            self.assertEqual(self.client.get("/api/jobs", headers=headers).status_code, 200, site)

    def test_cross_site_websocket_is_refused(self):
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect(f"ws://{LOCAL}/api/ws", headers={"Sec-Fetch-Site": "cross-site"}) as socket:
                self.fail(f"connected and received {socket.receive_json()['type']}")

    def test_link_from_another_site_still_opens_the_app(self):
        headers = {"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document"}
        response = self.client.get("/", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn("app", response.text)


class PersistenceTests(unittest.TestCase):
    def test_jobs_survive_a_restart_and_running_jobs_become_interrupted(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = make_settings(folder)
            with local_client(settings) as client:
                job = client.post("/api/jobs", json={"kind": "benchmark", "request": {"problems": ["n_queens"], "segments": [{"size": "4,5"}], "solvers": ["cdcl"]}}).json()
                deadline = time.monotonic() + 60
                while client.get(f"/api/jobs/{job['id']}").json()["status"] != "done" and time.monotonic() < deadline:
                    time.sleep(0.1)

            from sat_web.store import Store

            store = Store(settings.db_path)
            store.insert_job({"kind": "solve", "title": "ghost", "status": "running", "request": {}})
            store.close()

            with local_client(make_settings(folder)) as client:
                jobs = {item["title"]: item for item in client.get("/api/jobs").json()["jobs"]}
                self.assertEqual(jobs["ghost"]["status"], "interrupted")
                restored = client.get(f"/api/jobs/{job['id']}/rows").json()["rows"]
                self.assertEqual(len(restored), 2)

    def test_a_database_from_before_the_environment_column_still_opens(self):
        # The jobs table as it was created before META-2: no environment column.
        old_schema = """
            CREATE TABLE jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, title TEXT NOT NULL,
                status TEXT NOT NULL, created_at TEXT, started_at TEXT, finished_at TEXT,
                request TEXT, progress TEXT, instance TEXT, result TEXT, error TEXT,
                errors TEXT, logs TEXT, workdir TEXT
            )
        """
        request = {"problem": "n_queens", "params": {"size": 5}, "solver": "cdcl"}
        with tempfile.TemporaryDirectory() as folder:
            settings = make_settings(folder)
            settings.db_path.parent.mkdir(parents=True, exist_ok=True)
            db = sqlite3.connect(str(settings.db_path))
            db.execute(old_schema)
            db.execute(
                "INSERT INTO jobs (kind, title, status, request) VALUES (?, ?, ?, ?)",
                ("solve", "from an old version", "done", json.dumps(request)),
            )
            db.commit()
            db.close()

            with local_client(settings) as client:
                jobs = client.get("/api/jobs").json()["jobs"]
                self.assertEqual([job["title"] for job in jobs], ["from an old version"])
                self.assertIsNone(client.get(f"/api/jobs/{jobs[0]['id']}").json()["environment"])

                # The added column holds the environment of a new job across a restart.
                new_id = client.post("/api/jobs", json={"kind": "solve", "request": request}).json()["id"]
                deadline = time.monotonic() + 60
                while client.get(f"/api/jobs/{new_id}").json()["status"] not in ("done", "failed", "cancelled") and time.monotonic() < deadline:
                    time.sleep(0.1)
                self.assertEqual(client.get(f"/api/jobs/{new_id}").json()["status"], "done")

            with local_client(make_settings(folder)) as client:
                self.assertIsNone(client.get(f"/api/jobs/{jobs[0]['id']}").json()["environment"])
                restored = client.get(f"/api/jobs/{new_id}").json()["environment"]
                self.assertEqual(restored["python_implementation"], platform.python_implementation())

    def test_jobs_saved_with_removed_solver_options_still_open_and_rerun(self):
        # Before the ProbSAT rewrite its options included noise and adaptive_noise
        # (audit item A3); saved jobs keep them.
        old_options = {"noise": 0.5, "adaptive_noise": False, "max_flips": 2000, "random_seed": 1}
        benchmark = {"problems": ["n_queens"], "segments": [{"size": "4,5"}], "solvers": [{"solver": "probsat"}, {"solver": "cdcl"}]}
        solve = {"problem": "n_queens", "params": {"size": 5}, "solver": "probsat"}
        with tempfile.TemporaryDirectory() as folder:
            with local_client(make_settings(folder)) as client:
                ids = {}
                for kind, request in (("benchmark", benchmark), ("solve", solve)):
                    ids[kind] = client.post("/api/jobs", json={"kind": kind, "request": request}).json()["id"]
                    deadline = time.monotonic() + 60
                    while client.get(f"/api/jobs/{ids[kind]}").json()["status"] != "done" and time.monotonic() < deadline:
                        time.sleep(0.1)
                stored = {kind: client.get(f"/api/jobs/{job_id}").json()["request"] for kind, job_id in ids.items()}

            from sat_web.store import Store

            stored["benchmark"]["solvers"][0]["options"] = dict(old_options)
            stored["solve"]["options"] = dict(old_options)
            store = Store(make_settings(folder).db_path)
            for kind, job_id in ids.items():
                store.update_job(job_id, request=stored[kind])
            store.close()

            with local_client(make_settings(folder)) as client:
                benchmark_id = ids["benchmark"]
                for index in (0, 1, 3):
                    with self.subTest(row=index):
                        self.assertEqual(client.get(f"/api/jobs/{benchmark_id}/rows/{index}/case").status_code, 200)
                        self.assertEqual(client.get(f"/api/jobs/{benchmark_id}/rows/{index}/cnf").status_code, 200)

                rerun = client.post(f"/api/jobs/{benchmark_id}/rerun")
                self.assertEqual(rerun.status_code, 201, rerun.text)
                options = client.get(f"/api/jobs/{rerun.json()['id']}").json()["request"]["solvers"][0]["options"]
                self.assertNotIn("noise", options)
                self.assertNotIn("adaptive_noise", options)
                # Options the solver still has are kept.
                self.assertEqual((options["max_flips"], options["random_seed"]), (2000, 1))

                rerun = client.post(f"/api/jobs/{ids['solve']}/rerun")
                self.assertEqual(rerun.status_code, 201, rerun.text)
                options = client.get(f"/api/jobs/{rerun.json()['id']}").json()["request"]["options"]
                self.assertNotIn("noise", options)
                self.assertEqual((options["max_flips"], options["random_seed"]), (2000, 1))

                # Only saved jobs are cleaned: a new request with that option is still refused.
                fresh = client.post("/api/jobs", json={"kind": "solve", "request": {**solve, "options": old_options}})
                self.assertEqual(fresh.status_code, 422)
                self.assertIn("options.noise", fresh.json()["errors"])


class FrontendServingTests(unittest.TestCase):
    def test_spa_fallback_serves_index_for_client_routes(self):
        with tempfile.TemporaryDirectory() as folder:
            dist = Path(folder) / "dist"
            (dist / "assets").mkdir(parents=True)
            (dist / "index.html").write_text("<html>app</html>")
            (dist / "assets" / "app.js").write_text("console.log(1)")
            (dist / "favicon.png").write_bytes(b"png")
            with local_client(make_settings(folder, dist)) as client:
                self.assertIn("app", client.get("/benchmarks/results").text)
                self.assertEqual(client.get("/assets/app.js").text, "console.log(1)")
                self.assertEqual(client.get("/favicon.png").content, b"png")
                self.assertEqual(client.get("/api/missing").status_code, 404)


if __name__ == "__main__":
    unittest.main()
