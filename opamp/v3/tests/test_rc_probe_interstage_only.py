from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import SimOptions

from components import require_sky130_install, run_ngspice_sim
from components.diffpair_p import DiffpairPParams, diffpair_p
from opamp.v3.opamp_core import OpampCoreParams, _mos_params
from opamp.v3.pdk_passives import pdk_mim_capacitor, pdk_precision_resistor
from opamp.v3.tests._helpers import BaseV3SimTest, build_debug_core_params, reset_metrics_file, write_metrics_json


METRICS_PATH = Path(__file__).with_name("rc_probe_interstage_only_metrics.json")


def interstage_only(params: OpampCoreParams) -> h.Module:
    pmos = sky130_hdl21.primitives.PMOS_1p8V_STD
    nmos = sky130_hdl21.primitives.NMOS_1p8V_STD
    diffpair = diffpair_p(DiffpairPParams(w_in=params.w_in, l_in=params.l_in, nf_in=1, m_in=1))

    mod = h.Module(name="RcInterstageOnly")
    mod.VINP, mod.VINN, mod.EN, mod.VDD, mod.VSS, mod.VDRV = h.Ports(6)
    mod.vx, mod.vref = h.Signals(2)
    mod.ibias1, mod.ibias2 = h.Signals(2)
    mod.tail1 = h.Signal(name="tail1")
    mod.vbp1 = h.Signal(name="vbp1")
    mod.vss_bias1 = h.Signal(name="vss_bias1")
    mod.vss_bias2 = h.Signal(name="vss_bias2")
    mod.enb = h.Signal(name="enb")
    mod.tail1_drv = h.Signal(name="tail1_drv")
    mod.vx_load = h.Signal(name="vx_load")
    mod.vref_load = h.Signal(name="vref_load")
    mod.vdrv_s2p = h.Signal(name="vdrv_s2p")
    mod.vdrv_s2n = h.Signal(name="vdrv_s2n")
    mod.vprobe_s2p = h.Vdc(dc=0)(p=mod.vdrv_s2p, n=mod.VDRV)
    mod.vprobe_s2n = h.Vdc(dc=0)(p=mod.vdrv_s2n, n=mod.VDRV)

    inv_npar = _mos_params(1.0, 0.15)
    inv_ppar = _mos_params(2.0, 0.15)
    mod.m_enb_p = pmos(inv_ppar)(d=mod.enb, g=mod.EN, s=mod.VDD, b=mod.VDD)
    mod.m_enb_n = nmos(inv_npar)(d=mod.enb, g=mod.EN, s=mod.VSS, b=mod.VSS)

    tail_ref_par = _mos_params(params.w_tail_ref, params.l_tail_ref)
    tail_par = _mos_params(params.w_tail, params.l_tail)
    mod.m_ibias1_ref = pmos(tail_ref_par)(d=mod.vbp1, g=mod.vbp1, s=mod.VDD, b=mod.VDD)
    mod.r_ibias1_ref = pdk_precision_resistor(params.r_stage1_bias, p=mod.vbp1, n=mod.vss_bias1, bulk=mod.VSS)
    mod.m_bias1_en = nmos(_mos_params(4.0, 0.15))(d=mod.vss_bias1, g=mod.EN, s=mod.VSS, b=mod.VSS)
    mod.m_ibias1 = pmos(tail_par)(d=mod.ibias1, g=mod.vbp1, s=mod.VDD, b=mod.VDD)
    mod.m_tail1_sw = pmos(_mos_params(params.w_tail_sw, params.l_tail_sw))(d=mod.tail1_drv, g=mod.enb, s=mod.ibias1, b=mod.VDD)
    mod.vlink_tail1 = h.Vdc(dc=0)(p=mod.tail1_drv, n=mod.tail1)

    mod.xin = diffpair(INP=mod.VINP, INN=mod.VINN, OUTP=mod.vx, OUTN=mod.vref, TAIL=mod.tail1, VDD=mod.VDD, VSS=mod.VSS)
    load_par = _mos_params(params.w_load, params.l_load)
    mod.vlink_load_out = h.Vdc(dc=0)(p=mod.vx_load, n=mod.vx)
    mod.vlink_load_ref = h.Vdc(dc=0)(p=mod.vref_load, n=mod.vref)
    mod.m_load_ref = nmos(load_par)(d=mod.vref_load, g=mod.vref, s=mod.VSS, b=mod.VSS)
    mod.m_load_out = nmos(load_par)(d=mod.vx_load, g=mod.vref, s=mod.VSS, b=mod.VSS)

    stage2_bias_ref_par = _mos_params(params.w_stage2_bias_ref, params.l_stage2_bias_ref)
    mod.m_ibias2_ref = pmos(stage2_bias_ref_par)(d=mod.ibias2, g=mod.ibias2, s=mod.VDD, b=mod.VDD)
    mod.r_ibias2_ref = pdk_precision_resistor(params.r_stage2_bias, p=mod.ibias2, n=mod.vss_bias2, bulk=mod.VSS)
    mod.m_bias2_en = nmos(_mos_params(4.0, 0.15))(d=mod.vss_bias2, g=mod.EN, s=mod.VSS, b=mod.VSS)
    mod.m_ibias2_off = pmos(inv_ppar)(d=mod.ibias2, g=mod.EN, s=mod.VDD, b=mod.VDD)
    mod.m_stage2_p = pmos(_mos_params(params.w_stage2_p, params.l_stage2_p))(d=mod.vdrv_s2p, g=mod.ibias2, s=mod.VDD, b=mod.VDD)
    mod.m_stage2_n = nmos(_mos_params(params.w_stage2_n, params.l_stage2_n))(d=mod.vdrv_s2n, g=mod.vx, s=mod.VSS, b=mod.VSS)
    mod.m_stage2_off = nmos(inv_npar)(d=mod.VDRV, g=mod.enb, s=mod.VSS, b=mod.VSS)
    mod.cc = pdk_mim_capacitor(params.c_comp, p=mod.vx, n=mod.VDRV)
    return mod


