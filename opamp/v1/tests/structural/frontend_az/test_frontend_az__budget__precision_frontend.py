from __future__ import annotations

import sys
import unittest
from pathlib import Path

from opamp.v1.frontend_az import (
    run_pedestal_zero_input_test,
    run_settling_in_phase_window_test,
)
from opamp.v1.tests.structural._helpers import init_sky130_install


ROOT = Path(__file__).resolve().parents[3]


class TestFrontendAzBudgetPrecisionFrontend(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(ROOT))
        init_sky130_install()

    def test_frontend_az__char__precision_frontend(self) -> None:
        pedestal = run_pedestal_zero_input_test()
        settling = run_settling_in_phase_window_test()

        self.assertEqual(pedestal["component"], "frontend_az")
        self.assertEqual(settling["component"], "frontend_az")
        self.assertEqual(pedestal["category"], "contract")
        self.assertEqual(settling["category"], "contract")
        self.assertIn("margin", pedestal)
        self.assertIn("margin", settling)
        self.assertIn("settling_mid50_tail_uV", settling["metrics"])

        self.assertGreaterEqual(pedestal["metrics"]["pedestal_uV"], 0.0)
        self.assertGreaterEqual(settling["metrics"]["settling_residue_uV"], 0.0)
        self.assertGreaterEqual(settling["metrics"]["settling_mid50_tail_uV"], 0.0)
        self.assertTrue(
            settling["metrics"]["settling_mid50_tail_uV"] <= settling["metrics"]["settling_residue_uV"],
            "Interior-window residue should not exceed the full-phase residue for the standalone frontend characterization",
        )


if __name__ == "__main__":
    unittest.main()
