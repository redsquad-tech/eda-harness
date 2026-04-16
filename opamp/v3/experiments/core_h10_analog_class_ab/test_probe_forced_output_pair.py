from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import SimOptions

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.opamp_core import OpampCoreParams, _mos_params
from opamp.v3.prod.rc import current_core_params
from opamp.v3.tests._helpers import BaseV3SimTest


METRICS_PATH = Path(__file__).with_name("forced_output_pair_metrics.json")


def _debug_params() -> OpampCoreParams:
    base = current_core_params()
    return OpampCoreParams(
        architecture_name=base.architecture_name,
        w_in=base.w_in,
        l_in=base.l_in,
        w_load=base.w_load,
        l_load=base.l_load,
        w_tail_ref=base.w_tail_ref,
        l_tail_ref=base.l_tail_ref,
        w_tail=base.w_tail,
        l_tail=base.l_tail,
        r_stage1_bias=base.r_stage1_bias,
        w_tail_sw=base.w_tail_sw,
        l_tail_sw=base.l_tail_sw,
        tail_switch_stack=base.tail_switch_stack,
        w_stage2_n=base.w_stage2_n,
        l_stage2_n=base.l_stage2_n,
        w_stage2_p=base.w_stage2_p,
        l_stage2_p=base.l_stage2_p,
        w_stage2_bias_ref=base.w_stage2_bias_ref,
        l_stage2_bias_ref=base.l_stage2_bias_ref,
        r_stage2_bias=base.r_stage2_bias,
        w_out_n=base.w_out_n,
        l_out_n=base.l_out_n,
        w_out_boost=base.w_out_boost,
        l_out_boost=base.l_out_boost,
        w_out_pd=base.w_out_pd,
        l_out_pd=base.l_out_pd,
        r_vdrv_out=base.r_vdrv_out,
        r_gp=base.r_gp,
        r_gp_pullup=base.r_gp_pullup,
        r_gp_boost=base.r_gp_boost,
        r_gp_boost_pullup=base.r_gp_boost_pullup,
        isolate_gp_link_in_shutdown=base.isolate_gp_link_in_shutdown,
        w_gp_sw=base.w_gp_sw,
        l_gp_sw=base.l_gp_sw,
        c_comp=base.c_comp,
        debug_current_probes=True,
    )


def forced_output_pair(params: OpampCoreParams) -> h.Module:
    pmos = sky130_hdl21.primitives.PMOS_1p8V_STD
    nmos = sky130_hdl21.primitives.NMOS_1p8V_STD

    mod = h.Module(name="CoreH10ForcedOutputPair")
    mod.VGN, mod.VGP, mod.VOUT, mod.VDD, mod.VSS = h.Ports(5)
    mod.vout_op = h.Signal(name="vout_op")
    mod.vout_on = h.Signal(name="vout_on")
    mod.vprobe_outp = h.Vdc(dc=0)(p=mod.vout_op, n=mod.VOUT)
    mod.vprobe_outn = h.Vdc(dc=0)(p=mod.vout_on, n=mod.VOUT)
    mod.m_out_p = pmos(_mos_params(max(float(params.w_out_n) * 2.0, 1.0), float(params.l_out_n)))(d=mod.vout_op, g=mod.VGP, s=mod.VDD, b=mod.VDD)
    mod.m_out_n = nmos(_mos_params(max(float(params.w_out_n), 1.0), float(params.l_out_n)))(d=mod.vout_on, g=mod.VGN, s=mod.VSS, b=mod.VSS)
    return mod


def _build_tb(dut, *, vgn: float, vgp: float):
    @h.module
    class Tb:
        VSS = h.Port()
        vdd, vout, vgn_sig, vgp_sig = h.Signals(4)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        vvgn = h.Vdc(dc=vgn)(p=vgn_sig, n=VSS)
        vvgp = h.Vdc(dc=vgp)(p=vgp_sig, n=VSS)
        rload = h.Res(r=1e12)(p=vout, n=VSS)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        xdut = dut(VGN=vgn_sig, VGP=vgp_sig, VOUT=vout, VDD=vdd, VSS=VSS)

    return Tb


def _op_case(dut, *, name: str, vgn: float, vgp: float) -> dict[str, float | str]:
    install = require_sky130_install()
    sim = Sim(tb=_build_tb(dut, vgn=vgn, vgp=vgp), attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)])
    res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/core_h9_forced_pair_{uuid4().hex[:8]}")
    d = res.an[0].data
    vdd = float(d["v(xtop.vdd)"])
    vout = float(d["v(xtop.vout)"])
    return {
        "case": name,
        "vgn_in_V": float(vgn),
        "vgp_in_V": float(vgp),
        "gate_spread_V": float(vgp - vgn),
        "ab_spread_V": float(vgn - vgp),
        "gate_cm_V": float(0.5 * (vgp + vgn)),
        "vout_V": vout,
        "out_p_vsg_V": vdd - float(vgp),
        "out_p_vsd_V": vdd - vout,
        "out_n_vgs_V": float(vgn),
        "out_n_vds_V": vout,
        "i_out_p_A": float(d["i(v.xtop.xxdut.vvprobe_outp)"]),
        "i_out_n_A": float(d["i(v.xtop.xxdut.vvprobe_outn)"]),
        "quiescent_overlap_A": abs(float(d["i(v.xtop.xxdut.vvprobe_outp)"])) + abs(float(d["i(v.xtop.xxdut.vvprobe_outn)"])),
    }


class TestCoreH10ForcedOutputPair(BaseV3SimTest):
    def test_probe_forced_output_pair(self):
        dut = forced_output_pair(_debug_params())
        payload = {
            "cases": [
                _op_case(dut, name="both_mid", vgn=0.90, vgp=0.90),
                _op_case(dut, name="n_weaker_p_low", vgn=0.35, vgp=0.20),
                _op_case(dut, name="n_mid_p_low", vgn=0.60, vgp=0.20),
                _op_case(dut, name="n_low_p_high", vgn=0.10, vgp=1.40),
                _op_case(dut, name="n_off_p_on", vgn=0.00, vgp=0.20),
                _op_case(dut, name="n_on_p_off", vgn=1.20, vgp=1.80),
                _op_case(dut, name="ab_window_nominal", vgn=0.35, vgp=0.80),
                _op_case(dut, name="ab_window_stronger_n", vgn=0.60, vgp=0.80),
            ]
        }
        METRICS_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        self.assertEqual(len(payload["cases"]), 8)
