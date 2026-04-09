from __future__ import annotations

import unittest

from opamp.v3.autonomous_az_followup_batches import build_batches as build_az_followup_batches
from opamp.v3.autonomous_core_followup_batches import build_batches as build_core_followup_batches


class AutonomousFollowupBatchSmokeTest(unittest.TestCase):
    def test_core_followup_batches_exist(self) -> None:
        batches = build_core_followup_batches()
        self.assertIn("stability_repair", batches)
        self.assertIn("mixed_repair", batches)
        self.assertGreaterEqual(len(batches["stability_repair"]), 4)

    def test_az_followup_batches_exist(self) -> None:
        batches = build_az_followup_batches()
        self.assertIn("combo_frontier", batches)
        self.assertIn("finish_frontier", batches)
        self.assertGreaterEqual(len(batches["combo_frontier"]), 4)
