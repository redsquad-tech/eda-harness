from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import hdl21 as h
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import SimOptions

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.output_path_reference import default_reference_output_path_params, reference_output_path_method2
from opamp.v3.tests._helpers import BaseV3SimTest, reset_metrics_file, write_metrics_json


METRICS_PATH = Path(__file__).with_name("rc_probe_reference_output_path_dc_audit_metrics.json")


def _build_tb(dut, *, vdrv: float):
    @h.module
    class Tb:
        VSS = h.Port()
        vdd, vdrv_sig, vout = h.Signals(3)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        vvdrv = h.Vdc(dc=vdrv)(p=vdrv_sig, n=VSS)
        rload = h.Res(r=1e12)(p=vout, n=VSS)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        xdut = dut(VDRV=vdrv_sig, VOUT=vout, VDD=vdd, VSS=VSS)

    return Tb


def _node_v(data: dict[str, float], key: str) -> float:
    if key in {"0", "v(0)", "v(xtop.vss)", "v(xtop.xxdut.vss)"}:
        return 0.0
    return float(data[key])


def _nmos_audit(data: dict[str, float], *, d: str, g: str, s: str, current_key: str | None = None) -> dict[str, float]:
    vd = _node_v(data, d)
    vg = _node_v(data, g)
    vs = _node_v(data, s)
    payload = {
        "vd_V": vd,
        "vg_V": vg,
        "vs_V": vs,
        "vgs_V": vg - vs,
        "vds_V": vd - vs,
    }
    if current_key is not None and current_key in data:
        payload["current_A"] = float(data[current_key])
    return payload


def _pmos_audit(data: dict[str, float], *, d: str, g: str, s: str, current_key: str | None = None) -> dict[str, float]:
    vd = _node_v(data, d)
    vg = _node_v(data, g)
    vs = _node_v(data, s)
    payload = {
        "vd_V": vd,
        "vg_V": vg,
        "vs_V": vs,
        "vsg_V": vs - vg,
        "vsd_V": vs - vd,
    }
    if current_key is not None and current_key in data:
        payload["current_A"] = float(data[current_key])
    return payload


def _case(dut, *, name: str, vdrv: float):
    install = require_sky130_install()
    sim = Sim(
        tb=_build_tb(dut, vdrv=vdrv),
        attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)],
    )
    res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/rc_refaudit_{uuid4().hex[:8]}")
    d = res.an[0].data
    values = {k: float(v) for k, v in d.items()}
    payload = {
        "case": name,
        "vdrv_in_V": vdrv,
        "vout_V": float(d["v(xtop.vout)"]),
        "vdrvb_V": float(d["v(xtop.xxdut.vdrvb)"]),
        "vgn_q_V": float(d["v(xtop.xxdut.vgn_q)"]),
        "vgp_q_V": float(d["v(xtop.xxdut.vgp_q)"]),
        "vgn_V": float(d["v(xtop.xxdut.vgn)"]),
        "vgp_V": float(d["v(xtop.xxdut.vgp)"]),
        "m_inv_n": _nmos_audit(
            values,
            d="v(xtop.xxdut.vdrvb)",
            g="v(xtop.vdrv_sig)",
            s="v(xtop.vss)",
        ),
        "m_inv_p": _pmos_audit(
            values,
            d="v(xtop.xxdut.vdrvb)",
            g="v(xtop.vdrv_sig)",
            s="v(xtop.vdd)",
        ),
        "m_bias_n": _nmos_audit(
            values,
            d="v(xtop.xxdut.vgn_q)",
            g="v(xtop.xxdut.vgn_q)",
            s="v(xtop.xxdut.vss_bias_n)",
            current_key="i(v.xtop.xxdut.vvprobe_bias_n)",
        ),
        "m_bias_p": _pmos_audit(
            values,
            d="v(xtop.xxdut.vgp_q)",
            g="v(xtop.xxdut.vgp_q)",
            s="v(xtop.xxdut.vdd_bias_p)",
            current_key="i(v.xtop.xxdut.vvprobe_bias_p)",
        ),
        "m_out_n": _nmos_audit(
            values,
            d="v(xtop.xxdut.vout_n)",
            g="v(xtop.xxdut.vgn)",
            s="v(xtop.vss)",
            current_key="i(v.xtop.xxdut.vvprobe_outn)",
        ),
        "m_out_p": _pmos_audit(
            values,
            d="v(xtop.xxdut.vout_p)",
            g="v(xtop.xxdut.vgp)",
            s="v(xtop.vdd)",
            current_key="i(v.xtop.xxdut.vvprobe_outp)",
        ),
    }
    return payload


class TestRcProbeReferenceOutputPathDcAudit(BaseV3SimTest):
    def test_probe_rc_reference_output_path_dc_audit(self):
        reset_metrics_file(METRICS_PATH)
        dut = reference_output_path_method2(default_reference_output_path_params())
        payload = {
            "cases": [
                _case(dut, name="vdrv_0p0", vdrv=0.0),
                _case(dut, name="vdrv_0p8", vdrv=0.8),
                _case(dut, name="vdrv_1p0", vdrv=1.0),
                _case(dut, name="vdrv_1p6", vdrv=1.6),
            ]
        }
        write_metrics_json(METRICS_PATH, payload)
        self.assertEqual(len(payload["cases"]), 4)
