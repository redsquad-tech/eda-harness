from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import hdl21 as h
import numpy as np
from hdl21.sim import Op, Save, SaveMode, Sim, Tran
from vlsirtools.spice import SimOptions

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.tests._helpers import BaseV3SimTest
from opamp.v3.tests.test_rc_probe_output_subckt import _debug_params, output_subckt


METRICS_PATH = Path(__file__).with_name("rc_probe_output_op_vs_tran_metrics.json")


def _tran_waveform(result, signal_name: str) -> np.ndarray:
    tran = result.an[0].tran if hasattr(result.an[0], "tran") else result.an[0]
    if hasattr(tran, "signals"):
        target = signal_name.lower()
        signals = list(tran.signals)
        idx = next((i for i, name in enumerate(signals) if name.lower() == target), None)
        if idx is None:
            raise RuntimeError(f"Signal {signal_name} not found in tran result: {signals}")
        nsignals = len(signals)
        data = list(tran.data)
        npts = len(data) // nsignals
        start = idx * npts
        return np.asarray(data[start : start + npts], dtype=float)
    return np.asarray(tran.data[signal_name], dtype=float)


def _build_op_tb(dut, *, vdrv: float):
    @h.module
    class Tb:
        VSS = h.Port()
        vdrv_sig, vout, vdd = h.Signals(3)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        vvdrv = h.Vdc(dc=vdrv)(p=vdrv_sig, n=VSS)
        rload = h.Res(r=1e6)(p=vout, n=VSS)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        xdut = dut(VDRV=vdrv_sig, VOUT=vout, VDD=vdd, VSS=VSS)

    return Tb


def _build_tran_tb(dut, *, vdrv: float):
    @h.module
    class Tb:
        VSS = h.Port()
        vdrv_sig, vout, vdd = h.Signals(3)
        vvdd = h.Vpulse(v1=0.0, v2=1.8, delay=0.0, rise=100e-9, fall=100e-9, width=20e-6, period=40e-6)(p=vdd, n=VSS)
        vvdrv = h.Vpulse(v1=0.0, v2=vdrv, delay=0.0, rise=100e-9, fall=100e-9, width=20e-6, period=40e-6)(p=vdrv_sig, n=VSS)
        rload = h.Res(r=1e6)(p=vout, n=VSS)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        xdut = dut(VDRV=vdrv_sig, VOUT=vout, VDD=vdd, VSS=VSS)

    return Tb


def _case(dut, *, name: str, vdrv: float) -> dict[str, float | str]:
    install = require_sky130_install()
    op_sim = Sim(tb=_build_op_tb(dut, vdrv=vdrv), attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)])
    op_res = run_ngspice_sim(op_sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/rc_optran_op_{uuid4().hex[:8]}")
    op_data = op_res.an[0].data

    tran_sim = Sim(
        tb=_build_tran_tb(dut, vdrv=vdrv),
        attrs=[Tran(tstop=10e-6, tstep=10e-9), Save(SaveMode.ALL), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)],
    )
    tran_res = run_ngspice_sim(tran_sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/rc_optran_tran_{uuid4().hex[:8]}")
    vout_tran = _tran_waveform(tran_res, "v(xtop.vout)")
    vgn_tran = _tran_waveform(tran_res, "v(xtop.xxdut.vgn)")
    vgp_tran = _tran_waveform(tran_res, "v(xtop.xxdut.vgp)")

    return {
        "case": name,
        "vdrv_in_V": float(vdrv),
        "op_vout_V": float(op_data["v(xtop.vout)"]),
        "op_vgn_V": float(op_data["v(xtop.xxdut.vgn)"]),
        "op_vgp_V": float(op_data["v(xtop.xxdut.vgp)"]),
        "tran_vout_final_V": float(vout_tran[-1]),
        "tran_vgn_final_V": float(vgn_tran[-1]),
        "tran_vgp_final_V": float(vgp_tran[-1]),
        "abs_vout_delta_V": abs(float(vout_tran[-1]) - float(op_data["v(xtop.vout)"])),
    }


class TestRcProbeOutputOpVsTran(BaseV3SimTest):
    def test_probe_rc_output_op_vs_tran(self):
        dut = output_subckt(_debug_params())
        payload = {
            "cases": [
                _case(dut, name="vdrv_1p0", vdrv=1.0),
                _case(dut, name="vdrv_1p8", vdrv=1.8),
            ]
        }
        METRICS_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        self.assertEqual(len(payload["cases"]), 2)
