from __future__ import annotations

import sys
import unittest
from pathlib import Path

from components.second_stage import run_gain_gmro_test, run_load_drive_test, run_swing_test
from tests.structural._helpers import init_sky130_install
from tests.structural.second_stage.specs_second_stage import (
    OUTPUT_CURRENT_ABS_MIN_UA,
    OUTPUT_SWING_HIGH_MIN,
    OUTPUT_SWING_LOW_MAX,
)


ROOT = Path(__file__).resolve().parents[3]


class TestSecondStageBudgetDriveAndCharacterization(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(ROOT))
        init_sky130_install()

    def test_second_stage__budget__drive_and_gain(self) -> None:
        swing = run_swing_test()
        drive = run_load_drive_test()
        gain_char = run_gain_gmro_test()

        self.assertEqual(swing["component"], "second_stage")
        self.assertEqual(drive["component"], "second_stage")
        self.assertEqual(gain_char["component"], "second_stage")
        self.assertEqual(swing["category"], "contract")
        self.assertEqual(drive["category"], "char")
        self.assertEqual(gain_char["category"], "char")

        self.assertIn("gain_est", gain_char["metrics"])
        self.assertIn("vbias_dc", gain_char["metrics"])
        self.assertIn("vout_dc", gain_char["metrics"])

        self.assertLessEqual(
            swing["metrics"]["output_swing_low"],
            OUTPUT_SWING_LOW_MAX,
            "Spec requires compliant low swing <= 0.1 V at nominal supply",
        )
        self.assertGreaterEqual(
            swing["metrics"]["output_swing_high"],
            OUTPUT_SWING_HIGH_MIN,
            "Spec requires compliant high swing >= VDD - 0.1 V at nominal supply",
        )
        self.assertGreaterEqual(
            abs(1e6 * drive["metrics"]["source_current"]),
            OUTPUT_CURRENT_ABS_MIN_UA,
            "Spec requires at least +25 uA output source capability",
        )
        self.assertGreaterEqual(
            abs(1e6 * drive["metrics"]["sink_current"]),
            OUTPUT_CURRENT_ABS_MIN_UA,
            "Spec requires at least -25 uA output sink capability",
        )


if __name__ == "__main__":
    unittest.main()
