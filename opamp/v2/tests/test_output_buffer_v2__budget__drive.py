from __future__ import annotations

import unittest

from opamp.v2.output_buffer import run_load_drive_test, run_swing_test
from opamp.v2.tests._helpers import BaseV2SimTest
from opamp.v2.tests.specs_output_buffer_v2 import OUTPUT_CURRENT_ABS_MIN_UA, OUTPUT_SWING_HIGH_MIN, OUTPUT_SWING_LOW_MAX


@unittest.skip("Legacy experimental block: output_buffer is no longer part of the active v2 architecture.")
class TestOutputBufferV2BudgetDrive(BaseV2SimTest):
    def test_output_buffer_v2__budget__drive(self) -> None:
        swing = run_swing_test()
        drive = run_load_drive_test()

        self.assertEqual(swing["component"], "output_stage")
        self.assertEqual(drive["component"], "output_stage")
        self.assertLessEqual(swing["metrics"]["output_swing_low"], OUTPUT_SWING_LOW_MAX)
        self.assertGreaterEqual(swing["metrics"]["output_swing_high"], OUTPUT_SWING_HIGH_MIN)
        self.assertGreaterEqual(1e6 * drive["metrics"]["source_current"], OUTPUT_CURRENT_ABS_MIN_UA)
        self.assertGreaterEqual(1e6 * drive["metrics"]["sink_current"], OUTPUT_CURRENT_ABS_MIN_UA)


if __name__ == "__main__":
    unittest.main()
