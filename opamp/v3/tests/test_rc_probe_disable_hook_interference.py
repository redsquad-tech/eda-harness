from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import hdl21 as h
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import SimOptions

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.opamp_core import opamp_core
from opamp.v3.tests._helpers import BaseV3SimTest, build_debug_core_params, reset_metrics_file, write_metrics_json


METRICS_PATH = Path(__file__).with_name("rc_probe_disable_hook_interference_metrics.json")


def _build_tb(dut):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp, vinn, vout, en, vdd = h.Signals(5)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        ven = h.Vdc(dc=1.8)(p=en, n=VSS)
        vvinn = h.Vdc(dc=0.9)(p=vinn, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinp)
        rl = h.Res(r=1e6)(p=vout, n=VSS)
        cl = h.Cap(c=1e-12)(p=vout, n=VSS)
        xdut = dut(VINP=vinp, VINN=vinn, VOUT=vout, EN=en, VDD=vdd, VSS=VSS)

    return Tb


class TestRcProbeDisableHookInterference(BaseV3SimTest):
    def test_probe_rc_disable_hook_interference(self):
        reset_metrics_file(METRICS_PATH)
        install = require_sky130_install()
        dut = opamp_core(build_debug_core_params())
        sim = Sim(
            tb=_build_tb(dut),
            attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)],
        )
        res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/rc_disable_{uuid4().hex[:8]}")
        d = res.an[0].data
        vdd = float(d["v(xtop.vdd)"])
        en = float(d["v(xtop.en)"])
        enb = float(d["v(xtop.xxdut.enb)"])
        payload = {
            "en_V": en,
            "enb_V": enb,
            "stage2_off_vgs_V": enb - 0.0,
            "stage2_off_vds_V": float(d["v(xtop.xxdut.vdrv)"]) - 0.0,
            "ibias1_off_vsg_V": vdd - en,
            "ibias1_off_vsd_V": vdd - float(d["v(xtop.xxdut.vbp1)"]),
            "tail1_off_vsg_V": vdd - en,
            "tail1_off_vsd_V": vdd - float(d["v(xtop.xxdut.tail1_drv)"]),
            "ibias2_off_vsg_V": vdd - en,
            "ibias2_off_vsd_V": vdd - float(d["v(xtop.xxdut.ibias2)"]),
            "vdrv_V": float(d["v(xtop.xxdut.vdrv)"]),
            "vout_V": float(d["v(xtop.vout)"]),
            "vx_V": float(d["v(xtop.xxdut.vx)"]),
            "vref_V": float(d["v(xtop.xxdut.vref)"]),
        }
        write_metrics_json(METRICS_PATH, payload)
        self.assertLess(abs(payload["stage2_off_vgs_V"]), 1e-3)
        self.assertLess(abs(payload["ibias1_off_vsg_V"]), 1e-3)
        self.assertLess(abs(payload["tail1_off_vsg_V"]), 1e-3)
        self.assertLess(abs(payload["ibias2_off_vsg_V"]), 1e-3)
