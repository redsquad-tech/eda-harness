from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import hdl21 as h
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import SimOptions

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.tests._helpers import BaseV3SimTest, build_debug_core_params, reset_metrics_file, write_metrics_json
from opamp.v3.tests._probe_blocks import output_stage_probe


METRICS_PATH = Path(__file__).with_name("rc_probe_output_stage_one_device_metrics.json")


def _build_tb(dut, *, vgn: float, vgp: float):
    @h.module
    class Tb:
        VSS = h.Port()
        vdd, vout, vgn_sig, vgp_sig = h.Signals(4)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        vvgn = h.Vdc(dc=vgn)(p=vgn_sig, n=VSS)
        vvgp = h.Vdc(dc=vgp)(p=vgp_sig, n=VSS)
        rload = h.Res(r=1e12)(p=vout, n=VSS)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        xdut = dut(VGN=vgn_sig, VGP=vgp_sig, VOUT=vout, VDD=vdd, VSS=VSS)

    return Tb


def _run(dut, *, name: str, vgn: float, vgp: float) -> dict[str, float | str]:
    install = require_sky130_install()
    sim = Sim(
        tb=_build_tb(dut, vgn=vgn, vgp=vgp),
        attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)],
    )
    res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/rc_out1dev_{uuid4().hex[:8]}")
    d = res.an[0].data
    return {
        "case": name,
        "vgn_V": float(vgn),
        "vgp_V": float(vgp),
        "vout_V": float(d["v(xtop.vout)"]),
        "i_out_p_A": float(d["i(v.xtop.xxdut.vvprobe_outp)"]),
        "i_out_n_A": float(d["i(v.xtop.xxdut.vvprobe_outn)"]),
    }


class TestRcProbeOutputStageOneDevice(BaseV3SimTest):
    def test_probe_rc_output_stage_one_device(self):
        reset_metrics_file(METRICS_PATH)
        dut = output_stage_probe(build_debug_core_params())
        payload = {
            "nmos_nearly_only": _run(dut, name="nmos_nearly_only", vgn=1.2, vgp=1.6),
            "pmos_nearly_only": _run(dut, name="pmos_nearly_only", vgn=0.1, vgp=0.6),
            "both_mild": _run(dut, name="both_mild", vgn=0.72, vgp=0.90),
        }
        write_metrics_json(METRICS_PATH, payload)
        self.assertTrue(True)
