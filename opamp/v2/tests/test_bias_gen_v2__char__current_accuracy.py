from __future__ import annotations

import unittest

from opamp.v2.bias_gen import run_current_accuracy_test
from opamp.v2.tests._helpers import BaseV2SimTest
from opamp.v2.tests.specs_bias_gen_v2 import RATIO_ERROR_ABS_MAX


class TestBiasGenV2CharCurrentAccuracy(BaseV2SimTest):
    def test_bias_gen_v2__char__current_accuracy(self) -> None:
        result = run_current_accuracy_test()
        metrics = result["metrics"]

        self.assertEqual(result["component"], "bias_gen")
        self.assertEqual(result["category"], "char")
        self.assertFinite(metrics["ratio_est"])
        self.assertFinite(metrics["ratio_error_abs"])
        self.assertLessEqual(metrics["ratio_error_abs"], RATIO_ERROR_ABS_MAX)


if __name__ == "__main__":
    unittest.main()
