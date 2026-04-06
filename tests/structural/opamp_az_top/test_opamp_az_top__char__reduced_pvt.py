from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

from components.opamp_az_top import run_reduced_pvt_test
from tests.structural._helpers import init_sky130_install


ROOT = Path(__file__).resolve().parents[3]


class TestOpampAzTopCharReducedPvt(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(ROOT))
        init_sky130_install()

    def test_opamp_az_top__char__reduced_pvt(self) -> None:
        result = run_reduced_pvt_test()
        metrics = result["metrics"]

        self.assertEqual(result["component"], "opamp_az_top")
        self.assertEqual(result["category"], "char")
        self.assertIn("cases", metrics)
        self.assertEqual(len(metrics["cases"]), 5)
        self.assertTrue(math.isfinite(metrics["worst_residual_offset_uV"]))
        self.assertTrue(math.isfinite(metrics["worst_pedestal_mid50_uV"]))
        self.assertTrue(math.isfinite(metrics["worst_settling_mid50_uV"]))


if __name__ == "__main__":
    unittest.main()
