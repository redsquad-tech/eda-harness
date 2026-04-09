import unittest
from ._acceptance_report import assert_report_ok, reduced_acceptance_rows


class TestV3ProdAcceptanceMaximumSpec(unittest.TestCase):
    def test_reduced_acceptance_maximum_spec(self) -> None:
        assert_report_ok(self, "prod_reduced_acceptance", reduced_acceptance_rows)


if __name__ == "__main__":
    unittest.main()
