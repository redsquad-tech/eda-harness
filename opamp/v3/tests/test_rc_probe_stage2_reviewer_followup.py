from __future__ import annotations

import dataclasses
import traceback
from pathlib import Path

import hdl21 as h

from opamp.v1.tests.structural._helpers import init_sky130_install
from opamp.v3.measure_core import run_open_loop_test
from opamp.v3.prod.rc import current_core_params
from opamp.v3.tests._helpers import BaseV3SimTest, reset_metrics_file, write_metrics_json


METRICS_PATH = Path(__file__).with_name("rc_probe_stage2_reviewer_followup_metrics.json")


class TestRcProbeStage2ReviewerFollowup(BaseV3SimTest):
    def test_reviewer_stage2n_alternatives(self) -> None:
        reset_metrics_file(METRICS_PATH)
        try:
            init_sky130_install()
            base = current_core_params()
            cases = {
                "stage2n_6_12": dataclasses.replace(
                    base, w_stage2_n=6.0, l_stage2_n=12.0, w_stage2_p=15.0, l_stage2_p=12.0
                ),
                "stage2n_4_8": dataclasses.replace(
                    base, w_stage2_n=4.0, l_stage2_n=8.0, w_stage2_p=15.0, l_stage2_p=12.0
                ),
            }

            payload = {}
            for name, params in cases.items():
                h.generator.cache.reset()
                metrics = run_open_loop_test(params)["metrics"]
                payload[name] = {
                    "aol_db": metrics.get("aol_db"),
                    "direct_dc_gain_db": metrics.get("direct_dc_gain_db"),
                    "gbw_hz": metrics.get("gbw_hz"),
                    "phase_margin_deg": metrics.get("phase_margin_deg"),
                    "gain_margin_db": metrics.get("gain_margin_db"),
                    "iq_uA": metrics.get("iq_uA"),
                    "direct_vout_dc": metrics.get("direct_vout_dc"),
                    "ac_fixture_ok": metrics.get("ac_fixture_ok"),
                }

            write_metrics_json(METRICS_PATH, payload)
            self.assertTrue(bool(payload["stage2n_6_12"]["ac_fixture_ok"]))
            self.assertTrue(bool(payload["stage2n_4_8"]["ac_fixture_ok"]))
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
