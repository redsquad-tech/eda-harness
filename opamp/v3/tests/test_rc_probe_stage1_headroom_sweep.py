from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import hdl21 as h
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import ResultFormat

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.common import unique_ngspice_options
from opamp.v3.opamp_core import OpampCoreParams, opamp_core
from opamp.v3.tests._helpers import BaseV3SimTest, build_core_params, reset_metrics_file, write_metrics_json


METRICS_PATH = Path(__file__).with_name("rc_probe_stage1_headroom_sweep_metrics.json")


def _build_tb(dut):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, en, vdd_sig = h.Signals(5)
        vvdd = h.Vdc(dc=1.8)(p=vdd_sig, n=VSS)
        ven = h.Vdc(dc=1.8)(p=en, n=VSS)
        vvinp = h.Vdc(dc=0.9)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=0.9)(p=vinn_sig, n=VSS)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, EN=en, VDD=vdd_sig, VSS=VSS)

    return Tb


def _run_case(name: str, **updates) -> dict[str, float | str]:
    install = require_sky130_install()
    params = build_core_params(**updates)
    dut = opamp_core(params)
    res = run_ngspice_sim(
        Sim(
            tb=_build_tb(dut),
            attrs=[
                Op(),
                Save("v(xtop.vout), v(xtop.xxdut.vx), v(xtop.xxdut.vref), v(xtop.xxdut.tail1), v(xtop.xxdut.vdrv)"),
                h.sim.Literal(".temp 27"),
                install.include(h.pdk.Corner.TYP),
            ],
        ),
        unique_ngspice_options(f"rc_probe_stage1_headroom_{name}", fmt=ResultFormat.SIM_DATA),
        rundir=f"./tmp/rc_s1_headroom_{uuid4().hex[:8]}",
    )
    d = res.an[0].data
    vx = float(d["v(xtop.xxdut.vx)"])
    vref = float(d["v(xtop.xxdut.vref)"])
    tail1 = float(d["v(xtop.xxdut.tail1)"])
    vdrv = float(d["v(xtop.xxdut.vdrv)"])
    return {
        "case": name,
        "w_load_um": float(params.w_load),
        "l_load_um": float(params.l_load),
        "vx_V": vx,
        "vref_V": vref,
        "tail1_V": tail1,
        "vdrv_V": vdrv,
        "vin_cm_minus_vx_V": 0.9 - vx,
        "vdd_minus_tail1_V": 1.8 - tail1,
        "vx_minus_vref_V": vx - vref,
    }


class TestRcProbeStage1HeadroomSweep(BaseV3SimTest):
    def test_probe_stage1_headroom_sweep(self) -> None:
        reset_metrics_file(METRICS_PATH)
        cases = [
            _run_case("base"),
            _run_case("wload8_l10", w_load=8.0, l_load=10.0),
            _run_case("wload12_l10", w_load=12.0, l_load=10.0),
            _run_case("wload8_l12", w_load=8.0, l_load=12.0),
            _run_case("wload12_l12", w_load=12.0, l_load=12.0),
            _run_case("wload16_l12", w_load=16.0, l_load=12.0),
        ]
        write_metrics_json(METRICS_PATH, {"cases": cases})
        self.assertEqual(len(cases), 6)
