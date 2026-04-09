from __future__ import annotations

import unittest

from opamp.v3.autonomous_az_mismatch_repair_batches import build_cases


class TestV3SmokeAutonomousAzMismatchRepairBatches(unittest.TestCase):
    def test_cases_exist_and_are_unique(self) -> None:
        cases = build_cases()
        names = [case.name for case in cases]
        self.assertEqual(len(names), len(set(names)))
        self.assertIn("repair_baseline", names)
        self.assertIn("m4r2_cap300_wswn1p2_wswp1p8_nf2", names)
        self.assertGreaterEqual(len(cases), 7)


if __name__ == "__main__":
    unittest.main()
