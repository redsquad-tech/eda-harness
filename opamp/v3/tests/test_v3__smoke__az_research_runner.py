from __future__ import annotations

import json
import unittest

from opamp.v3.az_research_plan import build_az_research_plan
from opamp.v3.az_research_runner import build_executable_variants


class TestV3SmokeAzResearchRunner(unittest.TestCase):
    def test_all_plan_variants_have_runner_entries(self) -> None:
        plan = build_az_research_plan()
        executable = build_executable_variants()
        variant_ids = {variant.variant_id for hypothesis in plan for variant in hypothesis.variants}
        self.assertEqual(variant_ids, set(executable))

    def test_pre_mc_variants_are_runnable(self) -> None:
        executable = build_executable_variants()
        self.assertTrue(executable["az_h1_v1_cap200_shuntp10_freq200k"].runnable)
        self.assertTrue(executable["az_h2_v2_cap200_shuntp10_rtop600_freq200k"].runnable)
        self.assertTrue(executable["az_h3_v2_cap200_shuntp10_dead100ns"].runnable)

    def test_mc_variants_are_explicitly_marked_unavailable(self) -> None:
        executable = build_executable_variants()
        payload = {
            variant_id: {
                "runnable": item.runnable,
                "reason": item.unavailable_reason,
            }
            for variant_id, item in executable.items()
            if variant_id.startswith("az_h4_")
        }
        self.assertFalse(payload["az_h4_v1_mc_cap200_shuntp10_freq200k"]["runnable"])
        self.assertIn("MC bench", payload["az_h4_v1_mc_cap200_shuntp10_freq200k"]["reason"])
        json.dumps(payload)


if __name__ == "__main__":
    unittest.main()
