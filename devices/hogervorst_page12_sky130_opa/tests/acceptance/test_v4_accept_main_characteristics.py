from pathlib import Path

from devices.hogervorst_page12_sky130_opa.measure import (
    V4OutputDriveTbParams,
    V4SupplyCurrentTbParams,
    run_open_loop_test,
    run_output_drive_test,
    run_supply_current_test,
)
from devices.hogervorst_page12_sky130_opa.tests._helpers import BaseV4SimTest, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_accept_main_characteristics_metrics.json")


ACCEPTANCE = {
    "vdd_nominal": 1.8,
    "drive_current_uA": 25.0,
    "rails_low_v": 0.0,
    "rails_high_v": 1.8,
    "aol_db_min": 0.0,
    "aol_db_max": 200.0,
    "gbw_hz_min": 1.0,
    "gbw_hz_max": 1e9,
    "phase_margin_deg_min": 0.0,
    "phase_margin_deg_max": 180.0,
    "gain_margin_db_min": 0.0,
    "gain_margin_db_max": 200.0,
    "iq_uA_min": 0.0,
    "iq_uA_max": 1e3,
}


class TestV4AcceptMainCharacteristics(BaseV4SimTest):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        open_loop = run_open_loop_test()["metrics"]
        enabled = run_supply_current_test(
            tb_params=V4SupplyCurrentTbParams(
                vdd=ACCEPTANCE["vdd_nominal"],
                en_v=ACCEPTANCE["vdd_nominal"],
                az_v=0.0,
                inf_v=ACCEPTANCE["vdd_nominal"],
            )
        )["metrics"]
        disabled = run_supply_current_test(
            tb_params=V4SupplyCurrentTbParams(
                vdd=ACCEPTANCE["vdd_nominal"],
                en_v=0.0,
                az_v=0.0,
                inf_v=0.0,
            )
        )["metrics"]
        source_25 = run_output_drive_test(
            tb_params=V4OutputDriveTbParams(
                vdd=ACCEPTANCE["vdd_nominal"],
                vin_target=0.9,
                load_current_uA=ACCEPTANCE["drive_current_uA"],
                direction="source",
            )
        )["metrics"]
        sink_25 = run_output_drive_test(
            tb_params=V4OutputDriveTbParams(
                vdd=ACCEPTANCE["vdd_nominal"],
                vin_target=0.9,
                load_current_uA=ACCEPTANCE["drive_current_uA"],
                direction="sink",
            )
        )["metrics"]

        cls.payload = {
            "acceptance": ACCEPTANCE,
            "open_loop": open_loop,
            "enabled": enabled,
            "disabled": disabled,
            "source_25uA": source_25,
            "sink_25uA": sink_25,
            "summary": {
                "disabled_to_enabled_ratio": float(disabled["iq_uA"]) / max(float(enabled["iq_uA"]), 1e-30),
                "source_25uA_vout_within_rails": (
                    ACCEPTANCE["rails_low_v"] <= float(source_25["vout_dc"]) <= ACCEPTANCE["rails_high_v"]
                ),
                "sink_25uA_vout_within_rails": (
                    ACCEPTANCE["rails_low_v"] <= float(sink_25["vout_dc"]) <= ACCEPTANCE["rails_high_v"]
                ),
                "enabled_vout_within_rails": (
                    ACCEPTANCE["rails_low_v"] <= float(enabled["vout_dc"]) <= ACCEPTANCE["rails_high_v"]
                ),
                "disabled_vout_within_rails": (
                    ACCEPTANCE["rails_low_v"] <= float(disabled["vout_dc"]) <= ACCEPTANCE["rails_high_v"]
                ),
            },
        }
        write_metrics_json(METRICS_PATH, cls.payload)

    def test_open_loop_gain_is_finite_and_in_range(self) -> None:
        value = float(self.payload["open_loop"]["aol_db"])
        self.assertFinite(value, "open_loop.aol_db must be finite")
        self.assertMetricBetween("aol_db", value, ACCEPTANCE["aol_db_min"], ACCEPTANCE["aol_db_max"])

    def test_gbw_is_finite_and_in_range(self) -> None:
        value = float(self.payload["open_loop"]["gbw_hz"])
        self.assertFinite(value, "open_loop.gbw_hz must be finite")
        self.assertMetricBetween("gbw_hz", value, ACCEPTANCE["gbw_hz_min"], ACCEPTANCE["gbw_hz_max"])

    def test_phase_margin_is_finite_and_in_range(self) -> None:
        value = float(self.payload["open_loop"]["phase_margin_deg"])
        self.assertFinite(value, "open_loop.phase_margin_deg must be finite")
        self.assertMetricBetween(
            "phase_margin_deg",
            value,
            ACCEPTANCE["phase_margin_deg_min"],
            ACCEPTANCE["phase_margin_deg_max"],
        )

    def test_gain_margin_is_finite_and_in_range(self) -> None:
        value = float(self.payload["open_loop"]["gain_margin_db"])
        self.assertFinite(value, "open_loop.gain_margin_db must be finite")
        self.assertMetricBetween(
            "gain_margin_db",
            value,
            ACCEPTANCE["gain_margin_db_min"],
            ACCEPTANCE["gain_margin_db_max"],
        )

    def test_enabled_supply_current_is_finite_and_positive(self) -> None:
        value = float(self.payload["enabled"]["iq_uA"])
        self.assertFinite(value, "enabled.iq_uA must be finite")
        self.assertMetricBetween("enabled.iq_uA", value, ACCEPTANCE["iq_uA_min"], ACCEPTANCE["iq_uA_max"])

    def test_disabled_supply_current_is_finite_and_non_negative(self) -> None:
        value = float(self.payload["disabled"]["iq_uA"])
        self.assertFinite(value, "disabled.iq_uA must be finite")
        self.assertMetricBetween("disabled.iq_uA", value, ACCEPTANCE["iq_uA_min"], ACCEPTANCE["iq_uA_max"])

    def test_enabled_output_bias_is_within_rails(self) -> None:
        value = float(self.payload["enabled"]["vout_dc"])
        self.assertFinite(value, "enabled.vout_dc must be finite")
        self.assertTrue(
            self.payload["summary"]["enabled_vout_within_rails"],
            f"enabled.vout_dc={value:.6g} must stay within [{ACCEPTANCE['rails_low_v']:.6g}, "
            f"{ACCEPTANCE['rails_high_v']:.6g}] V",
        )

    def test_disabled_output_bias_is_within_rails(self) -> None:
        value = float(self.payload["disabled"]["vout_dc"])
        self.assertFinite(value, "disabled.vout_dc must be finite")
        self.assertTrue(
            self.payload["summary"]["disabled_vout_within_rails"],
            f"disabled.vout_dc={value:.6g} must stay within [{ACCEPTANCE['rails_low_v']:.6g}, "
            f"{ACCEPTANCE['rails_high_v']:.6g}] V",
        )

    def test_source_drive_stays_within_rails(self) -> None:
        value = float(self.payload["source_25uA"]["vout_dc"])
        self.assertFinite(value, "source_25uA.vout_dc must be finite")
        self.assertTrue(
            self.payload["summary"]["source_25uA_vout_within_rails"],
            f"source_25uA.vout_dc={value:.6g} must stay within [{ACCEPTANCE['rails_low_v']:.6g}, "
            f"{ACCEPTANCE['rails_high_v']:.6g}] V under {ACCEPTANCE['drive_current_uA']:.6g} uA load",
        )

    def test_sink_drive_stays_within_rails(self) -> None:
        value = float(self.payload["sink_25uA"]["vout_dc"])
        self.assertFinite(value, "sink_25uA.vout_dc must be finite")
        self.assertTrue(
            self.payload["summary"]["sink_25uA_vout_within_rails"],
            f"sink_25uA.vout_dc={value:.6g} must stay within [{ACCEPTANCE['rails_low_v']:.6g}, "
            f"{ACCEPTANCE['rails_high_v']:.6g}] V under {ACCEPTANCE['drive_current_uA']:.6g} uA load",
        )

    def test_source_drive_pushes_output_higher_than_sink_drive(self) -> None:
        source_vout = float(self.payload["source_25uA"]["vout_dc"])
        sink_vout = float(self.payload["sink_25uA"]["vout_dc"])
        self.assertFinite(source_vout, "source_25uA.vout_dc must be finite")
        self.assertFinite(sink_vout, "sink_25uA.vout_dc must be finite")
        self.assertGreater(
            source_vout,
            sink_vout,
            f"Expected source drive to bias output above sink drive, got source={source_vout:.6g} V "
            f"and sink={sink_vout:.6g} V",
        )
