from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import hdl21 as h
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import SimOptions

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.tests._helpers import BaseV3SimTest, reset_metrics_file, write_metrics_json
from opamp.v3.tests._probe_blocks import output_driver_probe


METRICS_PATH = Path(__file__).with_name("rc_probe_gate_drivers_metrics.json")


def _build_tb(dut, *, vdrv: float):
    @h.module
    class Tb:
        VSS = h.Port()
        vdd, vdrv_sig, vgn, vgp = h.Signals(4)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        vvdrv = h.Vdc(dc=vdrv)(p=vdrv_sig, n=VSS)
        xdut = dut(VDRV=vdrv_sig, VGN=vgn, VGP=vgp, VDD=vdd, VSS=VSS)

    return Tb


def _op_case(dut, *, name: str, vdrv: float) -> dict[str, float | str]:
    install = require_sky130_install()
    sim = Sim(tb=_build_tb(dut, vdrv=vdrv), attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)])
    res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/rc_drv_{uuid4().hex[:8]}")
    d = res.an[0].data
    vgn = float(d["v(xtop.vgn)"])
    vgp = float(d["v(xtop.vgp)"])
    return {
        "case": name,
        "vdrv_in_V": float(vdrv),
        "vgn_V": vgn,
        "vgp_V": vgp,
        "vgn_minus_vgp_V": vgn - vgp,
        "gate_avg_V": 0.5 * (vgn + vgp),
        "vgn_minus_vdrv_V": vgn - float(vdrv),
        "vgp_minus_vdrv_V": vgp - float(vdrv),
    }


class TestRcProbeGateDrivers(BaseV3SimTest):
    def test_probe_rc_gate_drivers(self):
        reset_metrics_file(METRICS_PATH)
        dut = output_driver_probe()
        payload = {
            "cases": [
                _op_case(dut, name="vdrv_0p0", vdrv=0.0),
                _op_case(dut, name="vdrv_0p4", vdrv=0.4),
                _op_case(dut, name="vdrv_0p8", vdrv=0.8),
                _op_case(dut, name="vdrv_1p0", vdrv=1.0),
                _op_case(dut, name="vdrv_1p2", vdrv=1.2),
                _op_case(dut, name="vdrv_1p6", vdrv=1.6),
                _op_case(dut, name="vdrv_1p8", vdrv=1.8),
            ]
        }
        write_metrics_json(METRICS_PATH, payload)
        self.assertEqual(len(payload["cases"]), 7)
