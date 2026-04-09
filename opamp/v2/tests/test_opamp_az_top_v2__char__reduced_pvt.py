from __future__ import annotations

import unittest

from opamp.v2.opamp_az_top import run_reduced_pvt_test
from opamp.v2.tests._helpers import BaseV2SimTest


@unittest.skip("Deferred: v2 currently validates only fast TT screens before reduced-PVT AZ characterization.")
class TestOpampAzTopV2CharReducedPvt(BaseV2SimTest):
    def test_opamp_az_top_v2__char__reduced_pvt(self) -> None:
        result = run_reduced_pvt_test()
        metrics = result["metrics"]

        self.assertEqual(result["component"], "opamp_az_top")
        self.assertFinite(metrics["worst_residual_offset_uV"])
        self.assertFinite(metrics["worst_pedestal_mid50_uV"])
        self.assertFinite(metrics["worst_settling_mid50_uV"])


if __name__ == "__main__":
    unittest.main()
