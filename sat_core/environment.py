"""
The machine and software a run happens on, from the standard library only.

run_environment() is meant to be called inside the process that runs the
solver, so it reports PyPy when PyPy runs the job. The machine facts (OS, CPU,
RAM) are the same for every process, so the server reads them once with
machine_facts() and passes them in (A39). Every lookup is wrapped: a fact that
cannot be found is None, never an error (docs/plans/done/run-metadata.md).

With WIZSAT_SOLVER_PYTHON set, the solvers run in a child of another
interpreter, and the job asks that interpreter for its name and version once
(interpreter_facts, RUNNER-6). The setting is read when a run starts, and a
job process's environment does not change while it runs, so every run of the
job uses that interpreter.
"""

import functools
import json
import os
import platform
import shutil
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
# A cold PyPy start on a busy machine (or the first start after an antivirus
# scan on Windows) can take seconds.
INTERPRETER_TIMEOUT_SECONDS = 15
# One line from the interpreter that is asked: ["PyPy", "3.10.14"].
INTERPRETER_PROBE = "import json, platform; print(json.dumps([platform.python_implementation(), platform.python_version()]))"
UNKNOWN_INTERPRETER = {"python_implementation": "unknown", "python_version": ""}
# The oldest PyPy the solvers run on (the repo needs Python 3.10), and the names looked up on PATH.
MIN_PYPY_VERSION = (3, 10)
PYPY_COMMANDS = ("pypy3", "pypy")


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


def _git_facts() -> tuple[str | None, bool | None]:
    """(short commit, dirty) from one git call: every job asks (A39)."""

    # --branch adds "# branch.oid <commit>" ahead of the changed files, which
    # "--porcelain=v2" lists one per line ("?" for an untracked one). Without
    # --no-optional-locks, status may take .git/index.lock to refresh the
    # index, and a commit made at the same moment fails.
    status = _git("--no-optional-locks", "status", "--porcelain=v2", "--branch")
    if status is None:
        return None, None
    lines = status.splitlines()
    oid = next((line.split()[2] for line in lines if line.startswith("# branch.oid ")), None)
    if oid is None or oid == "(initial)":
        return None, None
    # Seven characters, as `git rev-parse --short` gives in a repository this size.
    return oid[:7], any(line and not line.startswith("#") for line in lines)


@functools.cache
def _machine() -> dict:
    return {
        "os": _first(lambda: f"{platform.system()} {platform.release()} ({platform.machine()})"),
        "cpu_model": _cpu_model(),
        "cpu_logical_cores": os.cpu_count(),
        "cpu_physical_cores": _cpu_physical_cores(),
        "ram_total_gb": _ram_total_gb(),
    }


def machine_facts() -> dict:
    """OS, CPU and RAM: the facts that stay the same for every process on this machine.

    Computed once per process; the caller gets a copy. The server reads them
    once and passes them to each job, so a fresh worker does not read them again.
    """

    return dict(_machine())


def interpreter_facts(python: str | None = None) -> dict:
    """python_implementation and python_version of the interpreter `python` (a path or a command).

    Without `python`, this process's. The interpreter is started the way the
    solver child is (sat_core.solver_process.run_in_child: the same folder,
    the setting left out), so the one asked is the one that runs the solvers.
    An interpreter that cannot be started, does not answer within
    INTERPRETER_TIMEOUT_SECONDS or gives no readable answer is
    UNKNOWN_INTERPRETER, never this process's own: that would put the wrong
    interpreter on the runs.
    """

    if python is None:
        return {"python_implementation": platform.python_implementation(), "python_version": platform.python_version()}
    if os.path.dirname(python):
        # Resolved against our folder before the probe runs in REPO_ROOT, as run_in_child does.
        python = os.path.abspath(python)
    # The setting's name, written out: solver_registry is a layer above this module.
    env = {name: value for name, value in os.environ.items() if name != "WIZSAT_SOLVER_PYTHON"}
    try:
        out = subprocess.run(
            [python, "-c", INTERPRETER_PROBE],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=REPO_ROOT,
            env=env,
            timeout=INTERPRETER_TIMEOUT_SECONDS,
        )
    except Exception:
        return dict(UNKNOWN_INTERPRETER)
    if out.returncode != 0:
        return dict(UNKNOWN_INTERPRETER)
    # The first line that is the answer: a site hook may print around it.
    for line in out.stdout.splitlines():
        try:
            answer = json.loads(line)
        except ValueError:
            continue
        if isinstance(answer, list) and len(answer) == 2 and all(isinstance(fact, str) for fact in answer) and answer[0]:
            return {"python_implementation": answer[0], "python_version": answer[1]}
    return dict(UNKNOWN_INTERPRETER)


