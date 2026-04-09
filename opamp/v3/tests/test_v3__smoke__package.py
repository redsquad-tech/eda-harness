from __future__ import annotations

import unittest

from opamp import v3


class TestV3SmokePackage(unittest.TestCase):
    def test_v3_exports(self) -> None:
        self.assertTrue(hasattr(v3, "ARCHITECTURE_EXPERIMENT"))
        self.assertTrue(hasattr(v3, "BLOCK_ROLES"))
        self.assertTrue(hasattr(v3, "TEST_MATRIX"))
        self.assertTrue(hasattr(v3, "opamp_core_v3"))
        self.assertTrue(hasattr(v3, "frontend_az_v3"))
        self.assertTrue(hasattr(v3, "opamp_az_top_v3"))


if __name__ == "__main__":
    unittest.main()
