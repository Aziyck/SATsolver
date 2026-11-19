"""The cases of every preset, pinned.

The order of the cases sets every row index (case.index * solvers + position),
so stored benchmarks and the frontend depend on it. This test fails when a
change to case expansion reorders, relabels or reseeds any preset case. After a
deliberate change, rerun it with WIZSAT_RECORD_GOLDEN=1 to rewrite the file.
"""

import json
import os
import unittest
from pathlib import Path

from sat_core.benchmark import parse_request
from sat_core.presets import PRESETS

GOLDEN = Path(__file__).parent / "fixtures" / "preset_cases.jsonl"


def preset_case_lines() -> list[str]:
    lines = []
    for preset in PRESETS:
        for case in parse_request(preset.request).cases:
            lines.append(
                json.dumps(
                    [preset.key, case.index, case.problem, case.repeat, case.segment, case.label, case.params],
                    sort_keys=True,
                )
            )
    return lines


class PresetCaseTests(unittest.TestCase):
    def test_every_preset_case_matches_the_recorded_file(self):
        lines = preset_case_lines()
        if os.environ.get("WIZSAT_RECORD_GOLDEN") == "1":
            GOLDEN.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.assertEqual(lines, GOLDEN.read_text(encoding="utf-8").splitlines())


if __name__ == "__main__":
    unittest.main()
