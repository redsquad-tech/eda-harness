from __future__ import annotations

import sys
import unittest
from pathlib import Path

from components.opamp_core import (
    run_disabled_leakage_test,
    run_output_drive_test,
    run_output_swing_test,
)
from tests.structural._helpers import init_sky130_install
from tests.structural.opamp_core.specs_opamp_core import (
    DISABLED_LEAKAGE_NA_MAX,
    OUTPUT_CURRENT_ABS_MIN_UA,
    OUTPUT_SWING_HIGH_MIN,
    OUTPUT_SWING_LOW_MAX,
)


ROOT = Path(__file__).resolve().parents[3]


class TestOpampCoreBudgetSwingDriveLeakage(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(ROOT))
        init_sky130_install()

    def test_opamp_core__budget__swing_drive_leakage(self) -> None:
        swing = run_output_swing_test()
        drive = run_output_drive_test()
        leakage = run_disabled_leakage_test()

        self.assertEqual(swing["component"], "opamp_core")
        self.assertEqual(drive["component"], "opamp_core")
        self.assertEqual(leakage["component"], "opamp_core")
        self.assertEqual(swing["category"], "char")
        self.assertEqual(drive["category"], "char")
        self.assertEqual(leakage["category"], "char")

        self.assertLessEqual(swing["metrics"]["vout_low_actual"], OUTPUT_SWING_LOW_MAX)
        self.assertGreaterEqual(swing["metrics"]["vout_high_actual"], OUTPUT_SWING_HIGH_MIN)

        self.assertGreaterEqual(drive["metrics"]["requested_source_load_uA"], OUTPUT_CURRENT_ABS_MIN_UA)
        self.assertGreaterEqual(drive["metrics"]["requested_sink_load_uA"], OUTPUT_CURRENT_ABS_MIN_UA)
        self.assertGreaterEqual(drive["metrics"]["vout_source"], OUTPUT_SWING_LOW_MAX)
        self.assertLessEqual(drive["metrics"]["vout_source"], OUTPUT_SWING_HIGH_MIN)
        self.assertGreaterEqual(drive["metrics"]["vout_sink"], OUTPUT_SWING_LOW_MAX)
        self.assertLessEqual(drive["metrics"]["vout_sink"], OUTPUT_SWING_HIGH_MIN)

        self.assertLessEqual(leakage["metrics"]["disabled_leakage_nA"], DISABLED_LEAKAGE_NA_MAX)


if __name__ == "__main__":
    unittest.main()
