from __future__ import annotations

import unittest

from opamp.v2.frontend_az import run_pedestal_zero_input_test, run_settling_in_phase_window_test
from opamp.v2.tests._helpers import BaseV2SimTest
from opamp.v2.tests.specs_frontend_az_v2 import PEDESTAL_UV_MAX, SETTLING_RESIDUE_UV_MAX


@unittest.skip("Deferred: frontend-only settling/pedestal contracts are still being redefined; product precision is checked at opamp_az_top.")
class TestFrontendAzV2BudgetPrecisionFrontend(BaseV2SimTest):
    def test_frontend_az_v2__budget__precision_frontend(self) -> None:
        pedestal = run_pedestal_zero_input_test()
        settling = run_settling_in_phase_window_test()

        self.assertEqual(pedestal["component"], "frontend_az")
        self.assertEqual(settling["component"], "frontend_az")
        self.assertLessEqual(pedestal["metrics"]["pedestal_uV"], PEDESTAL_UV_MAX)
        self.assertLessEqual(settling["metrics"]["settling_mid50_tail_uV"], SETTLING_RESIDUE_UV_MAX)


if __name__ == "__main__":
    unittest.main()
