from pathlib import Path

from devices.hogervorst_page12_sky130_opa.measure import run_open_loop_test, run_supply_current_test, V4SupplyCurrentTbParams
from devices.hogervorst_page12_sky130_opa.opamp import NeuronOaParams
from devices.hogervorst_page12_sky130_opa.tests._helpers import BaseV4SimTest, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_budget_comp_wrapper_blocks_metrics.json")


class TestV4BudgetCompWrapperBlocks(BaseV4SimTest):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.params = NeuronOaParams()
        cls.open_loop = run_open_loop_test()["metrics"]
        cls.enabled = run_supply_current_test(tb_params=V4SupplyCurrentTbParams(en_v=1.8, az_v=0.0, inf_v=1.8))["metrics"]
        cls.disabled = run_supply_current_test(tb_params=V4SupplyCurrentTbParams(en_v=0.0, az_v=0.0, inf_v=0.0))["metrics"]
        cls.payload = {
            "open_loop": cls.open_loop,
            "enabled": cls.enabled,
            "disabled": cls.disabled,
            "params": {
                "cc_each_pF": cls.params.output.cc * 1e12,
                "rc_each_kOhm": cls.params.output.rc / 1000.0,
                "tg_wp": cls.params.tg.wp,
                "tg_wn": cls.params.tg.wn,
            },
        }
        write_metrics_json(METRICS_PATH, cls.payload)

    def test_compensation_network_compensation_cap_total(self) -> None:
        self.assertMetricBetween("compensation_cap_total_pF", self.payload["params"]["cc_each_pF"] * 2.0, 0.5, 0.7)

    def test_compensation_network_phase_margin_contribution_target(self) -> None:
        self.assertMetricAtLeast("phase_margin_contribution_target_deg", float(self.open_loop["phase_margin_deg"]), 60.0)

    def test_compensation_network_top_rccc_branch_compensation_cap(self) -> None:
        self.assertMetricBetween("top_RcCc_branch_compensation_cap_pF", self.payload["params"]["cc_each_pF"], 0.25, 0.35)

    def test_compensation_network_bottom_rccc_branch_compensation_cap(self) -> None:
        self.assertMetricBetween("bottom_RcCc_branch_compensation_cap_pF", self.payload["params"]["cc_each_pF"], 0.25, 0.35)

    def test_compensation_network_top_rccc_branch_nulling_resistor_seed(self) -> None:
        self.assertMetricBetween("top_RcCc_branch_nulling_resistor_seed_kOhm", self.payload["params"]["rc_each_kOhm"], 15.0, 40.0)

    def test_compensation_network_bottom_rccc_branch_nulling_resistor_seed(self) -> None:
        self.assertMetricBetween("bottom_RcCc_branch_nulling_resistor_seed_kOhm", self.payload["params"]["rc_each_kOhm"], 15.0, 40.0)

    def test_wrapper_control_test_inference_mode_overhead_current(self) -> None:
        self.skipTest("wrapper inference overhead current needs core-vs-wrapper current decomposition")

    def test_wrapper_control_test_disabled_leakage_total(self) -> None:
        self.assertMetricAtMost("wrapper_control_test_disabled_leakage_total_nA", float(self.disabled["iq_uA"]) * 1000.0, 6.0)

    def test_wrapper_control_test_aux_switch_ron(self) -> None:
        self.skipTest("aux_switch_ron needs dedicated switch on-resistance bench")

    def test_wrapper_control_test_aux_switch_off_leakage_each(self) -> None:
        self.skipTest("aux_switch_off_leakage_each needs dedicated switch leakage bench")

    def test_wrapper_control_test_vout_test_switch_ron(self) -> None:
        self.skipTest("vout_test_switch_ron needs dedicated switch on-resistance bench")

    def test_wrapper_control_test_vout_test_switch_off_leakage(self) -> None:
        self.skipTest("vout_test_switch_off_leakage needs dedicated switch leakage bench")

    def test_wrapper_control_test_mode_decode_and_latches_inference_overhead_current(self) -> None:
        self.skipTest("mode_decode_and_latches_inference_overhead_current needs wrapper current decomposition")

    def test_wrapper_control_test_test_chain_keepalive_inference_overhead_current(self) -> None:
        self.skipTest("test_chain_keepalive_inference_overhead_current needs wrapper current decomposition")

    def test_wrapper_control_test_output_isolation_switch_off_leakage(self) -> None:
        self.skipTest("output_isolation_switch_off_leakage needs dedicated switch leakage bench")

    def test_wrapper_control_test_agnd_to_vbase_switch_ron(self) -> None:
        self.skipTest("agnd_to_vbase_switch_ron needs dedicated switch on-resistance bench")

    def test_wrapper_control_test_agnd_to_vbase_switch_off_leakage(self) -> None:
        self.skipTest("agnd_to_vbase_switch_off_leakage needs dedicated switch leakage bench")

    def test_wrapper_control_test_avdd_to_vfeed_switch_ron(self) -> None:
        self.skipTest("avdd_to_vfeed_switch_ron needs dedicated switch on-resistance bench")

    def test_wrapper_control_test_avdd_to_vfeed_switch_off_leakage(self) -> None:
        self.skipTest("avdd_to_vfeed_switch_off_leakage needs dedicated switch leakage bench")

    def test_wrapper_control_test_vout_to_vtest_switch_ron(self) -> None:
        self.skipTest("vout_to_vtest_switch_ron needs dedicated switch on-resistance bench")

    def test_wrapper_control_test_vout_to_vtest_switch_off_leakage(self) -> None:
        self.skipTest("vout_to_vtest_switch_off_leakage needs dedicated switch leakage bench")
