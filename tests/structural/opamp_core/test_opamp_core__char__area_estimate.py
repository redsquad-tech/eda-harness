from __future__ import annotations

import sys
import unittest
from pathlib import Path

from components.opamp_core import run_area_estimate


ROOT = Path(__file__).resolve().parents[3]


class TestOpampCoreCharAreaEstimate(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(ROOT))

    def test_opamp_core__char__area_estimate(self) -> None:
        result = run_area_estimate()
        metrics = result["metrics"]

        self.assertEqual(result["component"], "opamp_core")
        self.assertEqual(result["category"], "char")
        self.assertGreater(metrics["transistor_area_um2"], 0.0)
        self.assertGreater(metrics["comp_cap_fF"], 0.0)
        self.assertGreater(metrics["total_device_count"], 0)


if __name__ == "__main__":
    unittest.main()
