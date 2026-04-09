from __future__ import annotations

import unittest

from ._acceptance_report import assert_report_ok, load_sweep_rows


class TestV3ProdAcceptanceLoadSweep(unittest.TestCase):
    def test_load_sweep_maximum_spec(self) -> None:
        assert_report_ok(self, "prod_load_sweep", load_sweep_rows)


if __name__ == "__main__":
    unittest.main()
