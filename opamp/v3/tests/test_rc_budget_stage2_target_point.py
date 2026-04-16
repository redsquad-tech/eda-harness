from __future__ import annotations

import json
from pathlib import Path

from opamp.v3.tests._helpers import BaseV3SimTest
from opamp.v3.tests.test_rc_probe_stage2_standalone import _debug_params, _op_case, stage2_core


METRICS_PATH = Path(__file__).with_name("rc_budget_stage2_target_point_metrics.json")


class TestRcBudgetStage2TargetPoint(BaseV3SimTest):
    def test_stage2_target_point_near_first_stage_nominal(self) -> None:
        dut = stage2_core(_debug_params())
        case = _op_case(dut, name="vx_0p48", vx=0.48)
        payload = {
            "case": case,
            "budgets": {
                "vx_target_V": 0.48,
                "vdrv_min_V": 0.9,
                "vdrv_max_V": 1.2,
                "stage2_current_ratio_min": 0.1,
                "stage2_current_ratio_max": 10.0,
            },
        }
        METRICS_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        self.assertGreaterEqual(float(case["vdrv_V"]), 0.9)
        self.assertLessEqual(float(case["vdrv_V"]), 1.2)
        self.assertGreaterEqual(float(case["stage2_current_ratio"]), 0.1)
        self.assertLessEqual(float(case["stage2_current_ratio"]), 10.0)
