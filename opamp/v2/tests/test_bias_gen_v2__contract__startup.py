from __future__ import annotations

import unittest

from opamp.v2.bias_gen import run_startup_test
from opamp.v2.tests._helpers import BaseV2SimTest
from opamp.v2.tests.specs_bias_gen_v2 import STARTUP_CURRENT_MIN_UA


class TestBiasGenV2ContractStartup(BaseV2SimTest):
    def test_bias_gen_v2__contract__startup(self) -> None:
        result = run_startup_test()
        metrics = result["metrics"]

        self.assertEqual(result["component"], "bias_gen")
        self.assertEqual(result["category"], "contract")
        self.assertTrue(metrics["startup_ok"])
        self.assertGreaterEqual(1e6 * float(metrics["i_ibias1_est"]), STARTUP_CURRENT_MIN_UA)
        self.assertGreaterEqual(1e6 * float(metrics["i_ibias2_est"]), STARTUP_CURRENT_MIN_UA)


if __name__ == "__main__":
    unittest.main()
