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


METRICS_PATH = Path(__file__).with_name("rc_probe_output_ic_sweep_metrics.json")


def _build_tb(dut, *, vdrv: float, vout_ic: float):
    @h.module
    class Tb:
        VSS = h.Port()
        vdrv_sig, vout, vdd = h.Signals(3)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        vvdrv = h.Vdc(dc=vdrv)(p=vdrv_sig, n=VSS)
        rload = h.Res(r=1e6)(p=vout, n=VSS)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        xdut = dut(VDRV=vdrv_sig, VOUT=vout, VDD=vdd, VSS=VSS)

    return Tb, h.sim.Literal(f".nodeset v(xtop.vout)={float(vout_ic)}")


def _case(dut, *, name: str, vdrv: float, vout_ic: float) -> dict[str, float | str]:
    install = require_sky130_install()
    tb, nodeset = _build_tb(dut, vdrv=vdrv, vout_ic=vout_ic)
    sim = Sim(tb=tb, attrs=[Op(), Save("all"), nodeset, h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)])
    res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/rc_ic_{uuid4().hex[:8]}")
    d = res.an[0].data
    return {
        "case": name,
        "vdrv_in_V": float(vdrv),
        "vout_ic_V": float(vout_ic),
        "vgn_V": float(d["v(xtop.xxdut.vgn)"]),
        "vgp_V": float(d["v(xtop.xxdut.vgp)"]),
        "vout_V": float(d["v(xtop.vout)"]),
        "i_out_p_A": float(d["i(v.xtop.xxdut.vvprobe_outp)"]),
        "i_out_n_A": float(d["i(v.xtop.xxdut.vvprobe_outn)"]),
    }


class TestRcProbeOutputIcSweep(BaseV3SimTest):
    def test_probe_rc_output_ic_sweep(self):
        dut = output_subckt(_debug_params())
        payload = {
            "cases": [
                _case(dut, name="vdrv_1p0_ic_0p0", vdrv=1.0, vout_ic=0.0),
                _case(dut, name="vdrv_1p0_ic_0p9", vdrv=1.0, vout_ic=0.9),
                _case(dut, name="vdrv_1p0_ic_1p8", vdrv=1.0, vout_ic=1.8),
                _case(dut, name="vdrv_1p8_ic_0p0", vdrv=1.8, vout_ic=0.0),
                _case(dut, name="vdrv_1p8_ic_0p9", vdrv=1.8, vout_ic=0.9),
                _case(dut, name="vdrv_1p8_ic_1p8", vdrv=1.8, vout_ic=1.8),
            ]
        }
        METRICS_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        self.assertEqual(len(payload["cases"]), 6)
