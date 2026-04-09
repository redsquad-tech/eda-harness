from __future__ import annotations

import unittest

from opamp.v3.current_experiment import _serialize_params, family_a_cases, family_g_cases, family_h_cases, family_j_cases, family_s_cases
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

    def test_family_s_cases_exist(self) -> None:
        cases = family_s_cases()
        names = [case.name for case in cases]
        self.assertIn("baseline", names)
        self.assertIn("S3_stage2_n_smaller_longer", names)
        self.assertIn("S6_stage2_n_smaller_longer_ccomp_up", names)
        self.assertEqual(len(names), len(set(names)))

    def test_family_g_cases_exist(self) -> None:
        cases = family_g_cases()
        names = [case.name for case in cases]
        self.assertIn("baseline", names)
        self.assertIn("G1B_tail35_bias3p0_lin3p5", names)
        self.assertIn("G1D_tail35_bias3p5_lin3p5", names)
        self.assertEqual(len(names), len(set(names)))

    def test_family_h_cases_exist(self) -> None:
        cases = family_h_cases()
        names = [case.name for case in cases]
        self.assertIn("baseline", names)
        self.assertIn("H2_stage2n18_l8", names)
        self.assertIn("H4_stage2n18_l8_p10", names)
        self.assertEqual(len(names), len(set(names)))

    def test_family_j_cases_exist(self) -> None:
        cases = family_j_cases()
        names = [case.name for case in cases]
        self.assertIn("baseline", names)
        self.assertIn("J1_lin4p0", names)
        self.assertIn("J4_lin4p0_stage2p10", names)
        self.assertEqual(len(names), len(set(names)))


if __name__ == "__main__":
    unittest.main()
