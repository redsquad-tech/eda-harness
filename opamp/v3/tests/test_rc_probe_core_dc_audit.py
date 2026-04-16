from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import hdl21 as h
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import SimOptions

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.opamp_core import opamp_core
from opamp.v3.tests._helpers import BaseV3SimTest, build_debug_core_params, reset_metrics_file, write_metrics_json


METRICS_PATH = Path(__file__).with_name("rc_probe_core_dc_audit_metrics.json")


def _build_tb(dut):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp, vinn, vout, en, vdd = h.Signals(5)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        ven = h.Vdc(dc=1.8)(p=en, n=VSS)
        vvinp = h.Vdc(dc=0.9)(p=vinp, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinn)
        rl = h.Res(r=1e6)(p=vout, n=VSS)
        cl = h.Cap(c=1e-12)(p=vout, n=VSS)
        xdut = dut(VINP=vinp, VINN=vinn, VOUT=vout, EN=en, VDD=vdd, VSS=VSS)

    return Tb


def _node_v(v: dict[str, float], key: str) -> float:
    if key in {"0", "v(0)", "v(xtop.vss)", "v(xtop.xxdut.vss)"}:
        return 0.0
    return float(v[key])


def _nmos(v: dict[str, float], *, d: str, g: str, s: str, current: str | None = None) -> dict[str, float]:
    vd = _node_v(v, d)
    vg = _node_v(v, g)
    vs = _node_v(v, s)
    payload = {"vd_V": vd, "vg_V": vg, "vs_V": vs, "vgs_V": vg - vs, "vds_V": vd - vs}
    if current is not None and current in v:
        payload["current_A"] = float(v[current])
    return payload


def _pmos(v: dict[str, float], *, d: str, g: str, s: str, current: str | None = None) -> dict[str, float]:
    vd = _node_v(v, d)
    vg = _node_v(v, g)
    vs = _node_v(v, s)
    payload = {"vd_V": vd, "vg_V": vg, "vs_V": vs, "vsg_V": vs - vg, "vsd_V": vs - vd}
    if current is not None and current in v:
        payload["current_A"] = float(v[current])
    return payload


class TestRcProbeCoreDcAudit(BaseV3SimTest):
    def test_probe_rc_core_dc_audit(self):
        reset_metrics_file(METRICS_PATH)
        install = require_sky130_install()
        dut = opamp_core(build_debug_core_params())
        sim = Sim(tb=_build_tb(dut), attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)])
        res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/rc_coreaudit_{uuid4().hex[:8]}")
        d = res.an[0].data
        v = {k: float(val) for k, val in d.items()}
        output_path_present = "v(xtop.xxdut.xxout_driver.vgn_q)" in d
        payload = {
            "summary": {
                "vin_V": 0.9,
                "vx_V": float(d["v(xtop.xxdut.vx)"]),
                "vref_V": float(d["v(xtop.xxdut.vref)"]),
                "vdrv_V": float(d["v(xtop.xxdut.vdrv)"]),
                "vgn_V": float(d.get("v(xtop.xxdut.vgn)", 0.0)),
                "vgp_V": float(d.get("v(xtop.xxdut.vgp)", 1.8)),
                "vout_V": float(d["v(xtop.vout)"]),
                "output_path_present": output_path_present,
            },
            "m_stage2_n": _nmos(
                v,
                d="v(xtop.xxdut.vdrv_s2n)",
                g="v(xtop.xxdut.vx)",
                s="v(xtop.vss)",
                current="i(v.xtop.xxdut.vvprobe_s2n)",
            ),
            "m_stage2_p": _pmos(
                v,
                d="v(xtop.xxdut.vdrv_s2p)",
                g="v(xtop.xxdut.ibias2)",
                s="v(xtop.vdd)",
                current="i(v.xtop.xxdut.vvprobe_s2p)",
            ),
            "m_out_n": (
                _nmos(
                    v,
                    d="v(xtop.xxdut.vout_on)",
                    g="v(xtop.xxdut.vgn)",
                    s="v(xtop.vss)",
                    current="i(v.xtop.xxdut.vvprobe_outn)",
                )
                if "i(v.xtop.xxdut.vvprobe_outn)" in d
                else None
            ),
            "m_out_p": (
                _pmos(
                    v,
                    d="v(xtop.xxdut.vout_op)",
                    g="v(xtop.xxdut.vgp)",
                    s="v(xtop.vdd)",
                    current="i(v.xtop.xxdut.vvprobe_outp)",
                )
                if "i(v.xtop.xxdut.vvprobe_outp)" in d
                else None
            ),
            "m_drv_bias_n": (
                _nmos(
                    v,
                    d="v(xtop.xxdut.xxout_driver.vgn_q)",
                    g="v(xtop.xxdut.xxout_driver.vgn_q)",
                    s="v(xtop.vss)",
                )
                if output_path_present
                else None
            ),
            "m_drv_bias_p": (
                _pmos(
                    v,
                    d="v(xtop.xxdut.xxout_driver.vgp_q)",
                    g="v(xtop.xxdut.xxout_driver.vgp_q)",
                    s="v(xtop.xxdut.vdd_vg_pre)",
                )
                if output_path_present
                else None
            ),
            "i_vdrv_into_driver_A": float(d.get("i(v.xtop.xxdut.vvprobe_vdrv_drv)", 0.0)),
        }
        write_metrics_json(METRICS_PATH, payload)
        self.assertTrue(True)
