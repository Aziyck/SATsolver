"""run_environment(): the machine and software facts recorded with every run."""

import json
import unittest
from pathlib import Path
from unittest import mock

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
        environment._collect.cache_clear()
        self.addCleanup(environment._collect.cache_clear)

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

    def test_git_facts_come_from_git_output(self):
        def fake_run(cmd, **_):
            out = "abc1234\n" if "rev-parse" in cmd else " M file.py\n"
            return mock.Mock(returncode=0, stdout=out)

        with (
            mock.patch.object(environment, "_has_git_checkout", return_value=True),
            mock.patch.object(environment.subprocess, "run", side_effect=fake_run),
        ):
            facts = run_environment()
        self.assertEqual(facts["git_commit"], "abc1234")
        self.assertIs(facts["git_dirty"], True)

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
