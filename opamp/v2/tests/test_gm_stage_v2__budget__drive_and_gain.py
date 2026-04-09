from __future__ import annotations

import unittest

from opamp.v2.gm_stage import run_gain_gmro_test, run_load_drive_test, run_swing_test
from opamp.v2.tests._helpers import BaseV2SimTest
from opamp.v2.tests.specs_gm_stage_v2 import (
    OUTPUT_CURRENT_ABS_MIN_UA,
    OUTPUT_SWING_HIGH_MAX,
    OUTPUT_SWING_LOW_MIN,
    OUTPUT_SWING_SPAN_MIN,
)


class TestGmStageV2BudgetDriveAndGain(BaseV2SimTest):
    def test_gm_stage_v2__budget__drive_and_gain(self) -> None:
        swing = run_swing_test()
        drive = run_load_drive_test()
        gain = run_gain_gmro_test()

        self.assertEqual(swing["component"], "second_stage")
        self.assertEqual(drive["component"], "second_stage")
        self.assertEqual(gain["component"], "second_stage")
        self.assertGreaterEqual(swing["metrics"]["output_swing_low"], OUTPUT_SWING_LOW_MIN)
        self.assertLessEqual(swing["metrics"]["output_swing_high"], OUTPUT_SWING_HIGH_MAX)
        self.assertGreaterEqual(
            abs(swing["metrics"]["output_swing_high"] - swing["metrics"]["output_swing_low"]),
            OUTPUT_SWING_SPAN_MIN,
        )
        self.assertGreaterEqual(1e6 * drive["metrics"]["source_current"], OUTPUT_CURRENT_ABS_MIN_UA)
        self.assertGreaterEqual(1e6 * drive["metrics"]["sink_current"], OUTPUT_CURRENT_ABS_MIN_UA)
        self.assertFinite(gain["metrics"]["gain_est"])


if __name__ == "__main__":
    unittest.main()
