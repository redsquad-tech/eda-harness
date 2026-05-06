from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21 as sky130
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import ResultFormat

from devices.hogervorst_page12_sky130_opa.common import default_ngspice_options, run_ngspice_sim
from devices.hogervorst_page12_sky130_opa.opamp import Page12CoreParams, compile_for_sky130, page12_analog_core
from devices.hogervorst_page12_sky130_opa.tests._helpers import BaseV4SimTest, find_signal, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_page12_core_lowcm_ideal_bias_metrics.json")


def _build_tb(params: Page12CoreParams, vinp_v: float, vinn_v: float):
    dut = page12_analog_core(params)

    @h.module
    class Tb:
        VSS = h.Port()
        avdd, vinp_sig, vinn_sig, vout = h.Signals(4)
        tail_p, tail_n = h.Signals(2)
        vbias1, vbias2, vbias3 = h.Signals(3)
        m24_gate_mid, m35_gate_mid = h.Signals(2)
        pnode_l, pnode_r, nnode_l, nnode_r = h.Signals(4)
        vref_mid, vgp, vgn = h.Signals(3)

        vvdd = h.Vdc(dc=1.8)(p=avdd, n=VSS)
        vvinp = h.Vdc(dc=vinp_v)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=vinn_v)(p=vinn_sig, n=VSS)

        # Idealized bias replacement for topology isolation.
        itail_p = h.Idc(dc=1.6e-6)(p=avdd, n=tail_p)
        itail_n = h.Idc(dc=1.6e-6)(p=tail_n, n=VSS)
        ibias_p = h.Idc(dc=0.45e-6)(p=avdd, n=m24_gate_mid)
        ibias_n = h.Idc(dc=0.45e-6)(p=m35_gate_mid, n=VSS)
        vb1 = h.Vdc(dc=0.824)(p=vbias1, n=VSS)
        vb2 = h.Vdc(dc=0.891)(p=vbias2, n=VSS)
        vb3 = h.Vdc(dc=0.634)(p=vbias3, n=VSS)

        rfb = h.Res(r=1.0)(p=vout, n=vinn_sig)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        rload = h.Res(r=1e9)(p=vout, n=VSS)

        xdut = dut(
            vinp=vinp_sig,
            vinn=vinn_sig,
            avdd=avdd,
            agnd=VSS,
            vout=vout,
            tail_p=tail_p,
            tail_n=tail_n,
            vbias1=vbias1,
            vbias2=vbias2,
            vbias3=vbias3,
            m24_gate_mid=m24_gate_mid,
            m35_gate_mid=m35_gate_mid,
            pnode_l=pnode_l,
            pnode_r=pnode_r,
            nnode_l=nnode_l,
            nnode_r=nnode_r,
            vref_mid=vref_mid,
            vgp=vgp,
            vgn=vgn,
        )

    return Tb


def measure_page12_core_lowcm_ideal_bias(params: Page12CoreParams | None = None) -> dict:
    params = params or Page12CoreParams()
    rows = []

    for idx, vin_v in enumerate((0.0, 0.1, 0.5, 0.9)):
        tb = h.elaborate(_build_tb(params, vinp_v=vin_v, vinn_v=vin_v))
        compile_for_sky130(tb)
        sim = Sim(
            tb=tb,
            attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), sky130.install.include(h.pdk.Corner.TYP)],
        )
        result = run_ngspice_sim(
            sim,
            default_ngspice_options(f"opamp_v4_page12_core_lowcm_{idx}_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
        )
        data = result.an[0].data

        row = {
            "vin_V": vin_v,
            "iq_uA": -1e6 * find_signal(data, exact="i(v.xtop.vvvdd)"),
            "vout_V": find_signal(data, exact="v(xtop.vout)"),
            "tail_p_V": find_signal(data, exact="v(xtop.tail_p)"),
            "tail_n_V": find_signal(data, exact="v(xtop.tail_n)"),
            "vbias1_V": find_signal(data, exact="v(xtop.vbias1)"),
            "vbias2_V": find_signal(data, exact="v(xtop.vbias2)"),
            "vbias3_V": find_signal(data, exact="v(xtop.vbias3)"),
            "m24_gate_mid_V": find_signal(data, exact="v(xtop.m24_gate_mid)"),
            "m35_gate_mid_V": find_signal(data, exact="v(xtop.m35_gate_mid)"),
            "pnode_l_V": find_signal(data, exact="v(xtop.pnode_l)"),
            "pnode_r_V": find_signal(data, exact="v(xtop.pnode_r)"),
            "nnode_l_V": find_signal(data, exact="v(xtop.nnode_l)"),
            "nnode_r_V": find_signal(data, exact="v(xtop.nnode_r)"),
            "vref_mid_V": find_signal(data, exact="v(xtop.vref_mid)"),
            "vgp_V": find_signal(data, exact="v(xtop.vgp)"),
            "vgn_V": find_signal(data, exact="v(xtop.vgn)"),
        }
        row["derived"] = {
            "driver_diff_V": row["vgp_V"] - row["vgn_V"],
            "driver_cm_V": 0.5 * (row["vgp_V"] + row["vgn_V"]),
            "internal_nodes_finite": all(abs(row[key]) < 10.0 for key in row if key.endswith("_V")),
            "drivers_within_rails": all(0.0 <= row[key] <= 1.8 for key in ("vgp_V", "vgn_V", "vout_V")),
            "collapsed_like_product": row["iq_uA"] < 10.0 and abs(row["vout_V"]) < 1e-3,
        }
        rows.append(row)

    return {
        "rows": rows,
        "summary": {
            "low_cm_collapsed_points": [row["vin_V"] for row in rows if row["derived"]["collapsed_like_product"]],
            "all_nodes_finite": all(row["derived"]["internal_nodes_finite"] for row in rows),
            "all_driver_nodes_within_rails": all(row["derived"]["drivers_within_rails"] for row in rows),
            "vin0_iq_uA": rows[0]["iq_uA"],
            "vin0_vout_V": rows[0]["vout_V"],
            "vin09_iq_uA": rows[-1]["iq_uA"],
            "vin09_vout_V": rows[-1]["vout_V"],
        },
    }


class TestV4Page12CoreLowCmIdealBias(BaseV4SimTest):
    def test_page12_core_lowcm_ideal_bias(self) -> None:
        payload = measure_page12_core_lowcm_ideal_bias()
        write_metrics_json(METRICS_PATH, payload)

        self.assertTrue(payload["summary"]["all_nodes_finite"])
        self.assertTrue(payload["summary"]["all_driver_nodes_within_rails"])
        self.assertGreater(payload["summary"]["vin09_iq_uA"], 0.0)
        self.assertMetricBetween("vin09_vout_V", payload["summary"]["vin09_vout_V"], 0.0, 1.8)
