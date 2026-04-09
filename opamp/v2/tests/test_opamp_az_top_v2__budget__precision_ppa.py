from __future__ import annotations

import unittest

from opamp.v2.opamp_az_top import run_noise_and_offset_test
from opamp.v2.tests._helpers import BaseV2SimTest
from opamp.v2.tests.specs_opamp_az_top_v2 import PEDESTAL_UV_MAX, RESIDUAL_OFFSET_UV_MAX, SETTLING_RESIDUE_UV_MAX


class TestOpampAzTopV2BudgetPrecisionPpa(BaseV2SimTest):
    def test_opamp_az_top_v2__budget__precision_ppa(self) -> None:
        result = run_noise_and_offset_test()
        metrics = result["metrics"]

        self.assertEqual(result["component"], "opamp_az_top")
        self.assertLessEqual(metrics["residual_offset_uV"], RESIDUAL_OFFSET_UV_MAX)
        self.assertLessEqual(metrics["pedestal_mid50_uV"], PEDESTAL_UV_MAX)
        self.assertLessEqual(metrics["settling_mid50_uV"], SETTLING_RESIDUE_UV_MAX)


if __name__ == "__main__":
    unittest.main()
