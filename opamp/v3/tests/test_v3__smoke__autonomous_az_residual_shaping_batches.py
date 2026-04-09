from __future__ import annotations

import unittest

from opamp.v3.autonomous_az_residual_shaping_batches import build_cases


class TestV3SmokeAutonomousAzResidualShapingBatches(unittest.TestCase):
    def test_cases_exist_and_are_unique(self) -> None:
        cases = build_cases()
        names = [case.name for case in cases]
        self.assertEqual(len(names), len(set(names)))
        self.assertIn("shape_baseline_m3r2", names)
        self.assertIn("shape_sym_10f", names)
        self.assertGreaterEqual(len(cases), 5)


if __name__ == "__main__":
    unittest.main()
