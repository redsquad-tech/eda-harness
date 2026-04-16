from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import hdl21 as h
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import SimOptions

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.tests._helpers import BaseV3SimTest, reset_metrics_file, write_metrics_json
from opamp.v3.tests._probe_blocks import output_path_probe
from opamp.v3.tests.test_rc_probe_core import _debug_params


METRICS_PATH = Path(__file__).with_name("rc_probe_integrated_output_transfer_metrics.json")


def _build_tb(dut, *, vdrv_dc: float):
    @h.module
    class Tb:
        VSS = h.Port()
        vdrv, vout, vdd = h.Signals(3)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        vvdrv = h.Vdc(dc=vdrv_dc)(p=vdrv, n=VSS)
        rl = h.Res(r=1e6)(p=vout, n=VSS)
        cl = h.Cap(c=1e-12)(p=vout, n=VSS)
        xdut = dut(VDRV=vdrv, VOUT=vout, VDD=vdd, VSS=VSS)

    return Tb


class TestRcProbeIntegratedOutputTransfer(BaseV3SimTest):
    def test_probe_rc_integrated_output_transfer(self):
        reset_metrics_file(METRICS_PATH)
        install = require_sky130_install()
        dut = output_path_probe(_debug_params())
        cases = []
        for vdrv_dc in (0.4, 0.8, 1.0, 1.2, 1.6):
            sim = Sim(
                tb=_build_tb(dut, vdrv_dc=vdrv_dc),
                attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)],
            )
            res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/rc_outxf_{uuid4().hex[:8]}")
            d = res.an[0].data
            i_out_p = float(d["i(v.xtop.xxdut.vvprobe_outp)"])
            i_out_n = float(d["i(v.xtop.xxdut.vvprobe_outn)"])
            cases.append(
                {
                    "vdrv_V": float(vdrv_dc),
                    "vout_V": float(d["v(xtop.vout)"]),
                    "vgn_V": float(d["v(xtop.xxdut.vgn)"]),
                    "vgp_V": float(d["v(xtop.xxdut.vgp)"]),
                    "gate_avg_V": 0.5 * (float(d["v(xtop.xxdut.vgn)"]) + float(d["v(xtop.xxdut.vgp)"])),
                    "gate_spread_V": float(d["v(xtop.xxdut.vgn)"]) - float(d["v(xtop.xxdut.vgp)"]),
                    "i_out_p_A": i_out_p,
                    "i_out_n_A": i_out_n,
                    "quiescent_overlap_A": abs(i_out_p) + abs(i_out_n),
                }
            )
        payload = {"cases": cases}
        write_metrics_json(METRICS_PATH, payload)
        self.assertEqual(len(cases), 5)
