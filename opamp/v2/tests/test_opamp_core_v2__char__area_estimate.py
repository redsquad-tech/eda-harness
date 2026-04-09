from __future__ import annotations

import unittest

from opamp.v2.opamp_core import run_area_estimate
from opamp.v2.tests._helpers import BaseV2SimTest


class TestOpampCoreV2CharAreaEstimate(BaseV2SimTest):
    def test_opamp_core_v2__char__area_estimate(self) -> None:
        result = run_area_estimate()
        metrics = result["metrics"]

        self.assertEqual(result["component"], "opamp_core")
        self.assertGreater(metrics["transistor_area_um2"], 0.0)
        self.assertGreater(metrics["total_device_count"], 0)


if __name__ == "__main__":
    unittest.main()
