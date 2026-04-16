from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import hdl21 as h
import numpy as np
import sky130_hdl21
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import SimOptions

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.opamp_core import _mos_params
from opamp.v3.pdk_passives import pdk_precision_resistor
from opamp.v3.prod.rc import current_core_params
from opamp.v3.tests._helpers import BaseV3SimTest


METRICS_PATH = Path(__file__).with_name("rc_probe_stage2_cascode_bias_sweep_metrics.json")


def stage2_casc_p_only(params) -> h.Module:
    pmos = sky130_hdl21.primitives.PMOS_1p8V_STD
    nmos = sky130_hdl21.primitives.NMOS_1p8V_STD

    mod = h.Module(name="RcStage2CascPBiasOnly")
    mod.VX, mod.VBCAS2P, mod.VDRV, mod.EN, mod.VDD, mod.VSS = h.Ports(6)
    mod.ibias2 = h.Signal(name="ibias2")
    mod.vss_bias2 = h.Signal(name="vss_bias2")
    mod.vstage2_p_int = h.Signal(name="vstage2_p_int")
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

    mod.m_stage2_p = pmos(_mos_params(params.w_stage2_p, params.l_stage2_p))(d=mod.vstage2_p_int, g=mod.ibias2, s=mod.VDD, b=mod.VDD)
    mod.m_stage2_casc_p = pmos(_mos_params(12.0, 1.0))(d=mod.vdrv_s2p, g=mod.VBCAS2P, s=mod.vstage2_p_int, b=mod.VDD)
    mod.m_stage2_n = nmos(_mos_params(params.w_stage2_n, params.l_stage2_n))(d=mod.vdrv_s2n, g=mod.VX, s=mod.VSS, b=mod.VSS)
    mod.m_stage2_off = nmos(inv_npar)(d=mod.VDRV, g=mod.enb, s=mod.VSS, b=mod.VSS)
    return mod


def _build_tb(dut, *, vx: float, vbcas2p: float):
    @h.module
    class Tb:
        VSS = h.Port()
        vdd, vdrv, vx_sig, vbcas2p_sig, en = h.Signals(5)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        vven = h.Vdc(dc=1.8)(p=en, n=VSS)
        vvx = h.Vdc(dc=vx)(p=vx_sig, n=VSS)
        vvbcas = h.Vdc(dc=vbcas2p)(p=vbcas2p_sig, n=VSS)
        cload = h.Cap(c=100e-15)(p=vdrv, n=VSS)
        xdut = dut(VX=vx_sig, VBCAS2P=vbcas2p_sig, VDRV=vdrv, EN=en, VDD=vdd, VSS=VSS)

    return Tb


def _op_case(dut, *, vx: float, vbcas2p: float) -> dict[str, float]:
    install = require_sky130_install()
    sim = Sim(
        tb=_build_tb(dut, vx=vx, vbcas2p=vbcas2p),
        attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)],
    )
    res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/rc_s2_casp_{uuid4().hex[:8]}")
    d = res.an[0].data
    i_p = float(d["i(v.xtop.xxdut.vvprobe_s2p)"])
    i_n = float(d["i(v.xtop.xxdut.vvprobe_s2n)"])
    return {
        "vx_in_V": float(vx),
        "vbcas2p_V": float(vbcas2p),
        "vdrv_V": float(d["v(xtop.vdrv)"]),
        "ibias2_V": float(d["v(xtop.xxdut.ibias2)"]),
        "i_stage2_p_A": i_p,
        "i_stage2_n_A": i_n,
        "stage2_current_ratio": abs(i_n) / max(abs(i_p), 1e-18),
    }


class TestRcProbeStage2CascodeBiasSweep(BaseV3SimTest):
    def test_probe_stage2_cascode_bias_sweep(self) -> None:
        params = current_core_params()
        dut = stage2_casc_p_only(params)
        vx_values = [0.35, 0.45, 0.55, 0.65, 0.75, 0.85]
        vbias_values = [0.9, 1.05, 1.2, 1.35, 1.5, 1.6]
        cases = [_op_case(dut, vx=vx, vbcas2p=vbias) for vx in vx_values for vbias in vbias_values]

        useful = [
            c
            for c in cases
            if 0.7 <= float(c["vdrv_V"]) <= 1.1 and 0.3 <= float(c["stage2_current_ratio"]) <= 1.2
        ]
        payload = {"cases": cases, "useful_window": useful}
        METRICS_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        self.assertEqual(len(cases), len(vx_values) * len(vbias_values))
