from __future__ import annotations

import unittest

from opamp.v2.bias_gen import run_disable_off_test
from opamp.v2.tests._helpers import BaseV2SimTest


class TestBiasGenV2CharDisableOff(BaseV2SimTest):
    def test_bias_gen_v2__char__disable_off(self) -> None:
        result = run_disable_off_test()
        metrics = result["metrics"]

        self.assertEqual(result["component"], "bias_gen")
        self.assertEqual(result["category"], "char")
        self.assertFinite(metrics["i_ibias1_off_est"])
        self.assertFinite(metrics["i_ibias2_off_est"])
        self.assertFinite(metrics["vbp_off"])
        self.assertFinite(metrics["vbp_headroom_to_vdd"])
        self.assertGreaterEqual(metrics["i_ibias1_off_est"], 0.0)
        self.assertGreaterEqual(metrics["i_ibias2_off_est"], 0.0)
        self.assertGreaterEqual(metrics["vbp_off"], 0.0)
        self.assertLessEqual(metrics["vbp_off"], 1.8)


if __name__ == "__main__":
    unittest.main()
