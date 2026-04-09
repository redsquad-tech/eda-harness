from __future__ import annotations

import unittest

from ._acceptance_report import assert_report_ok, timing_mc_rows


class TestV3ProdAcceptanceTimingAndMc(unittest.TestCase):
    def test_timing_and_mc_maximum_spec(self) -> None:
        assert_report_ok(self, "prod_timing_and_mc", timing_mc_rows)


if __name__ == "__main__":
    unittest.main()
