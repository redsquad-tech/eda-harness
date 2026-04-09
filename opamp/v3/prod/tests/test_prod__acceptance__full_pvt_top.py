from __future__ import annotations

import unittest

from ._acceptance_report import assert_report_ok, full_pvt_top_rows


class TestV3ProdAcceptanceFullPvtTop(unittest.TestCase):
    def test_top_full_pvt_maximum_spec(self) -> None:
        assert_report_ok(self, "prod_full_pvt_top", full_pvt_top_rows)


if __name__ == "__main__":
    unittest.main()
