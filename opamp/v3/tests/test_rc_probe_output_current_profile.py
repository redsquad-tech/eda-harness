from __future__ import annotations
from pathlib import Path

from opamp.v3.opamp_core import opamp_core
from opamp.v3.tests._helpers import BaseV3SimTest, reset_metrics_file, write_metrics_json
from opamp.v3.tests.test_rc_probe_core import _debug_params, _op_case


METRICS_PATH = Path(__file__).with_name("rc_probe_output_current_profile_metrics.json")


class TestRcProbeOutputCurrentProfile(BaseV3SimTest):
    def test_probe_rc_output_current_profile(self):
        reset_metrics_file(METRICS_PATH)
        dut = opamp_core(_debug_params())
        cases = [
            _op_case(dut, "follower_zero", vin=0.0),
            _op_case(dut, "follower_mid", vin=0.9),
            _op_case(dut, "swing_high_target", vin=1.6),
            _op_case(dut, "drive_source_20u", vin=0.9, load_mode="source", load_uA=20.0),
            _op_case(dut, "drive_sink_20u", vin=0.9, load_mode="sink", load_uA=20.0),
        ]
        for case in cases:
            i_out_p = abs(float(case["i_out_p_A"]))
            i_out_n = abs(float(case["i_out_n_A"]))
            denom = max(min(i_out_p, i_out_n), 1e-18)
            case["current_imbalance_ratio"] = max(i_out_p, i_out_n) / denom
            case["dominant_branch"] = "nmos" if i_out_n >= i_out_p else "pmos"
        payload = {"cases": cases}
        write_metrics_json(METRICS_PATH, payload)
        self.assertEqual(len(cases), 5)
