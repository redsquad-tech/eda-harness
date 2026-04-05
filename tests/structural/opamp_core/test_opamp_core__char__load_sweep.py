from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

from components.opamp_core import run_load_sweep_test
from tests.structural._helpers import init_sky130_install


ROOT = Path(__file__).resolve().parents[3]


class TestOpampCoreCharLoadSweep(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(ROOT))
        init_sky130_install()

    def test_opamp_core__char__load_sweep(self) -> None:
        result = run_load_sweep_test()
        metrics = result["metrics"]

        self.assertEqual(result["component"], "opamp_core")
        self.assertEqual(result["category"], "char")
        self.assertIn("cases", metrics)
        self.assertEqual(set(metrics["cases"].keys()), {"c_load_0fF", "c_load_1000fF", "c_load_2000fF"})
        self.assertTrue(math.isfinite(metrics["worst_aol_db"]))
        self.assertTrue(math.isfinite(metrics["worst_phase_margin_deg"]))
        self.assertTrue(math.isfinite(metrics["worst_iq_uA"]))
        for case in metrics["cases"].values():
            self.assertTrue(case["ac_fixture_ok"])


if __name__ == "__main__":
    unittest.main()
