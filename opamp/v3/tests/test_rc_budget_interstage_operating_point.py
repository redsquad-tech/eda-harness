from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import hdl21 as h
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import SimOptions

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.opamp_core import opamp_core
from opamp.v3.tests._helpers import BaseV3SimTest, build_debug_core_params, reset_metrics_file, write_metrics_json


METRICS_PATH = Path(__file__).with_name("rc_budget_interstage_operating_point_metrics.json")


def _build_tb(dut):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp, vinn, vout, en, vdd = h.Signals(5)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        ven = h.Vdc(dc=1.8)(p=en, n=VSS)
        vvinp = h.Vdc(dc=0.9)(p=vinp, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinn)
        rl = h.Res(r=1e6)(p=vout, n=VSS)
        cl = h.Cap(c=1e-12)(p=vout, n=VSS)
        xdut = dut(VINP=vinp, VINN=vinn, VOUT=vout, EN=en, VDD=vdd, VSS=VSS)

    return Tb


class TestRcBudgetInterstageOperatingPoint(BaseV3SimTest):
    def test_interstage_operating_point_not_collapsed(self) -> None:
        reset_metrics_file(METRICS_PATH)
        install = require_sky130_install()
        dut = opamp_core(build_debug_core_params())
        sim = Sim(tb=_build_tb(dut), attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)])
        res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/rc_interstage_{uuid4().hex[:8]}")
        d = res.an[0].data

        vx = float(d["v(xtop.xxdut.vx)"])
        vdrv = float(d["v(xtop.xxdut.vdrv)"])
        i_stage2_p = abs(float(d["i(v.xtop.xxdut.vvprobe_s2p)"]))
        i_stage2_n = abs(float(d["i(v.xtop.xxdut.vvprobe_s2n)"]))
        current_ratio = i_stage2_n / max(i_stage2_p, 1e-18)

        payload = {
            "vin_V": 0.9,
            "vx_V": vx,
            "vdrv_V": vdrv,
            "vout_V": float(d["v(xtop.vout)"]),
            "i_stage2_p_A": i_stage2_p,
            "i_stage2_n_A": i_stage2_n,
            "stage2_n_to_p_ratio": current_ratio,
            "budgets": {
                "vx_nominal_min_V": 0.1,
                "vx_nominal_max_V": 1.7,
                "vdrv_nominal_max_V": 1.5,
                "stage2_n_to_p_ratio_min": 1e-3,
            },
        }
        write_metrics_json(METRICS_PATH, payload)

        self.assertGreaterEqual(vx, 0.1, "Balanced nominal must not collapse VX to ground")
        self.assertLessEqual(vx, 1.7, "Balanced nominal must not rail VX")
        self.assertLessEqual(vdrv, 1.5, "Balanced nominal must not rail VDRV high")
        self.assertGreaterEqual(current_ratio, 1e-3, "Stage2 NMOS must not be effectively off at nominal")
