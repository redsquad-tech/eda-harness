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
from opamp.v3.measure_core import OpampCoreOpenLoopTbParams
from opamp.v3.opamp_core import opamp_core
from opamp.v3.s1s2_path import s1s2_path
from opamp.v3.tests._helpers import BaseV3SimTest, build_core_params, reset_metrics_file, write_metrics_json


METRICS_PATH = Path(__file__).with_name("rc_probe_vdrv_as_output_ac_metrics.json")


def _gain_metrics(freq: np.ndarray, gain: np.ndarray) -> dict[str, float]:
    mag = np.abs(gain)
    mag_db = 20.0 * np.log10(np.maximum(mag, 1e-30))
    phase_deg, _ = negative_feedback_phase_trace(gain)
    gbw_hz, _ = interp_crossing(freq, mag, 1.0)
    phase_margin_deg = float("nan")
    if math.isfinite(gbw_hz):
        phase_at_unity = interp_value(freq, phase_deg, gbw_hz)
        if math.isfinite(phase_at_unity):
            phase_margin_deg = 180.0 + phase_at_unity
    return {
        "aol_db": float(mag_db[0]) if len(mag_db) else float("nan"),
        "gbw_hz": float(gbw_hz),
        "phase_margin_deg": float(phase_margin_deg),
    }


def _build_core_tb(dut, tb: OpampCoreOpenLoopTbParams):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, en, vdd_sig = h.Signals(5)
        vvdd = h.Vdc(dc=float(tb.vdd))(p=vdd_sig, n=VSS)
        ven = h.Vdc(dc=float(tb.vdd))(p=en, n=VSS)
        vvinp = h.Vdc(dc=float(tb.v_cm))(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=float(tb.v_cm), ac=1.0)(p=vinn_sig, n=VSS)
        lfb = h.Ind(l=1e9)(p=vout, n=vinp_sig)
        cload = h.Cap(c=float(tb.c_load))(p=vout, n=VSS)
        rload = h.Res(r=float(tb.r_probe))(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, EN=en, VDD=vdd_sig, VSS=VSS)

    return Tb


def _build_vdrv_tb(dut, tb: OpampCoreOpenLoopTbParams):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, en, vdd_sig = h.Signals(5)
        vvdd = h.Vdc(dc=float(tb.vdd))(p=vdd_sig, n=VSS)
        ven = h.Vdc(dc=float(tb.vdd))(p=en, n=VSS)
        vvinp = h.Vdc(dc=float(tb.v_cm))(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=float(tb.v_cm), ac=1.0)(p=vinn_sig, n=VSS)
        lfb = h.Ind(l=1e9)(p=vout, n=vinp_sig)
        cload = h.Cap(c=float(tb.c_load))(p=vout, n=VSS)
        rload = h.Res(r=float(tb.r_probe))(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, EN=en, VDD=vdd_sig, VSS=VSS, VDRV=vout)

    return Tb


