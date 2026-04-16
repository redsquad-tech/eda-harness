from __future__ import annotations

from pathlib import Path

from opamp.v3.opamp_core import opamp_core
from opamp.v3.tests._helpers import BaseV3SimTest, reset_metrics_file, write_metrics_json
from opamp.v3.tests.test_rc_probe_core import _debug_params, _op_case


METRICS_PATH = Path(__file__).with_name("rc_probe_core_loop_sign_metrics.json")


class TestRcProbeCoreLoopSign(BaseV3SimTest):
    def test_probe_rc_core_loop_sign(self):
        reset_metrics_file(METRICS_PATH)
        dut = opamp_core(_debug_params())
        vin_cases = [0.85, 0.90, 0.95]
        cases = [_op_case(dut, f"follower_{str(v).replace('.', 'p')}", vin=v) for v in vin_cases]
        payload = {
            "cases": cases,
            "dvout_over_dvin": float(cases[-1]["vout_V"]) - float(cases[0]["vout_V"]),
            "dvx_over_dvin": float(cases[-1]["vx_V"]) - float(cases[0]["vx_V"]),
            "dvdrv_over_dvin": float(cases[-1]["vdrv_V"]) - float(cases[0]["vdrv_V"]),
        }
        write_metrics_json(METRICS_PATH, payload)
        self.assertEqual(len(cases), 3)
