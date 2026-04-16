from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21 as sky130
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import ResultFormat

from devices.hogervorst_page12_sky130_opa.common import default_ngspice_options, run_ngspice_sim
from devices.hogervorst_page12_sky130_opa.opamp import NeuronOaParams, compile_for_sky130, neuron_core_oa_sky130
from devices.hogervorst_page12_sky130_opa.tests._helpers import BaseV4SimTest, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_probe_bias_branch_currents_metrics.json")


def _build_tb(dut, *, en_v: float):
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
        ven = h.Vdc(dc=en_v)(p=d_en_oa, n=VSS)
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


def _run_case(*, en_v: float, label: str) -> dict[str, float]:
    dut = h.elaborate(neuron_core_oa_sky130(NeuronOaParams()))
    compile_for_sky130(dut)
    op_save = [
        "@m.xtop.xxdut.xbias.xmp_ref.msky130_fd_pr__pfet_01v8[id]",
        "@m.xtop.xxdut.xbias.xmp_nref_feed.msky130_fd_pr__pfet_01v8[id]",
        "@m.xtop.xxdut.xbias.xmn_ref.msky130_fd_pr__nfet_01v8[id]",
        "@m.xtop.xxdut.xbias.xmp_i0_p_ref.msky130_fd_pr__pfet_01v8[id]",
        "@m.xtop.xxdut.xbias.xmn_i0_p_sink.msky130_fd_pr__nfet_01v8[id]",
        "@m.xtop.xxdut.xbias.xmp_ibias_p_ref.msky130_fd_pr__pfet_01v8[id]",
        "@m.xtop.xxdut.xbias.xmn_ibias_p_sink.msky130_fd_pr__nfet_01v8[id]",
        "@m.xtop.xxdut.xbias.xmp_i0_n_feed.msky130_fd_pr__pfet_01v8[id]",
        "@m.xtop.xxdut.xbias.xmn_i0_n_ref.msky130_fd_pr__nfet_01v8[id]",
        "@m.xtop.xxdut.xbias.xmp_ibias_n_feed.msky130_fd_pr__pfet_01v8[id]",
        "@m.xtop.xxdut.xbias.xmn_ibias_n_ref.msky130_fd_pr__nfet_01v8[id]",
        "v(xtop.xxdut.iref_int)",
        "v(xtop.xxdut.vbias1)",
        "v(xtop.xxdut.vbias2)",
        "v(xtop.xxdut.vbias3)",
        "i(v.xtop.vvvdd)",
    ]
    sim = Sim(
        tb=_build_tb(dut, en_v=en_v),
        attrs=[Op(), Save(", ".join(op_save)), h.sim.Literal(".temp 27"), sky130.install.include(h.pdk.Corner.TYP)],
    )
    result = run_ngspice_sim(
        sim,
        default_ngspice_options(f"opamp_v4_probe_biascur_{label}_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
    )
    d = result.an[0].data
    return {
        "id_ref_A": abs(float(d["i(@m.xtop.xxdut.xbias.xmp_ref.msky130_fd_pr__pfet_01v8[id])"])),
        "id_nref_feed_A": abs(float(d["i(@m.xtop.xxdut.xbias.xmp_nref_feed.msky130_fd_pr__pfet_01v8[id])"])),
        "id_nref_A": abs(float(d["i(@m.xtop.xxdut.xbias.xmn_ref.msky130_fd_pr__nfet_01v8[id])"])),
        "id_i0_p_A": abs(float(d["i(@m.xtop.xxdut.xbias.xmp_i0_p_ref.msky130_fd_pr__pfet_01v8[id])"])),
        "id_i0_p_sink_A": abs(float(d["i(@m.xtop.xxdut.xbias.xmn_i0_p_sink.msky130_fd_pr__nfet_01v8[id])"])),
        "id_ibias_p_A": abs(float(d["i(@m.xtop.xxdut.xbias.xmp_ibias_p_ref.msky130_fd_pr__pfet_01v8[id])"])),
        "id_ibias_p_sink_A": abs(float(d["i(@m.xtop.xxdut.xbias.xmn_ibias_p_sink.msky130_fd_pr__nfet_01v8[id])"])),
        "id_i0_n_feed_A": abs(float(d["i(@m.xtop.xxdut.xbias.xmp_i0_n_feed.msky130_fd_pr__pfet_01v8[id])"])),
        "id_i0_n_A": abs(float(d["i(@m.xtop.xxdut.xbias.xmn_i0_n_ref.msky130_fd_pr__nfet_01v8[id])"])),
        "id_ibias_n_feed_A": abs(float(d["i(@m.xtop.xxdut.xbias.xmp_ibias_n_feed.msky130_fd_pr__pfet_01v8[id])"])),
        "id_ibias_n_A": abs(float(d["i(@m.xtop.xxdut.xbias.xmn_ibias_n_ref.msky130_fd_pr__nfet_01v8[id])"])),
        "iref_int_V": float(d["v(xtop.xxdut.iref_int)"]),
        "vbias1_V": float(d["v(xtop.xxdut.vbias1)"]),
        "vbias2_V": float(d["v(xtop.xxdut.vbias2)"]),
        "vbias3_V": float(d["v(xtop.xxdut.vbias3)"]),
        "iq_total_A": abs(float(d["i(v.xtop.vvvdd)"])),
    }


class TestV4ProbeBiasBranchCurrents(BaseV4SimTest):
    def test_probe_bias_branch_currents(self) -> None:
        enabled = _run_case(en_v=1.8, label="enabled")
        disabled = _run_case(en_v=0.0, label="disabled")
        payload = {"enabled": enabled, "disabled": disabled}
        payload["summary"] = {
            "i0_p_match_ratio": enabled["id_i0_p_A"] / max(enabled["id_i0_p_sink_A"], 1e-30),
            "ibias_p_match_ratio": enabled["id_ibias_p_A"] / max(enabled["id_ibias_p_sink_A"], 1e-30),
            "i0_n_match_ratio": enabled["id_i0_n_feed_A"] / max(enabled["id_i0_n_A"], 1e-30),
            "ibias_n_match_ratio": enabled["id_ibias_n_feed_A"] / max(enabled["id_ibias_n_A"], 1e-30),
            "ref_gating_ratio": disabled["id_ref_A"] / max(enabled["id_ref_A"], 1e-30),
        }
        write_metrics_json(METRICS_PATH, payload)

        self.assertGreater(enabled["id_ref_A"], 1e-9)
        self.assertGreater(enabled["iq_total_A"], 1e-9)
        self.assertLess(payload["summary"]["i0_p_match_ratio"], 10.0)
        self.assertLess(payload["summary"]["ibias_p_match_ratio"], 10.0)
        self.assertLess(payload["summary"]["i0_n_match_ratio"], 10.0)
        self.assertLess(payload["summary"]["ibias_n_match_ratio"], 10.0)
        self.assertFinite(payload["summary"]["ref_gating_ratio"], "ref_gating_ratio must be finite")
