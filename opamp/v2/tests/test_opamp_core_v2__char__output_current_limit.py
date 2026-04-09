from __future__ import annotations

import unittest

from opamp.v2.opamp_core import run_output_current_limit_test
from opamp.v2.tests._helpers import BaseV2SimTest


@unittest.skip("Deferred: v2 currently validates only fast TT screens before current-limit characterization.")
class TestOpampCoreV2CharOutputCurrentLimit(BaseV2SimTest):
    def test_opamp_core_v2__char__output_current_limit(self) -> None:
        result = run_output_current_limit_test()
        metrics = result["metrics"]

        self.assertEqual(result["component"], "opamp_core")
        self.assertGreaterEqual(metrics["max_source_current_uA"], 0.0)
        self.assertGreaterEqual(metrics["max_sink_current_uA"], 0.0)


if __name__ == "__main__":
    unittest.main()
