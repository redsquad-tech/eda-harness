from __future__ import annotations
from pathlib import Path
from uuid import uuid4

import hdl21 as h
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import SimOptions

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.opamp_core import OpampCoreParams
from opamp.v3.tests._helpers import BaseV3SimTest, build_debug_core_params, reset_metrics_file, write_metrics_json
from opamp.v3.tests._probe_blocks import output_path_probe


METRICS_PATH = Path(__file__).with_name("rc_probe_output_subckt_metrics.json")


def _debug_params() -> OpampCoreParams:
    return build_debug_core_params()


def output_subckt(params: OpampCoreParams) -> h.Module:
    return output_path_probe(params)


def _build_tb(dut, *, vdrv: float, load_mode: str = "none", load_uA: float = 0.0):
    @h.module
    class Tb:
        VSS = h.Port()
        vdrv_sig, vout, vdd = h.Signals(3)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        vvdrv = h.Vdc(dc=vdrv)(p=vdrv_sig, n=VSS)
        rload = h.Res(r=1e12)(p=vout, n=VSS)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        xdut = dut(VDRV=vdrv_sig, VOUT=vout, VDD=vdd, VSS=VSS)
        # External load semantics:
        # - source: inject current into VOUT, DUT must sink it to hold low.
        # - sink: draw current from VOUT, DUT must source it to hold high.
        if load_mode == "source":
            iload = h.Idc(dc=load_uA * 1e-6)(p=vdd, n=vout)
        elif load_mode == "sink":
            iload = h.Idc(dc=load_uA * 1e-6)(p=vout, n=VSS)

    return Tb


def _op_case(dut, *, name: str, vdrv: float, load_mode: str = "none", load_uA: float = 0.0) -> dict[str, float | str]:
    install = require_sky130_install()
    sim = Sim(tb=_build_tb(dut, vdrv=vdrv, load_mode=load_mode, load_uA=load_uA), attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)])
    res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/rc_out_{uuid4().hex[:8]}")
    d = res.an[0].data
    vdd = float(d["v(xtop.vdd)"])
    vgn = float(d["v(xtop.xxdut.vgn)"])
    vgp = float(d["v(xtop.xxdut.vgp)"])
    vout = float(d["v(xtop.vout)"])
    i_out_p = float(d["i(v.xtop.xxdut.vvprobe_outp)"])
    i_out_n = float(d["i(v.xtop.xxdut.vvprobe_outn)"])
    return {
        "case": name,
        "vdrv_in_V": float(vdrv),
        "load_mode": load_mode,
        "load_uA": float(load_uA),
        "vgn_V": vgn,
        "vgp_V": vgp,
        "vgn_minus_vgp_V": vgn - vgp,
        "gate_avg_V": 0.5 * (vgn + vgp),
        "vout_V": vout,
        "out_p_vsg_V": vdd - vgp,
        "out_p_vsd_V": vdd - vout,
        "out_n_vgs_V": vgn,
        "out_n_vds_V": vout,
        "i_out_p_A": i_out_p,
        "i_out_n_A": i_out_n,
        "quiescent_overlap_A": abs(i_out_p) + abs(i_out_n),
    }


class TestRcProbeOutputSubckt(BaseV3SimTest):
    def test_probe_rc_output_subckt(self):
        reset_metrics_file(METRICS_PATH)
        dut = output_subckt(_debug_params())
        payload = {
            "cases": [
                _op_case(dut, name="vdrv_0p0", vdrv=0.0),
                _op_case(dut, name="vdrv_0p8", vdrv=0.8),
                _op_case(dut, name="vdrv_1p0", vdrv=1.0),
                _op_case(dut, name="vdrv_1p2", vdrv=1.2),
                _op_case(dut, name="vdrv_1p6", vdrv=1.6),
                _op_case(dut, name="vdrv_1p8", vdrv=1.8),
                _op_case(dut, name="vdrv_1p0_source20u", vdrv=1.0, load_mode="source", load_uA=20.0),
                _op_case(dut, name="vdrv_1p0_sink20u", vdrv=1.0, load_mode="sink", load_uA=20.0),
            ]
        }
        write_metrics_json(METRICS_PATH, payload)
        self.assertEqual(len(payload["cases"]), 8)
