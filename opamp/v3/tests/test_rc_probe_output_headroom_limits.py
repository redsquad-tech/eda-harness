from __future__ import annotations

import json
from pathlib import Path

from opamp.v3.specs import OpampAzV3MaximumSpec, min_required_output_high
from opamp.v3.tests._helpers import BaseV3SimTest
from opamp.v3.tests.test_rc_probe_output_subckt import _debug_params, _op_case, output_subckt


METRICS_PATH = Path(__file__).with_name("rc_probe_output_headroom_limits_metrics.json")


class TestRcProbeOutputHeadroomLimits(BaseV3SimTest):
    def test_probe_rc_output_headroom_limits(self):
        dut = output_subckt(_debug_params())
        spec = OpampAzV3MaximumSpec()

        low_case = _op_case(dut, name="headroom_low_limit", vdrv=0.0)
        high_case = _op_case(dut, name="headroom_high_limit", vdrv=1.8)

        payload = {
            "topology": "complementary_source_follower",
            "cases": [low_case, high_case],
            "derived": {
                "spec_low_target_V": float(spec.output_swing_low_max_v),
                "spec_high_target_V": float(min_required_output_high(spec.vdd_nominal_v)),
                "achieved_low_limit_V": float(low_case["vout_V"]),
                "achieved_high_limit_V": float(high_case["vout_V"]),
                "low_headroom_error_V": float(low_case["vout_V"] - spec.output_swing_low_max_v),
                "high_headroom_error_V": float(min_required_output_high(spec.vdd_nominal_v) - high_case["vout_V"]),
                "meets_low_swing_spec": bool(low_case["vout_V"] <= spec.output_swing_low_max_v),
                "meets_high_swing_spec": bool(high_case["vout_V"] >= min_required_output_high(spec.vdd_nominal_v)),
            },
        }

        METRICS_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        self.assertEqual(len(payload["cases"]), 2)
