from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import hdl21 as h
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import SimOptions

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.opamp_core import OpampCoreParams
from opamp.v3.tests._helpers import BaseV3SimTest, build_debug_core_params, reset_metrics_file, write_metrics_json
from opamp.v3.tests._probe_blocks import output_stage_probe


METRICS_PATH = Path(__file__).with_name("rc_probe_output_pair_map_metrics.json")


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


def _op_case(dut, *, vgn: float, vgp: float) -> dict[str, float]:
    install = require_sky130_install()
    sim = Sim(tb=_build_tb(dut, vgn=vgn, vgp=vgp), attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)])
    res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/rc_pairmap_{uuid4().hex[:8]}")
    d = res.an[0].data
    vdd = float(d["v(xtop.vdd)"])
    vout = float(d["v(xtop.vout)"])
    i_out_p = float(d["i(v.xtop.xxdut.vvprobe_outp)"])
    i_out_n = float(d["i(v.xtop.xxdut.vvprobe_outn)"])
    return {
        "vgn_in_V": float(vgn),
        "vgp_in_V": float(vgp),
        "gate_avg_V": 0.5 * (float(vgn) + float(vgp)),
        "gate_spread_V": float(vgn) - float(vgp),
        "vout_V": vout,
        "vout_error_to_mid_V": abs(vout - 0.9),
        "out_p_vsg_V": vdd - float(vgp),
        "out_p_vsd_V": vdd - vout,
        "out_n_vgs_V": float(vgn),
        "out_n_vds_V": vout,
        "i_out_p_A": i_out_p,
        "i_out_n_A": i_out_n,
        "quiescent_overlap_A": abs(i_out_p) + abs(i_out_n),
    }


class TestRcProbeOutputPairMap(BaseV3SimTest):
    def test_probe_rc_output_pair_map(self):
        reset_metrics_file(METRICS_PATH)
        dut = forced_output_pair(_debug_params())
        vgn_values = [0.60, 0.68, 0.76, 0.84]
        vgp_values = [0.72, 0.80, 0.88, 0.96]

        cases = []
        for vgn in vgn_values:
            for vgp in vgp_values:
                cases.append(_op_case(dut, vgn=vgn, vgp=vgp))

        best_mid = min(cases, key=lambda item: item["vout_error_to_mid_V"])
        payload = {
            "grid": {"vgn_values_V": vgn_values, "vgp_values_V": vgp_values},
            "best_mid_case": best_mid,
            "cases": cases,
        }
        write_metrics_json(METRICS_PATH, payload)
        self.assertEqual(len(cases), len(vgn_values) * len(vgp_values))
