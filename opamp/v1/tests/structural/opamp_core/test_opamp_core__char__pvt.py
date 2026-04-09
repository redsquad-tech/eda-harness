from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

from opamp.v1.opamp_core import run_pvt_test
from opamp.v1.tests.structural._helpers import init_sky130_install


ROOT = Path(__file__).resolve().parents[3]


class TestOpampCoreCharPvt(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(ROOT))
        init_sky130_install()

    def test_opamp_core__char__pvt(self) -> None:
        result = run_pvt_test()
        metrics = result["metrics"]

        self.assertEqual(result["component"], "opamp_core")
        self.assertEqual(result["category"], "char")
        self.assertIn("cases", metrics)
        self.assertEqual(len(metrics["cases"]), 27)
        self.assertTrue(math.isfinite(metrics["worst_aol_db"]))
        self.assertTrue(math.isfinite(metrics["worst_gbw_hz"]))
        self.assertTrue(math.isfinite(metrics["worst_phase_margin_deg"]))
        self.assertTrue(math.isfinite(metrics["worst_iq_uA"]))
        self.assertTrue(all(case["ac_fixture_ok"] for case in metrics["cases"].values()))


if __name__ == "__main__":
    unittest.main()