def find_pypy() -> dict | None:
    """The PyPy the app can run solvers in, as {"path", "version"}, or None (INTERP-1).

    WIZSAT_SOLVER_PYTHON when set, otherwise the first of pypy3 and pypy on
    PATH. A candidate counts only when it answers PyPy with Python 3.10 or
    newer. A setting that is set but not usable gives None, not a PyPy found
    on PATH: the setting is the owner's choice, and a wrong one must show.
    The path stays on the server; callers that talk to the browser report
    only availability and version.
    """

    # The setting's name, written out: solver_registry is a layer above this module.
    setting = os.environ.get("WIZSAT_SOLVER_PYTHON", "").strip()
    if setting:
        candidates = [setting]
    else:
        candidates, seen = [], set()
        for path in filter(None, (_on_path(command) for command in PYPY_COMMANDS)):
            # pypy is often a link to pypy3: probe one interpreter once.
            if os.path.realpath(path) not in seen:
                seen.add(os.path.realpath(path))
                candidates.append(path)
    for path in candidates:
        facts = interpreter_facts(path)
        version = _version_tuple(facts["python_version"])
        if facts["python_implementation"] == "PyPy" and version is not None and version >= MIN_PYPY_VERSION:
            return {"path": path, "version": facts["python_version"]}
    return None


def _on_path(command: str) -> str | None:
    """`command` in the folders of PATH, never in the current folder.

    shutil.which on Windows also searches the current folder first, so a
    pypy3.cmd left in the folder the server starts from would be run as PyPy.
    """

    for folder in os.environ.get("PATH", "").split(os.pathsep):
        if not folder or not os.path.isabs(folder):
            continue
        found = shutil.which(command, path=folder)
        if found and os.path.dirname(os.path.abspath(found)) == os.path.abspath(folder):
            return found
    return None


def _version_tuple(text: str) -> tuple[int, int] | None:
    """(major, minor) of "3.12.15", or None when the text does not start with two numbers."""

    parts = text.split(".")
    try:
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return None


def run_environment(machine: dict | None = None, solver_python: str | None = None) -> dict:
    """Every fact above as a JSON-ready dict.

    `machine` is what machine_facts() returned, possibly in another process;
    without it this process reads them. The interpreter facts come from this
    process, so they name the interpreter that runs the job, or, with
    `solver_python` (the WIZSAT_SOLVER_PYTHON setting), from the interpreter
    that runs its solvers. Git is asked on every call: a worker imports the
    code from disk when it starts, so a solver edited while the server runs
    has to show up as a dirty tree.
    """

    machine = machine_facts() if machine is None else machine
    commit, dirty = _git_facts()
    return {
        **interpreter_facts(solver_python),
        "os": machine.get("os"),
        "cpu_model": machine.get("cpu_model"),
        "cpu_logical_cores": machine.get("cpu_logical_cores"),
        "cpu_physical_cores": machine.get("cpu_physical_cores"),
        "ram_total_gb": machine.get("ram_total_gb"),
        "wizsat_version": VERSION,
        "git_commit": commit,
        "git_dirty": dirty,
    }
