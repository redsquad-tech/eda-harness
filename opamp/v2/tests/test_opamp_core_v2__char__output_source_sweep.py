from __future__ import annotations

import unittest

from opamp.v2.opamp_core import run_output_source_sweep_test
from opamp.v2.tests._helpers import BaseV2SimTest


class TestOpampCoreV2CharOutputSourceSweep(BaseV2SimTest):
    def test_opamp_core_v2__char__output_source_sweep(self) -> None:
        result = run_output_source_sweep_test()
        metrics = result["metrics"]
        cases = metrics["cases"]

        self.assertEqual(result["component"], "opamp_core")
        self.assertEqual(result["category"], "char")
        self.assertGreaterEqual(len(cases), 3)
        self.assertFinite(metrics["worst_vout_source"])
        self.assertFinite(metrics["worst_current_uA"])
        for case in cases:
            self.assertFinite(case["current_uA"])
            self.assertFinite(case["vout_source"])


if __name__ == "__main__":
    unittest.main()
