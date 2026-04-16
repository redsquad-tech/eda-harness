from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import hdl21 as h
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import SimOptions

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.opamp_core import opamp_core
from opamp.v3.tests._helpers import BaseV3SimTest, build_debug_core_params, reset_metrics_file, write_metrics_json
from opamp.v3.tests._probe_blocks import output_path_probe


METRICS_PATH = Path(__file__).with_name("rc_probe_output_path_internal_metrics.json")


def _build_output_path_tb(dut, *, vdrv: float):
    @h.module
    class Tb:
        VSS = h.Port()
        vdrv_sig, vout, vdd = h.Signals(3)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        vvdrv = h.Vdc(dc=vdrv)(p=vdrv_sig, n=VSS)
        rload = h.Res(r=1e12)(p=vout, n=VSS)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        xdut = dut(VDRV=vdrv_sig, VOUT=vout, VDD=vdd, VSS=VSS)

    return Tb


def _build_core_tb(dut):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp, vinn, vout, en, vdd = h.Signals(5)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        ven = h.Vdc(dc=1.8)(p=en, n=VSS)
        vvinn = h.Vdc(dc=0.9)(p=vinn, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinp)
        rl = h.Res(r=1e6)(p=vout, n=VSS)
        cl = h.Cap(c=1e-12)(p=vout, n=VSS)
        xdut = dut(VINP=vinp, VINN=vinn, VOUT=vout, EN=en, VDD=vdd, VSS=VSS)

    return Tb


def _run_output_path_case(dut, *, name: str, vdrv: float) -> dict[str, float | str]:
    install = require_sky130_install()
    sim = Sim(
        tb=_build_output_path_tb(dut, vdrv=vdrv),
        attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)],
    )
    res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/rc_path_int_{uuid4().hex[:8]}")
    d = res.an[0].data
    vgn = float(d["v(xtop.xxdut.vgn)"])
    vgp = float(d["v(xtop.xxdut.vgp)"])
    vgn_q = float(d["v(xtop.xxdut.xxdrv.vgn_q)"])
    vgp_q = float(d["v(xtop.xxdut.xxdrv.vgp_q)"])
    vout = float(d["v(xtop.vout)"])
    return {
        "case": name,
        "vdrv_in_V": float(vdrv),
        "vgn_q_V": vgn_q,
        "vgp_q_V": vgp_q,
        "vgn_V": vgn,
        "vgp_V": vgp,
        "vgn_minus_vgn_q_V": vgn - vgn_q,
        "vgp_minus_vgp_q_V": vgp - vgp_q,
        "gate_avg_V": 0.5 * (vgn + vgp),
        "gate_spread_V": vgn - vgp,
        "vout_V": vout,
        "i_out_p_A": float(d["i(v.xtop.xxdut.vvprobe_outp)"]),
        "i_out_n_A": float(d["i(v.xtop.xxdut.vvprobe_outn)"]),
    }


def _run_core_case(dut) -> dict[str, float]:
    install = require_sky130_install()
    sim = Sim(
        tb=_build_core_tb(dut),
        attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)],
    )
    res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/rc_core_int_{uuid4().hex[:8]}")
    d = res.an[0].data
    vgn = float(d["v(xtop.xxdut.vgn)"])
    vgp = float(d["v(xtop.xxdut.vgp)"])
    return {
        "vdrv_V": float(d["v(xtop.xxdut.vdrv)"]),
        "vgn_q_V": float(d["v(xtop.xxdut.xxout_driver.vgn_q)"]),
        "vgp_q_V": float(d["v(xtop.xxdut.xxout_driver.vgp_q)"]),
        "vgn_V": vgn,
        "vgp_V": vgp,
        "vgn_minus_vgn_q_V": vgn - float(d["v(xtop.xxdut.xxout_driver.vgn_q)"]),
        "vgp_minus_vgp_q_V": vgp - float(d["v(xtop.xxdut.xxout_driver.vgp_q)"]),
        "gate_avg_V": 0.5 * (vgn + vgp),
        "gate_spread_V": vgn - vgp,
        "vout_V": float(d["v(xtop.vout)"]),
        "vx_V": float(d["v(xtop.xxdut.vx)"]),
        "vref_V": float(d["v(xtop.xxdut.vref)"]),
        "i_out_p_A": float(d["i(v.xtop.xxdut.vvprobe_outp)"]),
        "i_out_n_A": float(d["i(v.xtop.xxdut.vvprobe_outn)"]),
    }


class TestRcProbeOutputPathInternal(BaseV3SimTest):
    def test_probe_rc_output_path_internal(self):
        reset_metrics_file(METRICS_PATH)
        params = build_debug_core_params()
        standalone_probe = output_path_probe(params)
        payload = {
            "standalone_output_path": [
                _run_output_path_case(standalone_probe, name="vdrv_1p0", vdrv=1.0),
                _run_output_path_case(standalone_probe, name="vdrv_1p6", vdrv=1.6),
            ],
            "full_core_nominal": _run_core_case(opamp_core(params)),
        }
        write_metrics_json(METRICS_PATH, payload)
        self.assertEqual(len(payload["standalone_output_path"]), 2)