class TestRcProbeVdrvAsOutputAc(BaseV3SimTest):
    def test_probe_vdrv_as_output_ac(self) -> None:
        reset_metrics_file(METRICS_PATH)
        install = require_sky130_install()
        params = build_core_params()
        tb = OpampCoreOpenLoopTbParams()

        full = opamp_core(params)
        full_ac = Sim(
            tb=_build_core_tb(full, tb),
            attrs=[
                Ac(sweep=LogSweep(float(tb.f_start), float(tb.f_stop), int(tb.npts))),
                Save("v(xtop.vout), v(xtop.vinn_sig)"),
                h.sim.Literal(f".temp {float(tb.temp_c)}"),
                install.include(h.pdk.Corner.TYP),
            ],
        )
        full_op = Sim(
            tb=_build_core_tb(full, tb),
            attrs=[
                Op(),
                Save("v(xtop.vout)"),
                h.sim.Literal(f".temp {float(tb.temp_c)}"),
                install.include(h.pdk.Corner.TYP),
            ],
        )

        vdrv_out = s1s2_path(params)
        vdrv_ac = Sim(
            tb=_build_vdrv_tb(vdrv_out, tb),
            attrs=[
                Ac(sweep=LogSweep(float(tb.f_start), float(tb.f_stop), int(tb.npts))),
                Save("v(xtop.vout), v(xtop.vinn_sig)"),
                h.sim.Literal(f".temp {float(tb.temp_c)}"),
                install.include(h.pdk.Corner.TYP),
            ],
        )
        vdrv_op = Sim(
            tb=_build_vdrv_tb(vdrv_out, tb),
            attrs=[
                Op(),
                Save("v(xtop.vout)"),
                h.sim.Literal(f".temp {float(tb.temp_c)}"),
                install.include(h.pdk.Corner.TYP),
            ],
        )

        full_ac_res = run_ngspice_sim(
            full_ac,
            unique_ngspice_options("rc_probe_vdrv_as_output_full_ac", fmt=ResultFormat.SIM_DATA),
            rundir=f"./tmp/rc_vdrvout_full_ac_{uuid4().hex[:8]}",
        )
        full_op_res = run_ngspice_sim(
            full_op,
            unique_ngspice_options("rc_probe_vdrv_as_output_full_op", fmt=ResultFormat.SIM_DATA),
            rundir=f"./tmp/rc_vdrvout_full_op_{uuid4().hex[:8]}",
        )
        vdrv_ac_res = run_ngspice_sim(
            vdrv_ac,
            unique_ngspice_options("rc_probe_vdrv_as_output_vdrv_ac", fmt=ResultFormat.SIM_DATA),
            rundir=f"./tmp/rc_vdrvout_vdrv_ac_{uuid4().hex[:8]}",
        )
        vdrv_op_res = run_ngspice_sim(
            vdrv_op,
            unique_ngspice_options("rc_probe_vdrv_as_output_vdrv_op", fmt=ResultFormat.SIM_DATA),
            rundir=f"./tmp/rc_vdrvout_vdrv_op_{uuid4().hex[:8]}",
        )

        freq, full_vout = extract_ac_trace(full_ac_res, "v(xtop.vout)")
        _, full_vin = extract_ac_trace(full_ac_res, "v(xtop.vinn_sig)")
        _, vdrv_vout = extract_ac_trace(vdrv_ac_res, "v(xtop.vout)")
        _, vdrv_vin = extract_ac_trace(vdrv_ac_res, "v(xtop.vinn_sig)")

        freq = np.asarray(freq, dtype=float)
        full_gain = np.asarray(full_vout) / np.where(np.abs(np.asarray(full_vin)) > 1e-30, np.asarray(full_vin), 1e-30 + 0j)
        vdrv_gain = np.asarray(vdrv_vout) / np.where(np.abs(np.asarray(vdrv_vin)) > 1e-30, np.asarray(vdrv_vin), 1e-30 + 0j)

        payload = {
            "full_core": {
                "dc_vout_V": op_scalar(full_op_res, "v(xtop.vout)"),
                **_gain_metrics(freq, full_gain),
            },
            "vdrv_as_output": {
                "dc_vout_V": op_scalar(vdrv_op_res, "v(xtop.vout)"),
                **_gain_metrics(freq, vdrv_gain),
            },
            "delta": {
                "aol_db": float(_gain_metrics(freq, vdrv_gain)["aol_db"] - _gain_metrics(freq, full_gain)["aol_db"]),
                "gbw_hz_ratio": float(_gain_metrics(freq, vdrv_gain)["gbw_hz"] / max(_gain_metrics(freq, full_gain)["gbw_hz"], 1e-30)),
            },
        }
        write_metrics_json(METRICS_PATH, payload)

        self.assertGreater(float(payload["vdrv_as_output"]["aol_db"]), float(payload["full_core"]["aol_db"]) + 20.0)
