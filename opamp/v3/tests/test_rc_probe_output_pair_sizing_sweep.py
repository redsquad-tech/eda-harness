from __future__ import annotations

from pathlib import Path

from opamp.v3.tests._helpers import BaseV3SimTest, build_debug_core_params, reset_metrics_file, write_metrics_json
from opamp.v3.tests._probe_blocks import output_stage_probe
from opamp.v3.tests.test_rc_probe_output_pair_local_map import _point


METRICS_PATH = Path(__file__).with_name("rc_probe_output_pair_sizing_sweep_metrics.json")


class TestRcProbeOutputPairSizingSweep(BaseV3SimTest):
    def test_probe_rc_output_pair_sizing_sweep(self):
        reset_metrics_file(METRICS_PATH)
        vgn_values = [0.70, 0.74, 0.78]
        vgp_values = [0.86, 0.90, 0.94]
        configs = [
            {"name": "base_1p2_0p5", "w_out_n": 1.2, "l_out_n": 0.5},
            {"name": "weak_0p6_0p5", "w_out_n": 0.6, "l_out_n": 0.5},
            {"name": "long_1p2_1p0", "w_out_n": 1.2, "l_out_n": 1.0},
            {"name": "weak_long_0p6_1p0", "w_out_n": 0.6, "l_out_n": 1.0},
            {"name": "very_long_1p2_2p0", "w_out_n": 1.2, "l_out_n": 2.0},
        ]

        results = []
        for cfg in configs:
            dut = output_stage_probe(
                build_debug_core_params(w_out_n=cfg["w_out_n"], l_out_n=cfg["l_out_n"])
            )
            cases = []
            for vgn in vgn_values:
                for vgp in vgp_values:
                    cases.append(_point(dut, vgn=vgn, vgp=vgp))
            best = min(cases, key=lambda item: item["vout_error_to_mid_V"])
            results.append(
                {
                    "config": cfg,
                    "best_mid_case": best,
                    "cases": cases,
                }
            )

        payload = {
            "grid": {"vgn_values_V": vgn_values, "vgp_values_V": vgp_values},
            "results": results,
            "best_config": min(results, key=lambda item: item["best_mid_case"]["vout_error_to_mid_V"]),
        }
        write_metrics_json(METRICS_PATH, payload)
        self.assertEqual(len(results), len(configs))
