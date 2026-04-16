from __future__ import annotations
from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import SimOptions

from components import require_sky130_install, run_ngspice_sim
from components.diffpair_p import DiffpairPParams, diffpair_p
from opamp.v3.opamp_core import (
    OpampCoreParams,
    SharedGateOutputStageParams,
    _mos_params,
    opamp_core,
    shared_gate_output_stage,
)
from opamp.v3.pdk_passives import pdk_mim_capacitor, pdk_resistor
from opamp.v3.tests._helpers import BaseV3SimTest, build_core_params, build_debug_core_params, reset_metrics_file, write_metrics_json


METRICS_PATH = Path(__file__).with_name("rc_probe_idealized_driver_ab_metrics.json")


def _idealized_driver_core(params: OpampCoreParams) -> h.Module:
    pmos = sky130_hdl21.primitives.PMOS_1p8V_STD
    nmos = sky130_hdl21.primitives.NMOS_1p8V_STD

    diffpair = diffpair_p(DiffpairPParams(w_in=params.w_in, l_in=params.l_in, nf_in=1, m_in=1))
    out_stage = shared_gate_output_stage(
        SharedGateOutputStageParams(
            w_n=max(float(params.w_out_n), 1.0),
            l_n=float(params.l_out_n),
            w_p=max(float(params.w_out_n) * 2.0, 1.0),
            l_p=float(params.l_out_n),
        )
    )

    mod = h.Module(name="OpampCoreV3IdealDriver")
    mod.VINP, mod.VINN, mod.VOUT, mod.EN, mod.VDD, mod.VSS = h.Ports(6)
    mod.vx, mod.vref, mod.vdrv = h.Signals(3)
    mod.ibias1, mod.ibias2 = h.Signals(2)
    mod.tail1 = h.Signal(name="tail1")
    mod.vbp1 = h.Signal(name="vbp1")
    mod.vinp_int = h.Signal(name="vinp_int")
    mod.vinn_int = h.Signal(name="vinn_int")
    mod.vss_bias1 = h.Signal(name="vss_bias1")
    mod.vss_bias2 = h.Signal(name="vss_bias2")
    mod.enb = h.Signal(name="enb")
    mod.vgn = h.Signal(name="vgn")
    mod.vgp = h.Signal(name="vgp")
    mod.vgn_bias = h.Signal(name="vgn_bias")
    mod.vgp_bias = h.Signal(name="vgp_bias")
    mod.tail1_drv = h.Signal(name="tail1_drv")
    mod.vx_load = h.Signal(name="vx_load")
    mod.vref_load = h.Signal(name="vref_load")

    inv_npar = _mos_params(1.0, 0.15)
    inv_ppar = _mos_params(2.0, 0.15)
    mod.m_enb_p = pmos(inv_ppar)(d=mod.enb, g=mod.EN, s=mod.VDD, b=mod.VDD)
    mod.m_enb_n = nmos(inv_npar)(d=mod.enb, g=mod.EN, s=mod.VSS, b=mod.VSS)

    tail_ref_par = _mos_params(params.w_tail_ref, params.l_tail_ref)
    tail_par = _mos_params(params.w_tail, params.l_tail)
    mod.m_ibias1_ref = pmos(tail_ref_par)(d=mod.vbp1, g=mod.vbp1, s=mod.VDD, b=mod.VDD)
    mod.r_ibias1_ref = pdk_resistor(params.r_stage1_bias, p=mod.vbp1, n=mod.vss_bias1, bulk=mod.VSS)
    mod.m_bias1_en = nmos(_mos_params(4.0, 0.15))(d=mod.vss_bias1, g=mod.EN, s=mod.VSS, b=mod.VSS)
    mod.m_ibias1 = pmos(tail_par)(d=mod.ibias1, g=mod.vbp1, s=mod.VDD, b=mod.VDD)
    mod.m_tail1_sw = pmos(_mos_params(params.w_tail_sw, params.l_tail_sw))(d=mod.tail1_drv, g=mod.enb, s=mod.ibias1, b=mod.VDD)
    mod.m_ibias1_off = pmos(inv_ppar)(d=mod.vbp1, g=mod.EN, s=mod.VDD, b=mod.VDD)
    mod.m_ibias1_tail_off = pmos(inv_ppar)(d=mod.ibias1, g=mod.EN, s=mod.VDD, b=mod.VDD)
    mod.m_tail1_off = pmos(inv_ppar)(d=mod.tail1_drv, g=mod.EN, s=mod.VDD, b=mod.VDD)

    tg_npar = _mos_params(4.0, 0.15)
    tg_ppar = _mos_params(4.0, 0.15)
    mod.m_vinp_tg_n = nmos(tg_npar)(d=mod.vinp_int, g=mod.EN, s=mod.VINP, b=mod.VSS)
    mod.m_vinp_tg_p = pmos(tg_ppar)(d=mod.vinp_int, g=mod.enb, s=mod.VINP, b=mod.VDD)
    mod.m_vinn_tg_n = nmos(tg_npar)(d=mod.vinn_int, g=mod.EN, s=mod.VINN, b=mod.VSS)
    mod.m_vinn_tg_p = pmos(tg_ppar)(d=mod.vinn_int, g=mod.enb, s=mod.VINN, b=mod.VDD)
    mod.m_vinp_off = pmos(inv_ppar)(d=mod.vinp_int, g=mod.EN, s=mod.VDD, b=mod.VDD)
    mod.m_vinn_off = pmos(inv_ppar)(d=mod.vinn_int, g=mod.EN, s=mod.VDD, b=mod.VDD)

    if params.debug_current_probes:
        mod.vdrv_s2p = h.Signal(name="vdrv_s2p")
        mod.vdrv_s2n = h.Signal(name="vdrv_s2n")
        mod.vout_op = h.Signal(name="vout_op")
        mod.vout_on = h.Signal(name="vout_on")
        mod.vprobe_s2p = h.Vdc(dc=0)(p=mod.vdrv_s2p, n=mod.vdrv)
        mod.vprobe_s2n = h.Vdc(dc=0)(p=mod.vdrv_s2n, n=mod.vdrv)
        mod.vprobe_outp = h.Vdc(dc=0)(p=mod.vout_op, n=mod.VOUT)
        mod.vprobe_outn = h.Vdc(dc=0)(p=mod.vout_on, n=mod.VOUT)
        vdrv_s2p = mod.vdrv_s2p
        vdrv_s2n = mod.vdrv_s2n
        vout_op = mod.vout_op
        vout_on = mod.vout_on
    else:
        vdrv_s2p = mod.vdrv
        vdrv_s2n = mod.vdrv
        vout_op = mod.VOUT
        vout_on = mod.VOUT

    mod.xin = diffpair(INP=mod.vinp_int, INN=mod.vinn_int, OUTP=mod.vx, OUTN=mod.vref, TAIL=mod.tail1, VDD=mod.VDD, VSS=mod.VSS)
    load_par = _mos_params(params.w_load, params.l_load)
    mod.m_load_ref = nmos(load_par)(d=mod.vref_load, g=mod.vref, s=mod.VSS, b=mod.VSS)
    mod.m_load_out = nmos(load_par)(d=mod.vx_load, g=mod.vref, s=mod.VSS, b=mod.VSS)
    mod.vlink_tail1 = h.Vdc(dc=0)(p=mod.tail1_drv, n=mod.tail1)
    mod.vlink_load_out = h.Vdc(dc=0)(p=mod.vx_load, n=mod.vx)
    mod.vlink_load_ref = h.Vdc(dc=0)(p=mod.vref_load, n=mod.vref)

    stage2_bias_ref_par = _mos_params(params.w_stage2_bias_ref, params.l_stage2_bias_ref)
    mod.m_ibias2_ref = pmos(stage2_bias_ref_par)(d=mod.ibias2, g=mod.ibias2, s=mod.VDD, b=mod.VDD)
    mod.r_ibias2_ref = pdk_resistor(params.r_stage2_bias, p=mod.ibias2, n=mod.vss_bias2, bulk=mod.VSS)
    mod.m_bias2_en = nmos(_mos_params(4.0, 0.15))(d=mod.vss_bias2, g=mod.EN, s=mod.VSS, b=mod.VSS)
    mod.m_ibias2_off = pmos(inv_ppar)(d=mod.ibias2, g=mod.EN, s=mod.VDD, b=mod.VDD)

    mod.m_stage2_p = pmos(_mos_params(params.w_stage2_p, params.l_stage2_p))(d=vdrv_s2p, g=mod.ibias2, s=mod.VDD, b=mod.VDD)
    mod.m_stage2_n = nmos(_mos_params(params.w_stage2_n, params.l_stage2_n))(d=vdrv_s2n, g=mod.vx, s=mod.VSS, b=mod.VSS)
    mod.m_stage2_off = nmos(inv_npar)(d=mod.vdrv, g=mod.enb, s=mod.VSS, b=mod.VSS)

    # Idealized direct two-gate law with explicit branch offsets.
    mod.vvgn_bias = h.Vdc(dc=0.45)(p=mod.vgn_bias, n=mod.VSS)
    mod.vvgp_bias = h.Vdc(dc=0.65)(p=mod.vgp_bias, n=mod.VSS)
    mod.evgn = h.Vcvs(h.ControlledSourceParams(gain=0.22))(p=mod.vgn, n=mod.vgn_bias, cp=mod.VDD, cn=mod.vdrv)
    mod.evgp = h.Vcvs(h.ControlledSourceParams(gain=0.18))(p=mod.vgp, n=mod.vgp_bias, cp=mod.VDD, cn=mod.vdrv)
    mod.xout_stage = out_stage(VGN=mod.vgn, VGP=mod.vgp, VOUTP=vout_op, VOUTN=vout_on, VDD=mod.VDD, VSS=mod.VSS)

    mod.cc = pdk_mim_capacitor(params.c_comp, p=mod.vx, n=mod.vdrv)
    return mod


