from __future__ import annotations

import math
import traceback
from pathlib import Path

from opamp.v1.tests.structural._helpers import init_sky130_install
from opamp.v3.measure_core import run_open_loop_test
from opamp.v3.tests._helpers import BaseV3SimTest, reset_metrics_file, write_metrics_json


METRICS_PATH = Path(__file__).with_name("rc_probe_open_loop_metrics.json")


class TestRcProbeOpenLoopMetrics(BaseV3SimTest):
    def test_open_loop_measurement_uses_direct_gain_and_loop_fixtures(self) -> None:
        reset_metrics_file(METRICS_PATH)
        try:
            init_sky130_install()
            metrics = run_open_loop_test()["metrics"]
            write_metrics_json(METRICS_PATH, metrics)
            self.assertTrue(bool(metrics["ac_fixture_ok"]), msg=str(metrics.get("ac_error", "")))
            self.assertTrue(math.isfinite(float(metrics["direct_vout_dc"])))
            self.assertGreaterEqual(float(metrics["direct_vout_dc"]), 0.0)
            self.assertLessEqual(float(metrics["direct_vout_dc"]), 1.8)
            if bool(metrics["aol_estimate_valid"]):
                self.assertTrue(math.isfinite(float(metrics["aol_db"])))
                self.assertGreater(float(metrics["aol_db"]), 0.0)
                self.assertLess(float(metrics["aol_db"]), 120.0)
                self.assertTrue(math.isfinite(float(metrics["gbw_hz"])))
                self.assertTrue(math.isfinite(float(metrics["phase_margin_deg"])))
            else:
                self.assertTrue(math.isnan(float(metrics["aol_db"])))
        except Exception as exc:
            write_metrics_json(
                METRICS_PATH,
                {
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                },
            )
            raise
