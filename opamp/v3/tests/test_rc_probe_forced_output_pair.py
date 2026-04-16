from __future__ import annotations
from pathlib import Path
from uuid import uuid4

import hdl21 as h
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import SimOptions

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.opamp_core import OpampCoreParams
from opamp.v3.tests._helpers import BaseV3SimTest, build_debug_core_params, reset_metrics_file, write_metrics_json
from opamp.v3.tests._probe_blocks import debug_params, output_stage_probe


METRICS_PATH = Path(__file__).with_name("rc_probe_forced_output_pair_metrics.json")


def _debug_params() -> OpampCoreParams:
    return build_debug_core_params()


def forced_output_pair(params: OpampCoreParams) -> h.Module:
    return output_stage_probe(params)


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


def _op_case(dut, *, name: str, vgn: float, vgp: float) -> dict[str, float | str]:
    install = require_sky130_install()
    sim = Sim(tb=_build_tb(dut, vgn=vgn, vgp=vgp), attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)])
    res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/rc_forced_{uuid4().hex[:8]}")
    d = res.an[0].data
    vdd = float(d["v(xtop.vdd)"])
    vout = float(d["v(xtop.vout)"])
    i_out_p = float(d["i(v.xtop.xxdut.vvprobe_outp)"])
    i_out_n = float(d["i(v.xtop.xxdut.vvprobe_outn)"])
    return {
        "case": name,
        "vgn_in_V": float(vgn),
        "vgp_in_V": float(vgp),
        "vout_V": vout,
        "out_p_vsg_V": vdd - float(vgp),
        "out_p_vsd_V": vdd - vout,
        "out_n_vgs_V": float(vgn),
        "out_n_vds_V": vout,
        "i_out_p_A": i_out_p,
        "i_out_n_A": i_out_n,
        "quiescent_overlap_A": abs(i_out_p) + abs(i_out_n),
    }


class TestRcProbeForcedOutputPair(BaseV3SimTest):
    def test_probe_rc_forced_output_pair(self):
        reset_metrics_file(METRICS_PATH)
        dut = forced_output_pair(_debug_params())
        payload = {
            "cases": [
                _op_case(dut, name="both_low", vgn=0.10, vgp=0.10),
                _op_case(dut, name="nominal_equal", vgn=0.72, vgp=0.72),
                _op_case(dut, name="n_on_p_off", vgn=1.20, vgp=1.60),
                _op_case(dut, name="n_off_p_on", vgn=0.10, vgp=0.60),
                _op_case(dut, name="both_high", vgn=1.60, vgp=1.60),
            ]
        }
        write_metrics_json(METRICS_PATH, payload)
        self.assertEqual(len(payload["cases"]), 5)
