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
from devices.hogervorst_page12_sky130_opa.tests._helpers import BaseV4SimTest, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_frontend_isolated_currents_metrics.json")


def _build_tb(params: NeuronOaParams):
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
        vvinp = h.Vdc(dc=0.90)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=0.90)(p=vinn_sig, n=VSS)
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


class TestV4FrontendIsolatedCurrents(BaseV4SimTest):
    def test_frontend_isolated_currents(self) -> None:
        dut = h.elaborate(_build_tb(NeuronOaParams()))
        compile_for_sky130(dut)
        saves = [
            "@m.xtop.xbias.xmp_i0_p_out.msky130_fd_pr__pfet_01v8[id]",
            "@m.xtop.xbias.xmn_i0_n_out.msky130_fd_pr__nfet_01v8[id]",
            "@m.xtop.xfrontend.xpinp_l.msky130_fd_pr__pfet_01v8[id]",
            "@m.xtop.xfrontend.xpinp_r.msky130_fd_pr__pfet_01v8[id]",
            "@m.xtop.xfrontend.xninp_l.msky130_fd_pr__nfet_01v8[id]",
            "@m.xtop.xfrontend.xninp_r.msky130_fd_pr__nfet_01v8[id]",
            "@m.xtop.xfrontend.xmpb1_l.msky130_fd_pr__pfet_01v8[id]",
            "@m.xtop.xfrontend.xmpb1_r.msky130_fd_pr__pfet_01v8[id]",
            "@m.xtop.xfrontend.xmnb3_l.msky130_fd_pr__nfet_01v8[id]",
            "@m.xtop.xfrontend.xmnb3_r.msky130_fd_pr__nfet_01v8[id]",
        ]
        sim = Sim(
            tb=dut,
            attrs=[Op(), Save(", ".join(saves)), h.sim.Literal(".temp 27"), sky130.install.include(h.pdk.Corner.TYP)],
        )
        result = run_ngspice_sim(
            sim,
            default_ngspice_options(f"opamp_v4_frontend_curr_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
        )
        d = result.an[0].data
        payload = {
            "tail_p_A": abs(float(d["i(@m.xtop.xbias.xmp_i0_p_out.msky130_fd_pr__pfet_01v8[id])"])),
            "tail_n_A": abs(float(d["i(@m.xtop.xbias.xmn_i0_n_out.msky130_fd_pr__nfet_01v8[id])"])),
            "pinp_l_A": abs(float(d["i(@m.xtop.xfrontend.xpinp_l.msky130_fd_pr__pfet_01v8[id])"])),
            "pinp_r_A": abs(float(d["i(@m.xtop.xfrontend.xpinp_r.msky130_fd_pr__pfet_01v8[id])"])),
            "ninp_l_A": abs(float(d["i(@m.xtop.xfrontend.xninp_l.msky130_fd_pr__nfet_01v8[id])"])),
            "ninp_r_A": abs(float(d["i(@m.xtop.xfrontend.xninp_r.msky130_fd_pr__nfet_01v8[id])"])),
            "mpb1_l_A": abs(float(d["i(@m.xtop.xfrontend.xmpb1_l.msky130_fd_pr__pfet_01v8[id])"])),
            "mpb1_r_A": abs(float(d["i(@m.xtop.xfrontend.xmpb1_r.msky130_fd_pr__pfet_01v8[id])"])),
            "mnb3_l_A": abs(float(d["i(@m.xtop.xfrontend.xmnb3_l.msky130_fd_pr__nfet_01v8[id])"])),
            "mnb3_r_A": abs(float(d["i(@m.xtop.xfrontend.xmnb3_r.msky130_fd_pr__nfet_01v8[id])"])),
        }
        payload["summary"] = {
            "tail_ratio_p_to_n": payload["tail_p_A"] / max(payload["tail_n_A"], 1e-30),
            "pinp_balance": payload["pinp_l_A"] / max(payload["pinp_r_A"], 1e-30),
            "ninp_balance": payload["ninp_l_A"] / max(payload["ninp_r_A"], 1e-30),
        }
        write_metrics_json(METRICS_PATH, payload)

        for key, value in payload.items():
            if key == "summary":
                continue
            self.assertFinite(value, key)
