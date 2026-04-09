from __future__ import annotations

import unittest

from opamp.v2.opamp_core import run_fast_checks
from opamp.v2.tests._helpers import BaseV2SimTest


class TestOpampCoreV2ScreenFastNominal(BaseV2SimTest):
    def test_opamp_core_v2__screen__fast_nominal(self) -> None:
        results = run_fast_checks()
        open_loop_metrics = results["open_loop"]["metrics"]

        self.assertIn("structural", results)
        self.assertIn("open_loop", results)
        self.assertTrue(results["structural"]["pass"])
        self.assertFinite(open_loop_metrics["aol_db"])
        self.assertFinite(open_loop_metrics["direct_dc_gain_db"])
        self.assertFinite(open_loop_metrics["iq_uA"])
        self.assertIn("gbw_hz", open_loop_metrics)
        self.assertIn("phase_margin_deg", open_loop_metrics)


if __name__ == "__main__":
    unittest.main()
