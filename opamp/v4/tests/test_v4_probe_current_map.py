from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21 as sky130
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import ResultFormat

from opamp.v4.common import default_ngspice_options, run_ngspice_sim
from opamp.v4.opamp import NeuronOaParams, compile_for_sky130, neuron_core_oa_sky130
from opamp.v4.tests._helpers import BaseV4SimTest, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_probe_current_map_metrics.json")


def _build_tb(dut):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, avdd = h.Signals(4)
        iref, vbase, vfeed, vtest = h.Signals(4)
        d_en_oa, d_az_oa, d_inf_oa = h.Signals(3)
        d_treset_oa, d_tcki, d_tcko, d_tdi, d_tdo = h.Signals(5)

        vvdd = h.Vdc(dc=1.8)(p=avdd, n=VSS)
        vvinp = h.Vdc(dc=0.9)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=0.9)(p=vinn_sig, n=VSS)
        ven = h.Vdc(dc=1.8)(p=d_en_oa, n=VSS)
        vaz = h.Vdc(dc=0.0)(p=d_az_oa, n=VSS)
        vinf = h.Vdc(dc=1.8)(p=d_inf_oa, n=VSS)
        vtreset = h.Vdc(dc=0.0)(p=d_treset_oa, n=VSS)
        vtcki = h.Vdc(dc=0.0)(p=d_tcki, n=VSS)
        vtdi = h.Vdc(dc=0.0)(p=d_tdi, n=VSS)
        iiref = h.Idc(dc=0.25e-6)(p=iref, n=VSS)

        rfb = h.Res(r=1.0)(p=vout, n=vinn_sig)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        rload = h.Res(r=1e9)(p=vout, n=VSS)

        xdut = dut(
            avdd1p2=avdd,
            agnd=VSS,
            vinp=vinp_sig,
            vinn=vinn_sig,
            vout=vout,
            in0u25_oa=iref,
            vbase=vbase,
            vfeed=vfeed,
            d_en_oa=d_en_oa,
            d_az_oa=d_az_oa,
            d_inf_oa=d_inf_oa,
            vtest=vtest,
            d_treset_oa=d_treset_oa,
            d_tcki=d_tcki,
            d_tcko=d_tcko,
            d_tdi=d_tdi,
            d_tdo=d_tdo,
        )

    return Tb


