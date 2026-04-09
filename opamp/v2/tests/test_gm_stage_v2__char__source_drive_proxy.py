from __future__ import annotations

import unittest

from opamp.v2.gm_stage import run_source_drive_proxy_test
from opamp.v2.tests._helpers import BaseV2SimTest


class TestGmStageV2CharSourceDriveProxy(BaseV2SimTest):
    def test_gm_stage_v2__char__source_drive_proxy(self) -> None:
        result = run_source_drive_proxy_test()
        metrics = result["metrics"]
        cases = metrics["cases"]

        self.assertEqual(result["component"], "second_stage")
        self.assertEqual(result["category"], "char")
        self.assertGreaterEqual(len(cases), 3)
        self.assertFinite(metrics["worst_vout_source"])
        self.assertFinite(metrics["worst_current_uA"])
        for case in cases:
            self.assertFinite(case["current_uA"])
            self.assertFinite(case["vout_source"])
            self.assertFinite(case["iq_uA"])
            self.assertGreaterEqual(case["iq_uA"], 0.0)


if __name__ == "__main__":
    unittest.main()