def _build_follower_tb(dut, *, vin: float, load_mode: str = "none", load_uA: float = 0.0):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp, vinn, vout, en, vdd = h.Signals(5)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        ven = h.Vdc(dc=1.8)(p=en, n=VSS)
        vvinn = h.Vdc(dc=vin)(p=vinn, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinp)
        rl = h.Res(r=1e6)(p=vout, n=VSS)
        cl = h.Cap(c=1e-12)(p=vout, n=VSS)
        xdut = dut(VINP=vinp, VINN=vinn, VOUT=vout, EN=en, VDD=vdd, VSS=VSS)
        # External load semantics:
        # - source: inject current into VOUT, DUT must sink it to hold low.
        # - sink: draw current from VOUT, DUT must source it to hold high.
        if load_mode == "source":
            iload = h.Idc(dc=load_uA * 1e-6)(p=vdd, n=vout)
        elif load_mode == "sink":
            iload = h.Idc(dc=load_uA * 1e-6)(p=vout, n=VSS)

    return Tb


def _op_case(dut, *, name: str, vin: float, load_mode: str = "none", load_uA: float = 0.0) -> dict[str, float | str]:
    install = require_sky130_install()
    sim = Sim(tb=_build_follower_tb(dut, vin=vin, load_mode=load_mode, load_uA=load_uA), attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)])
    res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/rc_ideal_drv_op_{uuid4().hex[:8]}")
    d = res.an[0].data
    return {
        "case": name,
        "vin_V": float(vin),
        "load_mode": load_mode,
        "load_uA": float(load_uA),
        "vx_V": float(d["v(xtop.xxdut.vx)"]),
        "vref_V": float(d["v(xtop.xxdut.vref)"]),
        "vdrv_V": float(d["v(xtop.xxdut.vdrv)"]),
        "vgn_V": float(d["v(xtop.xxdut.vgn)"]),
        "vgp_V": float(d["v(xtop.xxdut.vgp)"]),
        "gate_avg_V": 0.5 * (float(d["v(xtop.xxdut.vgn)"]) + float(d["v(xtop.xxdut.vgp)"])),
        "gate_spread_V": float(d["v(xtop.xxdut.vgn)"]) - float(d["v(xtop.xxdut.vgp)"]),
        "vout_V": float(d["v(xtop.vout)"]),
        "i_stage2_p_A": float(d["i(v.xtop.xxdut.vvprobe_s2p)"]),
        "i_stage2_n_A": float(d["i(v.xtop.xxdut.vvprobe_s2n)"]),
        "i_out_p_A": float(d["i(v.xtop.xxdut.vvprobe_outp)"]),
        "i_out_n_A": float(d["i(v.xtop.xxdut.vvprobe_outn)"]),
    }


class TestRcProbeIdealizedDriverAB(BaseV3SimTest):
    def test_probe_current_vs_idealized_driver(self) -> None:
        reset_metrics_file(METRICS_PATH)
        current_dc = opamp_core(build_debug_core_params())
        ideal_dc = _idealized_driver_core(build_debug_core_params())

        payload = {
            "current": {
                "follower_mid": _op_case(current_dc, name="follower_mid", vin=0.9),
                "drive_source_20u": _op_case(current_dc, name="drive_source_20u", vin=0.9, load_mode="source", load_uA=20.0),
                "drive_sink_20u": _op_case(current_dc, name="drive_sink_20u", vin=0.9, load_mode="sink", load_uA=20.0),
            },
            "idealized_driver": {
                "follower_mid": _op_case(ideal_dc, name="follower_mid", vin=0.9),
                "drive_source_20u": _op_case(ideal_dc, name="drive_source_20u", vin=0.9, load_mode="source", load_uA=20.0),
                "drive_sink_20u": _op_case(ideal_dc, name="drive_sink_20u", vin=0.9, load_mode="sink", load_uA=20.0),
            },
        }
        write_metrics_json(METRICS_PATH, payload)
        self.assertTrue(True)
