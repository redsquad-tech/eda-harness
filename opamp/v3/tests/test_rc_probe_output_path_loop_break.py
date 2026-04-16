from __future__ import annotations

import json
import math
from pathlib import Path
from uuid import uuid4

import hdl21 as h
import numpy as np
from hdl21.sim import Ac, LogSweep, Op, Save, Sim
from vlsirtools.spice import ResultFormat

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.common import extract_ac_trace, interp_crossing, interp_value, negative_feedback_phase_trace, op_scalar, unique_ngspice_options
from opamp.v3.opamp_core import opamp_core
from opamp.v3.s1s2_path import s1s2_path
from opamp.v3.tests._probe_blocks import output_path_probe
from opamp.v3.tests._helpers import BaseV3SimTest, build_core_params, reset_metrics_file, write_metrics_json


METRICS_PATH = Path(__file__).with_name("rc_probe_output_path_loop_break_metrics.json")


def _phase_margin(freq: np.ndarray, gain: np.ndarray) -> tuple[float, float]:
    mag = np.abs(gain)
    phase_deg, _ = negative_feedback_phase_trace(gain)
    unity_hz, _ = interp_crossing(freq, mag, 1.0)
    pm = float("nan")
    if math.isfinite(unity_hz):
        phase_at_unity = interp_value(freq, phase_deg, unity_hz)
        if math.isfinite(phase_at_unity):
            pm = 180.0 + phase_at_unity
    return float(unity_hz), float(pm)


def _gain_metrics(freq: np.ndarray, gain: np.ndarray) -> dict[str, float]:
    mag = np.abs(gain)
    aol_db = 20.0 * math.log10(max(float(mag[0]), 1e-30))
    unity_hz, pm = _phase_margin(freq, gain)
    return {
        "aol_db": float(aol_db),
        "gbw_hz": float(unity_hz),
        "phase_margin_deg": float(pm),
    }


def _build_full_core_tb(dut):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, en, vdd_sig = h.Signals(5)
        vvdd = h.Vdc(dc=1.8)(p=vdd_sig, n=VSS)
        ven = h.Vdc(dc=1.8)(p=en, n=VSS)
        vvinp = h.Vdc(dc=0.9)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=0.9, ac=1.0)(p=vinn_sig, n=VSS)
        lfb = h.Ind(l=1e9)(p=vout, n=vinp_sig)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        rload = h.Res(r=1e12)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, EN=en, VDD=vdd_sig, VSS=VSS)

    return Tb


def _build_bypass_tb(dut):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, en, vdd_sig = h.Signals(5)
        vvdd = h.Vdc(dc=1.8)(p=vdd_sig, n=VSS)
        ven = h.Vdc(dc=1.8)(p=en, n=VSS)
        vvinp = h.Vdc(dc=0.9)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=0.9, ac=1.0)(p=vinn_sig, n=VSS)
        lfb = h.Ind(l=1e9)(p=vout, n=vinp_sig)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        rload = h.Res(r=1e12)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, EN=en, VDD=vdd_sig, VSS=VSS, VDRV=vout)

    return Tb


def _build_output_path_tb(dut):
    @h.module
    class Tb:
        VSS = h.Port()
        vdrv_sig, vout, vdd_sig = h.Signals(3)
        vvdd = h.Vdc(dc=1.8)(p=vdd_sig, n=VSS)
        vvdrv = h.Vdc(dc=0.533, ac=1.0)(p=vdrv_sig, n=VSS)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        rload = h.Res(r=1e12)(p=vout, n=VSS)
        xdut = dut(VDRV=vdrv_sig, VOUT=vout, VDD=vdd_sig, VSS=VSS)

    return Tb


