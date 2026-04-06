from __future__ import annotations

import sys
import unittest
from pathlib import Path

from components.opamp_core import run_output_current_limit_test
from tests.structural._helpers import init_sky130_install
ROOT = Path(__file__).resolve().parents[3]


class TestOpampCoreCharOutputCurrentLimit(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(ROOT))
        init_sky130_install()

    def test_opamp_core__char__output_current_limit(self) -> None:
        result = run_output_current_limit_test()
        metrics = result["metrics"]

        self.assertEqual(result["component"], "opamp_core")
        self.assertEqual(result["category"], "char")
        self.assertIn("max_source_current_uA", metrics)
        self.assertIn("max_sink_current_uA", metrics)
        self.assertGreaterEqual(metrics["max_source_current_uA"], 0.0)
        self.assertGreaterEqual(metrics["max_sink_current_uA"], 0.0)
        self.assertGreaterEqual(metrics["compliant_high_v"], metrics["compliant_low_v"])


if __name__ == "__main__":
    unittest.main()
