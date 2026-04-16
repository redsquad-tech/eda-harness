from __future__ import annotations

import traceback
from pathlib import Path
from uuid import uuid4

import hdl21 as h
import numpy as np
from hdl21.sim import Ac, LogSweep, Op, Save, Sim
from vlsirtools.spice import ResultFormat

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.common import extract_ac_trace, interp_crossing, interp_value, op_scalar, unique_ngspice_options
from opamp.v3.opamp_ota import opamp_ota, ota_params_from_core
from opamp.v3.tests._helpers import BaseV3SimTest, build_core_params, reset_metrics_file, write_metrics_json


METRICS_PATH = Path(__file__).with_name("rc_probe_ota_open_loop_metrics.json")


def _build_open_loop_op_tb(dut):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, vdd_sig = h.Signals(4)
        vvdd = h.Vdc(dc=1.8)(p=vdd_sig, n=VSS)
        vvinp = h.Vdc(dc=0.90005)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=0.89995)(p=vinn_sig, n=VSS)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, VDD=vdd_sig, VSS=VSS)

    return Tb


def _build_open_loop_ac_tb(dut):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, vdd_sig = h.Signals(4)
        vvdd = h.Vdc(dc=1.8)(p=vdd_sig, n=VSS)
        vvinp = h.Vdc(dc=0.9, ac=50e-6)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=0.9, ac=-50e-6)(p=vinn_sig, n=VSS)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, VDD=vdd_sig, VSS=VSS)

    return Tb


class TestRcProbeOtaOpenLoop(BaseV3SimTest):
    def test_probe_ota_open_loop(self) -> None:
        reset_metrics_file(METRICS_PATH)
        try:
            install = require_sky130_install()
            dut = opamp_ota(ota_params_from_core(build_core_params()))

            op_res = run_ngspice_sim(
                Sim(
                    tb=_build_open_loop_op_tb(dut),
                    attrs=[
                        Op(),
                        Save("v(xtop.vout), v(xtop.xxdut.vx), v(xtop.xxdut.vdrv)"),
                        h.sim.Literal(".temp 27"),
                        install.include(h.pdk.Corner.TYP),
                    ],
                ),
                unique_ngspice_options("rc_probe_ota_open_loop_op", fmt=ResultFormat.SIM_DATA),
                rundir=f"./tmp/rc_ota_op_{uuid4().hex[:8]}",
            )

            ac_res = run_ngspice_sim(
                Sim(
                    tb=_build_open_loop_ac_tb(dut),
                    attrs=[
                        Ac(sweep=LogSweep(1.0, 1e9, 40)),
                        Save("v(xtop.vout), v(xtop.vinp_sig), v(xtop.vinn_sig)"),
                        h.sim.Literal(".temp 27"),
                        install.include(h.pdk.Corner.TYP),
                    ],
                ),
                unique_ngspice_options("rc_probe_ota_open_loop_ac", fmt=ResultFormat.SIM_DATA),
                rundir=f"./tmp/rc_ota_ac_{uuid4().hex[:8]}",
            )

            freqs, vout = extract_ac_trace(ac_res, "v(xtop.vout)")
            _, vinp = extract_ac_trace(ac_res, "v(xtop.vinp_sig)")
            _, vinn = extract_ac_trace(ac_res, "v(xtop.vinn_sig)")
            vin_diff = np.asarray(vinp) - np.asarray(vinn)
            gain_mag = np.abs(np.asarray(vout)) / 100e-6
            aol_db = float(20.0 * np.log10(max(float(gain_mag[0]), 1e-30)))
            open_loop_gain = np.asarray(vout) / np.where(np.abs(vin_diff) > 1e-30, vin_diff, 1e-30 + 0j)
            mag = np.abs(open_loop_gain)
            ugf_hz, _ = interp_crossing(np.asarray(freqs, dtype=float), mag, 1.0)
            phase_unwrapped_deg = np.unwrap(np.angle(open_loop_gain)) * 180.0 / np.pi
            phase_at_ugf_deg = float("nan")
            if np.isfinite(ugf_hz):
                phase_at_ugf_deg = float(interp_value(np.asarray(freqs, dtype=float), phase_unwrapped_deg, ugf_hz))

            payload = {
                "aol_db": aol_db,
                "ugbw_hz": float(ugf_hz),
                "phase_at_ugbw_deg": phase_at_ugf_deg,
                "vout_dc": op_scalar(op_res, "v(xtop.vout)"),
                "vx_dc": op_scalar(op_res, "v(xtop.xxdut.vx)"),
                "vdrv_dc": op_scalar(op_res, "v(xtop.xxdut.vdrv)"),
            }
            write_metrics_json(METRICS_PATH, payload)

            self.assertFinite(float(payload["aol_db"]))
            self.assertFinite(float(payload["ugbw_hz"]))
        except Exception as exc:
            write_metrics_json(
                METRICS_PATH,
                {
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                },
            )
            raise
