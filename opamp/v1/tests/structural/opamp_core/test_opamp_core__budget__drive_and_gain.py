from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

from opamp.v1.opamp_core import run_open_loop_test
from opamp.v1.tests.structural._helpers import init_sky130_install
from opamp.v1.tests.structural.opamp_core.specs_opamp_core import (
    AOL_DB_MIN,
    GAIN_MARGIN_DB_MIN,
    GBW_HZ_MAX,
    GBW_HZ_MIN,
    IQ_UA_MAX,
    PHASE_MARGIN_DEG_MIN,
)


ROOT = Path(__file__).resolve().parents[3]


class TestOpampCoreBudgetDriveAndGain(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(ROOT))
        init_sky130_install()

    def test_opamp_core__budget__drive_and_gain(self) -> None:
        result = run_open_loop_test()
        metrics = result["metrics"]

        self.assertEqual(result["component"], "opamp_core")
        self.assertEqual(result["category"], "char")

        self.assertIn("aol_db", metrics, "Spec-grade open-loop test must report DC gain in dB")
        self.assertIn("gbw_hz", metrics, "Spec-grade open-loop test must report GBW in Hz")
        self.assertIn("phase_margin_deg", metrics, "Spec-grade open-loop test must report phase margin")
        self.assertIn("gain_margin_db", metrics, "Spec-grade open-loop test must report gain margin")
        self.assertIn("iq_uA", metrics, "Spec-grade open-loop test must report quiescent current")
        self.assertIn("ac_fixture_ok", metrics, "Spec-grade open-loop test must report whether the AC fixture converged")
        self.assertIn("direct_dc_gain_db", metrics, "Spec-grade open-loop test must report direct differential DC gain")
        self.assertIn("loop_gain_dc_db", metrics, "Spec-grade open-loop test must report loop-break low-frequency gain separately")
        self.assertIn("low_freq_phase_deg_raw", metrics, "Spec-grade open-loop test must report the raw low-frequency loop phase")
        self.assertIn("phase_at_unity_deg_raw", metrics, "Spec-grade open-loop test must report the raw loop phase at unity")
        self.assertIn("sign_offset_detected", metrics, "Spec-grade open-loop test must report whether a 180-degree sign offset was detected")

        self.assertTrue(metrics["ac_fixture_ok"], "Spec-grade gain and stability metrics must come from the loop-break AC fixture")
        self.assertFalse(metrics["sign_offset_detected"], "Loop-break fixture must not rely on a hidden 180-degree sign correction")
        self.assertTrue(math.isfinite(metrics["phase_margin_deg"]), "Phase margin must be finite for a valid spec-grade AC measurement")
        self.assertGreaterEqual(metrics["phase_margin_deg"], 0.0, "Phase margin must be reported in physical degrees")
        self.assertLessEqual(metrics["phase_margin_deg"], 180.0, "Phase margin above 180 deg indicates an invalid loop-gain interpretation")
        self.assertFalse(math.isnan(metrics["gain_margin_db"]), "Gain margin must be measurable or explicitly infinite, not NaN")
        self.assertTrue(math.isfinite(metrics["direct_dc_gain_db"]), "Direct DC gain must be finite")
        self.assertTrue(math.isfinite(metrics["loop_gain_dc_db"]), "Loop-break DC gain must be finite")
        self.assertTrue(math.isfinite(metrics["low_freq_phase_deg_raw"]), "Raw low-frequency phase must be finite")
        self.assertTrue(math.isfinite(metrics["phase_at_unity_deg_raw"]), "Raw unity-gain phase must be finite")

        self.assertGreaterEqual(metrics["aol_db"], AOL_DB_MIN)
        self.assertGreaterEqual(metrics["gbw_hz"], GBW_HZ_MIN)
        self.assertLessEqual(metrics["gbw_hz"], GBW_HZ_MAX)
        self.assertGreaterEqual(metrics["phase_margin_deg"], PHASE_MARGIN_DEG_MIN)
        self.assertGreaterEqual(metrics["gain_margin_db"], GAIN_MARGIN_DB_MIN)
        self.assertLessEqual(metrics["iq_uA"], IQ_UA_MAX)


if __name__ == "__main__":
    unittest.main()
