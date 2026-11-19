"""
The machine and software a run happens on, from the standard library only.

Meant to be called inside the process that runs the solver, so it reports PyPy
when PyPy runs the job. Every lookup is wrapped: a fact that cannot be found is
None, never an error (docs/plans/run-metadata.md).
"""

import functools
import os
import platform
import subprocess
import sys
from pathlib import Path

VERSION = "2.0.0"

CPUINFO = Path("/proc/cpuinfo")
# Memory limit of the container, cgroup v2 then v1. "max" (v2) or a number near
# 2**63 (v1) means no limit; taking the smaller of limit and host RAM drops both.
CGROUP_MEMORY_FILES = (
    Path("/sys/fs/cgroup/memory.max"),
    Path("/sys/fs/cgroup/memory/memory.limit_in_bytes"),
)
REPO_ROOT = Path(__file__).resolve().parents[1]
SUBPROCESS_TIMEOUT_SECONDS = 5


def _first(*lookups):
    """The first lookup that gives a non-empty value; a lookup that raises counts as empty."""

    for lookup in lookups:
        try:
            value = lookup()
        except Exception:
            continue
        if value:
            return value
    return None


def _cpuinfo_blocks() -> list[dict[str, str]]:
    """One dict per logical processor of /proc/cpuinfo (Linux)."""

    blocks = []
    for chunk in CPUINFO.read_text(encoding="utf-8", errors="replace").split("\n\n"):
        fields = {}
        for line in chunk.splitlines():
            key, sep, value = line.partition(":")
            if sep:
                fields[key.strip()] = value.strip()
        if fields:
            blocks.append(fields)
    return blocks


def _cpu_model() -> str | None:
    def linux():
        return next(b["model name"] for b in _cpuinfo_blocks() if "model name" in b)

    def macos():
        out = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT_SECONDS
        )
        return out.stdout.strip() if out.returncode == 0 else None

    def windows():
        import winreg  # only exists on Windows

        key = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as handle:
            return winreg.QueryValueEx(handle, "ProcessorNameString")[0].strip()

    def processor():
        # On Linux/ARM this is often just the architecture name, which is not a model.
        name = platform.processor()
        return None if name == platform.machine() else name

    by_system = {"Linux": linux, "Darwin": macos, "Windows": windows}
    return _first(by_system.get(platform.system(), lambda: None), processor)


def _cpu_physical_cores() -> int | None:
    """Linux only: distinct (physical id, core id) pairs. None where the file lacks them."""

    try:
        pairs = {
            (b["physical id"], b["core id"]) for b in _cpuinfo_blocks() if "physical id" in b and "core id" in b
        }
    except Exception:
        return None
    return len(pairs) or None


def _host_ram_bytes() -> int | None:
    def posix():
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")

    def macos():
        # sysconf has no SC_PHYS_PAGES on macOS.
        out = subprocess.run(
            ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT_SECONDS
        )
        return int(out.stdout) if out.returncode == 0 else None

    def windows():
        import ctypes

        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(MemoryStatus)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return status.ullTotalPhys

    return _first(windows) if sys.platform == "win32" else _first(posix, macos)


def _cgroup_limit_bytes() -> int | None:
    limits = []
    for path in CGROUP_MEMORY_FILES:
        try:
            limits.append(int(path.read_text().strip()))
        except (OSError, ValueError):
            continue
    return min(limits, default=None)


def _ram_total_gb() -> float | None:
    """RAM the run can use: the host's, or the container's limit when that is smaller."""

    total = min(filter(None, (_host_ram_bytes(), _cgroup_limit_bytes())), default=None)
    return round(total / 1024**3, 1) if total else None


def _has_git_checkout() -> bool:
    # A bare "git" call would find a repository around an installed copy of the
    # project and report that repository's commit.
    return (REPO_ROOT / ".git").exists()


def _git(*args: str) -> str | None:
    """Output of a git command in the project folder; None if git is missing or fails."""

    if not _has_git_checkout():
        return None
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT_SECONDS
        )
    except Exception:
        return None
    return out.stdout if out.returncode == 0 else None


def _git_dirty() -> bool | None:
    status = _git("status", "--porcelain")
    return None if status is None else bool(status.strip())


@functools.cache
def _collect() -> dict:
    commit = _git("rev-parse", "--short", "HEAD")
    return {
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "os": _first(lambda: f"{platform.system()} {platform.release()} ({platform.machine()})"),
        "cpu_model": _cpu_model(),
        "cpu_logical_cores": os.cpu_count(),
        "cpu_physical_cores": _cpu_physical_cores(),
        "ram_total_gb": _ram_total_gb(),
        "wizsat_version": VERSION,
        "git_commit": commit.strip() if commit else None,
        "git_dirty": _git_dirty() if commit else None,
    }


def run_environment() -> dict:
    """The facts above as a JSON-ready dict. Computed once per process; the caller gets a copy."""

    return dict(_collect())
