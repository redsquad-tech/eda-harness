from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import hdl21 as h
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import SimOptions

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.tests._helpers import BaseV3SimTest, build_debug_core_params, reset_metrics_file, write_metrics_json
from opamp.v3.tests._probe_blocks import output_stage_probe


METRICS_PATH = Path(__file__).with_name("rc_probe_output_pair_local_map_metrics.json")


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


def _point(dut, *, vgn: float, vgp: float) -> dict[str, float]:
    install = require_sky130_install()
    sim = Sim(
        tb=_build_tb(dut, vgn=vgn, vgp=vgp),
        attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)],
    )
    res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/rc_pairlocal_{uuid4().hex[:8]}")
    d = res.an[0].data
    vout = float(d["v(xtop.vout)"])
    return {
        "vgn_in_V": float(vgn),
        "vgp_in_V": float(vgp),
        "gate_avg_V": 0.5 * (float(vgn) + float(vgp)),
        "gate_spread_V": float(vgn) - float(vgp),
        "vout_V": vout,
        "vout_error_to_mid_V": abs(vout - 0.9),
        "i_out_p_A": float(d["i(v.xtop.xxdut.vvprobe_outp)"]),
        "i_out_n_A": float(d["i(v.xtop.xxdut.vvprobe_outn)"]),
    }


class TestRcProbeOutputPairLocalMap(BaseV3SimTest):
    def test_probe_rc_output_pair_local_map(self):
        reset_metrics_file(METRICS_PATH)
        dut = output_stage_probe(build_debug_core_params())
        vgn_values = [0.70, 0.72, 0.74, 0.76, 0.78, 0.80]
        vgp_values = [0.86, 0.88, 0.90, 0.92, 0.94]
        cases = []
        for vgn in vgn_values:
            for vgp in vgp_values:
                cases.append(_point(dut, vgn=vgn, vgp=vgp))
        payload = {
            "grid": {"vgn_values_V": vgn_values, "vgp_values_V": vgp_values},
            "best_mid_case": min(cases, key=lambda item: item["vout_error_to_mid_V"]),
            "cases": cases,
        }
        write_metrics_json(METRICS_PATH, payload)
        self.assertEqual(len(cases), len(vgn_values) * len(vgp_values))
