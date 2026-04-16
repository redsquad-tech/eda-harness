from __future__ import annotations

import json
import math
from pathlib import Path
from uuid import uuid4

import hdl21 as h
import numpy as np
from hdl21.sim import Ac, LogSweep, Save, Sim
from vlsirtools.spice import ResultFormat

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.common import extract_ac_trace, interp_crossing, interp_value, unique_ngspice_options
from opamp.v3.opamp_core import opamp_core
from opamp.v3.tests._helpers import BaseV3SimTest, build_core_params


METRICS_PATH = Path(__file__).with_name("rc_probe_loop_partition_ac_metrics.json")


def _build_tb(dut):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, en, vdd_sig = h.Signals(5)
        vvdd = h.Vdc(dc=1.8)(p=vdd_sig, n=VSS)
        ven = h.Vdc(dc=1.8)(p=en, n=VSS)
        vvinn = h.Vdc(dc=0.9, ac=1.0)(p=vinn_sig, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinp_sig)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        rload = h.Res(r=1e12)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, EN=en, VDD=vdd_sig, VSS=VSS)

    return Tb


def _mag_phase(z: complex) -> dict[str, float]:
    return {
        "mag_vv": float(abs(z)),
        "phase_deg": float(np.angle(z) * 180.0 / math.pi),
    }


class TestRcProbeLoopPartitionAc(BaseV3SimTest):
    def test_probe_loop_partition_ac(self):
        install = require_sky130_install()
        dut = opamp_core(build_core_params())
        sim = Sim(
            tb=_build_tb(dut),
            attrs=[
                Ac(sweep=LogSweep(1.0, 1e9, 40)),
                Save(
                    "v(xtop.vinp_sig), v(xtop.xxdut.vx), v(xtop.xxdut.vdrv), "
                    "v(xtop.xxdut.vgn), v(xtop.xxdut.vgp), v(xtop.vout)"
                ),
                h.sim.Literal(".temp 27"),
                install.include(h.pdk.Corner.TYP),
            ],
        )
        res = run_ngspice_sim(
            sim,
            unique_ngspice_options("rc_probe_loop_partition_ac", fmt=ResultFormat.SIM_DATA),
            rundir=f"./tmp/rc_loop_part_{uuid4().hex[:8]}",
        )

        freq, vin = extract_ac_trace(res, "v(xtop.vinp_sig)")
        _, vx = extract_ac_trace(res, "v(xtop.xxdut.vx)")
        _, vdrv = extract_ac_trace(res, "v(xtop.xxdut.vdrv)")
        _, vgn = extract_ac_trace(res, "v(xtop.xxdut.vgn)")
        _, vgp = extract_ac_trace(res, "v(xtop.xxdut.vgp)")
        _, vout = extract_ac_trace(res, "v(xtop.vout)")

        freq = np.asarray(freq, dtype=float)
        vin = np.asarray(vin)
        vx = np.asarray(vx)
        vdrv = np.asarray(vdrv)
        vgn = np.asarray(vgn)
        vgp = np.asarray(vgp)
        vout = np.asarray(vout)
        gate_avg = 0.5 * (vgn + vgp)
        gate_spread = vgn - vgp

        closed_loop_gain = vout / np.where(np.abs(vin) > 1e-30, vin, 1e-30 + 0j)
        loop_gain = closed_loop_gain / np.where(np.abs(1.0 - closed_loop_gain) > 1e-30, 1.0 - closed_loop_gain, 1e-30 + 0j)
        unity_hz, _ = interp_crossing(freq, np.abs(loop_gain), 1.0)

        low = {
            "freq_Hz": float(freq[0]),
            "vinp_to_vx": _mag_phase(vx[0] / vin[0]),
            "vx_to_vdrv": _mag_phase(vdrv[0] / vx[0]),
            "vdrv_to_gate_avg": _mag_phase(gate_avg[0] / vdrv[0]),
            "vdrv_to_gate_spread": _mag_phase(gate_spread[0] / vdrv[0]),
            "gate_avg_to_vgn": _mag_phase(vgn[0] / gate_avg[0]),
            "gate_avg_to_vgp": _mag_phase(vgp[0] / gate_avg[0]),
            "gate_avg_to_vout": _mag_phase(vout[0] / gate_avg[0]),
            "vdrv_to_vout": _mag_phase(vout[0] / vdrv[0]),
            "vinp_to_vout": _mag_phase(vout[0] / vin[0]),
            "loop_gain": _mag_phase(loop_gain[0]),
        }
        payload = {
            "low_freq": low,
            "unity_loop_crossing_Hz": float(unity_hz),
            "unity_phase_margin_deg": float(180.0 + interp_value(freq, np.unwrap(np.angle(loop_gain)) * 180.0 / math.pi, unity_hz))
            if math.isfinite(unity_hz)
            else float("nan"),
        }
        METRICS_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        self.assertTrue(True)
