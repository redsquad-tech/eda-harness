from __future__ import annotations

import unittest

from opamp.v2.opamp_core import run_disable_nodes_test
from opamp.v2.tests._helpers import BaseV2SimTest


class TestOpampCoreV2CharDisableNodes(BaseV2SimTest):
    def test_opamp_core_v2__char__disable_nodes(self) -> None:
        result = run_disable_nodes_test()
        metrics = result["metrics"]

        self.assertEqual(result["component"], "opamp_core")
        self.assertEqual(result["category"], "char")
        rail_eps = 1e-3
        for name in ("vx_dc", "vref_dc", "ibias1_dc", "ibias2_dc", "vbp_dc", "vout_dc", "iq_uA"):
            self.assertFinite(metrics[name], msg=f"{name} should be finite")
        for name in ("vx_dc", "vref_dc", "ibias1_dc", "ibias2_dc", "vbp_dc", "vout_dc"):
            self.assertGreaterEqual(metrics[name], -rail_eps, msg=f"{name} should stay within rails")
            self.assertLessEqual(metrics[name], 1.8 + rail_eps, msg=f"{name} should stay within rails")
        self.assertGreaterEqual(metrics["iq_uA"], 0.0)


if __name__ == "__main__":
    unittest.main()
