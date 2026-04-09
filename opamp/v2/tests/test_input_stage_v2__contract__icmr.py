from __future__ import annotations

import unittest

from opamp.v2.input_stage import run_icmr_test
from opamp.v2.tests._helpers import BaseV2SimTest


class TestInputStageV2ContractIcmr(BaseV2SimTest):
    def test_input_stage_v2__contract__icmr(self) -> None:
        result = run_icmr_test()
        metrics = result["metrics"]

        self.assertEqual(result["component"], "gain_stage")
        self.assertEqual(result["category"], "contract")
        self.assertIn("lo_in_range", metrics)
        self.assertIn("hi_in_range", metrics)
        self.assertTrue(metrics["lo_in_range"])
        self.assertTrue(metrics["hi_in_range"])


if __name__ == "__main__":
    unittest.main()
