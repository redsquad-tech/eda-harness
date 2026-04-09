from __future__ import annotations

import unittest

from opamp.v2.opamp_core import run_load_sweep_test
from opamp.v2.tests._helpers import BaseV2SimTest


@unittest.skip("Deferred: v2 currently validates only fast TT screens before load-sweep characterization.")
class TestOpampCoreV2CharLoadSweep(BaseV2SimTest):
    def test_opamp_core_v2__char__load_sweep(self) -> None:
        result = run_load_sweep_test()
        metrics = result["metrics"]

        self.assertEqual(result["component"], "opamp_core")
        self.assertFinite(metrics["worst_aol_db"])
        self.assertFinite(metrics["worst_phase_margin_deg"])
        self.assertFinite(metrics["worst_iq_uA"])


if __name__ == "__main__":
    unittest.main()
