"""
Which processes run, for tests that check a process ended (RUNNER-5).

A solver child is a grandchild of the test (server -> job -> child), or a
great-grandchild under a worker pool, so the test holds no Popen for it: it
finds the child in the system's process table and holds it from then on.
"""

import os
import signal
import subprocess
import sys
import time

SOLVER_CHILD_MODULE = "sat_core.solver_process"
# Taken at import: a test may patch subprocess.Popen to start another child
# program (child_process_spy), and the lookups below must still run.
REAL_POPEN = subprocess.Popen


def _output(command):
    with REAL_POPEN(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, errors="replace") as process:
        output, _ = process.communicate(timeout=60)
    return output


def process_table():
    """Every process as (pid, parent pid, command line)."""

    if sys.platform == "win32":
        script = (
            "Get-CimInstance Win32_Process | ForEach-Object "
            "{ '{0} {1} {2}' -f $_.ProcessId, $_.ParentProcessId, $_.CommandLine }"
        )
        command = ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]
    else:
        command = ["ps", "-A", "-o", "pid=", "-o", "ppid=", "-o", "args="]
    output = _output(command)
    table = []
    for line in output.splitlines():
        parts = line.split(None, 2)
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            table.append((int(parts[0]), int(parts[1]), parts[2] if len(parts) == 3 else ""))
    return table


def solver_children_of(pid):
    """Pids of the solver children among the descendants of `pid`."""

    table = process_table()
    children = {}
    for child, parent, _ in table:
        children.setdefault(parent, []).append(child)
    command_lines = {child: command for child, _, command in table}
    found, todo = set(), [pid]
    while todo:
        for child in children.get(todo.pop(), []):
            # Windows keeps a dead parent's pid as ParentProcessId, and pids are
            # reused: a process seen twice is not walked again.
            if child not in found and child != pid:
                found.add(child)
                todo.append(child)
    return {child for child in found if SOLVER_CHILD_MODULE in command_lines.get(child, "")}


class HeldProcess:
    """
    A process the test did not start, held from the moment it was found.

    On Windows an open handle keeps the pid from being given to another
    process, so a check or a kill later reaches this process and no other.
    POSIX hands out pids in order, so one is reused only after the counter
    wraps, far beyond a test's few seconds.
    """

    def __init__(self, pid):
        self.pid = pid
        self._handle = None
        if sys.platform == "win32":
            kernel32 = _kernel32()
            synchronize, terminate, query_limited_information = 0x00100000, 0x0001, 0x1000
            self._handle = kernel32.OpenProcess(synchronize | terminate | query_limited_information, False, pid)

    def __repr__(self):
        return f"HeldProcess({self.pid})"

    def is_running(self):
        if sys.platform == "win32":
            if not self._handle:
                return False
            import ctypes
            from ctypes import wintypes

            code, still_active = wintypes.DWORD(), 259
            return bool(_kernel32().GetExitCodeProcess(self._handle, ctypes.byref(code))) and code.value == still_active
        try:
            os.kill(self.pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        # A zombie has ended; it waits only for a parent to collect it (a
        # container without an init process may never do that).
        state = _output(["ps", "-o", "stat=", "-p", str(self.pid)]).strip()
        return bool(state) and not state.startswith("Z")

    def release(self):
        """Kill the process if it still runs (a test that failed), then let go of it."""

        if self.is_running():
            if sys.platform == "win32":
                _kernel32().TerminateProcess(self._handle, 1)
            else:
                try:
                    os.kill(self.pid, signal.SIGKILL)
                except OSError:
                    pass
        if self._handle:
            _kernel32().CloseHandle(self._handle)
            self._handle = None


def hold(test, pids):
    """HeldProcess for each pid, released (killed if still running) when `test` ends."""

    held = [HeldProcess(pid) for pid in pids]
    for process in held:
        test.addCleanup(process.release)
    return held


def wait_for_solver_children(test, pid, count=1, timeout=30):
    """Hold the solver children under `pid` once at least `count` of them run; an empty list if they do not."""

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        children = solver_children_of(pid)
        if len(children) >= count:
            return hold(test, children)
        time.sleep(0.2)
    return []


def wait_until_ended(processes, timeout=10):
    """The pids of the held processes still running after `timeout` seconds."""

    deadline = time.monotonic() + timeout
    running = list(processes)
    while running and time.monotonic() < deadline:
        running = [process for process in running if process.is_running()]
        if running:
            time.sleep(0.2)
    return {process.pid for process in running}


def _kernel32():
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel32.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    return kernel32
