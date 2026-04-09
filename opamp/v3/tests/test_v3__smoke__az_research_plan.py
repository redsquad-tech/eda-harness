from __future__ import annotations

import json
import unittest

from opamp.v3.az_research_plan import build_az_research_plan, build_az_research_tests, render_markdown


class TestV3SmokeAzResearchPlan(unittest.TestCase):
    def test_hypothesis_ids_are_unique(self) -> None:
        plan = build_az_research_plan()
        ids = [item.hypothesis_id for item in plan]
        self.assertEqual(len(ids), len(set(ids)))

    def test_variant_ids_are_unique(self) -> None:
        plan = build_az_research_plan()
        variant_ids = [variant.variant_id for hyp in plan for variant in hyp.variants]
        self.assertEqual(len(variant_ids), len(set(variant_ids)))

    def test_contains_current_frontier_variants(self) -> None:
        plan = build_az_research_plan()
        variant_ids = {variant.variant_id for hyp in plan for variant in hyp.variants}
        self.assertIn("az_h1_v1_cap200_shuntp10_freq200k", variant_ids)
        self.assertIn("az_h2_v1_cap200_shuntp10_rtop600", variant_ids)

    def test_markdown_and_json_render(self) -> None:
        plan = build_az_research_plan()
        tests = build_az_research_tests()
        markdown = render_markdown(plan, tests)
        self.assertIn("AZ Research Plan", markdown)
        self.assertIn("az_h1", markdown)
        json.dumps([test.test_id for test in tests])
