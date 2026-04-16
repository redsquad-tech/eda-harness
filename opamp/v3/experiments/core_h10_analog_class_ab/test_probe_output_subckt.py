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
from opamp.v3.pdk_passives import pdk_resistor
from opamp.v3.prod.rc import current_core_params
from opamp.v3.tests._helpers import BaseV3SimTest


METRICS_PATH = Path(__file__).with_name("output_subckt_metrics.json")


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


def output_subckt(params: OpampCoreParams) -> h.Module:
    pmos = sky130_hdl21.primitives.PMOS_1p8V_STD
    nmos = sky130_hdl21.primitives.NMOS_1p8V_STD

    mod = h.Module(name="CoreH10OutputSubckt")
    mod.VDRV, mod.VOUT, mod.VDD, mod.VSS = h.Ports(4)
    mod.vbuf = h.Signal(name="vbuf")
    mod.vgn = h.Signal(name="vgn")
    mod.vgp = h.Signal(name="vgp")
    mod.vbuf_drv = h.Signal(name="vbuf_drv")
    mod.vgn_drv = h.Signal(name="vgn_drv")
    mod.vgp_drv = h.Signal(name="vgp_drv")
    mod.vout_op = h.Signal(name="vout_op")
    mod.vout_on = h.Signal(name="vout_on")

    mod.vprobe_vbuf = h.Vdc(dc=0)(p=mod.vbuf_drv, n=mod.vbuf)
    mod.vprobe_vgn = h.Vdc(dc=0)(p=mod.vgn_drv, n=mod.vgn)
    mod.vprobe_vgp = h.Vdc(dc=0)(p=mod.vgp_drv, n=mod.vgp)
    mod.vprobe_outp = h.Vdc(dc=0)(p=mod.vout_op, n=mod.VOUT)
    mod.vprobe_outn = h.Vdc(dc=0)(p=mod.vout_on, n=mod.VOUT)

    mod.m_buf_p = pmos(_mos_params(2.0, 0.15))(d=mod.vbuf_drv, g=mod.VDRV, s=mod.VDD, b=mod.VDD)
    mod.m_buf_n = nmos(_mos_params(1.0, 0.15))(d=mod.vbuf_drv, g=mod.VDRV, s=mod.VSS, b=mod.VSS)
    mod.r_vgn_pulldown = pdk_resistor(150e3, p=mod.vgn, n=mod.VSS, bulk=mod.VSS)
    mod.m_vgn_p = pmos(_mos_params(0.8, 0.15))(d=mod.VSS, g=mod.VDRV, s=mod.vgn_drv, b=mod.VDD)
    mod.r_vgp_pullup = pdk_resistor(150e3, p=mod.VDD, n=mod.vgp, bulk=mod.VSS)
    mod.m_vgp_n = nmos(_mos_params(0.8, 0.15))(d=mod.VDD, g=mod.VDRV, s=mod.vgp_drv, b=mod.VSS)
    mod.m_out_p = pmos(_mos_params(max(float(params.w_out_n) * 2.0, 1.0), float(params.l_out_n)))(d=mod.vout_op, g=mod.vgp, s=mod.VDD, b=mod.VDD)
    mod.m_out_n = nmos(_mos_params(max(float(params.w_out_n), 1.0), float(params.l_out_n)))(d=mod.vout_on, g=mod.vgn, s=mod.VSS, b=mod.VSS)
    return mod


def _build_tb(dut, *, vdrv: float, load_mode: str = "none", load_uA: float = 0.0):
    @h.module
    class Tb:
        VSS = h.Port()
        vdrv_sig, vout, vdd = h.Signals(3)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        vvdrv = h.Vdc(dc=vdrv)(p=vdrv_sig, n=VSS)
        rload = h.Res(r=1e12)(p=vout, n=VSS)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        xdut = dut(VDRV=vdrv_sig, VOUT=vout, VDD=vdd, VSS=VSS)
        if load_mode == "source":
            iload = h.Idc(dc=load_uA * 1e-6)(p=vout, n=VSS)
        elif load_mode == "sink":
            iload = h.Idc(dc=load_uA * 1e-6)(p=vdd, n=vout)

    return Tb


def _op_case(dut, *, name: str, vdrv: float, load_mode: str = "none", load_uA: float = 0.0) -> dict[str, float | str]:
    install = require_sky130_install()
    sim = Sim(tb=_build_tb(dut, vdrv=vdrv, load_mode=load_mode, load_uA=load_uA), attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)])
    res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/core_h9_subckt_{uuid4().hex[:8]}")
    d = res.an[0].data
    vdd = float(d["v(xtop.vdd)"])
    vbuf = float(d["v(xtop.xxdut.vbuf)"])
    vgn = float(d["v(xtop.xxdut.vgn)"])
    vgp = float(d["v(xtop.xxdut.vgp)"])
    vout = float(d["v(xtop.vout)"])
    return {
        "case": name,
        "vdrv_in_V": float(vdrv),
        "load_mode": load_mode,
        "load_uA": float(load_uA),
        "vbuf_V": vbuf,
        "vgn_V": vgn,
        "vgp_V": vgp,
        "gate_spread_V": vgp - vgn,
        "ab_spread_V": vgn - vgp,
        "gate_cm_V": 0.5 * (vgp + vgn),
        "vout_V": vout,
        "out_p_vsg_V": vdd - vgp,
        "out_p_vsd_V": vdd - vout,
        "out_n_vgs_V": vgn,
        "out_n_vds_V": vout,
        "i_vbuf_driver_A": float(d["i(v.xtop.xxdut.vvprobe_vbuf)"]),
        "i_vgn_driver_A": float(d["i(v.xtop.xxdut.vvprobe_vgn)"]),
        "i_vgp_driver_A": float(d["i(v.xtop.xxdut.vvprobe_vgp)"]),
        "i_out_p_A": float(d["i(v.xtop.xxdut.vvprobe_outp)"]),
        "i_out_n_A": float(d["i(v.xtop.xxdut.vvprobe_outn)"]),
        "quiescent_overlap_A": abs(float(d["i(v.xtop.xxdut.vvprobe_outp)"])) + abs(float(d["i(v.xtop.xxdut.vvprobe_outn)"])),
    }


class TestCoreH10ProbeOutputSubckt(BaseV3SimTest):
    def test_probe_output_subckt(self):
        dut = output_subckt(_debug_params())
        payload = {
            "cases": [
                _op_case(dut, name="vdrv_0p0", vdrv=0.0),
                _op_case(dut, name="vdrv_0p8", vdrv=0.8),
                _op_case(dut, name="vdrv_1p0", vdrv=1.0),
                _op_case(dut, name="vdrv_1p2", vdrv=1.2),
                _op_case(dut, name="vdrv_1p6", vdrv=1.6),
                _op_case(dut, name="vdrv_1p8", vdrv=1.8),
                _op_case(dut, name="vdrv_1p0_source20u", vdrv=1.0, load_mode="source", load_uA=20.0),
                _op_case(dut, name="vdrv_1p0_sink20u", vdrv=1.0, load_mode="sink", load_uA=20.0),
            ]
        }
        METRICS_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        self.assertEqual(len(payload["cases"]), 8)
