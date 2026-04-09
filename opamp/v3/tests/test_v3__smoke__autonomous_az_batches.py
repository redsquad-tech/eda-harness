from __future__ import annotations

import unittest

from opamp.v3.autonomous_az_batches import build_batches
from opamp.v3.tests._helpers import BaseV3Test


class TestV3SmokeAutonomousAzBatches(BaseV3Test):
    def test_batches_exist_and_have_unique_case_names_per_batch(self) -> None:
        batches = build_batches()
        self.assertIn("path_topology", batches)
        self.assertIn("cap_bank", batches)
        self.assertIn("timing_profiles", batches)
        self.assertIn("finish_rc", batches)
        for cases in batches.values():
            names = [case.name for case in cases]
            self.assertEqual(len(names), len(set(names)))
            self.assertIn("baseline", names)


if __name__ == "__main__":
    unittest.main()
