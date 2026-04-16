from pathlib import Path

from opamp.v4.measure import (
    V4OutputDriveTbParams,
    V4SupplyCurrentTbParams,
    run_open_loop_test,
    run_output_drive_test,
    run_supply_current_test,
)
from opamp.v4.tests._helpers import BaseV4SimTest, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_accept_spec_snapshot_metrics.json")


SPEC = {
    "aol_db_min": 80.0,
    "gbw_hz_min": 1e6,
    "phase_margin_deg_min": 30.0,
    "iq_enabled_uA_max": 10.0,
    "iq_disabled_uA_max": 0.015,  # 15 nA
    "drive_current_uA": 25.0,
}


class TestV4AcceptSpecSnapshot(BaseV4SimTest):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        open_loop = run_open_loop_test()["metrics"]
        enabled = run_supply_current_test(
            tb_params=V4SupplyCurrentTbParams(en_v=1.8, az_v=0.0, inf_v=1.8)
        )["metrics"]
        disabled = run_supply_current_test(
            tb_params=V4SupplyCurrentTbParams(en_v=0.0, az_v=0.0, inf_v=0.0)
        )["metrics"]
        source_25 = run_output_drive_test(
            tb_params=V4OutputDriveTbParams(load_current_uA=SPEC["drive_current_uA"], direction="source")
        )["metrics"]
        sink_25 = run_output_drive_test(
            tb_params=V4OutputDriveTbParams(load_current_uA=SPEC["drive_current_uA"], direction="sink")
        )["metrics"]

        cls.payload = {
            "spec": SPEC,
            "open_loop": open_loop,
            "enabled": enabled,
            "disabled": disabled,
            "source_25uA": source_25,
            "sink_25uA": sink_25,
            "summary": {
                "disabled_to_enabled_ratio": float(disabled["iq_uA"]) / max(float(enabled["iq_uA"]), 1e-30),
                "source_25uA_vout_within_rails": 0.0 <= float(source_25["vout_dc"]) <= 1.8,
                "sink_25uA_vout_within_rails": 0.0 <= float(sink_25["vout_dc"]) <= 1.8,
            },
        }
        write_metrics_json(METRICS_PATH, cls.payload)

    def test_aol_meets_spec(self) -> None:
        value = float(self.payload["open_loop"]["aol_db"])
        self.assertMetricGreater("aol_db", value, SPEC["aol_db_min"])

    def test_gbw_meets_spec(self) -> None:
        value = float(self.payload["open_loop"]["gbw_hz"])
        self.assertMetricGreater("gbw_hz", value, SPEC["gbw_hz_min"])

    def test_phase_margin_meets_spec(self) -> None:
        value = float(self.payload["open_loop"]["phase_margin_deg"])
        self.assertMetricGreater("phase_margin_deg", value, SPEC["phase_margin_deg_min"])

    def test_enabled_iq_meets_spec(self) -> None:
        value = float(self.payload["enabled"]["iq_uA"])
        self.assertMetricLess("iq_enabled_uA", value, SPEC["iq_enabled_uA_max"])

    def test_disabled_leakage_meets_spec(self) -> None:
        value = float(self.payload["disabled"]["iq_uA"])
        self.assertMetricLess("iq_disabled_uA", value, SPEC["iq_disabled_uA_max"])

    def test_source_25ua_probe_is_finite_and_within_rails(self) -> None:
        value = float(self.payload["source_25uA"]["vout_dc"])
        self.assertFinite(value, "source_25uA.vout_dc must be finite")
        self.assertTrue(
            self.payload["summary"]["source_25uA_vout_within_rails"],
            f"source_25uA.vout_dc={value:.6g} must stay within [0, 1.8] V under {SPEC['drive_current_uA']:.6g} uA load",
        )

    def test_sink_25ua_probe_is_finite_and_within_rails(self) -> None:
        value = float(self.payload["sink_25uA"]["vout_dc"])
        self.assertFinite(value, "sink_25uA.vout_dc must be finite")
        self.assertTrue(
            self.payload["summary"]["sink_25uA_vout_within_rails"],
            f"sink_25uA.vout_dc={value:.6g} must stay within [0, 1.8] V under {SPEC['drive_current_uA']:.6g} uA load",
        )