class TestRcProbeOutputPathLoopBreak(BaseV3SimTest):
    def test_probe_output_path_breaks_main_loop(self) -> None:
        reset_metrics_file(METRICS_PATH)
        install = require_sky130_install()
        params = build_core_params()

        full_dut = opamp_core(params)
        full_ac = Sim(
            tb=_build_full_core_tb(full_dut),
            attrs=[
                Ac(sweep=LogSweep(1.0, 1e9, 40)),
                Save("v(xtop.vout), v(xtop.xdut.vdrv), v(xtop.vinn_sig)"),
                h.sim.Literal(".temp 27"),
                install.include(h.pdk.Corner.TYP),
            ],
        )
        full_op = Sim(
            tb=_build_full_core_tb(full_dut),
            attrs=[
                Op(),
                Save("v(xtop.vout)"),
                h.sim.Literal(".temp 27"),
                install.include(h.pdk.Corner.TYP),
            ],
        )
        full_ac_res = run_ngspice_sim(
            full_ac,
            unique_ngspice_options("rc_probe_output_path_loop_break_full_ac", fmt=ResultFormat.SIM_DATA),
            rundir=f"./tmp/rc_loopbreak_full_ac_{uuid4().hex[:8]}",
        )
        full_op_res = run_ngspice_sim(
            full_op,
            unique_ngspice_options("rc_probe_output_path_loop_break_full_op", fmt=ResultFormat.SIM_DATA),
            rundir=f"./tmp/rc_loopbreak_full_op_{uuid4().hex[:8]}",
        )

        bypass_dut = s1s2_path(params)
        bypass_ac = Sim(
            tb=_build_bypass_tb(bypass_dut),
            attrs=[
                Ac(sweep=LogSweep(1.0, 1e9, 40)),
                Save("v(xtop.vout), v(xtop.vinn_sig)"),
                h.sim.Literal(".temp 27"),
                install.include(h.pdk.Corner.TYP),
            ],
        )
        bypass_op = Sim(
            tb=_build_bypass_tb(bypass_dut),
            attrs=[
                Op(),
                Save("v(xtop.vout)"),
                h.sim.Literal(".temp 27"),
                install.include(h.pdk.Corner.TYP),
            ],
        )
        bypass_ac_res = run_ngspice_sim(
            bypass_ac,
            unique_ngspice_options("rc_probe_output_path_loop_break_bypass_ac", fmt=ResultFormat.SIM_DATA),
            rundir=f"./tmp/rc_loopbreak_bypass_ac_{uuid4().hex[:8]}",
        )
        bypass_op_res = run_ngspice_sim(
            bypass_op,
            unique_ngspice_options("rc_probe_output_path_loop_break_bypass_op", fmt=ResultFormat.SIM_DATA),
            rundir=f"./tmp/rc_loopbreak_bypass_op_{uuid4().hex[:8]}",
        )

        path_dut = output_path_probe(params)
        path_ac = Sim(
            tb=_build_output_path_tb(path_dut),
            attrs=[
                Ac(sweep=LogSweep(1.0, 1e9, 40)),
                Save("v(xtop.vout), v(xtop.vdrv_sig)"),
                h.sim.Literal(".temp 27"),
                install.include(h.pdk.Corner.TYP),
            ],
        )
        path_ac_res = run_ngspice_sim(
            path_ac,
            unique_ngspice_options("rc_probe_output_path_loop_break_path_ac", fmt=ResultFormat.SIM_DATA),
            rundir=f"./tmp/rc_loopbreak_path_ac_{uuid4().hex[:8]}",
        )

        freq, _ = extract_ac_trace(full_ac_res, "v(xtop.vout)")
        _, vout = extract_ac_trace(full_ac_res, "v(xtop.vout)")
        _, bypass_vout = extract_ac_trace(bypass_ac_res, "v(xtop.vout)")
        _, path_vout = extract_ac_trace(path_ac_res, "v(xtop.vout)")
        _, path_vdrv = extract_ac_trace(path_ac_res, "v(xtop.vdrv_sig)")

        freq = np.asarray(freq, dtype=float)
        vout = np.asarray(vout)
        bypass_vout = np.asarray(bypass_vout)
        path_vout = np.asarray(path_vout)
        path_vdrv = np.asarray(path_vdrv)

        full_vout_gain = vout
        bypass_gain = bypass_vout
        path_gain = path_vout / np.where(np.abs(path_vdrv) > 1e-30, path_vdrv, 1e-30 + 0j)

        payload = {
            "full_core": {
                "dc_vout_V": op_scalar(full_op_res, "v(xtop.vout)"),
                "gain_to_vout": _gain_metrics(freq, full_vout_gain),
            },
            "bypass_output_path": {
                "dc_vout_V": op_scalar(bypass_op_res, "v(xtop.vout)"),
                "gain_to_vout": _gain_metrics(freq, bypass_gain),
            },
            "standalone_output_path": {
                "low_freq_vdrv_to_vout_vv": float(abs(path_gain[0])),
                "low_freq_vdrv_to_vout_db": float(20.0 * math.log10(max(abs(path_gain[0]), 1e-30))),
                "gain_to_vout": _gain_metrics(freq, path_gain),
            },
        }
        write_metrics_json(METRICS_PATH, payload)

        full_vout_m = payload["full_core"]["gain_to_vout"]
        bypass_m = payload["bypass_output_path"]["gain_to_vout"]
        path_m = payload["standalone_output_path"]["gain_to_vout"]

        self.assertGreater(float(bypass_m["aol_db"]), float(full_vout_m["aol_db"]) + 20.0)
        self.assertLess(float(path_m["aol_db"]), 0.0)
        self.assertLess(float(payload["standalone_output_path"]["low_freq_vdrv_to_vout_vv"]), 0.2)
