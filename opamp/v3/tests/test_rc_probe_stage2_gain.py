from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import hdl21 as h
import numpy as np
from hdl21.sim import Ac, LogSweep, Op, Save, Sim
from vlsirtools.spice import SimOptions

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.tests._helpers import BaseV3SimTest, build_debug_core_params
from opamp.v3.tests.test_rc_probe_stage2_standalone import stage2_core


METRICS_PATH = Path(__file__).with_name("rc_probe_stage2_gain_metrics.json")


def _build_op_tb(dut, *, vx: float):
    @h.module
    class Tb:
        VSS = h.Port()
        vdd, vdrv, vx_sig, en = h.Signals(4)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        vven = h.Vdc(dc=1.8)(p=en, n=VSS)
        vvx = h.Vdc(dc=vx)(p=vx_sig, n=VSS)
        cload = h.Cap(c=100e-15)(p=vdrv, n=VSS)
        xdut = dut(VX=vx_sig, VDRV=vdrv, EN=en, VDD=vdd, VSS=VSS)

    return Tb


def _build_ac_tb(dut, *, vx: float):
    @h.module
    class Tb:
        VSS = h.Port()
        vdd, vdrv, vx_sig, en = h.Signals(4)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        vven = h.Vdc(dc=1.8)(p=en, n=VSS)
        vvx = h.Vdc(dc=vx, ac=1e-3)(p=vx_sig, n=VSS)
        cload = h.Cap(c=100e-15)(p=vdrv, n=VSS)
        xdut = dut(VX=vx_sig, VDRV=vdrv, EN=en, VDD=vdd, VSS=VSS)

    return Tb


def _run_case(vx: float) -> dict[str, float]:
    install = require_sky130_install()
    dut = stage2_core(build_debug_core_params())
    op_res = run_ngspice_sim(
        Sim(
            tb=_build_op_tb(dut, vx=vx),
            attrs=[Op(), Save("v(xtop.vdrv), v(xtop.xxdut.ibias2)"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)],
        ),
        SimOptions(fmt="sim_data"),
        rundir=f"./tmp/rc_s2_gain_op_{uuid4().hex[:8]}",
    )
    ac_res = run_ngspice_sim(
        Sim(
            tb=_build_ac_tb(dut, vx=vx),
            attrs=[Ac(sweep=LogSweep(1.0, 1e6, 20)), Save("v(xtop.vdrv)"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)],
        ),
        SimOptions(fmt="sim_data"),
        rundir=f"./tmp/rc_s2_gain_ac_{uuid4().hex[:8]}",
    )
    op_data = op_res.an[0].data
    ac_data = ac_res.an[0].data
    vdrv_ac = np.asarray(ac_data["v(xtop.vdrv)"])
    av2_vv = abs(vdrv_ac[0]) / 1e-3
    av2_db = float(20.0 * np.log10(max(av2_vv, 1e-30)))
    return {
        "vx_in_V": float(vx),
        "vdrv_dc_V": float(op_data["v(xtop.vdrv)"]),
        "ibias2_V": float(op_data["v(xtop.xxdut.ibias2)"]),
        "av2_db": av2_db,
    }


class TestRcProbeStage2Gain(BaseV3SimTest):
    def test_probe_stage2_gain(self) -> None:
        payload = {
            "cases": [
                _run_case(0.4920730791485733),
                _run_case(0.5964480707640147),
                _run_case(0.6150377937322378),
            ]
        }
        METRICS_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        self.assertEqual(len(payload["cases"]), 3)
