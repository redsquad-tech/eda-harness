from __future__ import annotations

import unittest

from opamp.v3.autonomous_az_mismatch_batches import build_cases


class TestV3SmokeAutonomousAzMismatchBatches(unittest.TestCase):
    def test_cases_exist_and_are_unique(self) -> None:
        cases = build_cases()
        names = [case.name for case in cases]
        self.assertEqual(len(names), len(set(names)))
        self.assertIn("baseline_cap200_shuntp10_rtop600_freq200k", names)
        self.assertIn("m4_cap300_big_switches", names)
        self.assertGreaterEqual(len(cases), 6)


if __name__ == "__main__":
    unittest.main()
