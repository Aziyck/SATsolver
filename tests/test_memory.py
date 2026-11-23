"""peak_memory_mb(): the peak memory of this process, on every platform (MEM-1)."""

import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from sat_core import memory
from sat_core.memory import peak_memory_mb

ROOT = Path(__file__).resolve().parents[1]

# A child that allocates 50 MB and touches every page, so the resident size really grows.
GROWTH = """
from sat_core.memory import peak_memory_mb
before = peak_memory_mb()
block = bytearray(50 * 1024 * 1024)
for i in range(0, len(block), 4096):
    block[i] = 1
print(before, peak_memory_mb())
"""


def in_fresh_process(code: str) -> list[float]:
    """The numbers `code` prints, run in a new interpreter: the peak never falls, so this test
    process's peak would carry every earlier test's."""

    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60, check=True, cwd=ROOT)
    return [float(value) for value in out.stdout.split()]


class PeakMemoryTests(unittest.TestCase):
    def test_a_positive_number_of_megabytes(self):
        self.assertIsInstance(peak_memory_mb(), float)
        (peak,) = in_fresh_process("from sat_core.memory import peak_memory_mb; print(peak_memory_mb())")
        # A bare interpreter is a few to tens of MB; 1 GB would mean a wrong unit.
        self.assertTrue(1 < peak < 1000, peak)

    def test_the_peak_grows_by_the_size_of_a_50_mb_allocation(self):
        # Started from a process that has used 150 MB: on Linux, getrusage's ru_maxrss
        # carries the parent's peak into the child, which would hide the growth (MEM-1).
        # Not on macOS: whether its ru_maxrss inherits too is unmeasured (memory plan, MEM-1).
        parent_peak = bytearray(0 if sys.platform == "darwin" else 150 * 1024 * 1024)
        for i in range(0, len(parent_peak), 4096):
            parent_peak[i] = 1
        before, after = in_fresh_process(GROWTH)
        del parent_peak
        self.assertTrue(40 < after - before < 80, (before, after))

    @unittest.skipIf(sys.platform == "win32", "the resource module does not exist on Windows")
    def test_linux_counts_kilobytes_and_macos_bytes(self):
        usage = mock.Mock(ru_maxrss=51200)
        with mock.patch("resource.getrusage", return_value=usage):
            self.assertEqual(memory._posix_peak_bytes("linux") / 1024**2, 50.0)
        usage = mock.Mock(ru_maxrss=50 * 1024**2)
        with mock.patch("resource.getrusage", return_value=usage):
            self.assertEqual(memory._posix_peak_bytes("darwin") / 1024**2, 50.0)

    def test_linux_reads_vmhwm_in_kilobytes(self):
        status = mock.Mock(read_text=mock.Mock(return_value="Name:\tpython\nVmPeak:\t 999999 kB\nVmHWM:\t   51200 kB\n"))
        with mock.patch.object(memory, "PROC_STATUS", status):
            self.assertEqual(memory._linux_peak_bytes() / 1024**2, 50.0)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux reads /proc")
    def test_linux_without_proc_falls_back_to_getrusage(self):
        with (
            mock.patch.object(memory, "PROC_STATUS", Path("/nonexistent/status")),
            mock.patch("resource.getrusage", return_value=mock.Mock(ru_maxrss=51200)),
        ):
            self.assertEqual(peak_memory_mb(), 50.0)

    @unittest.skipIf(sys.platform == "win32", "the resource module does not exist on Windows")
    def test_a_failing_platform_call_gives_none_not_an_exception(self):
        with (
            mock.patch.object(memory, "PROC_STATUS", Path("/nonexistent/status")),
            mock.patch("resource.getrusage", side_effect=OSError("denied")),
        ):
            self.assertIsNone(peak_memory_mb())

    @unittest.skipUnless(sys.platform == "win32", "the Windows call")
    def test_a_failing_windows_call_gives_none_not_an_exception(self):
        import ctypes

        with mock.patch.object(ctypes, "WinDLL", side_effect=OSError("psapi missing")):
            self.assertIsNone(peak_memory_mb())

    def test_an_unreadable_value_gives_none(self):
        for bad in (RuntimeError("boom"), 0, -5):
            with self.subTest(bad=bad):
                patch = mock.patch.object(memory, "_peak_bytes", **({"side_effect": bad} if isinstance(bad, Exception) else {"return_value": bad}))
                with patch:
                    self.assertIsNone(peak_memory_mb())


if __name__ == "__main__":
    unittest.main()
