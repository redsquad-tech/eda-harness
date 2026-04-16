from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21 as sky130
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import ResultFormat

from devices.hogervorst_page12_sky130_opa.common import default_ngspice_options, run_ngspice_sim
from devices.hogervorst_page12_sky130_opa.opamp import NeuronOaParams, complementary_cascode_frontend, compile_for_sky130
from devices.hogervorst_page12_sky130_opa.opa_bias import OpaBiasGen
from devices.hogervorst_page12_sky130_opa.tests._helpers import BaseV4SimTest, find_signal, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_frontend_isolated_dc_metrics.json")


def _build_tb(params: NeuronOaParams, vinp_v: float, vinn_v: float):
    frontend = complementary_cascode_frontend(params.frontend)
    bias = OpaBiasGen(params.bias)

    @h.module
    class Tb:
        VSS = h.Port()
        avdd, vinp_sig, vinn_sig, iref = h.Signals(4)
        vbias1, vbias2, vbias3 = h.Signals(3)
        tail_p, tail_n, vgp, vgn = h.Signals(4)
        vb_m24, vb_m35 = h.Signals(2)

        vvdd = h.Vdc(dc=1.8)(p=avdd, n=VSS)
        vvinp = h.Vdc(dc=vinp_v)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=vinn_v)(p=vinn_sig, n=VSS)
        iiref = h.Idc(dc=0.25e-6)(p=iref, n=VSS)

        xbias = bias(
            avdd=avdd,
            agnd=VSS,
            iref=iref,
            i0_p=tail_p,
            i0_n=tail_n,
            ibias_p=vb_m24,
            ibias_n=vb_m35,
            vbias1=vbias1,
            vbias2=vbias2,
            vbias3=vbias3,
        )
        # Give the Monticelli-side current outputs a DC path in the isolated frontend bench.
        ribp = h.Res(r=100_000)(p=vb_m24, n=VSS)
        ribn = h.Res(r=100_000)(p=vb_m35, n=avdd)
        xfrontend = frontend(
            vinp=vinp_sig,
            vinn=vinn_sig,
            avdd=avdd,
            agnd=VSS,
            tail_p=tail_p,
            tail_n=tail_n,
            vbias1=vbias1,
            vbias2=vbias2,
            vbias3=vbias3,
            vgp=vgp,
            vgn=vgn,
        )

    return Tb


def measure_frontend_isolated_dc(params: NeuronOaParams | None = None) -> dict:
    params = params or NeuronOaParams()
    rows = []
    for idx, vinp_v in enumerate((0.85, 0.90, 0.95)):
        tb = h.elaborate(_build_tb(params, vinp_v=vinp_v, vinn_v=0.90))
        compile_for_sky130(tb)
        sim = Sim(
            tb=tb,
            attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), sky130.install.include(h.pdk.Corner.TYP)],
        )
        result = run_ngspice_sim(
            sim,
            default_ngspice_options(f"opamp_v4_frontend_iso_{idx}_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
        )
        data = result.an[0].data
        rows.append(
            {
                "vinp_V": vinp_v,
                "vinn_V": 0.90,
                "vbias1_V": find_signal(data, exact="v(xtop.vbias1)"),
                "vbias2_V": find_signal(data, exact="v(xtop.vbias2)"),
                "vbias3_V": find_signal(data, exact="v(xtop.vbias3)"),
                "tail_p_V": find_signal(data, exact="v(xtop.tail_p)"),
                "tail_n_V": find_signal(data, exact="v(xtop.tail_n)"),
                "vgp_V": find_signal(data, exact="v(xtop.vgp)"),
                "vgn_V": find_signal(data, exact="v(xtop.vgn)"),
                "pnode_l_V": find_signal(data, suffix="pnode_l)"),
                "pnode_r_V": find_signal(data, suffix="pnode_r)"),
                "nnode_l_V": find_signal(data, suffix="nnode_l)"),
                "nnode_r_V": find_signal(data, suffix="nnode_r)"),
                "vref_mid_V": find_signal(data, suffix="vref_mid)"),
            }
        )

    first, mid, last = rows
    dv = last["vinp_V"] - first["vinp_V"]
    slope_p = (last["vgp_V"] - first["vgp_V"]) / dv
    slope_n = (last["vgn_V"] - first["vgn_V"]) / dv
    return {
        "rows": rows,
        "summary": {
            "vinp_to_vgp_slope": slope_p,
            "vinp_to_vgn_slope": slope_n,
            "stage1_cm_mid_V": 0.5 * (mid["vgp_V"] + mid["vgn_V"]),
            "stage1_diff_mid_V": mid["vgp_V"] - mid["vgn_V"],
            "pmos_biases_within_range": 0.2 <= mid["vbias1_V"] <= 1.6 and 0.2 <= mid["vbias2_V"] <= 1.6,
            "nmos_biases_within_range": 0.1 <= mid["vbias3_V"] <= 1.2,
            "stage1_signs_opposite": slope_p * slope_n < 0.0,
            "internal_nodes_finite": all(abs(mid[k]) < 10.0 for k in mid if k.endswith("_V")),
        },
    }


class TestV4FrontendIsolatedDc(BaseV4SimTest):
    def test_frontend_isolated_dc(self) -> None:
        payload = measure_frontend_isolated_dc()
        rows = payload["rows"]
        mid = rows[1]
        slope_p = payload["summary"]["vinp_to_vgp_slope"]
        slope_n = payload["summary"]["vinp_to_vgn_slope"]
        write_metrics_json(METRICS_PATH, payload)

        self.assertTrue(payload["summary"]["pmos_biases_within_range"], f"PMOS biases out of range: vbias1_V={mid['vbias1_V']:.6g}, vbias2_V={mid['vbias2_V']:.6g}")
        self.assertTrue(payload["summary"]["nmos_biases_within_range"], f"NMOS bias out of range: vbias3_V={mid['vbias3_V']:.6g}")
        self.assertFinite(payload["summary"]["vinp_to_vgp_slope"])
        self.assertFinite(payload["summary"]["vinp_to_vgn_slope"])
        self.assertTrue(payload["summary"]["stage1_signs_opposite"], f"vinp_to_vgp_slope={slope_p:.6g}, vinp_to_vgn_slope={slope_n:.6g} must have opposite signs")
        self.assertTrue(payload["summary"]["internal_nodes_finite"])
