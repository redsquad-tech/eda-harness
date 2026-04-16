from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import hdl21 as h
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import SimOptions

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.opamp_core import OpampCoreParams, opamp_core
from opamp.v3.tests._helpers import BaseV3SimTest, build_debug_core_params, reset_metrics_file, write_metrics_json


METRICS_PATH = Path(__file__).with_name("rc_probe_core_nominal_balance_metrics.json")


def _debug_params() -> OpampCoreParams:
    return build_debug_core_params()


def _build_tb(dut):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp, vinn, vout, en, vdd = h.Signals(5)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        ven = h.Vdc(dc=1.8)(p=en, n=VSS)
        vvinp = h.Vdc(dc=0.9)(p=vinp, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinn)
        rl = h.Res(r=1e6)(p=vout, n=VSS)
        cl = h.Cap(c=1e-12)(p=vout, n=VSS)
        xdut = dut(VINP=vinp, VINN=vinn, VOUT=vout, EN=en, VDD=vdd, VSS=VSS)

    return Tb


class TestRcProbeCoreNominalBalance(BaseV3SimTest):
    def test_probe_rc_core_nominal_balance(self):
        reset_metrics_file(METRICS_PATH)
        install = require_sky130_install()
        dut = opamp_core(_debug_params())
        sim = Sim(tb=_build_tb(dut), attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)])
        res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/rc_core_nom_{uuid4().hex[:8]}")
        d = res.an[0].data
        i_out_p = float(d.get("i(v.xtop.xxdut.vvprobe_outp)", 0.0))
        i_out_n = float(d.get("i(v.xtop.xxdut.vvprobe_outn)", 0.0))
        payload = {
            "vin_V": 0.9,
            "vx_V": float(d["v(xtop.xxdut.vx)"]),
            "vref_V": float(d["v(xtop.xxdut.vref)"]),
            "vdrv_V": float(d["v(xtop.xxdut.vdrv)"]),
            "vgn_V": float(d.get("v(xtop.xxdut.vgn)", 0.0)),
            "vgp_V": float(d.get("v(xtop.xxdut.vgp)", 1.8)),
            "gate_avg_V": 0.5 * (float(d.get("v(xtop.xxdut.vgn)", 0.0)) + float(d.get("v(xtop.xxdut.vgp)", 1.8))),
            "gate_spread_V": float(d.get("v(xtop.xxdut.vgn)", 0.0)) - float(d.get("v(xtop.xxdut.vgp)", 1.8)),
            "vout_V": float(d["v(xtop.vout)"]),
            "i_stage2_p_A": float(d["i(v.xtop.xxdut.vvprobe_s2p)"]),
            "i_stage2_n_A": float(d["i(v.xtop.xxdut.vvprobe_s2n)"]),
            "i_out_p_A": i_out_p,
            "i_out_n_A": i_out_n,
            "quiescent_overlap_A": abs(i_out_p) + abs(i_out_n),
        }
        write_metrics_json(METRICS_PATH, payload)
        self.assertTrue(True)
