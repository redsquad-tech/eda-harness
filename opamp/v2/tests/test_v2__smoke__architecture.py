from __future__ import annotations

from opamp.v2.architecture import ARCHITECTURE_EXPERIMENT, BLOCK_ROLES, TEST_MATRIX
from opamp.v2.tests._helpers import BaseV2Test


class TestV2SmokeArchitecture(BaseV2Test):
    def test_v2_architecture_metadata_exists(self) -> None:
        self.assertEqual(ARCHITECTURE_EXPERIMENT, "opamp_v2_systematic_redesign")
        self.assertGreaterEqual(len(BLOCK_ROLES), 7)
        self.assertIn("opamp_core", TEST_MATRIX)
        self.assertIn("opamp_az_top", TEST_MATRIX)
        self.assertIn("budget__open_loop_spec", TEST_MATRIX["opamp_core"])
        self.assertIn("budget__precision_ppa", TEST_MATRIX["opamp_az_top"])


if __name__ == "__main__":
    unittest.main()
