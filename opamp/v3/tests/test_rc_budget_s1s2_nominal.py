from __future__ import annotations

import json
from pathlib import Path

from opamp.v3.tests._helpers import BaseV3SimTest
from opamp.v3.tests.test_rc_probe_interstage_only import _build_tb, interstage_only
from opamp.v3.tests._helpers import build_debug_core_params
import hdl21 as h
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import SimOptions
from components import require_sky130_install, run_ngspice_sim
from uuid import uuid4


METRICS_PATH = Path(__file__).with_name("rc_budget_s1s2_nominal_metrics.json")


class TestRcBudgetS1S2Nominal(BaseV3SimTest):
    def test_balanced_nominal_tracks_vref(self) -> None:
        install = require_sky130_install()
        dut = interstage_only(build_debug_core_params())
        sim = Sim(tb=_build_tb(dut), attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)])
        res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/rc_s1s2_budget_{uuid4().hex[:8]}")
        d = res.an[0].data

        vx = float(d["v(xtop.xxdut.vx)"])
        vref = float(d["v(xtop.xxdut.vref)"])
        vdrv = float(d["v(xtop.vdrv)"])
        i_stage2_p = abs(float(d["i(v.xtop.xxdut.vvprobe_s2p)"]))
        i_stage2_n = abs(float(d["i(v.xtop.xxdut.vvprobe_s2n)"]))
        stage2_ratio = i_stage2_n / max(i_stage2_p, 1e-18)

        payload = {
            "vx_V": vx,
            "vref_V": vref,
            "vx_minus_vref_V": vx - vref,
            "vdrv_V": vdrv,
            "i_stage2_p_A": i_stage2_p,
            "i_stage2_n_A": i_stage2_n,
            "stage2_n_to_p_ratio": stage2_ratio,
            "budgets": {
                "abs_vx_minus_vref_max_V": 10e-3,
                "vref_min_V": 0.2,
                "vref_max_V": 1.6,
                "stage2_ratio_min": 0.05,
            },
        }
        METRICS_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

        self.assertLessEqual(abs(vx - vref), 10e-3)
        self.assertGreaterEqual(vref, 0.2)
        self.assertLessEqual(vref, 1.6)
        self.assertGreaterEqual(stage2_ratio, 0.05)
