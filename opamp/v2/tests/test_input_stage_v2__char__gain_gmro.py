from __future__ import annotations

import unittest

from opamp.v2.input_stage import run_gain_gmro_test
from opamp.v2.tests._helpers import BaseV2SimTest


class TestInputStageV2CharGainGmro(BaseV2SimTest):
    def test_input_stage_v2__char__gain_gmro(self) -> None:
        result = run_gain_gmro_test()
        metrics = result["metrics"]

        self.assertEqual(result["component"], "gain_stage")
        self.assertEqual(result["category"], "char")
        self.assertFinite(metrics["diff_gain_est"])
        self.assertFinite(metrics["vx_dc"])
        self.assertFinite(metrics["vref_dc"])
        self.assertGreater(metrics["tail_nominal_uA"], 0.0)


if __name__ == "__main__":
    unittest.main()
