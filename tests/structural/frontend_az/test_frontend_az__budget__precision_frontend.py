from __future__ import annotations

import sys
import unittest
from pathlib import Path

from components.frontend_az import (
    run_pedestal_zero_input_test,
    run_settling_in_phase_window_test,
)
from tests.structural._helpers import init_sky130_install
from tests.structural.frontend_az.specs_frontend_az import (
    PEDESTAL_UV_MAX,
    SETTLING_RESIDUE_UV_MAX,
)


ROOT = Path(__file__).resolve().parents[3]


class TestFrontendAzBudgetPrecisionFrontend(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(ROOT))
        init_sky130_install()

    def test_frontend_az__budget__precision_frontend(self) -> None:
        pedestal = run_pedestal_zero_input_test()
        settling = run_settling_in_phase_window_test()

        self.assertEqual(pedestal["component"], "frontend_az")
        self.assertEqual(settling["component"], "frontend_az")
        self.assertEqual(pedestal["category"], "contract")
        self.assertEqual(settling["category"], "contract")
        self.assertIn("margin", pedestal)
        self.assertIn("margin", settling)

        self.assertLessEqual(
            pedestal["metrics"]["pedestal_uV"],
            PEDESTAL_UV_MAX,
            "Spec requires pedestal-equivalent input error <= 50 uV at nominal",
        )
        self.assertLessEqual(
            settling["metrics"]["settling_residue_uV"],
            SETTLING_RESIDUE_UV_MAX,
            "Spec requires hold/ phase-window residue contribution <= 30 uV per AZ cycle",
        )


if __name__ == "__main__":
    unittest.main()
