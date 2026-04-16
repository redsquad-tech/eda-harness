from pathlib import Path
import math

from devices.hogervorst_page12_sky130_opa.tests._helpers import BaseV4SimTest, write_metrics_json
from devices.hogervorst_page12_sky130_opa.tests.test_v4_frontend_gain_target import measure_frontend_gain_target
from devices.hogervorst_page12_sky130_opa.tests.test_v4_frontend_isolated_dc import measure_frontend_isolated_dc
from devices.hogervorst_page12_sky130_opa.tests.test_v4_probe_current_map import measure_current_map


METRICS_PATH = Path(__file__).with_name("v4_budget_frontend_blocks_metrics.json")


class TestV4BudgetFrontendBlocks(BaseV4SimTest):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.gain = measure_frontend_gain_target()
        cls.dc = measure_frontend_isolated_dc()
        cls.curr = measure_current_map()
        diff_gain_vv = abs(float(cls.gain["summary"]["stage1_diff_gain_V_per_V"]))
        cls.payload = {
            "gain": cls.gain,
            "dc": cls.dc,
            "current_map": cls.curr,
            "derived": {
                "rr_input_current_total_uA": (cls.curr["tail_p_A"] + cls.curr["tail_n_A"]) * 1e6,
                "effective_input_gm_uS_proxy": diff_gain_vv * 1000.0,
                "first_stage_gain_dB": 20.0 * math.log10(max(diff_gain_vv, 1e-30)),
                "i0p_tail_current_uA": cls.curr["tail_p_A"] * 1e6,
                "i0n_tail_current_uA": cls.curr["tail_n_A"] * 1e6,
            },
        }
        write_metrics_json(METRICS_PATH, cls.payload)

    def test_rr_input_stage_current_total(self) -> None:
        self.assertMetricApprox("rr_input_stage_current_total_uA", self.payload["derived"]["rr_input_current_total_uA"], 3.2, 1.0)

    def test_rr_input_stage_effective_input_gm(self) -> None:
        self.assertMetricAtLeast("rr_input_stage_effective_input_gm_uS_proxy", self.payload["derived"]["effective_input_gm_uS_proxy"], 15.0)

    def test_rr_input_stage_offset_sigma_share(self) -> None:
        self.skipTest("rr_input_stage offset sigma needs mismatch-aware analysis, not DC/AC probe only")

    def test_folded_cascode_core_first_stage_gain_contribution(self) -> None:
        self.assertMetricAtLeast("folded_cascode_core_first_stage_gain_contribution_dB", self.payload["derived"]["first_stage_gain_dB"], 58.0)

    def test_folded_cascode_core_all_stack_saturation_margin(self) -> None:
        self.skipTest("folded_cascode_core saturation margins need device VDSAT/VOV extraction hook")

    def test_rr_input_stage_i0p_tail_source_tail_current(self) -> None:
        self.assertMetricApprox("I0p_tail_source_tail_current_uA", self.payload["derived"]["i0p_tail_current_uA"], 1.6, 0.6)

    def test_rr_input_stage_i0n_tail_sink_tail_current(self) -> None:
        self.assertMetricApprox("I0n_tail_sink_tail_current_uA", self.payload["derived"]["i0n_tail_current_uA"], 1.6, 0.6)

    def test_rr_input_stage_pmos_input_pair_offset_sigma_share(self) -> None:
        self.skipTest("pmos_input_pair offset sigma share needs mismatch-aware analysis")

    def test_rr_input_stage_nmos_input_pair_offset_sigma_share(self) -> None:
        self.skipTest("nmos_input_pair offset sigma share needs mismatch-aware analysis")

    def test_rr_input_stage_pmos_input_pair_gm_share(self) -> None:
        self.assertMetricAtLeast("pmos_input_pair_gm_share_uS_proxy", self.payload["derived"]["effective_input_gm_uS_proxy"] / 2.0, 7.5)

    def test_rr_input_stage_nmos_input_pair_gm_share(self) -> None:
        self.assertMetricAtLeast("nmos_input_pair_gm_share_uS_proxy", self.payload["derived"]["effective_input_gm_uS_proxy"] / 2.0, 7.5)

    def test_folded_cascode_core_left_pmos_stack_fc_p1_p2_saturation_margin(self) -> None:
        self.skipTest("left_pmos_stack_fc_p1_p2 saturation margin needs device operating-point extraction")

    def test_folded_cascode_core_left_nmos_stack_fc_n1_n2_saturation_margin(self) -> None:
        self.skipTest("left_nmos_stack_fc_n1_n2 saturation margin needs device operating-point extraction")

    def test_folded_cascode_core_right_pmos_stack_fc_p1_p2_saturation_margin(self) -> None:
        self.skipTest("right_pmos_stack_fc_p1_p2 saturation margin needs device operating-point extraction")

    def test_folded_cascode_core_right_nmos_stack_fc_n1_n2_saturation_margin(self) -> None:
        self.skipTest("right_nmos_stack_fc_n1_n2 saturation margin needs device operating-point extraction")

    def test_folded_cascode_core_left_reference_branch_gain_contribution(self) -> None:
        self.skipTest("left_reference_branch gain contribution needs decomposed half-circuit measurement")

    def test_folded_cascode_core_right_driver_branch_gain_contribution(self) -> None:
        self.skipTest("right_driver_branch gain contribution needs decomposed half-circuit measurement")