class TestV4ProbeCurrentMap(BaseV4SimTest):
    def test_probe_current_map(self) -> None:
        dut = h.elaborate(neuron_core_oa_sky130(NeuronOaParams()))
        compile_for_sky130(dut)
        op_save = [
            "@m.xtop.xxdut.xbias.xmp_ref.msky130_fd_pr__pfet_01v8[id]",
            "@m.xtop.xxdut.xbias.xmp_i0_p_ref.msky130_fd_pr__pfet_01v8[id]",
            "@m.xtop.xxdut.xbias.xmn_i0_p_sink.msky130_fd_pr__nfet_01v8[id]",
            "@m.xtop.xxdut.xbias.xmp_ibias_p_ref.msky130_fd_pr__pfet_01v8[id]",
            "@m.xtop.xxdut.xbias.xmn_ibias_p_sink.msky130_fd_pr__nfet_01v8[id]",
            "@m.xtop.xxdut.xbias.xmp_nref_feed.msky130_fd_pr__pfet_01v8[id]",
            "@m.xtop.xxdut.xbias.xmn_ref.msky130_fd_pr__nfet_01v8[id]",
            "@m.xtop.xxdut.xbias.xmp_i0_n_feed.msky130_fd_pr__pfet_01v8[id]",
            "@m.xtop.xxdut.xbias.xmn_i0_n_ref.msky130_fd_pr__nfet_01v8[id]",
            "@m.xtop.xxdut.xbias.xmp_ibias_n_feed.msky130_fd_pr__pfet_01v8[id]",
            "@m.xtop.xxdut.xbias.xmn_ibias_n_ref.msky130_fd_pr__nfet_01v8[id]",
            "@m.xtop.xxdut.xbias.xmp_i0_p_out.msky130_fd_pr__pfet_01v8[id]",
            "@m.xtop.xxdut.xbias.xmn_i0_n_out.msky130_fd_pr__nfet_01v8[id]",
            "@m.xtop.xxdut.xbias.xmp_ibias_p_out.msky130_fd_pr__pfet_01v8[id]",
            "@m.xtop.xxdut.xbias.xmn_ibias_n_out.msky130_fd_pr__nfet_01v8[id]",
            "@m.xtop.xxdut.xfrontend.xpinp_l.msky130_fd_pr__pfet_01v8[id]",
            "@m.xtop.xxdut.xfrontend.xpinp_r.msky130_fd_pr__pfet_01v8[id]",
            "@m.xtop.xxdut.xfrontend.xninp_l.msky130_fd_pr__nfet_01v8[id]",
            "@m.xtop.xxdut.xfrontend.xninp_r.msky130_fd_pr__nfet_01v8[id]",
            "@m.xtop.xxdut.xfrontend.xmpb1_l.msky130_fd_pr__pfet_01v8[id]",
            "@m.xtop.xxdut.xfrontend.xmpb1_r.msky130_fd_pr__pfet_01v8[id]",
            "@m.xtop.xxdut.xfrontend.xmnb3_l.msky130_fd_pr__nfet_01v8[id]",
            "@m.xtop.xxdut.xfrontend.xmnb3_r.msky130_fd_pr__nfet_01v8[id]",
            "@m.xtop.xxdut.xmont.xm24.msky130_fd_pr__nfet_01v8[id]",
            "@m.xtop.xxdut.xmont.xm35.msky130_fd_pr__pfet_01v8[id]",
            "@m.xtop.xxdut.xoutput_stage.xm1.msky130_fd_pr__nfet_01v8[id]",
            "@m.xtop.xxdut.xoutput_stage.xm2.msky130_fd_pr__pfet_01v8[id]",
            "i(v.xtop.vvvdd)",
        ]
        sim = Sim(
            tb=_build_tb(dut),
            attrs=[Op(), Save(", ".join(op_save)), h.sim.Literal(".temp 27"), sky130.install.include(h.pdk.Corner.TYP)],
        )
        result = run_ngspice_sim(
            sim,
            default_ngspice_options(f"opamp_v4_probe_currmap_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
        )
        d = result.an[0].data
        payload = {
            "bias_ref_A": abs(float(d["i(@m.xtop.xxdut.xbias.xmp_ref.msky130_fd_pr__pfet_01v8[id])"])),
            "bias_i0_p_ref_A": abs(float(d["i(@m.xtop.xxdut.xbias.xmp_i0_p_ref.msky130_fd_pr__pfet_01v8[id])"])),
            "bias_i0_p_sink_A": abs(float(d["i(@m.xtop.xxdut.xbias.xmn_i0_p_sink.msky130_fd_pr__nfet_01v8[id])"])),
            "bias_ibias_p_ref_A": abs(float(d["i(@m.xtop.xxdut.xbias.xmp_ibias_p_ref.msky130_fd_pr__pfet_01v8[id])"])),
            "bias_ibias_p_sink_A": abs(float(d["i(@m.xtop.xxdut.xbias.xmn_ibias_p_sink.msky130_fd_pr__nfet_01v8[id])"])),
            "bias_n_feed_A": abs(float(d["i(@m.xtop.xxdut.xbias.xmp_nref_feed.msky130_fd_pr__pfet_01v8[id])"])),
            "bias_n_ref_A": abs(float(d["i(@m.xtop.xxdut.xbias.xmn_ref.msky130_fd_pr__nfet_01v8[id])"])),
            "bias_i0_n_feed_A": abs(float(d["i(@m.xtop.xxdut.xbias.xmp_i0_n_feed.msky130_fd_pr__pfet_01v8[id])"])),
            "bias_i0_n_ref_A": abs(float(d["i(@m.xtop.xxdut.xbias.xmn_i0_n_ref.msky130_fd_pr__nfet_01v8[id])"])),
            "bias_ibias_n_feed_A": abs(float(d["i(@m.xtop.xxdut.xbias.xmp_ibias_n_feed.msky130_fd_pr__pfet_01v8[id])"])),
            "bias_ibias_n_ref_A": abs(float(d["i(@m.xtop.xxdut.xbias.xmn_ibias_n_ref.msky130_fd_pr__nfet_01v8[id])"])),
            "tail_p_A": abs(float(d["i(@m.xtop.xxdut.xbias.xmp_i0_p_out.msky130_fd_pr__pfet_01v8[id])"])),
            "tail_n_A": abs(float(d["i(@m.xtop.xxdut.xbias.xmn_i0_n_out.msky130_fd_pr__nfet_01v8[id])"])),
            "vb_m24_A": abs(float(d["i(@m.xtop.xxdut.xbias.xmp_ibias_p_out.msky130_fd_pr__pfet_01v8[id])"])),
            "vb_m35_A": abs(float(d["i(@m.xtop.xxdut.xbias.xmn_ibias_n_out.msky130_fd_pr__nfet_01v8[id])"])),
            "frontend_pinp_l_A": abs(float(d["i(@m.xtop.xxdut.xfrontend.xpinp_l.msky130_fd_pr__pfet_01v8[id])"])),
            "frontend_pinp_r_A": abs(float(d["i(@m.xtop.xxdut.xfrontend.xpinp_r.msky130_fd_pr__pfet_01v8[id])"])),
            "frontend_ninp_l_A": abs(float(d["i(@m.xtop.xxdut.xfrontend.xninp_l.msky130_fd_pr__nfet_01v8[id])"])),
            "frontend_ninp_r_A": abs(float(d["i(@m.xtop.xxdut.xfrontend.xninp_r.msky130_fd_pr__nfet_01v8[id])"])),
            "frontend_mpb1_l_A": abs(float(d["i(@m.xtop.xxdut.xfrontend.xmpb1_l.msky130_fd_pr__pfet_01v8[id])"])),
            "frontend_mpb1_r_A": abs(float(d["i(@m.xtop.xxdut.xfrontend.xmpb1_r.msky130_fd_pr__pfet_01v8[id])"])),
            "frontend_mnb3_l_A": abs(float(d["i(@m.xtop.xxdut.xfrontend.xmnb3_l.msky130_fd_pr__nfet_01v8[id])"])),
            "frontend_mnb3_r_A": abs(float(d["i(@m.xtop.xxdut.xfrontend.xmnb3_r.msky130_fd_pr__nfet_01v8[id])"])),
            "mont_n_bridge_A": abs(float(d["i(@m.xtop.xxdut.xmont.xm24.msky130_fd_pr__nfet_01v8[id])"])),
            "mont_p_bridge_A": abs(float(d["i(@m.xtop.xxdut.xmont.xm35.msky130_fd_pr__pfet_01v8[id])"])),
            "out_n_A": abs(float(d["i(@m.xtop.xxdut.xoutput_stage.xm1.msky130_fd_pr__nfet_01v8[id])"])),
            "out_p_A": abs(float(d["i(@m.xtop.xxdut.xoutput_stage.xm2.msky130_fd_pr__pfet_01v8[id])"])),
            "iq_total_A": abs(float(d["i(v.xtop.vvvdd)"])),
        }
        payload["summary"] = {
            "frontend_p_balance": payload["frontend_pinp_l_A"] / max(payload["frontend_pinp_r_A"], 1e-30),
            "frontend_n_balance": payload["frontend_ninp_l_A"] / max(payload["frontend_ninp_r_A"], 1e-30),
            "output_balance": payload["out_p_A"] / max(payload["out_n_A"], 1e-30),
        }
        write_metrics_json(METRICS_PATH, payload)

        for key, value in payload.items():
            if key == "summary":
                continue
            self.assertFinite(value, key)
        self.assertGreater(payload["iq_total_A"], 0.0)
        self.assertGreater(payload["bias_ref_A"], 0.0)
        self.assertGreater(payload["tail_n_A"], 0.0)
