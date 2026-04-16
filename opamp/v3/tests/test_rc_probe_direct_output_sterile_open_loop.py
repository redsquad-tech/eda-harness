from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import hdl21 as h
import numpy as np
from hdl21.sim import Ac, LogSweep, Op, Save, Sim
from vlsirtools.spice import ResultFormat

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.common import extract_ac_trace, op_scalar, unique_ngspice_options
from opamp.v3.opamp_core import opamp_core
from opamp.v3.tests._helpers import BaseV3SimTest, build_core_params, reset_metrics_file, write_metrics_json


METRICS_PATH = Path(__file__).with_name("rc_probe_direct_output_sterile_open_loop_metrics.json")


def _build_sterile_dc_tb(dut):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, en, vdd_sig = h.Signals(5)
        vvdd = h.Vdc(dc=1.8)(p=vdd_sig, n=VSS)
        ven = h.Vdc(dc=1.8)(p=en, n=VSS)
        vvinp = h.Vdc(dc=0.90005)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=0.89995)(p=vinn_sig, n=VSS)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, EN=en, VDD=vdd_sig, VSS=VSS)

    return Tb


def _build_sterile_ac_tb(dut):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, en, vdd_sig = h.Signals(5)
        vvdd = h.Vdc(dc=1.8)(p=vdd_sig, n=VSS)
        ven = h.Vdc(dc=1.8)(p=en, n=VSS)
        vvinp = h.Vdc(dc=0.9, ac=50e-6)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=0.9, ac=-50e-6)(p=vinn_sig, n=VSS)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, EN=en, VDD=vdd_sig, VSS=VSS)

    return Tb


class TestRcProbeDirectOutputSterileOpenLoop(BaseV3SimTest):
    def test_probe_direct_output_sterile_open_loop(self) -> None:
        reset_metrics_file(METRICS_PATH)
        install = require_sky130_install()
        dut = opamp_core(build_core_params())

        op_res = run_ngspice_sim(
            Sim(
                tb=_build_sterile_dc_tb(dut),
                attrs=[
                    Op(),
                    Save("v(xtop.vout), v(xtop.xxdut.vout_int)"),
                    h.sim.Literal(".temp 27"),
                    install.include(h.pdk.Corner.TYP),
                ],
            ),
            unique_ngspice_options("rc_probe_direct_output_sterile_op", fmt=ResultFormat.SIM_DATA),
            rundir=f"./tmp/rc_sterile_op_{uuid4().hex[:8]}",
        )
        ac_res = run_ngspice_sim(
            Sim(
                tb=_build_sterile_ac_tb(dut),
                attrs=[
                    Ac(sweep=LogSweep(1.0, 1e9, 40)),
                    Save("v(xtop.vout), v(xtop.xxdut.vout_int)"),
                    h.sim.Literal(".temp 27"),
                    install.include(h.pdk.Corner.TYP),
                ],
            ),
            unique_ngspice_options("rc_probe_direct_output_sterile_ac", fmt=ResultFormat.SIM_DATA),
            rundir=f"./tmp/rc_sterile_ac_{uuid4().hex[:8]}",
        )

        _, vout = extract_ac_trace(ac_res, "v(xtop.vout)")
        _, vdrv = extract_ac_trace(ac_res, "v(xtop.xxdut.vout_int)")
        vout = np.asarray(vout)
        vdrv = np.asarray(vdrv)
        gain_vv = abs(complex(vout[0])) / 100e-6
        payload = {
            "vout_dc": op_scalar(op_res, "v(xtop.vout)"),
            "vdrv_dc": op_scalar(op_res, "v(xtop.xxdut.vout_int)"),
            "direct_gain_db": float(20.0 * np.log10(max(gain_vv, 1e-30))),
            "vout_over_vdrv_mag": float(abs(complex(vout[0] / np.where(np.abs(vdrv[0]) > 1e-30, vdrv[0], 1e-30 + 0j)))),
        }
        write_metrics_json(METRICS_PATH, payload)

        self.assertAlmostEqual(float(payload["vout_dc"]), float(payload["vdrv_dc"]), delta=1e-6)
        self.assertGreater(float(payload["vout_over_vdrv_mag"]), 0.999)
