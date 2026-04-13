from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import hdl21 as h
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import SimOptions

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.output_path_reference import default_reference_output_path_params, reference_output_path_method2
from opamp.v3.tests._helpers import BaseV3SimTest, reset_metrics_file, write_metrics_json


METRICS_PATH = Path(__file__).with_name("rc_probe_reference_output_path_gate_network_metrics.json")


def _build_tb(dut, *, vdrv: float):
    @h.module
    class Tb:
        VSS = h.Port()
        vdd, vdrv_sig, vout = h.Signals(3)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        vvdrv = h.Vdc(dc=vdrv)(p=vdrv_sig, n=VSS)
        rload = h.Res(r=1e12)(p=vout, n=VSS)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        xdut = dut(VDRV=vdrv_sig, VOUT=vout, VDD=vdd, VSS=VSS)

    return Tb


def _case(dut, params, *, name: str, vdrv: float):
    install = require_sky130_install()
    sim = Sim(
        tb=_build_tb(dut, vdrv=vdrv),
        attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)],
    )
    res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/rc_refgate_{uuid4().hex[:8]}")
    d = res.an[0].data

    vdrvb = float(d["v(xtop.xxdut.vdrvb)"])
    vgn_q = float(d["v(xtop.xxdut.vgn_q)"])
    vgp_q = float(d["v(xtop.xxdut.vgp_q)"])
    vgn = float(d["v(xtop.xxdut.vgn)"])
    vgp = float(d["v(xtop.xxdut.vgp)"])

    i_keep_n = (vgn_q - vgn) / float(params.r_keep_n)
    i_keep_p = (vgp_q - vgp) / float(params.r_keep_p)
    i_sig_n = (vdrvb - vgn) / float(params.r_sig_n)
    i_sig_p = (vdrvb - vgp) / float(params.r_sig_p)

    return {
        "case": name,
        "vdrv_in_V": vdrv,
        "vdrvb_V": vdrvb,
        "vgn_q_V": vgn_q,
        "vgp_q_V": vgp_q,
        "vgn_V": vgn,
        "vgp_V": vgp,
        "vout_V": float(d["v(xtop.vout)"]),
        "i_keep_n_est_A": i_keep_n,
        "i_keep_p_est_A": i_keep_p,
        "i_sig_n_est_A": i_sig_n,
        "i_sig_p_est_A": i_sig_p,
        "i_out_n_A": float(d["i(v.xtop.xxdut.vvprobe_outn)"]),
        "i_out_p_A": float(d["i(v.xtop.xxdut.vvprobe_outp)"]),
        "i_bias_n_A": float(d["i(v.xtop.xxdut.vvprobe_bias_n)"]),
        "i_bias_p_A": float(d["i(v.xtop.xxdut.vvprobe_bias_p)"]),
    }


class TestRcProbeReferenceOutputPathGateNetwork(BaseV3SimTest):
    def test_probe_rc_reference_output_path_gate_network(self):
        reset_metrics_file(METRICS_PATH)
        params = default_reference_output_path_params()
        dut = reference_output_path_method2(params)
        payload = {
            "params": {
                "r_keep_n_ohm": float(params.r_keep_n),
                "r_keep_p_ohm": float(params.r_keep_p),
                "r_sig_n_ohm": float(params.r_sig_n),
                "r_sig_p_ohm": float(params.r_sig_p),
            },
            "cases": [
                _case(dut, params, name="vdrv_0p0", vdrv=0.0),
                _case(dut, params, name="vdrv_0p8", vdrv=0.8),
                _case(dut, params, name="vdrv_1p0", vdrv=1.0),
                _case(dut, params, name="vdrv_1p6", vdrv=1.6),
            ],
        }
        write_metrics_json(METRICS_PATH, payload)
        self.assertEqual(len(payload["cases"]), 4)
