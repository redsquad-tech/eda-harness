from __future__ import annotations

import unittest

from opamp.v2.bias_gen import run_reduced_corner_characterization_test
from opamp.v2.tests._helpers import BaseV2SimTest


class TestBiasGenV2CharReducedCorners(BaseV2SimTest):
    def test_bias_gen_v2__char__reduced_corners(self) -> None:
        result = run_reduced_corner_characterization_test()
        metrics = result["metrics"]
        cases = metrics["cases"]

        self.assertEqual(result["component"], "bias_gen")
        self.assertEqual(result["category"], "char")
        self.assertEqual(set(cases.keys()), {"TT_1.80V_27C", "FF_1.98V_125C", "SS_1.62V_-40C"})
        self.assertFinite(metrics["stage1_current_min_uA"])
        self.assertFinite(metrics["stage1_current_max_uA"])
        self.assertFinite(metrics["stage1_current_spread_ratio"])
        self.assertFinite(metrics["stage2_current_min_uA"])
        self.assertFinite(metrics["stage2_current_max_uA"])
        self.assertFinite(metrics["stage2_current_spread_ratio"])
        self.assertGreater(metrics["stage1_current_min_uA"], 0.0)
        self.assertGreater(metrics["stage2_current_min_uA"], 0.0)
        self.assertGreaterEqual(metrics["stage1_current_max_uA"], metrics["stage1_current_min_uA"])
        self.assertGreaterEqual(metrics["stage2_current_max_uA"], metrics["stage2_current_min_uA"])
        for case in cases.values():
            self.assertFinite(case["i_ibias1_uA"])
            self.assertFinite(case["i_ibias2_uA"])
            self.assertFinite(case["ratio_est"])
            self.assertFinite(case["ratio_target"])
            self.assertFinite(case["ratio_error_abs"])
            self.assertGreater(case["i_ibias1_uA"], 0.0)
            self.assertGreater(case["i_ibias2_uA"], 0.0)


if __name__ == "__main__":
    unittest.main()
