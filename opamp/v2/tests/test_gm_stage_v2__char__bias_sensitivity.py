from __future__ import annotations

import unittest

from opamp.v2.gm_stage import run_bias_sensitivity_test
from opamp.v2.tests._helpers import BaseV2SimTest


class TestGmStageV2CharBiasSensitivity(BaseV2SimTest):
    def test_gm_stage_v2__char__bias_sensitivity(self) -> None:
        result = run_bias_sensitivity_test()
        metrics = result["metrics"]
        cases = metrics["cases"]

        self.assertEqual(result["component"], "second_stage")
        self.assertEqual(result["category"], "char")
        self.assertGreaterEqual(len(cases), 3)
        self.assertFinite(metrics["min_vout_dc"])
        self.assertFinite(metrics["max_vout_dc"])
        self.assertFinite(metrics["min_iq_uA"])
        self.assertFinite(metrics["max_iq_uA"])
        for case in cases:
            self.assertFinite(case["vbias_dc"])
            self.assertFinite(case["vout_dc"])
            self.assertFinite(case["iq_uA"])
            self.assertGreaterEqual(case["iq_uA"], 0.0)


if __name__ == "__main__":
    unittest.main()
