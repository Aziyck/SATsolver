import subprocess
import sys
import unittest

from child_process_spy import replace_child_program


class ReplaceChildProgramTests(unittest.TestCase):
    def test_a_second_replacement_in_the_same_test_runs_its_own_program(self):
        # The bug this helper exists for: patches that stack ran the first program every time.
        inner = unittest.TestCase()
        for text in ("first", "second"):
            children = replace_child_program(inner, script=f"print({text!r})")
            child = subprocess.Popen(["ignored"], stdout=subprocess.PIPE, text=True)
            self.assertEqual(child.communicate()[0].strip(), text)
            self.assertEqual(children, [child])
        inner.doCleanups()

    def test_the_replacement_ends_with_the_test(self):
        inner = unittest.TestCase()
        replace_child_program(inner, script="pass")
        inner.doCleanups()

        child = subprocess.Popen([sys.executable, "-c", "print('real')"], stdout=subprocess.PIPE, text=True)
        self.assertEqual(child.communicate()[0].strip(), "real")

    def test_a_command_replaces_the_command_line(self):
        inner = unittest.TestCase()
        self.addCleanup(inner.doCleanups)
        replace_child_program(inner, command=[sys.executable, "-c", "print('from command')"])

        child = subprocess.Popen(["ignored"], stdout=subprocess.PIPE, text=True)
        self.assertEqual(child.communicate()[0].strip(), "from command")

    def test_without_a_program_the_real_command_runs_and_is_recorded(self):
        inner = unittest.TestCase()
        self.addCleanup(inner.doCleanups)
        children = replace_child_program(inner)

        child = subprocess.Popen([sys.executable, "-c", "print('as asked')"], stdout=subprocess.PIPE, text=True)
        self.assertEqual(child.communicate()[0].strip(), "as asked")
        self.assertEqual(children, [child])

    def test_a_child_still_running_at_the_end_is_killed(self):
        inner = unittest.TestCase()
        children = replace_child_program(inner, script="import time; time.sleep(60)")
        subprocess.Popen(["ignored"])
        self.assertIsNone(children[0].poll())

        inner.doCleanups()

        self.assertIsNotNone(children[0].poll())


if __name__ == "__main__":
    unittest.main()
