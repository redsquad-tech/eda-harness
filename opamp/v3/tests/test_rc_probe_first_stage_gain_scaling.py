from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
from uuid import uuid4

import hdl21 as h
import numpy as np
from hdl21.sim import Ac, LogSweep, Op, Save, Sim
from vlsirtools.spice import SimOptions

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.opamp_core import OpampCoreParams
from opamp.v3.tests._helpers import BaseV3SimTest, build_debug_core_params
from opamp.v3.tests.test_rc_probe_first_stage import first_stage


METRICS_PATH = Path(__file__).with_name("rc_probe_first_stage_gain_scaling_metrics.json")


def _case_params(name: str) -> OpampCoreParams:
    base = build_debug_core_params()
    base_payload = {f.name: getattr(base, f.name) for f in fields(base)}
    if name == "baseline":
        return base
    if name == "scale_x2":
        return OpampCoreParams(
            **{
                **base_payload,
                "w_in": 28.0,
                "l_in": 6.0,
                "w_load": 8.0,
                "l_load": 16.0,
            }
        )
    if name == "scale_x3":
        return OpampCoreParams(
            **{
                **base_payload,
                "w_in": 42.0,
                "l_in": 9.0,
                "w_load": 12.0,
                "l_load": 24.0,
            }
        )
    raise ValueError(name)


def _build_op_tb(dut):
    @h.module
    class Tb:
        VSS = h.Port()
        vdd, en, vinp_sig, vinn_sig = h.Signals(4)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        vven = h.Vdc(dc=1.8)(p=en, n=VSS)
        vvinp = h.Vdc(dc=0.9)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=0.9)(p=vinn_sig, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, EN=en, VDD=vdd, VSS=VSS)

    return Tb


def _build_ac_tb(dut):
    @h.module
    class Tb:
        VSS = h.Port()
        vdd, en, vinp_sig, vinn_sig = h.Signals(4)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        vven = h.Vdc(dc=1.8)(p=en, n=VSS)
        vvinp = h.Vdc(dc=0.9, ac=50e-6)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=0.9, ac=-50e-6)(p=vinn_sig, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, EN=en, VDD=vdd, VSS=VSS)

    return Tb


def _run_case(name: str) -> dict[str, float | str]:
    install = require_sky130_install()
    params = _case_params(name)
    dut = first_stage(params)

    op_res = run_ngspice_sim(
        Sim(
            tb=_build_op_tb(dut),
            attrs=[Op(), Save("v(xtop.xxdut.vx), v(xtop.xxdut.vref), v(xtop.xxdut.tail1)"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)],
        ),
        SimOptions(fmt="sim_data"),
        rundir=f"./tmp/rc_fs_gain_op_{uuid4().hex[:8]}",
    )
    ac_res = run_ngspice_sim(
        Sim(
            tb=_build_ac_tb(dut),
            attrs=[Ac(sweep=LogSweep(1.0, 1e6, 20)), Save("v(xtop.xxdut.vx), v(xtop.xxdut.vref)"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)],
        ),
        SimOptions(fmt="sim_data"),
        rundir=f"./tmp/rc_fs_gain_ac_{uuid4().hex[:8]}",
    )

    d = op_res.an[0].data
    ac = ac_res.an[0].data
    vx_ac = np.asarray(ac["v(xtop.xxdut.vx)"])
    vref_ac = np.asarray(ac["v(xtop.xxdut.vref)"])
    vin_diff = 100e-6
    av1_vx_db = float(20.0 * np.log10(max(abs(vx_ac[0]) / vin_diff, 1e-30)))
    av1_diff_db = float(20.0 * np.log10(max(abs(vx_ac[0] - vref_ac[0]) / vin_diff, 1e-30)))

    return {
        "case": name,
        "w_in": float(params.w_in),
        "l_in": float(params.l_in),
        "w_load": float(params.w_load),
        "l_load": float(params.l_load),
        "vx_dc_V": float(d["v(xtop.xxdut.vx)"]),
        "vref_dc_V": float(d["v(xtop.xxdut.vref)"]),
        "tail1_dc_V": float(d["v(xtop.xxdut.tail1)"]),
        "av1_vx_db": av1_vx_db,
        "av1_diff_db": av1_diff_db,
    }


class TestRcProbeFirstStageGainScaling(BaseV3SimTest):
    def test_first_stage_gain_scaling(self) -> None:
        payload = {"cases": [_run_case("baseline"), _run_case("scale_x2"), _run_case("scale_x3")]}
        METRICS_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        self.assertEqual(len(payload["cases"]), 3)
