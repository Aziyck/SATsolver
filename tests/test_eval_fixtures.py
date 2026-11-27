"""The do-item evals share one fixture script, copied into each case.

`claude plugin eval` runs a case's scaffold only from inside its folder, so
every case holds a copy of `.claude/skills/do-item/evals/_fixture/world.sh`.
This test fails when a copy has drifted from the source.
"""

import unittest
from pathlib import Path

EVALS = Path(__file__).resolve().parents[1] / ".claude" / "skills" / "do-item" / "evals"


class EvalFixtureCopiesTests(unittest.TestCase):
    def test_every_case_holds_the_same_fixture(self):
        source = (EVALS / "_fixture" / "world.sh").read_bytes()
        cases = [p for p in EVALS.iterdir() if (p / "case.yaml").exists()]
        self.assertGreaterEqual(len(cases), 6)
        for case in cases:
            with self.subTest(case=case.name):
                copy = case / "world.sh"
                self.assertTrue(copy.exists(), f"{copy} is missing")
                data = copy.read_bytes()
                # bash stops at "set -euo pipefail\r"; .gitattributes keeps *.sh LF.
                self.assertNotIn(b"\r", data, f"{copy} has CRLF line endings")
                self.assertEqual(
                    data, source, f"{copy} differs from _fixture/world.sh; copy it again"
                )
                self.assertIn("scaffold_script: world.sh", (case / "case.yaml").read_text())


if __name__ == "__main__":
    unittest.main()
