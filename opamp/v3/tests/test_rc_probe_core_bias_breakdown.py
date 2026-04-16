from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import hdl21 as h
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import SimOptions

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.opamp_core import opamp_core
from opamp.v3.tests._helpers import BaseV3SimTest, build_debug_core_params


METRICS_PATH = Path(__file__).with_name("rc_probe_core_bias_breakdown_metrics.json")


def _build_tb(dut):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp, vinn, vout, en, vdd = h.Signals(5)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        ven = h.Vdc(dc=1.8)(p=en, n=VSS)
        vvinn = h.Vdc(dc=0.9)(p=vinn, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinp)
        rl = h.Res(r=1e6)(p=vout, n=VSS)
        cl = h.Cap(c=1e-12)(p=vout, n=VSS)
        xdut = dut(VINP=vinp, VINN=vinn, VOUT=vout, EN=en, VDD=vdd, VSS=VSS)

    return Tb


class TestRcProbeCoreBiasBreakdown(BaseV3SimTest):
    def test_probe_core_bias_breakdown(self):
        install = require_sky130_install()
        dut = opamp_core(build_debug_core_params())
        sim = Sim(tb=_build_tb(dut), attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)])
        res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/rc_core_bias_{uuid4().hex[:8]}")
        d = res.an[0].data

        i_total = abs(float(d["i(v.xtop.vvvdd)"]))
        i_tail1 = abs(float(d["i(v.xtop.xxdut.vvprobe_tail1)"]))
        i_load_out = abs(float(d["i(v.xtop.xxdut.vvprobe_load_out)"]))
        i_load_ref = abs(float(d["i(v.xtop.xxdut.vvprobe_load_ref)"]))
        i_stage2_p = abs(float(d["i(v.xtop.xxdut.vvprobe_s2p)"]))
        i_stage2_n = abs(float(d["i(v.xtop.xxdut.vvprobe_s2n)"]))
        i_pre = abs(float(d["i(v.xtop.xxdut.vvprobe_vg_pre)"]))

        payload = {
            "vin_V": 0.9,
            "vout_V": float(d["v(xtop.vout)"]),
            "vx_V": float(d["v(xtop.xxdut.vx)"]),
            "vref_V": float(d["v(xtop.xxdut.vref)"]),
            "vdrv_V": float(d["v(xtop.xxdut.vdrv)"]),
            "vgn_V": float(d["v(xtop.xxdut.vgn)"]),
            "vgp_V": float(d["v(xtop.xxdut.vgp)"]),
            "gate_avg_V": 0.5 * (float(d["v(xtop.xxdut.vgn)"]) + float(d["v(xtop.xxdut.vgp)"])),
            "gate_spread_V": float(d["v(xtop.xxdut.vgn)"]) - float(d["v(xtop.xxdut.vgp)"]),
            "iq_total_A": i_total,
            "i_tail1_A": i_tail1,
            "i_load_out_A": i_load_out,
            "i_load_ref_A": i_load_ref,
            "i_stage2_p_A": i_stage2_p,
            "i_stage2_n_A": i_stage2_n,
            "i_predriver_vdd_A": i_pre,
        }
        payload["derived"] = {
            "first_stage_sum_A": i_tail1 + i_load_out + i_load_ref,
            "stage2_sum_A": i_stage2_p + i_stage2_n,
            "tracked_sum_A": i_tail1 + i_load_out + i_load_ref + i_stage2_p + i_stage2_n + i_pre,
            "untracked_iq_A": i_total - (i_tail1 + i_load_out + i_load_ref + i_stage2_p + i_stage2_n + i_pre),
        }
        METRICS_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        self.assertGreater(i_total, 0.0)
