from __future__ import annotations

import unittest

from opamp.v3.current_experiment import _serialize_params, family_a_cases
from opamp.v3.tests._helpers import BaseV3Test


class TestV3SmokeCurrentExperiment(BaseV3Test):
    def test_family_a_cases_exist(self) -> None:
        cases = family_a_cases()
        names = [case.name for case in cases]
        self.assertIn("baseline", names)
        self.assertIn("A1_tail_switch_weaker_longer", names)
        self.assertIn("A2_tail_switch_stack2", names)
        self.assertIn("A3_tail_switch_stack3", names)
        self.assertEqual(len(names), len(set(names)))

    def test_case_params_serialize(self) -> None:
        case = family_a_cases()[0]
        payload = _serialize_params(case.params)
        self.assertIn("w_tail_sw", payload)
        self.assertIn("tail_switch_stack", payload)
        self.assertGreaterEqual(payload["tail_switch_stack"], 1)


if __name__ == "__main__":
    unittest.main()
