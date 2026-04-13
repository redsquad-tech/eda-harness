from __future__ import annotations

from pathlib import Path

from opamp.v3.output_path_reference import default_reference_output_path_params, reference_output_path_method2
from opamp.v3.tests._helpers import BaseV3SimTest, reset_metrics_file, write_metrics_json
from opamp.v3.tests.test_rc_probe_reference_output_path import _case


METRICS_PATH = Path(__file__).with_name("rc_probe_reference_output_branch_semantics_metrics.json")


def _disabled() -> float:
    return 1e12


class TestRcProbeReferenceOutputBranchSemantics(BaseV3SimTest):
    def test_probe_rc_reference_output_branch_semantics(self):
        reset_metrics_file(METRICS_PATH)

        configs = {
            "keep_n_only": default_reference_output_path_params(
                r_keep_p=_disabled(),
                r_sig_n=_disabled(),
                r_sig_p=_disabled(),
            ),
            "keep_p_only": default_reference_output_path_params(
                r_keep_n=_disabled(),
                r_sig_n=_disabled(),
                r_sig_p=_disabled(),
            ),
            "sig_n_only": default_reference_output_path_params(
                r_keep_n=_disabled(),
                r_keep_p=_disabled(),
                r_sig_p=_disabled(),
            ),
            "sig_p_only": default_reference_output_path_params(
                r_keep_n=_disabled(),
                r_keep_p=_disabled(),
                r_sig_n=_disabled(),
            ),
        }

        payload: dict[str, dict[str, float | str]] = {}
        for name, params in configs.items():
            dut = reference_output_path_method2(params)
            low = _case(dut, name=f"{name}_vdrv_0p2", vdrv=0.2)
            high = _case(dut, name=f"{name}_vdrv_1p6", vdrv=1.6)
            payload[name] = {
                "low": low,
                "high": high,
                "delta_vgn_V": float(high["vgn_V"]) - float(low["vgn_V"]),
                "delta_vgp_V": float(high["vgp_V"]) - float(low["vgp_V"]),
                "delta_vout_V": float(high["vout_V"]) - float(low["vout_V"]),
                "delta_i_out_p_A": float(high["i_out_p_A"]) - float(low["i_out_p_A"]),
                "delta_i_out_n_A": float(high["i_out_n_A"]) - float(low["i_out_n_A"]),
            }

        write_metrics_json(METRICS_PATH, payload)

        for branch in payload.values():
            self.assertGreater(
                max(abs(branch["delta_vgn_V"]), abs(branch["delta_vgp_V"])),
                1e-3,
            )
            self.assertGreater(abs(branch["delta_vout_V"]), 1e-3)
