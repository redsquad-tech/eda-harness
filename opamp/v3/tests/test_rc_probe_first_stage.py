from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import SimOptions

from components import require_sky130_install, run_ngspice_sim
from components.diffpair_p import DiffpairPParams, diffpair_p
from opamp.v3.opamp_core import OpampCoreParams, _mos_params
from opamp.v3.pdk_passives import pdk_precision_resistor
from opamp.v3.tests._helpers import BaseV3SimTest, build_debug_core_params


METRICS_PATH = Path(__file__).with_name("rc_probe_first_stage_metrics.json")


def _debug_params() -> OpampCoreParams:
    return build_debug_core_params()


def first_stage(params: OpampCoreParams) -> h.Module:
    pmos = sky130_hdl21.primitives.PMOS_1p8V_STD
    nmos = sky130_hdl21.primitives.NMOS_1p8V_STD
    diffpair = diffpair_p(DiffpairPParams(w_in=params.w_in, l_in=params.l_in, nf_in=1, m_in=1))

    mod = h.Module(name="RcFirstStageProbe")
    mod.VINP, mod.VINN, mod.EN, mod.VDD, mod.VSS = h.Ports(5)
    mod.vx, mod.vref = h.Signals(2)
    mod.tail1, mod.ibias1, mod.vbp1, mod.vss_bias1 = h.Signals(4)
    mod.enb = h.Signal(name="enb")
    mod.vx_lp, mod.vref_lp, mod.tail_lp = h.Signals(3)
    mod.vprobe_vx = h.Vdc(dc=0)(p=mod.vx_lp, n=mod.vx)
    mod.vprobe_vref = h.Vdc(dc=0)(p=mod.vref_lp, n=mod.vref)
    mod.vprobe_tail = h.Vdc(dc=0)(p=mod.tail_lp, n=mod.tail1)

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
    mod.m_tail1_sw = pmos(_mos_params(params.w_tail_sw, params.l_tail_sw))(d=mod.tail_lp, g=mod.enb, s=mod.ibias1, b=mod.VDD)

    mod.xin = diffpair(INP=mod.VINP, INN=mod.VINN, OUTP=mod.vx_lp, OUTN=mod.vref_lp, TAIL=mod.tail1, VDD=mod.VDD, VSS=mod.VSS)
    load_par = _mos_params(params.w_load, params.l_load)
    mod.m_load_ref = nmos(load_par)(d=mod.vref, g=mod.vref, s=mod.VSS, b=mod.VSS)
    mod.m_load_out = nmos(load_par)(d=mod.vx, g=mod.vref, s=mod.VSS, b=mod.VSS)
    return mod


def _build_tb(dut, *, vinp: float, vinn: float):
    @h.module
    class Tb:
        VSS = h.Port()
        vdd, en, vinp_sig, vinn_sig = h.Signals(4)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        vven = h.Vdc(dc=1.8)(p=en, n=VSS)
        vvinp = h.Vdc(dc=vinp)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=vinn)(p=vinn_sig, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, EN=en, VDD=vdd, VSS=VSS)

    return Tb


def _op_case(dut, *, name: str, vinp: float, vinn: float) -> dict[str, float | str]:
    install = require_sky130_install()
    sim = Sim(tb=_build_tb(dut, vinp=vinp, vinn=vinn), attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)])
    res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/rc_fs_{uuid4().hex[:8]}")
    d = res.an[0].data
    return {
        "case": name,
        "vinp_V": float(vinp),
        "vinn_V": float(vinn),
        "vx_V": float(d["v(xtop.xxdut.vx)"]),
        "vref_V": float(d["v(xtop.xxdut.vref)"]),
        "vcm_out_V": 0.5 * (float(d["v(xtop.xxdut.vx)"]) + float(d["v(xtop.xxdut.vref)"])),
        "vdiff_out_V": float(d["v(xtop.xxdut.vx)"]) - float(d["v(xtop.xxdut.vref)"]),
        "i_vx_load_A": float(d["i(v.xtop.xxdut.vvprobe_vx)"]),
        "i_vref_load_A": float(d["i(v.xtop.xxdut.vvprobe_vref)"]),
        "i_tail_A": float(d["i(v.xtop.xxdut.vvprobe_tail)"]),
        "vbp1_V": float(d["v(xtop.xxdut.vbp1)"]),
        "ibias1_V": float(d["v(xtop.xxdut.ibias1)"]),
        "tail1_V": float(d["v(xtop.xxdut.tail1)"]),
    }


class TestRcProbeFirstStage(BaseV3SimTest):
    def test_probe_rc_first_stage(self):
        dut = first_stage(_debug_params())
        payload = {
            "cases": [
                _op_case(dut, name="balanced_mid", vinp=0.9, vinn=0.9),
                _op_case(dut, name="vinp_up_10m", vinp=0.91, vinn=0.9),
                _op_case(dut, name="vinn_up_10m", vinp=0.9, vinn=0.91),
                _op_case(dut, name="vinp_low_10m", vinp=0.89, vinn=0.9),
            ]
        }
        METRICS_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        self.assertEqual(len(payload["cases"]), 4)
