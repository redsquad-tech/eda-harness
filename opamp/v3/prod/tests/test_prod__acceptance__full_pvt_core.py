from __future__ import annotations

import unittest

from ._acceptance_report import assert_report_ok, full_pvt_core_rows


class TestV3ProdAcceptanceFullPvtCore(unittest.TestCase):
    def test_core_full_pvt_maximum_spec(self) -> None:
        assert_report_ok(self, "prod_full_pvt_core", full_pvt_core_rows)


if __name__ == "__main__":
    unittest.main()
