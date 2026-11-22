"""A stand-in for a second interpreter, such as PyPy, for tests that need one (RUNNER-6).

The script ignores its arguments and prints one line: the JSON list
[implementation, version] that sat_core.environment's interpreter probe
expects. It runs no solver: a run started with it ends as ERROR.
"""

import os
import stat
import sys
from pathlib import Path


def write_fake_python(folder: str, implementation: str = "PyPy", version: str = "3.10.14", line: str | None = None) -> str:
    """Write the script into `folder`; return the path to set as WIZSAT_SOLVER_PYTHON.

    `line` replaces the whole output line (an answer the probe cannot read).
    """

    if line is None:
        line = f'["{implementation}", "{version}"]'
    if sys.platform == "win32":
        # CreateProcess runs a .cmd file through cmd.exe, so Popen can start it.
        path = Path(folder, "fake-python.cmd")
        path.write_text(f"@echo {line}\r\n", encoding="ascii")
    else:
        path = Path(folder, "fake-python")
        path.write_text(f"#!/bin/sh\necho '{line}'\n", encoding="ascii")
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return os.fspath(path)
