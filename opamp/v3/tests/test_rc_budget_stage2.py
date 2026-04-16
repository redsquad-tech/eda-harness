from __future__ import annotations

import json
from pathlib import Path

from opamp.v3.tests._helpers import BaseV3SimTest
from opamp.v3.tests.test_rc_probe_stage2_standalone import _debug_params, _op_case, stage2_core


METRICS_PATH = Path(__file__).with_name("rc_budget_stage2_metrics.json")


class TestRcBudgetStage2(BaseV3SimTest):
    def test_stage2_current_budget(self) -> None:
        dut = stage2_core(_debug_params())
        cases = [
            _op_case(dut, name="vx_0p4", vx=0.4),
            _op_case(dut, name="vx_0p6", vx=0.6),
            _op_case(dut, name="vx_0p75", vx=0.75),
            _op_case(dut, name="vx_0p9", vx=0.9),
            _op_case(dut, name="vx_1p2", vx=1.2),
        ]
        nominal = next(case for case in cases if case["case"] == "vx_0p9")
        transition = next(case for case in cases if case["case"] == "vx_0p75")
        stage2_sum = abs(float(nominal["i_stage2_p_A"])) + abs(float(nominal["i_stage2_n_A"]))
        payload = {
            "cases": cases,
            "budgets": {
                "stage2_sum_nominal_max_A": 12e-6,
                "stage2_sum_nominal_A": stage2_sum,
                "inversion_law_ok": float(cases[0]["vdrv_V"]) > float(cases[1]["vdrv_V"]) > float(cases[2]["vdrv_V"]),
                "transition_ratio_min": 0.1,
                "transition_ratio_max": 10.0,
                "transition_ratio": float(transition["stage2_current_ratio"]),
                "transition_vdrv_min_V": 0.1,
                "transition_vdrv_max_V": 1.7,
                "transition_vdrv_V": float(transition["vdrv_V"]),
            },
        }
        METRICS_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        self.assertTrue(bool(payload["budgets"]["inversion_law_ok"]))
        self.assertLessEqual(stage2_sum, 12e-6)
        self.assertGreaterEqual(float(transition["stage2_current_ratio"]), 0.1)
        self.assertLessEqual(float(transition["stage2_current_ratio"]), 10.0)
        self.assertGreaterEqual(float(transition["vdrv_V"]), 0.1)
        self.assertLessEqual(float(transition["vdrv_V"]), 1.7)
