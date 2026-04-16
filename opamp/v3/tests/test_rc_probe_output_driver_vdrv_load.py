from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import hdl21 as h
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import SimOptions

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.opamp_core import opamp_core
from opamp.v3.tests._helpers import BaseV3SimTest, build_debug_core_params, reset_metrics_file, write_metrics_json


METRICS_PATH = Path(__file__).with_name("rc_probe_output_driver_vdrv_load_metrics.json")


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


def _run_case(**param_updates) -> dict[str, float]:
    install = require_sky130_install()
    dut = opamp_core(build_debug_core_params(**param_updates))
    sim = Sim(tb=_build_tb(dut), attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)])
    res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/rc_vdrvload_{uuid4().hex[:8]}")
    d = res.an[0].data
    return {
        "vx_V": float(d["v(xtop.xxdut.vx)"]),
        "vref_V": float(d["v(xtop.xxdut.vref)"]),
        "vdrv_V": float(d["v(xtop.xxdut.vdrv)"]),
        "vout_V": float(d["v(xtop.vout)"]),
        "i_stage2_p_A": float(d["i(v.xtop.xxdut.vvprobe_s2p)"]),
        "i_stage2_n_A": float(d["i(v.xtop.xxdut.vvprobe_s2n)"]),
        "i_vdrv_into_driver_A": float(d.get("i(v.xtop.xxdut.vvprobe_vdrv_drv)", 0.0)),
        "output_path_present": "i(v.xtop.xxdut.vvprobe_vdrv_drv)" in d,
    }


class TestRcProbeOutputDriverVdrvLoad(BaseV3SimTest):
    def test_probe_rc_output_driver_vdrv_load(self):
        reset_metrics_file(METRICS_PATH)
        payload = {
            "baseline": _run_case(),
            "signal_paths_opened": _run_case(
                r_outdrv_vgn_from_vdrv=1e15,
                r_outdrv_vgp_from_vdrv=1e15,
            ),
        }
        write_metrics_json(METRICS_PATH, payload)
        self.assertIn("baseline", payload)
        baseline = payload["baseline"]
        signal_paths_opened = payload["signal_paths_opened"]
        if not bool(baseline["output_path_present"]):
            self.assertAlmostEqual(float(baseline["i_vdrv_into_driver_A"]), 0.0, delta=1e-18)
            return
        stage2_quiescent = max(
            abs(float(baseline["i_stage2_p_A"])),
            abs(float(baseline["i_stage2_n_A"])),
            1e-18,
        )
        driver_load_ratio = abs(float(baseline["i_vdrv_into_driver_A"])) / stage2_quiescent
        self.assertLess(driver_load_ratio, 0.1)
        if abs(float(baseline["i_vdrv_into_driver_A"])) > 0.0:
            self.assertLess(
                abs(float(signal_paths_opened["i_vdrv_into_driver_A"])),
                abs(float(baseline["i_vdrv_into_driver_A"])),
            )
