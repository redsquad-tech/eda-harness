from __future__ import annotations

import unittest

from opamp.v3.measure_core import run_disabled_leakage_test, run_open_loop_test, run_output_drive_test, run_output_swing_test
from opamp.v3.tests._helpers import BaseV3SimTest


class TestOpampCoreV3CharTtNominal(BaseV3SimTest):
    def test_opamp_core_v3__char__tt_nominal(self) -> None:
        open_loop = run_open_loop_test()
        swing = run_output_swing_test()
        drive = run_output_drive_test()
        leakage = run_disabled_leakage_test()

        open_loop_metrics = open_loop["metrics"]
        swing_metrics = swing["metrics"]
        drive_metrics = drive["metrics"]
        leakage_metrics = leakage["metrics"]

        self.assertEqual(open_loop["component"], "opamp_core_v3")
        self.assertEqual(swing["component"], "opamp_core_v3")
        self.assertEqual(drive["component"], "opamp_core_v3")
        self.assertEqual(leakage["component"], "opamp_core_v3")

        self.assertTrue(open_loop_metrics["ac_fixture_ok"])
        self.assertFinite(open_loop_metrics["aol_db"])
        self.assertFinite(open_loop_metrics["iq_uA"])
        self.assertFinite(swing_metrics["vout_low_actual"])
        self.assertFinite(swing_metrics["vout_high_actual"])
        self.assertFinite(drive_metrics["vout_source"])
        self.assertFinite(drive_metrics["vout_sink"])
        self.assertFinite(leakage_metrics["disabled_leakage_nA"])


if __name__ == "__main__":
    unittest.main()
