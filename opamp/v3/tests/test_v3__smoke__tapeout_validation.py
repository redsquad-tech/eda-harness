from __future__ import annotations

import json
import unittest

from opamp.v3.tapeout_validation import build_tapeout_validation_plan, render_markdown
from opamp.v3.tests._helpers import BaseV3Test


class TestV3SmokeTapeoutValidation(BaseV3Test):
    def test_plan_has_unique_case_ids_and_filenames(self) -> None:
        plan = build_tapeout_validation_plan()
        case_ids = [case.case_id for case in plan]
        filenames = [case.filename for case in plan]
        self.assertEqual(len(case_ids), len(set(case_ids)))
        self.assertEqual(len(filenames), len(set(filenames)))

    def test_plan_contains_customer_critical_categories(self) -> None:
        plan = build_tapeout_validation_plan()
        categories = {case.category for case in plan}
        self.assertTrue({"contract", "budget", "pvt", "mc", "pex"}.issubset(categories))

    def test_markdown_renders(self) -> None:
        plan = build_tapeout_validation_plan()
        markdown = render_markdown(plan)
        self.assertIn("Tapeout Validation Test Plan", markdown)
        self.assertIn("test_opamp_az_top__mc__residual_offset.py", markdown)
        self.assertIn("test_opamp_az_top__pex__open_loop.py", markdown)

    def test_status_values_are_expected(self) -> None:
        plan = build_tapeout_validation_plan()
        statuses = {case.implementation_status for case in plan}
        self.assertEqual(statuses, {"v1_available", "planned", "v3_available"})
        json.dumps([case.case_id for case in plan])


if __name__ == "__main__":
    unittest.main()
