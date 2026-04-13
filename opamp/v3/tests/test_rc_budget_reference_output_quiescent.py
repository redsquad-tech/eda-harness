from __future__ import annotations

from pathlib import Path

from opamp.v3.tests._helpers import BaseV3SimTest, reset_metrics_file, write_metrics_json
from opamp.v3.tests.test_rc_probe_reference_output_quiescent_clamped import _case
from opamp.v3.output_path_reference import default_reference_output_path_params, reference_output_path_method2


METRICS_PATH = Path(__file__).with_name("rc_budget_reference_output_quiescent_metrics.json")


class TestRcBudgetReferenceOutputQuiescent(BaseV3SimTest):
    def test_budget_rc_reference_output_quiescent(self):
        reset_metrics_file(METRICS_PATH)

        dut = reference_output_path_method2(default_reference_output_path_params())
        payload = _case(dut, name="combined_vdrv_1p0", vdrv=1.0, vout_force=0.9)
        write_metrics_json(METRICS_PATH, payload)

        self.assertGreater(payload["quiescent_overlap_A"], 4e-6)
        self.assertLess(abs(payload["branch_imbalance_A"]), 5e-7)
        self.assertLess(payload["branch_balance_ratio"], 1.2)
        self.assertGreater(payload["branch_balance_ratio"], 1 / 1.2)
