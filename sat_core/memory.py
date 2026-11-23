"""
Peak memory of this process, from the standard library only (MEM-1).

The peak is the highest the process has been, so it only ever grows: read it in
a process that runs one solver run (docs/plans/memory-measurement.md).
"""

import sys
from pathlib import Path

PROC_STATUS = Path("/proc/self/status")


def _linux_peak_bytes() -> int:
    # VmHWM is the high-water mark of this process alone. ru_maxrss is not: on
    # Linux a child started by subprocess reports its parent's peak in it
    # (measured: a child of a 316 MB process read 316 MB after its own 50 MB).
    for line in PROC_STATUS.read_text().splitlines():
        if line.startswith("VmHWM:"):
            return int(line.split()[1]) * 1024  # "VmHWM:   12345 kB"
    raise ValueError("no VmHWM line")


def _posix_peak_bytes(platform_name: str = sys.platform) -> int:
    import resource  # POSIX only

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # The same field is bytes on macOS and kilobytes on Linux and the BSDs.
    return peak if platform_name == "darwin" else peak * 1024


def _windows_peak_bytes() -> int:
    import ctypes
    from ctypes import wintypes

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    # Without argtypes the process handle is cut to 32 bits on 64-bit Windows.
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessMemoryCounters), wintypes.DWORD]
    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return counters.PeakWorkingSetSize


def _peak_bytes() -> int:
    if sys.platform == "win32":
        return _windows_peak_bytes()
    if sys.platform.startswith("linux"):
        try:
            return _linux_peak_bytes()
        except (OSError, ValueError):
            pass  # no /proc (some containers): the inherited-peak caveat applies
    return _posix_peak_bytes()


def peak_memory_mb() -> float | None:
    """The highest memory this process has used, in MiB (1024**2 bytes, as ram_total_gb uses 1024**3);
    None where the platform cannot say. The stats keep the plan's names (`peak_memory_mb`)."""

    try:
        peak = _peak_bytes()
    except Exception:
        return None
    return peak / 1024**2 if peak > 0 else None
