"""run_environment(): the machine and software facts recorded with every run."""

import json
import platform
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fake_python import write_fake_python
from sat_core import environment
from sat_core.environment import VERSION, run_environment

# What the function reads itself. "workers" and "started_at" are job facts:
# they already live in the request and on the stored job.
KEYS = {
    "python_implementation",
    "python_version",
    "os",
    "cpu_model",
    "cpu_logical_cores",
    "cpu_physical_cores",
    "ram_total_gb",
    "wizsat_version",
    "git_commit",
    "git_dirty",
}


class RunEnvironmentTests(unittest.TestCase):
    def setUp(self):
        environment._machine.cache_clear()
        self.addCleanup(environment._machine.cache_clear)

    def test_returns_every_key_and_is_json_serialisable(self):
        facts = run_environment()
        self.assertEqual(set(facts), KEYS)
        self.assertEqual(json.loads(json.dumps(facts)), facts)

    def test_the_always_available_facts_have_real_values(self):
        facts = run_environment()
        self.assertIn(facts["python_implementation"], {"CPython", "PyPy"})
        self.assertRegex(facts["python_version"], r"^\d+\.\d+\.\d+")
        self.assertTrue(facts["os"])
        self.assertGreaterEqual(facts["cpu_logical_cores"], 1)
        self.assertEqual(facts["wizsat_version"], VERSION)

    def test_a_caller_cannot_change_the_cached_result(self):
        run_environment()["os"] = "changed"
        self.assertNotEqual(run_environment()["os"], "changed")

    def test_missing_cpuinfo_and_git_give_none_not_an_error(self):
        with (
            mock.patch.object(environment, "CPUINFO", Path("/nonexistent/cpuinfo")),
            mock.patch.object(environment.subprocess, "run", side_effect=FileNotFoundError("git")),
            mock.patch.object(environment.platform, "processor", return_value=""),
            mock.patch.object(environment.platform, "system", return_value="Linux"),
        ):
            facts = run_environment()
        self.assertEqual(set(facts), KEYS)
        for key in ("cpu_model", "cpu_physical_cores", "git_commit", "git_dirty"):
            self.assertIsNone(facts[key], key)

    def test_a_cgroup_memory_limit_wins_over_the_host_ram(self):
        host = 64 * 1024**3
        for text, expected in [
            ("2147483648\n", 2.0),  # cgroup v2 / v1 limit of 2 GiB
            ("max\n", 64.0),  # cgroup v2: no limit
            (str(2**63 - 4096), 64.0),  # cgroup v1: "no limit" is a huge number
            ("garbage", 64.0),
        ]:
            with self.subTest(text=text):
                environment._machine.cache_clear()
                limit_file = mock.Mock(read_text=mock.Mock(return_value=text))
                with (
                    mock.patch.object(environment, "_host_ram_bytes", return_value=host),
                    mock.patch.object(environment, "CGROUP_MEMORY_FILES", (limit_file,)),
                ):
                    self.assertEqual(run_environment()["ram_total_gb"], expected)

    def test_an_architecture_name_is_not_a_cpu_model(self):
        with (
            mock.patch.object(environment, "CPUINFO", Path("/nonexistent/cpuinfo")),
            mock.patch.object(environment.platform, "system", return_value="Linux"),
            mock.patch.object(environment.platform, "processor", return_value="aarch64"),
            mock.patch.object(environment.platform, "machine", return_value="aarch64"),
        ):
            self.assertIsNone(run_environment()["cpu_model"])

    def test_cpuinfo_gives_model_and_physical_cores(self):
        text = (
            "processor\t: 0\nmodel name\t: Test CPU @ 3GHz\nphysical id\t: 0\ncore id\t\t: 0\n\n"
            "processor\t: 1\nmodel name\t: Test CPU @ 3GHz\nphysical id\t: 0\ncore id\t\t: 0\n\n"  # hyper-thread
            "processor\t: 2\nmodel name\t: Test CPU @ 3GHz\nphysical id\t: 0\ncore id\t\t: 1\n"
        )
        with (
            mock.patch.object(environment, "CPUINFO", mock.Mock(read_text=mock.Mock(return_value=text))),
            mock.patch.object(environment.platform, "system", return_value="Linux"),
        ):
            facts = run_environment()
        self.assertEqual(facts["cpu_model"], "Test CPU @ 3GHz")
        self.assertEqual(facts["cpu_physical_cores"], 2)

    def git_facts_for(self, status_output):
        """Commit and dirty flag read from this `git status --porcelain=v2 --branch` output, and the git commands run."""

        commands = []

        def fake_run(cmd, **_):
            commands.append(cmd)
            return mock.Mock(returncode=0, stdout=status_output)

        with (
            mock.patch.object(environment, "_has_git_checkout", return_value=True),
            mock.patch.object(environment.subprocess, "run", side_effect=fake_run),
        ):
            facts = run_environment(machine={})
        return facts["git_commit"], facts["git_dirty"], commands

    def test_git_facts_come_from_one_git_command(self):
        # Every job runs this, so one subprocess instead of two (A39).
        head = "# branch.oid abc1234def5678abc1234def5678abc1234def56\n# branch.head main\n"
        commit, dirty, commands = self.git_facts_for(head + "1 .M N... 100644 100644 100644 aaa bbb file.py\n")
        self.assertEqual((commit, dirty), ("abc1234", True))
        self.assertEqual(len(commands), 1)
        self.assertEqual(self.git_facts_for(head)[:2], ("abc1234", False))
        self.assertEqual(self.git_facts_for(head + "? new_file.py\n")[:2], ("abc1234", True))
        # A repository without a commit yet.
        self.assertEqual(self.git_facts_for("# branch.oid (initial)\n# branch.head main\n")[:2], (None, None))

    def test_given_machine_facts_are_used_without_reading_the_machine(self):
        # The server reads them once and hands them to each job (A39).
        given = {"os": "Given OS", "cpu_model": "Given CPU", "cpu_logical_cores": 3, "cpu_physical_cores": None, "ram_total_gb": 1.5}
        with (
            mock.patch.object(environment, "_cpu_model", side_effect=AssertionError("CPU read")),
            mock.patch.object(environment, "_ram_total_gb", side_effect=AssertionError("RAM read")),
        ):
            facts = run_environment(machine=given)
        self.assertEqual(set(facts), KEYS)
        self.assertEqual({key: facts[key] for key in given}, given)
        self.assertEqual(facts["python_implementation"], environment.platform.python_implementation())

    def test_the_solver_interpreter_replaces_this_processs_interpreter(self):
        # With WIZSAT_SOLVER_PYTHON set, the solvers run in a child of that
        # interpreter, so a job records its name and version (RUNNER-6).
        given = {"os": "Given OS", "cpu_model": "Given CPU", "cpu_logical_cores": 3, "cpu_physical_cores": None, "ram_total_gb": 1.5}
        with tempfile.TemporaryDirectory() as folder:
            facts = run_environment(machine=given, solver_python=write_fake_python(folder, "PyPy", "3.10.14"))
        self.assertEqual(set(facts), KEYS)
        self.assertEqual((facts["python_implementation"], facts["python_version"]), ("PyPy", "3.10.14"))
        self.assertEqual({key: facts[key] for key in given}, given)

    def test_the_probe_reads_a_real_interpreter(self):
        facts = environment.interpreter_facts(sys.executable)
        self.assertEqual(
            facts, {"python_implementation": platform.python_implementation(), "python_version": platform.python_version()}
        )

    def test_output_around_the_answer_does_not_hide_it(self):
        # A sitecustomize or atexit hook of that interpreter may print too.
        printed = 'site hook\n{"a": "b"}\n["PyPy", "3.10.14"]\nbye\n'
        with mock.patch.object(environment.subprocess, "run", return_value=mock.Mock(returncode=0, stdout=printed)) as run:
            facts = environment.interpreter_facts("pypy3")
        self.assertEqual(facts, {"python_implementation": "PyPy", "python_version": "3.10.14"})
        self.assertEqual(run.call_args.kwargs["stdin"], environment.subprocess.DEVNULL)
        self.assertEqual(run.call_args.kwargs["cwd"], environment.REPO_ROOT)

    def test_an_interpreter_that_cannot_answer_is_unknown_not_this_one(self):
        # Reporting this process's interpreter instead would label the runs
        # with the wrong one, which is what the record is there to prevent.
        with tempfile.TemporaryDirectory() as folder:
            missing = str(Path(folder, "no-such-python"))
            for python in (missing, write_fake_python(folder, line="Python 3.10")):
                with self.subTest(python=python):
                    facts = environment.interpreter_facts(python)
                    self.assertEqual(facts, {"python_implementation": "unknown", "python_version": ""})

    def test_git_status_takes_no_lock_on_the_index(self):
        # Every job asks, so a plain "git status" would hold .git/index.lock while
        # the owner commits (found by the review of META-2).
        commands = []

        def fake_run(cmd, **_):
            commands.append(cmd)
            return mock.Mock(returncode=0, stdout="abc1234\n" if "rev-parse" in cmd else "")

        with (
            mock.patch.object(environment, "_has_git_checkout", return_value=True),
            mock.patch.object(environment.subprocess, "run", side_effect=fake_run),
        ):
            run_environment()
        status = next(cmd for cmd in commands if "status" in cmd)
        self.assertLess(status.index("--no-optional-locks"), status.index("status"))

    def test_outside_a_git_checkout_git_is_not_asked(self):
        with (
            mock.patch.object(environment, "_has_git_checkout", return_value=False),
            mock.patch.object(environment.subprocess, "run", side_effect=AssertionError("git was run")),
        ):
            facts = run_environment()
        self.assertIsNone(facts["git_commit"])
        self.assertIsNone(facts["git_dirty"])


if __name__ == "__main__":
    unittest.main()
