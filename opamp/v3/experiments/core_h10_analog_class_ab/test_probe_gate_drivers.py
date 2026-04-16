from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import SimOptions

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.opamp_core import _mos_params
from opamp.v3.pdk_passives import pdk_resistor
from opamp.v3.tests._helpers import BaseV3SimTest


METRICS_PATH = Path(__file__).with_name("driver_metrics.json")


def gate_drivers() -> h.Module:
    pmos = sky130_hdl21.primitives.PMOS_1p8V_STD
    nmos = sky130_hdl21.primitives.NMOS_1p8V_STD

    mod = h.Module(name="CoreH10GateDriversProbe")
    mod.VDRV, mod.VBUF, mod.VGN, mod.VGP, mod.VDD, mod.VSS = h.Ports(6)
    mod.vbuf_drv = h.Signal(name="vbuf_drv")
    mod.vgn_drv = h.Signal(name="vgn_drv")
    mod.vgp_drv = h.Signal(name="vgp_drv")
    mod.vprobe_vbuf = h.Vdc(dc=0)(p=mod.vbuf_drv, n=mod.VBUF)
    mod.vprobe_vgn = h.Vdc(dc=0)(p=mod.vgn_drv, n=mod.VGN)
    mod.vprobe_vgp = h.Vdc(dc=0)(p=mod.vgp_drv, n=mod.VGP)
    mod.m_buf_p = pmos(_mos_params(2.0, 0.15))(d=mod.vbuf_drv, g=mod.VDRV, s=mod.VDD, b=mod.VDD)
    mod.m_buf_n = nmos(_mos_params(1.0, 0.15))(d=mod.vbuf_drv, g=mod.VDRV, s=mod.VSS, b=mod.VSS)
    mod.r_vgn_pulldown = pdk_resistor(150e3, p=mod.VGN, n=mod.VSS, bulk=mod.VSS)
    mod.m_vgn_p = pmos(_mos_params(0.8, 0.15))(d=mod.VSS, g=mod.VDRV, s=mod.vgn_drv, b=mod.VDD)
    mod.r_vgp_pullup = pdk_resistor(150e3, p=mod.VDD, n=mod.VGP, bulk=mod.VSS)
    mod.m_vgp_n = nmos(_mos_params(0.8, 0.15))(d=mod.VDD, g=mod.VDRV, s=mod.vgp_drv, b=mod.VSS)
    return mod


def _build_tb(dut, *, vdrv: float):
    @h.module
    class Tb:
        VSS = h.Port()
        vdd, vdrv_sig, vbuf, vgn, vgp = h.Signals(5)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        vvdrv = h.Vdc(dc=vdrv)(p=vdrv_sig, n=VSS)
        xdut = dut(VDRV=vdrv_sig, VBUF=vbuf, VGN=vgn, VGP=vgp, VDD=vdd, VSS=VSS)

    return Tb


def _op_case(dut, *, name: str, vdrv: float) -> dict[str, float | str]:
    install = require_sky130_install()
    sim = Sim(tb=_build_tb(dut, vdrv=vdrv), attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)])
    res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/core_h9_drv_{uuid4().hex[:8]}")
    d = res.an[0].data
    vbuf = float(d["v(xtop.vbuf)"])
    vgn = float(d["v(xtop.vgn)"])
    vgp = float(d["v(xtop.vgp)"])
    return {
        "case": name,
        "vdrv_in_V": float(vdrv),
        "vbuf_V": vbuf,
        "vgn_V": vgn,
        "vgp_V": vgp,
        "gate_spread_V": vgp - vgn,
        "ab_spread_V": vgn - vgp,
        "gate_cm_V": 0.5 * (vgp + vgn),
        "vbuf_minus_vdrv_V": vbuf - float(vdrv),
        "vgn_minus_vdrv_V": vgn - float(vdrv),
        "vgp_minus_vdrv_V": vgp - float(vdrv),
        "i_vbuf_driver_A": float(d["i(v.xtop.xxdut.vvprobe_vbuf)"]),
        "i_vgn_driver_A": float(d["i(v.xtop.xxdut.vvprobe_vgn)"]),
        "i_vgp_driver_A": float(d["i(v.xtop.xxdut.vvprobe_vgp)"]),
    }


class TestCoreH10ProbeGateDrivers(BaseV3SimTest):
    def test_probe_gate_drivers(self):
        dut = gate_drivers()
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
        METRICS_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        self.assertEqual(len(payload["cases"]), 7)
