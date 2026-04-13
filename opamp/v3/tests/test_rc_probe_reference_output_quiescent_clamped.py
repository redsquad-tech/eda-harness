from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import hdl21 as h
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import SimOptions

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.output_path_reference import default_reference_output_path_params, reference_output_path_method2
from opamp.v3.tests._helpers import BaseV3SimTest, reset_metrics_file, write_metrics_json


METRICS_PATH = Path(__file__).with_name("rc_probe_reference_output_quiescent_clamped_metrics.json")


def _build_tb(dut, *, vdrv: float, vout_force: float):
    @h.module
    class Tb:
        VSS = h.Port()
        vdd, vdrv_sig, vout = h.Signals(3)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        vvdrv = h.Vdc(dc=vdrv)(p=vdrv_sig, n=VSS)
        vvout = h.Vdc(dc=vout_force)(p=vout, n=VSS)
        xdut = dut(VDRV=vdrv_sig, VOUT=vout, VDD=vdd, VSS=VSS)

    return Tb


def _case(dut, *, name: str, vdrv: float, vout_force: float) -> dict[str, float]:
    install = require_sky130_install()
    sim = Sim(
        tb=_build_tb(dut, vdrv=vdrv, vout_force=vout_force),
        attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)],
    )
    res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/rc_refclamp_{uuid4().hex[:8]}")
    d = res.an[0].data
    i_out_p = float(d["i(v.xtop.xxdut.vvprobe_outp)"])
    i_out_n = float(d["i(v.xtop.xxdut.vvprobe_outn)"])
    return {
        "case": name,
        "vdrv_in_V": vdrv,
        "vout_forced_V": vout_force,
        "vgn_q_V": float(d["v(xtop.xxdut.vgn_q)"]),
        "vgp_q_V": float(d["v(xtop.xxdut.vgp_q)"]),
        "vgn_V": float(d["v(xtop.xxdut.vgn)"]),
        "vgp_V": float(d["v(xtop.xxdut.vgp)"]),
        "gate_avg_V": 0.5 * (float(d["v(xtop.xxdut.vgn)"]) + float(d["v(xtop.xxdut.vgp)"])),
        "gate_spread_V": float(d["v(xtop.xxdut.vgn)"]) - float(d["v(xtop.xxdut.vgp)"]),
        "i_out_p_A": i_out_p,
        "i_out_n_A": i_out_n,
        "quiescent_overlap_A": abs(i_out_p) + abs(i_out_n),
        "branch_imbalance_A": i_out_p + i_out_n,
        "branch_balance_ratio": abs(i_out_p) / max(abs(i_out_n), 1e-30),
    }


class TestRcProbeReferenceOutputQuiescentClamped(BaseV3SimTest):
    def test_probe_rc_reference_output_quiescent_clamped(self):
        reset_metrics_file(METRICS_PATH)

        keep_only = reference_output_path_method2(default_reference_output_path_params(r_sig_n=1e12, r_sig_p=1e12))
        combined = reference_output_path_method2(default_reference_output_path_params())

        payload = {
            "keep_only_vdrv_1p0": _case(keep_only, name="keep_only_vdrv_1p0", vdrv=1.0, vout_force=0.9),
            "combined_vdrv_0p8": _case(combined, name="combined_vdrv_0p8", vdrv=0.8, vout_force=0.9),
            "combined_vdrv_1p0": _case(combined, name="combined_vdrv_1p0", vdrv=1.0, vout_force=0.9),
            "combined_vdrv_1p2": _case(combined, name="combined_vdrv_1p2", vdrv=1.2, vout_force=0.9),
        }
        write_metrics_json(METRICS_PATH, payload)

        self.assertGreater(payload["combined_vdrv_1p0"]["quiescent_overlap_A"], 1e-6)
        self.assertLess(payload["combined_vdrv_1p0"]["branch_balance_ratio"], 3.0)
        self.assertGreater(payload["combined_vdrv_1p0"]["branch_balance_ratio"], 1 / 3.0)
