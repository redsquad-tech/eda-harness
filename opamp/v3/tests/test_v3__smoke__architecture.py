from __future__ import annotations

import unittest

import hdl21 as h

from opamp.v3.architecture import ARCHITECTURE_EXPERIMENT, BLOCK_ROLES, DESIGN_RULES, TEST_MATRIX
from opamp.v3.frontend_az import FrontendAzParams, frontend_az, run_structural_checks as run_frontend_structural_checks
from opamp.v3.opamp_az_top import OpampAzTopParams, opamp_az_top, run_structural_checks as run_top_structural_checks
from opamp.v3.opamp_core import OpampCoreParams, opamp_core, run_structural_checks as run_core_structural_checks


class TestV3SmokeArchitecture(unittest.TestCase):
    def test_metadata(self) -> None:
        self.assertEqual(ARCHITECTURE_EXPERIMENT, "opamp_v3_clean_loop_redesign")
        self.assertGreaterEqual(len(BLOCK_ROLES), 3)
        self.assertGreaterEqual(len(DESIGN_RULES), 3)
        self.assertIn("opamp_core", TEST_MATRIX)
        self.assertIn("opamp_az_top", TEST_MATRIX)

    def test_generators_elaborate(self) -> None:
        core = h.elaborate(opamp_core(OpampCoreParams()))
        front = h.elaborate(frontend_az(FrontendAzParams()))
        top = h.elaborate(opamp_az_top(OpampAzTopParams()))
        self.assertTrue(core.name.startswith("OpampCoreV3"))
        self.assertTrue(front.name.startswith("FrontendAzV3"))
        self.assertTrue(top.name.startswith("OpampAzTopV3"))

    def test_structural_checks(self) -> None:
        self.assertTrue(all(run_core_structural_checks().values()))
        self.assertTrue(all(run_frontend_structural_checks().values()))
        self.assertTrue(all(run_top_structural_checks().values()))


if __name__ == "__main__":
    unittest.main()
