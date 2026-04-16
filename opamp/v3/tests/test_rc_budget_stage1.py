from __future__ import annotations

import json
from pathlib import Path

from opamp.v3.tests._helpers import BaseV3SimTest
from opamp.v3.tests.test_rc_probe_first_stage import _debug_params, _op_case, first_stage


METRICS_PATH = Path(__file__).with_name("rc_budget_stage1_metrics.json")


class TestRcBudgetStage1(BaseV3SimTest):
    def test_stage1_sign_and_bias_budget(self) -> None:
        dut = first_stage(_debug_params())
        cases = [
            _op_case(dut, name="balanced_mid", vinp=0.9, vinn=0.9),
            _op_case(dut, name="vinp_up_10m", vinp=0.91, vinn=0.9),
            _op_case(dut, name="vinn_up_10m", vinp=0.9, vinn=0.91),
        ]

        balanced = next(case for case in cases if case["case"] == "balanced_mid")
        vinp_up = next(case for case in cases if case["case"] == "vinp_up_10m")
        vinn_up = next(case for case in cases if case["case"] == "vinn_up_10m")

        tail_current = abs(float(balanced["i_tail_A"]))
        branch_imbalance = abs(abs(float(balanced["i_vx_load_A"])) - abs(float(balanced["i_vref_load_A"])))
        vcm_out = float(balanced["vcm_out_V"])

        payload = {
            "cases": cases,
            "budgets": {
                "tail_current_nominal_max_A": 1.0e-6,
                "tail_current_nominal_A": tail_current,
                "branch_imbalance_nominal_max_A": 5.0e-9,
                "branch_imbalance_nominal_A": branch_imbalance,
                "vcm_out_nominal_min_V": 0.2,
                "vcm_out_nominal_max_V": 1.6,
                "vcm_out_nominal_V": vcm_out,
                "vinp_up_drives_vx_down": float(vinp_up["vx_V"]) < float(balanced["vx_V"]),
                "vinn_up_drives_vx_up": float(vinn_up["vx_V"]) > float(balanced["vx_V"]),
            },
        }
        METRICS_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

        self.assertTrue(bool(payload["budgets"]["vinp_up_drives_vx_down"]))
        self.assertTrue(bool(payload["budgets"]["vinn_up_drives_vx_up"]))
        self.assertLessEqual(tail_current, 1.0e-6)
        self.assertLessEqual(branch_imbalance, 5.0e-9)
        self.assertGreaterEqual(vcm_out, 0.2)
        self.assertLessEqual(vcm_out, 1.6)
