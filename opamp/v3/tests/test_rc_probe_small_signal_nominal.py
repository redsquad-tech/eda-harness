from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import hdl21 as h
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import SimOptions

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.tests._helpers import BaseV3SimTest
from opamp.v3.tests.test_rc_probe_output_subckt import _debug_params, output_subckt


METRICS_PATH = Path(__file__).with_name("rc_probe_small_signal_nominal_metrics.json")


def _build_tb(dut, *, vdrv: float):
    @h.module
    class Tb:
        VSS = h.Port()
        vdrv_sig, vout, vdd = h.Signals(3)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        vvdrv = h.Vdc(dc=vdrv)(p=vdrv_sig, n=VSS)
        rload = h.Res(r=1e12)(p=vout, n=VSS)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        xdut = dut(VDRV=vdrv_sig, VOUT=vout, VDD=vdd, VSS=VSS)

    return Tb


def _point(dut, *, vdrv: float) -> dict[str, float]:
    install = require_sky130_install()
    sim = Sim(tb=_build_tb(dut, vdrv=vdrv), attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)])
    res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/rc_smallsig_{uuid4().hex[:8]}")
    d = res.an[0].data
    i_out_p = float(d["i(v.xtop.xxdut.vvprobe_outp)"])
    i_out_n = float(d["i(v.xtop.xxdut.vvprobe_outn)"])
    return {
        "vdrv_in_V": float(vdrv),
        "vgn_V": float(d["v(xtop.xxdut.vgn)"]),
        "vgp_V": float(d["v(xtop.xxdut.vgp)"]),
        "vout_V": float(d["v(xtop.vout)"]),
        "i_out_p_A": i_out_p,
        "i_out_n_A": i_out_n,
    }


class TestRcProbeSmallSignalNominal(BaseV3SimTest):
    def test_probe_rc_small_signal_nominal(self):
        dut = output_subckt(_debug_params())
        points = [_point(dut, vdrv=v) for v in (0.99, 1.00, 1.01)]
        dvout_dvdrv = (points[2]["vout_V"] - points[0]["vout_V"]) / (points[2]["vdrv_in_V"] - points[0]["vdrv_in_V"])
        diout_dvdrv = (
            (points[2]["i_out_p_A"] + points[2]["i_out_n_A"]) - (points[0]["i_out_p_A"] + points[0]["i_out_n_A"])
        ) / (points[2]["vdrv_in_V"] - points[0]["vdrv_in_V"])
        payload = {
            "points": points,
            "derived": {
                "dvout_dvdrv_V_per_V": dvout_dvdrv,
                "diout_dvdrv_A_per_V": diout_dvdrv,
            },
        }
        METRICS_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        self.assertEqual(len(points), 3)
