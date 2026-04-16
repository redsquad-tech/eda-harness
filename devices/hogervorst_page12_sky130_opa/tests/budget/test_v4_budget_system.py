from pathlib import Path

from devices.hogervorst_page12_sky130_opa.measure import (
    V4OpenLoopTbParams,
    V4OutputDriveTbParams,
    V4SupplyCurrentTbParams,
    run_open_loop_test,
    run_output_drive_test,
    run_supply_current_test,
)
from devices.hogervorst_page12_sky130_opa.tests._helpers import BaseV4SimTest, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_budget_system_metrics.json")


class TestV4BudgetSystem(BaseV4SimTest):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.open_loop_tb = V4OpenLoopTbParams()
        cls.enabled_tb = V4SupplyCurrentTbParams(en_v=1.8, az_v=0.0, inf_v=1.8)
        cls.cal_tb = V4SupplyCurrentTbParams(en_v=1.8, az_v=1.8, inf_v=0.0)
        cls.disabled_tb = V4SupplyCurrentTbParams(en_v=0.0, az_v=0.0, inf_v=0.0)
        cls.drive_source_tb = V4OutputDriveTbParams(load_current_uA=35.0, direction="source")
        cls.drive_sink_tb = V4OutputDriveTbParams(load_current_uA=35.0, direction="sink")

        cls.open_loop = run_open_loop_test(tb_params=cls.open_loop_tb)["metrics"]
        cls.enabled = run_supply_current_test(tb_params=cls.enabled_tb)["metrics"]
        cls.cal = run_supply_current_test(tb_params=cls.cal_tb)["metrics"]
        cls.disabled = run_supply_current_test(tb_params=cls.disabled_tb)["metrics"]
        cls.drive_source = run_output_drive_test(tb_params=cls.drive_source_tb)["metrics"]
        cls.drive_sink = run_output_drive_test(tb_params=cls.drive_sink_tb)["metrics"]

        cls.payload = {
            "tb": {
                "open_loop": cls.open_loop_tb.__dict__,
                "enabled": cls.enabled_tb.__dict__,
                "calibration": cls.cal_tb.__dict__,
                "disabled": cls.disabled_tb.__dict__,
                "drive_source": cls.drive_source_tb.__dict__,
                "drive_sink": cls.drive_sink_tb.__dict__,
            },
            "open_loop": cls.open_loop,
            "enabled": cls.enabled,
            "calibration": cls.cal,
            "disabled": cls.disabled,
            "drive_source_35uA": cls.drive_source,
            "drive_sink_35uA": cls.drive_sink,
            "derived": {
                "enabled_reserve_uA": 10.0 - float(cls.enabled["iq_uA"]),
                "source_headroom_V": 1.8 - float(cls.drive_source["vout_dc"]),
                "sink_headroom_V": float(cls.drive_sink["vout_dc"]),
            },
        }
        write_metrics_json(METRICS_PATH, cls.payload)

    def test_supply_voltage_nominal_retg(self) -> None:
        self.assertMetricApprox("supply_voltage_nominal_retg_V", self.open_loop_tb.vdd, 1.8, 1e-12)

    def test_in0u25_oa_ref_current_nominal(self) -> None:
        self.assertMetricApprox("in0u25_oa_ref_current_nominal_nA", self.open_loop_tb.iref_uA * 1000.0, 250.0, 1e-9)

    def test_in0u25_oa_ref_current_accepted_range(self) -> None:
        self.assertMetricBetween("in0u25_oa_ref_current_accepted_range_nA", self.open_loop_tb.iref_uA * 1000.0, 200.0, 300.0)

    def test_iq_inference_internal_planned(self) -> None:
        self.assertMetricAtMost("iq_inference_internal_planned_uA", float(self.enabled["iq_uA"]), 8.0)

    def test_iq_inference_internal_reserve(self) -> None:
        self.assertMetricAtLeast("iq_inference_internal_reserve_uA", float(self.payload["derived"]["enabled_reserve_uA"]), 2.0)

    def test_iq_inference_internal_budget_total(self) -> None:
        self.assertMetricAtMost("iq_inference_internal_budget_total_uA", float(self.enabled["iq_uA"]), 10.0)

    def test_iq_calibration_planned(self) -> None:
        self.assertMetricAtMost("iq_calibration_planned_uA", float(self.cal["iq_uA"]), 8.5)

    def test_iq_calibration_budget_total(self) -> None:
        self.assertMetricAtMost("iq_calibration_budget_total_uA", float(self.cal["iq_uA"]), 10.0)

    def test_disabled_leakage_total_target(self) -> None:
        self.assertMetricAtMost("disabled_leakage_total_target_nA", float(self.disabled["iq_uA"]) * 1000.0, 10.0)

    def test_open_loop_gain_target(self) -> None:
        self.assertMetricAtLeast("open_loop_gain_target_dB", float(self.open_loop["aol_db"]), 84.0)

    def test_gain_bandwidth_target(self) -> None:
        self.assertMetricAtLeast("gain_bandwidth_target_MHz", float(self.open_loop["gbw_hz"]) / 1e6, 1.3)

    def test_phase_margin_target(self) -> None:
        self.assertMetricAtLeast("phase_margin_target_deg", float(self.open_loop["phase_margin_deg"]), 60.0)

    def test_gain_margin_target(self) -> None:
        self.skipTest("gain_margin_target has no measurement hook yet in v4 AC testbench")

    def test_psrr_target(self) -> None:
        self.skipTest("psrr_target has no dedicated VDD injection measurement yet")

    def test_load_capacitance_supported(self) -> None:
        self.assertMetricApprox("load_capacitance_supported_pF", self.open_loop_tb.c_load * 1e12, 1.0, 1e-12)

    def test_output_current_target(self) -> None:
        self.assertMetricBetween("output_current_target_uA_source", self.drive_source_tb.load_current_uA, -35.0, 35.0)
        self.assertMetricBetween("output_current_target_uA_sink", -self.drive_sink_tb.load_current_uA, -35.0, 35.0)

    def test_output_headroom_to_rails_target_upper(self) -> None:
        self.assertMetricAtMost("output_headroom_to_rails_target_upper_V", float(self.payload["derived"]["source_headroom_V"]), 0.08)

    def test_output_headroom_to_rails_target_lower(self) -> None:
        self.assertMetricAtMost("output_headroom_to_rails_target_lower_V", float(self.payload["derived"]["sink_headroom_V"]), 0.08)

    def test_offset_after_cal_target_abs(self) -> None:
        self.skipTest("offset_after_cal_target_abs requires calibration/offset measurement bench")

    def test_offset_sigma_target(self) -> None:
        self.skipTest("offset_sigma_target requires mismatch/Monte-Carlo flow, not present in current v4 testbench")
