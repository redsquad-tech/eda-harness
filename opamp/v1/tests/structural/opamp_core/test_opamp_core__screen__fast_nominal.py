from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

from opamp.v1.opamp_core import run_fast_checks
from opamp.v1.tests.structural._helpers import init_sky130_install


ROOT = Path(__file__).resolve().parents[3]


class TestOpampCoreScreenFastNominal(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(ROOT))
        init_sky130_install()

    def test_opamp_core__screen__fast_nominal(self) -> None:
        results = run_fast_checks()

        self.assertIn("structural", results)
        self.assertIn("direct_dc_gain", results)
        self.assertIn("open_loop", results)
        self.assertIn("closed_loop_step", results)
        self.assertIn("output_drive", results)
        self.assertIn("disabled_leakage", results)

        structural = results["structural"]
        direct_gain = results["direct_dc_gain"]
        open_loop = results["open_loop"]
        step = results["closed_loop_step"]
        drive = results["output_drive"]
        leakage = results["disabled_leakage"]

        self.assertEqual(structural["component"], "opamp_core")
        self.assertTrue(structural["pass"])

        direct_metrics = direct_gain["metrics"]
        self.assertTrue(math.isfinite(direct_metrics["direct_gain_db"]))
        self.assertTrue(math.isfinite(direct_metrics["direct_gain_vv"]))
        self.assertTrue(math.isfinite(direct_metrics["vout_dc"]))
        self.assertTrue(math.isfinite(direct_metrics["low_freq_vout_mag"]))
        self.assertGreater(direct_metrics["iq_uA"], 0.0)

        open_metrics = open_loop["metrics"]
        self.assertTrue(open_metrics["ac_fixture_ok"], "Fast nominal screen must converge on the AC fixture")
        self.assertTrue(math.isfinite(open_metrics["aol_db"]))
        self.assertTrue(math.isfinite(open_metrics["gbw_hz"]))
        self.assertTrue(math.isfinite(open_metrics["phase_margin_deg"]))
        self.assertGreater(open_metrics["iq_uA"], 0.0)
        self.assertIn("phase_at_unity_deg_raw", open_metrics)
        self.assertIn("low_freq_phase_deg_raw", open_metrics)
        self.assertIn("sign_offset_detected", open_metrics)
        self.assertTrue(math.isfinite(open_metrics["phase_at_unity_deg_raw"]))
        self.assertTrue(math.isfinite(open_metrics["low_freq_phase_deg_raw"]))

        step_metrics = step["metrics"]
        self.assertTrue(math.isfinite(step_metrics["vout_final"]))
        self.assertTrue(math.isfinite(step_metrics["overshoot"]))
        self.assertGreater(step_metrics["vout_final"], 0.0)
        self.assertGreaterEqual(step_metrics["vout_peak"], step_metrics["vout_final"])

        drive_metrics = drive["metrics"]
        self.assertTrue(math.isfinite(drive_metrics["vout_source"]))
        self.assertTrue(math.isfinite(drive_metrics["vout_sink"]))
        self.assertTrue(math.isfinite(drive_metrics["target_vout"]))

        leakage_metrics = leakage["metrics"]
        self.assertTrue(math.isfinite(leakage_metrics["disabled_leakage_nA"]))
        self.assertGreaterEqual(leakage_metrics["disabled_leakage_nA"], 0.0)


if __name__ == "__main__":
    unittest.main()
