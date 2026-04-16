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
from opamp.v3.pdk_passives import pdk_precision_resistor
from opamp.v3.tests._helpers import BaseV3SimTest, build_debug_core_params


METRICS_PATH = Path(__file__).with_name("rc_probe_stage2_current_match_metrics.json")


def stage2_current_match_core(params: OpampCoreParams) -> h.Module:
    pmos = sky130_hdl21.primitives.PMOS_1p8V_STD
    nmos = sky130_hdl21.primitives.NMOS_1p8V_STD

    mod = h.Module(name="RcStage2CurrentMatch")
    mod.VX, mod.VOUT, mod.EN, mod.VDD, mod.VSS = h.Ports(5)
    mod.ibias2 = h.Signal(name="ibias2")
    mod.vss_bias2 = h.Signal(name="vss_bias2")
    mod.vout_s2p = h.Signal(name="vout_s2p")
    mod.vout_s2n = h.Signal(name="vout_s2n")
    mod.vprobe_s2p = h.Vdc(dc=0)(p=mod.vout_s2p, n=mod.VOUT)
    mod.vprobe_s2n = h.Vdc(dc=0)(p=mod.vout_s2n, n=mod.VOUT)

    stage2_bias_ref_par = _mos_params(params.w_stage2_bias_ref, params.l_stage2_bias_ref)
    mod.m_ibias2_ref = pmos(stage2_bias_ref_par)(d=mod.ibias2, g=mod.ibias2, s=mod.VDD, b=mod.VDD)
    mod.r_ibias2_ref = pdk_precision_resistor(params.r_stage2_bias, p=mod.ibias2, n=mod.vss_bias2, bulk=mod.VSS)
    mod.m_bias2_en = nmos(_mos_params(4.0, 0.15))(d=mod.vss_bias2, g=mod.EN, s=mod.VSS, b=mod.VSS)

    mod.m_stage2_p = pmos(_mos_params(params.w_stage2_p, params.l_stage2_p))(d=mod.vout_s2p, g=mod.ibias2, s=mod.VDD, b=mod.VDD)
    mod.m_stage2_n = nmos(_mos_params(params.w_stage2_n, params.l_stage2_n))(d=mod.vout_s2n, g=mod.VX, s=mod.VSS, b=mod.VSS)
    return mod


def _build_tb(dut, *, vx: float, vout: float):
    @h.module
    class Tb:
        VSS = h.Port()
        vdd, vout_sig, vx_sig, en = h.Signals(4)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        vven = h.Vdc(dc=1.8)(p=en, n=VSS)
        vvx = h.Vdc(dc=vx)(p=vx_sig, n=VSS)
        vvout = h.Vdc(dc=vout)(p=vout_sig, n=VSS)
        xdut = dut(VX=vx_sig, VOUT=vout_sig, EN=en, VDD=vdd, VSS=VSS)

    return Tb


class TestRcProbeStage2CurrentMatch(BaseV3SimTest):
    def test_probe_stage2_current_match(self) -> None:
        install = require_sky130_install()
        params = build_debug_core_params()
        dut = stage2_current_match_core(params)
        sim = Sim(
            tb=_build_tb(dut, vx=0.4891259346607286, vout=0.9),
            attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)],
        )
        res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/rc_s2_match_{uuid4().hex[:8]}")
        d = res.an[0].data

        i_stage2_p = float(d["i(v.xtop.xxdut.vvprobe_s2p)"])
        i_stage2_n = float(d["i(v.xtop.xxdut.vvprobe_s2n)"])
        target_p_lo = 0.7 * abs(i_stage2_n)
        target_p_hi = 0.9 * abs(i_stage2_n)

        payload = {
            "vx_forced_V": 0.4891259346607286,
            "vout_forced_V": 0.9,
            "ibias2_V": float(d["v(xtop.xxdut.ibias2)"]),
            "i_stage2_n_A": i_stage2_n,
            "i_stage2_p_A": i_stage2_p,
            "i_stage2_n_abs_uA": 1e6 * abs(i_stage2_n),
            "i_stage2_p_abs_uA": 1e6 * abs(i_stage2_p),
            "target_stage2_p_lo_uA": 1e6 * target_p_lo,
            "target_stage2_p_hi_uA": 1e6 * target_p_hi,
            "current_ratio_p_over_n": abs(i_stage2_p) / max(abs(i_stage2_n), 1e-18),
        }
        METRICS_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        self.assertTrue(abs(i_stage2_n) > 0.0)

