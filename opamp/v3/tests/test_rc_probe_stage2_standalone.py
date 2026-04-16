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
from opamp.v3.pdk_passives import pdk_mim_capacitor, pdk_precision_resistor
from opamp.v3.tests._helpers import BaseV3SimTest, build_debug_core_params


METRICS_PATH = Path(__file__).with_name("rc_probe_stage2_standalone_metrics.json")


def _debug_params() -> OpampCoreParams:
    return build_debug_core_params()


def stage2_core(params: OpampCoreParams) -> h.Module:
    pmos = sky130_hdl21.primitives.PMOS_1p8V_STD
    nmos = sky130_hdl21.primitives.NMOS_1p8V_STD

    mod = h.Module(name="RcStage2Standalone")
    mod.VX, mod.VDRV, mod.EN, mod.VDD, mod.VSS = h.Ports(5)
    mod.ibias2 = h.Signal(name="ibias2")
    mod.vss_bias2 = h.Signal(name="vss_bias2")
    mod.enb = h.Signal(name="enb")
    mod.vdrv_s2p = h.Signal(name="vdrv_s2p")
    mod.vdrv_s2n = h.Signal(name="vdrv_s2n")
    mod.vprobe_s2p = h.Vdc(dc=0)(p=mod.vdrv_s2p, n=mod.VDRV)
    mod.vprobe_s2n = h.Vdc(dc=0)(p=mod.vdrv_s2n, n=mod.VDRV)

    inv_npar = _mos_params(1.0, 0.15)
    inv_ppar = _mos_params(2.0, 0.15)
    mod.m_enb_p = pmos(inv_ppar)(d=mod.enb, g=mod.EN, s=mod.VDD, b=mod.VDD)
    mod.m_enb_n = nmos(inv_npar)(d=mod.enb, g=mod.EN, s=mod.VSS, b=mod.VSS)

    stage2_bias_ref_par = _mos_params(params.w_stage2_bias_ref, params.l_stage2_bias_ref)
    mod.m_ibias2_ref = pmos(stage2_bias_ref_par)(d=mod.ibias2, g=mod.ibias2, s=mod.VDD, b=mod.VDD)
    mod.r_ibias2_ref = pdk_precision_resistor(params.r_stage2_bias, p=mod.ibias2, n=mod.vss_bias2, bulk=mod.VSS)
    mod.m_bias2_en = nmos(_mos_params(4.0, 0.15))(d=mod.vss_bias2, g=mod.EN, s=mod.VSS, b=mod.VSS)
    mod.m_ibias2_off = pmos(inv_ppar)(d=mod.ibias2, g=mod.EN, s=mod.VDD, b=mod.VDD)

    mod.m_stage2_p = pmos(_mos_params(params.w_stage2_p, params.l_stage2_p))(d=mod.vdrv_s2p, g=mod.ibias2, s=mod.VDD, b=mod.VDD)
    mod.m_stage2_n = nmos(_mos_params(params.w_stage2_n, params.l_stage2_n))(d=mod.vdrv_s2n, g=mod.VX, s=mod.VSS, b=mod.VSS)
    mod.m_stage2_off = nmos(inv_npar)(d=mod.VDRV, g=mod.enb, s=mod.VSS, b=mod.VSS)
    mod.cc = pdk_mim_capacitor(params.c_comp, p=mod.VX, n=mod.VDRV)
    return mod


def _build_tb(dut, *, vx: float):
    @h.module
    class Tb:
        VSS = h.Port()
        vdd, vdrv, vx_sig, en = h.Signals(4)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        vven = h.Vdc(dc=1.8)(p=en, n=VSS)
        vvx = h.Vdc(dc=vx)(p=vx_sig, n=VSS)
        rload = h.Res(r=1e6)(p=vdrv, n=VSS)
        cload = h.Cap(c=100e-15)(p=vdrv, n=VSS)
        xdut = dut(VX=vx_sig, VDRV=vdrv, EN=en, VDD=vdd, VSS=VSS)

    return Tb


def _op_case(dut, *, name: str, vx: float) -> dict[str, float | str]:
    install = require_sky130_install()
    sim = Sim(tb=_build_tb(dut, vx=vx), attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)])
    res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/rc_s2_{uuid4().hex[:8]}")
    d = res.an[0].data
    return {
        "case": name,
        "vx_in_V": float(vx),
        "vdrv_V": float(d["v(xtop.vdrv)"]),
        "ibias2_V": float(d["v(xtop.xxdut.ibias2)"]),
        "i_stage2_p_A": float(d["i(v.xtop.xxdut.vvprobe_s2p)"]),
        "i_stage2_n_A": float(d["i(v.xtop.xxdut.vvprobe_s2n)"]),
        "stage2_current_ratio": abs(float(d["i(v.xtop.xxdut.vvprobe_s2n)"])) / max(abs(float(d["i(v.xtop.xxdut.vvprobe_s2p)"])), 1e-18),
    }


class TestRcProbeStage2Standalone(BaseV3SimTest):
    def test_probe_rc_stage2_standalone(self):
        dut = stage2_core(_debug_params())
        payload = {
            "cases": [
                _op_case(dut, name="vx_0p0", vx=0.0),
                _op_case(dut, name="vx_0p4", vx=0.4),
                _op_case(dut, name="vx_0p6", vx=0.6),
                _op_case(dut, name="vx_0p75", vx=0.75),
                _op_case(dut, name="vx_0p9", vx=0.9),
                _op_case(dut, name="vx_1p2", vx=1.2),
                _op_case(dut, name="vx_1p6", vx=1.6),
            ]
        }
        METRICS_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        self.assertEqual(len(payload["cases"]), 7)
