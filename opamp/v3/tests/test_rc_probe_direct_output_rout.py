from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import hdl21 as h
import numpy as np
from hdl21.sim import Ac, LogSweep, Save, Sim
from vlsirtools.spice import ResultFormat

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.common import extract_ac_trace, unique_ngspice_options
from opamp.v3.opamp_core import opamp_core
from opamp.v3.tests._helpers import BaseV3SimTest, build_core_params, reset_metrics_file, write_metrics_json


METRICS_PATH = Path(__file__).with_name("rc_probe_direct_output_rout_metrics.json")


def _build_sterile_rout_tb(dut):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, en, vdd_sig = h.Signals(5)
        vvdd = h.Vdc(dc=1.8)(p=vdd_sig, n=VSS)
        ven = h.Vdc(dc=1.8)(p=en, n=VSS)
        vvinp = h.Vdc(dc=0.9)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=0.9)(p=vinn_sig, n=VSS)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        iac = h.Idc(dc=0.0, ac=1.0)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, EN=en, VDD=vdd_sig, VSS=VSS)

    return Tb


def _build_follower_rout_tb(dut):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, en, vdd_sig = h.Signals(5)
        vvdd = h.Vdc(dc=1.8)(p=vdd_sig, n=VSS)
        ven = h.Vdc(dc=1.8)(p=en, n=VSS)
        vvinp = h.Vdc(dc=0.9)(p=vinp_sig, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinn_sig)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        rload = h.Res(r=1e12)(p=vout, n=VSS)
        iac = h.Idc(dc=0.0, ac=1.0)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, EN=en, VDD=vdd_sig, VSS=VSS)

    return Tb


class TestRcProbeDirectOutputRout(BaseV3SimTest):
    def test_probe_direct_output_rout(self) -> None:
        reset_metrics_file(METRICS_PATH)
        install = require_sky130_install()
        dut = opamp_core(build_core_params())

        def run(tb_builder, name: str):
            res = run_ngspice_sim(
                Sim(
                    tb=tb_builder(dut),
                    attrs=[
                        Ac(sweep=LogSweep(1.0, 1e6, 10)),
                        Save("v(xtop.vout)"),
                        h.sim.Literal(".temp 27"),
                        install.include(h.pdk.Corner.TYP),
                    ],
                ),
                unique_ngspice_options(name, fmt=ResultFormat.SIM_DATA),
                rundir=f"./tmp/{name}_{uuid4().hex[:8]}",
            )
            _, vout = extract_ac_trace(res, "v(xtop.vout)")
            zout = complex(np.asarray(vout)[0])  # 1 A AC current source => volts == ohms
            return float(abs(zout))

        sterile_rout = run(_build_sterile_rout_tb, "rc_probe_direct_output_rout_sterile")
        follower_rout = run(_build_follower_rout_tb, "rc_probe_direct_output_rout_follower")
        payload = {
            "sterile_rout_ohm": sterile_rout,
            "follower_rout_ohm": follower_rout,
            "rout_ratio_follower_over_sterile": follower_rout / max(sterile_rout, 1e-30),
        }
        write_metrics_json(METRICS_PATH, payload)
        self.assertTrue(np.isfinite(payload["sterile_rout_ohm"]))
        self.assertTrue(np.isfinite(payload["follower_rout_ohm"]))
