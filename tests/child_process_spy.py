"""
Run a given program in place of the solver child (sat_core/solver_process.py).

Tests that need the child to misbehave (print a broken line, sleep, raise)
call replace_child_program(): the runner starts its child as usual, but
the process that starts is the program the test names.
"""

import subprocess
import sys
from unittest import mock

# Taken at import, before any test patches it: a patch started in a subtest
# would otherwise be taken for the real class, and the patches would stack
# (every later run would start the first program).
REAL_POPEN = subprocess.Popen


def replace_child_program(test, script=None, command=None):
    """
    From now until the end of `test`, children start `script` or `command`.

    script is run as `python -c script` with this interpreter; command is a
    whole command line. With neither, the real child starts and is only
    recorded. Returns the list of children started so far (it grows). Every
    child still running when the test ends is killed.
    """

    children = []

    def popen(args, **kwargs):
        if script is not None:
            args = [sys.executable, "-c", script]
        elif command is not None:
            args = command
        child = REAL_POPEN(args, **kwargs)
        children.append(child)
        return child

    def kill_survivors():
        for child in children:
            if child.poll() is None:
                child.kill()
                child.wait()

    patcher = mock.patch("subprocess.Popen", side_effect=popen)
    patcher.start()
    # Cleanups run last in, first out: the patch is removed before the kill.
    test.addCleanup(kill_survivors)
    test.addCleanup(patcher.stop)
    return children
