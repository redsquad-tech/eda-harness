from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
from uuid import uuid4

import hdl21 as h
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import SimOptions

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.opamp_ota import OpampOtaParams, opamp_ota
from opamp.v3.tests._helpers import BaseV3SimTest, build_debug_core_params


METRICS_PATH = Path(__file__).with_name("rc_probe_ota_stage2p_bias_sweep_metrics.json")


def _base_params() -> OpampOtaParams:
    core = build_debug_core_params()
    payload = {f.name: getattr(core, f.name) for f in fields(core) if f.name in OpampOtaParams.__dict__}
    return OpampOtaParams(**payload)


def _with(params: OpampOtaParams, **updates) -> OpampOtaParams:
    payload = {f.name: getattr(params, f.name) for f in fields(params)}
    payload.update(updates)
    return OpampOtaParams(**payload)


def _build_tb(dut):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, vdd_sig = h.Signals(4)
        vvdd = h.Vdc(dc=1.8)(p=vdd_sig, n=VSS)
        vvinp = h.Vdc(dc=0.90005)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=0.89995)(p=vinn_sig, n=VSS)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, VDD=vdd_sig, VSS=VSS)

    return Tb


def _op_case(name: str, params: OpampOtaParams) -> dict[str, float | str]:
    install = require_sky130_install()
    dut = opamp_ota(params)
    sim = Sim(
        tb=_build_tb(dut),
        attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)],
    )
    res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/rc_ota_s2p_{uuid4().hex[:8]}")
    d = res.an[0].data
    return {
        "case": name,
        "w_stage2_p": float(params.w_stage2_p),
        "l_stage2_p": float(params.l_stage2_p),
        "r_stage2_bias": float(params.r_stage2_bias),
        "vx_V": float(d["v(xtop.xxdut.vx)"]),
        "vref_V": float(d["v(xtop.xxdut.vref)"]),
        "vdrv_V": float(d["v(xtop.xxdut.vdrv)"]),
        "ibias2_V": float(d["v(xtop.xxdut.ibias2)"]),
    }


class TestRcProbeOtaStage2PBiasSweep(BaseV3SimTest):
    def test_probe_ota_stage2p_bias_sweep(self) -> None:
        base = _base_params()
        cases = [
            ("baseline", base),
            ("weaker_p_w8_l12", _with(base, w_stage2_p=8.0, l_stage2_p=12.0)),
            ("weaker_p_w6_l12", _with(base, w_stage2_p=6.0, l_stage2_p=12.0)),
            ("weaker_p_w6_l16", _with(base, w_stage2_p=6.0, l_stage2_p=16.0)),
            ("weaker_p_bias7m", _with(base, r_stage2_bias=7.0e6)),
            ("weaker_p_bias9m", _with(base, r_stage2_bias=9.0e6)),
            ("combo_w6_l16_bias9m", _with(base, w_stage2_p=6.0, l_stage2_p=16.0, r_stage2_bias=9.0e6)),
        ]
        payload = {"cases": [_op_case(name, params) for name, params in cases]}
        METRICS_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        self.assertEqual(len(payload["cases"]), len(cases))
