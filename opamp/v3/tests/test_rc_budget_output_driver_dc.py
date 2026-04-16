from __future__ import annotations

import json
from pathlib import Path

from opamp.v3.tests._helpers import BaseV3SimTest, build_debug_core_params, reset_metrics_file, write_metrics_json
from opamp.v3.tests.test_rc_probe_idealized_driver_ab import _op_case
from opamp.v3.opamp_core import opamp_core


METRICS_PATH = Path(__file__).with_name("rc_budget_output_driver_dc_metrics.json")


class TestRcBudgetOutputDriverDc(BaseV3SimTest):
    def test_output_driver_dc_role_budget(self) -> None:
        reset_metrics_file(METRICS_PATH)
        dut = opamp_core(build_debug_core_params())

        follower_mid = _op_case(dut, name="follower_mid", vin=0.9)
        drive_source = _op_case(dut, name="drive_source_20u", vin=0.9, load_mode="source", load_uA=20.0)
        drive_sink = _op_case(dut, name="drive_sink_20u", vin=0.9, load_mode="sink", load_uA=20.0)

        payload = {
            "cases": {
                "follower_mid": follower_mid,
                "drive_source_20u": drive_source,
                "drive_sink_20u": drive_sink,
            },
            "budgets": {
                "nominal_vout_target_V": 0.9,
                "nominal_vout_max_error_V": 0.05,
                "nominal_gate_avg_min_V": 0.2,
                "nominal_gate_avg_max_V": 1.6,
                "drive_source_semantics": "external current injected into VOUT should push VOUT above nominal",
                "drive_sink_semantics": "external current drawn from VOUT should pull VOUT below nominal",
                "nominal_vout_error_V": abs(float(follower_mid["vout_V"]) - 0.9),
                "nominal_gate_avg_V": float(follower_mid["gate_avg_V"]),
                "nominal_gate_spread_V": float(follower_mid["gate_spread_V"]),
                "drive_source_vout_V": float(drive_source["vout_V"]),
                "drive_sink_vout_V": float(drive_sink["vout_V"]),
                "drive_source_above_nominal_V": float(drive_source["vout_V"]) - float(follower_mid["vout_V"]),
                "drive_sink_below_nominal_V": float(follower_mid["vout_V"]) - float(drive_sink["vout_V"]),
            },
        }
        write_metrics_json(METRICS_PATH, payload)

        self.assertLessEqual(float(payload["budgets"]["nominal_vout_error_V"]), 0.05)
        self.assertGreaterEqual(float(payload["budgets"]["nominal_gate_avg_V"]), 0.2)
        self.assertLessEqual(float(payload["budgets"]["nominal_gate_avg_V"]), 1.6)
        self.assertGreater(float(payload["budgets"]["drive_source_above_nominal_V"]), 0.0)
        self.assertGreater(float(payload["budgets"]["drive_sink_below_nominal_V"]), 0.0)