def _build_tb(dut):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp, vinn, en, vdd, vdrv = h.Signals(5)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        vven = h.Vdc(dc=1.8)(p=en, n=VSS)
        vvinp = h.Vdc(dc=0.9)(p=vinp, n=VSS)
        vvinn = h.Vdc(dc=0.9)(p=vinn, n=VSS)
        rload = h.Res(r=1e6)(p=vdrv, n=VSS)
        cload = h.Cap(c=1e-12)(p=vdrv, n=VSS)
        xdut = dut(VINP=vinp, VINN=vinn, EN=en, VDD=vdd, VSS=VSS, VDRV=vdrv)

    return Tb


class TestRcProbeInterstageOnly(BaseV3SimTest):
    def test_probe_rc_interstage_only(self):
        reset_metrics_file(METRICS_PATH)
        install = require_sky130_install()
        dut = interstage_only(build_debug_core_params())
        sim = Sim(tb=_build_tb(dut), attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)])
        res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/rc_interonly_{uuid4().hex[:8]}")
        d = res.an[0].data
        payload = {
            "vin_V": 0.9,
            "vx_V": float(d["v(xtop.xxdut.vx)"]),
            "vref_V": float(d["v(xtop.xxdut.vref)"]),
            "vx_minus_vref_V": float(d["v(xtop.xxdut.vx)"]) - float(d["v(xtop.xxdut.vref)"]),
            "vdrv_V": float(d["v(xtop.vdrv)"]),
            "i_stage2_p_A": float(d["i(v.xtop.xxdut.vvprobe_s2p)"]),
            "i_stage2_n_A": float(d["i(v.xtop.xxdut.vvprobe_s2n)"]),
            "i_tail1_A": float(d["i(v.xtop.xxdut.vvlink_tail1)"]),
            "i_load_out_A": float(d["i(v.xtop.xxdut.vvlink_load_out)"]),
            "i_load_ref_A": float(d["i(v.xtop.xxdut.vvlink_load_ref)"]),
        }
        write_metrics_json(METRICS_PATH, payload)
        self.assertTrue(True)
