from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21 as sky130
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import ResultFormat

from devices.hogervorst_page12_sky130_opa.source.common import default_ngspice_options, run_ngspice_sim
from devices.hogervorst_page12_sky130_opa.opamp import NeuronOaParams, compile_for_sky130
from devices.hogervorst_page12_sky130_opa.source.opa_bias import OpaBiasGen
from devices.hogervorst_page12_sky130_opa.source.legacy_cells import complementary_cascode_frontend
from devices.hogervorst_page12_sky130_opa.tests._helpers import BaseV4SimTest, find_signal, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_frontend_gain_target_metrics.json")


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


def measure_frontend_gain_target(params: NeuronOaParams | None = None) -> dict:
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
            default_ngspice_options(f"opamp_v4_frontend_gain_{idx}_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
        )
        data = result.an[0].data
        rows.append(
            {
                "vinp_V": vinp_v,
                "vgp_V": find_signal(data, exact="v(xtop.vgp)"),
                "vgn_V": find_signal(data, exact="v(xtop.vgn)"),
            }
        )

    first, mid, last = rows
    dv = last["vinp_V"] - first["vinp_V"]
    slope_p = (last["vgp_V"] - first["vgp_V"]) / dv
    slope_n = (last["vgn_V"] - first["vgn_V"]) / dv
    diff_gain = ((last["vgp_V"] - last["vgn_V"]) - (first["vgp_V"] - first["vgn_V"])) / dv
    return {
        "rows": rows,
        "summary": {
            "vinp_to_vgp_slope": slope_p,
            "vinp_to_vgn_slope": slope_n,
            "stage1_diff_gain_V_per_V": diff_gain,
            "stage1_cm_mid_V": 0.5 * (mid["vgp_V"] + mid["vgn_V"]),
        },
    }


class TestV4FrontendGainTarget(BaseV4SimTest):
    def test_frontend_gain_target(self) -> None:
        payload = measure_frontend_gain_target()
        write_metrics_json(METRICS_PATH, payload)

        self.assertFinite(payload["summary"]["stage1_diff_gain_V_per_V"])
        self.assertMetricGreater("stage1_diff_gain_V_per_V", payload["summary"]["stage1_diff_gain_V_per_V"], 0.05)
        self.assertMetricBetween("stage1_cm_mid_V", payload["summary"]["stage1_cm_mid_V"], 0.2, 1.6)
