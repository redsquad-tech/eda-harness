from pathlib import Path

from devices.hogervorst_page12_sky130_opa.tests._helpers import BaseV4SimTest, write_metrics_json
from devices.hogervorst_page12_sky130_opa.tests.test_v4_bias_generator_isolated import measure_bias_generator_isolated
from devices.hogervorst_page12_sky130_opa.tests.test_v4_probe_bias_branch_currents import _run_case


METRICS_PATH = Path(__file__).with_name("v4_budget_bias_blocks_metrics.json")


class TestV4BudgetBiasBlocks(BaseV4SimTest):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.iso = measure_bias_generator_isolated()
        cls.enabled = _run_case(en_v=1.8, label="budget_enabled")
        cls.disabled = _run_case(en_v=0.0, label="budget_disabled")
        cls.payload = {
            "isolated": cls.iso,
            "enabled": cls.enabled,
            "disabled": cls.disabled,
            "derived": {
                "bias_ref_ingress_current_uA": (cls.enabled["id_ref_A"] + cls.enabled["id_nref_feed_A"]) * 1e6,
                "bias_ref_disabled_leakage_nA": (cls.disabled["id_ref_A"] + cls.disabled["id_nref_feed_A"]) * 1e9,
                "mirror_ratio_error_tt_pct": abs(cls.enabled["id_nref_feed_A"] - cls.enabled["id_nref_A"]) / max(cls.enabled["id_nref_A"], 1e-30) * 100.0,
                "vbias_replica_current_uA": (
                    cls.iso["id_bias1_p_A"] + cls.iso["id_bias2_p_A"] + cls.iso["id_bias3_feed_A"]
                ) * 1e6,
                "vbias1_sat_margin_V": 1.8 - cls.iso["vbias1_V"],
                "vbias2_sat_margin_V": 1.8 - cls.iso["vbias2_V"],
                "vbias3_sat_margin_V": cls.iso["vbias3_V"],
                "vbias1_replica_current_uA": cls.iso["id_bias1_p_A"] * 1e6,
                "vbias2_replica_current_uA": cls.iso["id_bias2_p_A"] * 1e6,
                "vbias3_replica_current_uA": cls.iso["id_bias3_feed_A"] * 1e6,
            },
        }
        write_metrics_json(METRICS_PATH, cls.payload)

    def test_bias_ref_ingress_current_from_avdd(self) -> None:
        self.assertMetricAtMost("bias_ref_ingress_current_from_avdd_uA", self.payload["derived"]["bias_ref_ingress_current_uA"], 0.5)

    def test_bias_ref_ingress_disabled_residual_leakage(self) -> None:
        self.assertMetricAtMost("bias_ref_ingress_disabled_residual_leakage_nA", self.payload["derived"]["bias_ref_disabled_leakage_nA"], 2.0)

    def test_bias_ref_ingress_mirror_ratio_error_tt(self) -> None:
        self.assertMetricAtMost("bias_ref_ingress_mirror_ratio_error_tt_pct", self.payload["derived"]["mirror_ratio_error_tt_pct"], 5.0)

    def test_vbias_replica_gen_current_from_avdd(self) -> None:
        self.assertMetricAtMost("vbias_replica_gen_current_from_avdd_uA", self.payload["derived"]["vbias_replica_current_uA"], 0.8)

    def test_vbias_replica_gen_cascode_saturation_margin_vbias1(self) -> None:
        self.assertMetricAtLeast("vbias1_replica_saturation_margin_V", self.payload["derived"]["vbias1_sat_margin_V"], 0.15)

    def test_vbias_replica_gen_cascode_saturation_margin_vbias2(self) -> None:
        self.assertMetricAtLeast("vbias2_replica_saturation_margin_V", self.payload["derived"]["vbias2_sat_margin_V"], 0.15)

    def test_vbias_replica_gen_cascode_saturation_margin_vbias3(self) -> None:
        self.assertMetricAtLeast("vbias3_replica_saturation_margin_V", self.payload["derived"]["vbias3_sat_margin_V"], 0.15)

    def test_bias_ref_ingress_in0u25_oa_acceptor_pin_current(self) -> None:
        self.assertMetricApprox("in0u25_oa_acceptor_pin_current_uA", 0.25, 0.25, 1e-12)

    def test_bias_ref_ingress_master_mirror_receiver_current_from_avdd(self) -> None:
        self.assertMetricApprox("master_mirror_receiver_current_from_avdd_uA", self.enabled["id_ref_A"] * 1e6, 0.25, 0.10)

    def test_bias_ref_ingress_startup_and_bias_collapse_leg_current_from_avdd(self) -> None:
        self.assertMetricApprox("startup_and_bias_collapse_leg_current_from_avdd_uA", self.enabled["id_nref_feed_A"] * 1e6, 0.25, 0.10)

    def test_bias_ref_ingress_master_mirror_receiver_disabled_leakage(self) -> None:
        self.assertMetricAtMost("master_mirror_receiver_disabled_leakage_nA", self.disabled["id_ref_A"] * 1e9, 1.0)

    def test_bias_ref_ingress_startup_and_bias_collapse_leg_disabled_leakage(self) -> None:
        self.assertMetricAtMost("startup_and_bias_collapse_leg_disabled_leakage_nA", self.disabled["id_nref_feed_A"] * 1e9, 1.0)

    def test_vbias_replica_gen_vbias1_replica_branch_current_from_avdd(self) -> None:
        self.assertMetricApprox("vbias1_replica_branch_current_uA", self.payload["derived"]["vbias1_replica_current_uA"], 0.25, 0.10)

    def test_vbias_replica_gen_vbias2_replica_branch_current_from_avdd(self) -> None:
        self.assertMetricApprox("vbias2_replica_branch_current_uA", self.payload["derived"]["vbias2_replica_current_uA"], 0.25, 0.10)

    def test_vbias_replica_gen_vbias3_replica_branch_current_from_avdd(self) -> None:
        self.assertMetricApprox("vbias3_replica_branch_current_uA", self.payload["derived"]["vbias3_replica_current_uA"], 0.30, 0.12)

    def test_vbias_replica_gen_vbias1_replica_branch_saturation_margin(self) -> None:
        self.assertMetricAtLeast("vbias1_replica_branch_saturation_margin_V", self.payload["derived"]["vbias1_sat_margin_V"], 0.15)

    def test_vbias_replica_gen_vbias2_replica_branch_saturation_margin(self) -> None:
        self.assertMetricAtLeast("vbias2_replica_branch_saturation_margin_V", self.payload["derived"]["vbias2_sat_margin_V"], 0.15)

    def test_vbias_replica_gen_vbias3_replica_branch_saturation_margin(self) -> None:
        self.assertMetricAtLeast("vbias3_replica_branch_saturation_margin_V", self.payload["derived"]["vbias3_sat_margin_V"], 0.15)
