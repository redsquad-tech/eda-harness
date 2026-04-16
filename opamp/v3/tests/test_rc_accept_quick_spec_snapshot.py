from __future__ import annotations

import json
import math
import traceback
from pathlib import Path

import hdl21 as h

from opamp.v3.measure_core import (
    OpampCoreDisabledTbParams,
    OpampCoreFollowerTbParams,
    OpampCoreOpenLoopTbParams,
    run_disabled_leakage_shutdown_fixture_test,
    run_input_offset_monte_carlo,
    run_input_referred_offset_test,
    run_open_loop_test,
    run_output_swing_test,
)
from opamp.v3.specs import OpampAzV3TargetSpec
from opamp.v3.tests._helpers import BaseV3SimTest, build_core_params, reset_metrics_file, write_metrics_json


METRICS_PATH = Path(__file__).with_name("rc_accept_quick_spec_snapshot_metrics.json")


def _status(value: float, predicate: bool) -> str:
    if not math.isfinite(value):
        return "unknown"
    return "pass" if predicate else "fail"


class TestRcAcceptQuickSpecSnapshot(BaseV3SimTest):
    def test_quick_spec_snapshot(self) -> None:
        reset_metrics_file(METRICS_PATH)
        try:
            spec = OpampAzV3TargetSpec()
            params = build_core_params(c_comp=2.7e-12, r_comp_z=1e5)

            open_loop_tb = OpampCoreOpenLoopTbParams(
                vdd=1.8,
                c_load=1e-12,
                r_probe=1e12,
                v_cm=0.9,
                dc_v_diff=100e-6,
                f_start=1.0,
                f_stop=1e8,
                npts=20,
                temp_c=27.0,
            )
            follower_tb = OpampCoreFollowerTbParams(
                vdd=1.8,
                c_load=1e-12,
                r_probe=1e12,
                vout_low_target=0.1,
                vout_high_target=1.6,
                vout_mid_target=0.9,
                drive_current_uA=20.0,
                f_start=1.0,
                f_stop=1e8,
                npts=20,
                temp_c=27.0,
            )
            disabled_tb = OpampCoreDisabledTbParams(vdd=1.8, c_load=1e-12, r_probe=1e12, v_cm=0.9, temp_c=27.0)

            corners = {
                "TT": h.pdk.Corner.TYP,
                "FF": h.pdk.Corner.FAST,
                "SS": h.pdk.Corner.SLOW,
            }
            open_loop = {}
            for label, corner in corners.items():
                open_loop[label] = run_open_loop_test(params, open_loop_tb, corner=corner)["metrics"]

            swing = run_output_swing_test(params, follower_tb, corner=h.pdk.Corner.TYP)["metrics"]
            leakage = run_disabled_leakage_shutdown_fixture_test(params, disabled_tb, corner=h.pdk.Corner.TYP)["metrics"]
            offset = run_input_referred_offset_test(params, follower_tb, corner=h.pdk.Corner.TYP)["metrics"]
            mc = run_input_offset_monte_carlo(params, follower_tb, samples=8, model_section="tt_mm")["metrics"]

            summary = {
                "open_loop": open_loop,
                "swing": swing,
                "leakage": leakage,
                "offset": offset,
                "offset_mc": mc,
                "status": {
                    "tt_aol": _status(float(open_loop["TT"]["aol_db"]), float(open_loop["TT"]["aol_db"]) >= spec.aol_db_min),
                    "tt_gbw_min": _status(float(open_loop["TT"]["gbw_hz"]), float(open_loop["TT"]["gbw_hz"]) >= spec.gbw_hz_min),
                    "tt_gbw_max": _status(float(open_loop["TT"]["gbw_hz"]), float(open_loop["TT"]["gbw_hz"]) <= spec.gbw_hz_max),
                    "tt_pm": _status(float(open_loop["TT"]["phase_margin_deg"]), float(open_loop["TT"]["phase_margin_deg"]) >= spec.phase_margin_deg_min),
                    "tt_gm": _status(float(open_loop["TT"]["gain_margin_db"]), float(open_loop["TT"]["gain_margin_db"]) >= spec.gain_margin_db_min),
                    "tt_iq": _status(float(open_loop["TT"]["iq_uA"]), float(open_loop["TT"]["iq_uA"]) <= spec.iq_uA_max),
                    "ff_aol": _status(float(open_loop["FF"]["aol_db"]), float(open_loop["FF"]["aol_db"]) >= spec.aol_db_min),
                    "ss_aol": _status(float(open_loop["SS"]["aol_db"]), float(open_loop["SS"]["aol_db"]) >= spec.aol_db_min),
                    "swing_low": _status(float(swing["vout_low_actual"]), float(swing["vout_low_actual"]) <= spec.output_swing_low_max_v),
                    "swing_high": _status(float(swing["vout_high_actual"]), float(swing["vout_high_actual"]) >= spec.output_swing_high_min_v),
                    "leakage": _status(float(leakage["disabled_leakage_nA"]), float(leakage["disabled_leakage_nA"]) <= spec.disabled_leakage_nA_max),
                    "offset_nominal": _status(float(offset["input_referred_offset_abs_uV"]), float(offset["input_referred_offset_abs_uV"]) <= spec.residual_offset_uV_max),
                    "offset_mc_sigma": _status(float(mc["input_referred_offset_sigma_uV"]), float(mc["input_referred_offset_sigma_uV"]) <= 60.0),
                    "offset_mc_p99_vs_250uV": _status(float(mc["input_referred_offset_abs_p99_uV"]), float(mc["input_referred_offset_abs_p99_uV"]) <= spec.residual_offset_uV_max),
                },
            }
            write_metrics_json(METRICS_PATH, summary)

            self.assertTrue(all(math.isfinite(float(open_loop[c]["iq_uA"])) for c in open_loop))
            self.assertGreater(int(mc["samples_completed"]), 0)
        except Exception as exc:
            write_metrics_json(
                METRICS_PATH,
                {
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                },
            )
            raise
