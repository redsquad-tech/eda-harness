from __future__ import annotations
from pathlib import Path

from opamp.v3.opamp_core import opamp_core
from opamp.v3.tests._helpers import BaseV3SimTest, reset_metrics_file, write_metrics_json
from opamp.v3.tests.test_rc_probe_core import _debug_params as _core_debug_params, _op_case
from opamp.v3.tests.test_rc_probe_output_subckt import _debug_params as _out_debug_params, output_subckt
from opamp.v3.tests.test_rc_probe_small_signal_nominal import _point


METRICS_PATH = Path(__file__).with_name("rc_budget_output_path_metrics.json")


class TestRcBudgetOutputPath(BaseV3SimTest):
    def test_output_path_load_and_small_signal_budget(self) -> None:
        reset_metrics_file(METRICS_PATH)
        core = opamp_core(_core_debug_params())
        cases = {
            case["case"]: case
            for case in [
                _op_case(core, "follower_zero", vin=0.0),
                _op_case(core, "swing_high_target", vin=1.6),
                _op_case(core, "drive_source_20u", vin=0.9, load_mode="source", load_uA=20.0),
                _op_case(core, "drive_sink_20u", vin=0.9, load_mode="sink", load_uA=20.0),
            ]
        }
        out = output_subckt(_out_debug_params())
        points = [_point(out, vdrv=v) for v in (0.99, 1.00, 1.01)]
        vlow = float(cases["follower_zero"]["vout_V"])
        vhigh = float(cases["swing_high_target"]["vout_V"])
        source_vout = float(cases["drive_source_20u"]["vout_V"])
        sink_vout = float(cases["drive_sink_20u"]["vout_V"])
        gain = abs((points[2]["vout_V"] - points[0]["vout_V"]) / (points[2]["vdrv_in_V"] - points[0]["vdrv_in_V"]))

        payload = {
            "budgets": {
                "vout_low_max_V": 0.1,
                "vout_high_min_V": 1.6,
                "drive_source_20u_max_V": 0.1,
                "drive_sink_20u_min_V": 1.6,
                "small_signal_gain_min_vv": 0.05,
                "vout_low_V": vlow,
                "vout_high_V": vhigh,
                "drive_source_20u_V": source_vout,
                "drive_sink_20u_V": sink_vout,
                "small_signal_gain_vv": gain,
            }
        }
        write_metrics_json(METRICS_PATH, payload)
        self.assertLessEqual(vlow, 0.1)
        self.assertGreaterEqual(vhigh, 1.6)
        self.assertLessEqual(source_vout, 0.1)
        self.assertGreaterEqual(sink_vout, 1.6)
        self.assertGreaterEqual(gain, 0.05)
