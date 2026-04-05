from __future__ import annotations

import sys
import unittest
from pathlib import Path

from components.opamp_az_top import run_noise_and_offset_test
from tests.structural._helpers import init_sky130_install
from tests.structural.opamp_az_top.specs_opamp_az_top import (
    PEDESTAL_UV_MAX,
    RESIDUAL_OFFSET_UV_MAX,
    SETTLING_RESIDUE_UV_MAX,
)


ROOT = Path(__file__).resolve().parents[3]


class TestOpampAzTopBudgetPrecisionPpa(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(ROOT))
        init_sky130_install()

    def test_opamp_az_top__budget__precision_ppa(self) -> None:
        noise_and_offset = run_noise_and_offset_test()
        metrics = noise_and_offset["metrics"]

        self.assertEqual(noise_and_offset["component"], "opamp_az_top")
        self.assertEqual(noise_and_offset["category"], "contract")
        self.assertIn("residual_offset_uV", metrics)
        self.assertIn("pedestal_uV", metrics)
        self.assertIn("settling_residue_uV", metrics)

        self.assertLessEqual(metrics["residual_offset_uV"], RESIDUAL_OFFSET_UV_MAX)
        self.assertLessEqual(metrics["pedestal_uV"], PEDESTAL_UV_MAX)
        self.assertLessEqual(metrics["settling_residue_uV"], SETTLING_RESIDUE_UV_MAX)


if __name__ == "__main__":
    unittest.main()
