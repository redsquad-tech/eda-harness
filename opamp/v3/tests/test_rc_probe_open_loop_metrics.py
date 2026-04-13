from __future__ import annotations

import math

from opamp.v1.tests.structural._helpers import init_sky130_install
from opamp.v3.measure_core import run_open_loop_test
from opamp.v3.tests._helpers import BaseV3SimTest


class TestRcProbeOpenLoopMetrics(BaseV3SimTest):
    def test_open_loop_measurement_uses_biased_fixture(self) -> None:
        init_sky130_install()
        metrics = run_open_loop_test()["metrics"]
        self.assertTrue(bool(metrics["ac_fixture_ok"]))
        self.assertAlmostEqual(float(metrics["direct_vout_dc"]), 0.9, delta=0.05)
        if bool(metrics["aol_estimate_valid"]):
            self.assertTrue(math.isfinite(float(metrics["aol_db"])))
            self.assertGreater(float(metrics["aol_db"]), 0.0)
            self.assertLess(float(metrics["aol_db"]), 120.0)
            self.assertTrue(math.isfinite(float(metrics["gbw_hz"])))
            self.assertTrue(math.isfinite(float(metrics["phase_margin_deg"])))
        else:
            self.assertTrue(math.isnan(float(metrics["aol_db"])))
