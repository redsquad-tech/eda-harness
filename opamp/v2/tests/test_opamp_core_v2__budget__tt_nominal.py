from __future__ import annotations

import unittest

from opamp.v2.opamp_core import run_area_estimate, run_disabled_leakage_test, run_open_loop_test, run_output_drive_test, run_output_swing_test
from opamp.v2.tests._helpers import BaseV2SimTest
from opamp.v2.tests.specs_opamp_core_v2 import (
    AOL_DB_MIN,
    DISABLED_LEAKAGE_NA_MAX,
    GAIN_MARGIN_DB_MIN,
    GBW_HZ_MAX,
    GBW_HZ_MIN,
    IQ_UA_MAX,
    OUTPUT_CURRENT_ABS_MIN_UA,
    OUTPUT_SWING_HIGH_MIN,
    OUTPUT_SWING_LOW_MAX,
    PHASE_MARGIN_DEG_MIN,
)


class TestOpampCoreV2BudgetTtNominal(BaseV2SimTest):
    def test_opamp_core_v2__budget__tt_nominal(self) -> None:
        open_loop = run_open_loop_test()
        swing = run_output_swing_test()
        drive = run_output_drive_test()
        leakage = run_disabled_leakage_test()
        area = run_area_estimate()

        open_loop_metrics = open_loop["metrics"]
        swing_metrics = swing["metrics"]
        drive_metrics = drive["metrics"]
        leakage_metrics = leakage["metrics"]
        area_metrics = area["metrics"]

        self.assertEqual(open_loop["component"], "opamp_core")
        self.assertEqual(swing["component"], "opamp_core")
        self.assertEqual(drive["component"], "opamp_core")
        self.assertEqual(leakage["component"], "opamp_core")
        self.assertEqual(area["component"], "opamp_core")

        with self.subTest("open_loop_fixture"):
            self.assertTrue(open_loop_metrics["ac_fixture_ok"])
            self.assertFinite(open_loop_metrics["aol_db"])
            self.assertFinite(open_loop_metrics["iq_uA"])

        with self.subTest("aol_db"):
            self.assertGreaterEqual(open_loop_metrics["aol_db"], AOL_DB_MIN)

        with self.subTest("gbw_hz"):
            self.assertGreaterEqual(open_loop_metrics["gbw_hz"], GBW_HZ_MIN)
            self.assertLessEqual(open_loop_metrics["gbw_hz"], GBW_HZ_MAX)

        with self.subTest("phase_margin_deg"):
            self.assertGreaterEqual(open_loop_metrics["phase_margin_deg"], PHASE_MARGIN_DEG_MIN)

        with self.subTest("gain_margin_db"):
            self.assertGreaterEqual(open_loop_metrics["gain_margin_db"], GAIN_MARGIN_DB_MIN)

        with self.subTest("iq_uA"):
            self.assertLessEqual(open_loop_metrics["iq_uA"], IQ_UA_MAX)

        with self.subTest("swing_low"):
            self.assertLessEqual(swing_metrics["vout_low_actual"], OUTPUT_SWING_LOW_MAX)

        with self.subTest("swing_high"):
            self.assertGreaterEqual(swing_metrics["vout_high_actual"], OUTPUT_SWING_HIGH_MIN)

        with self.subTest("drive_requested"):
            self.assertGreaterEqual(drive_metrics["requested_source_load_uA"], OUTPUT_CURRENT_ABS_MIN_UA)
            self.assertGreaterEqual(drive_metrics["requested_sink_load_uA"], OUTPUT_CURRENT_ABS_MIN_UA)

        with self.subTest("drive_source_compliance"):
            self.assertGreaterEqual(drive_metrics["vout_source"], OUTPUT_SWING_LOW_MAX)
            self.assertLessEqual(drive_metrics["vout_source"], OUTPUT_SWING_HIGH_MIN)

        with self.subTest("drive_sink_compliance"):
            self.assertGreaterEqual(drive_metrics["vout_sink"], OUTPUT_SWING_LOW_MAX)
            self.assertLessEqual(drive_metrics["vout_sink"], OUTPUT_SWING_HIGH_MIN)

        with self.subTest("disabled_leakage"):
            self.assertLessEqual(leakage_metrics["disabled_leakage_nA"], DISABLED_LEAKAGE_NA_MAX)

        with self.subTest("area_proxy_positive"):
            self.assertGreater(area_metrics["transistor_area_um2"], 0.0)


if __name__ == "__main__":
    unittest.main()
