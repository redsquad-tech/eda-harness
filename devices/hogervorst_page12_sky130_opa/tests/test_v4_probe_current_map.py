from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21 as sky130
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import ResultFormat

from devices.hogervorst_page12_sky130_opa.source.common import default_ngspice_options, run_ngspice_sim
from devices.hogervorst_page12_sky130_opa.opamp import NeuronOaParams, compile_for_sky130, neuron_core_oa_sky130
from devices.hogervorst_page12_sky130_opa.tests._helpers import BaseV4SimTest, write_metrics_json


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


def measure_current_map() -> dict:
    dut = h.elaborate(neuron_core_oa_sky130(NeuronOaParams()))
    compile_for_sky130(dut)
    op_save = [
        "@m.xtop.xxdut.xpinp_l.msky130_fd_pr__pfet_01v8[id]",
        "@m.xtop.xxdut.xpinp_r.msky130_fd_pr__pfet_01v8[id]",
        "@m.xtop.xxdut.xninp_l.msky130_fd_pr__nfet_01v8[id]",
        "@m.xtop.xxdut.xninp_r.msky130_fd_pr__nfet_01v8[id]",
        "@m.xtop.xxdut.xmpb1_l.msky130_fd_pr__pfet_01v8[id]",
        "@m.xtop.xxdut.xmpb1_r.msky130_fd_pr__pfet_01v8[id]",
        "@m.xtop.xxdut.xmnb3_l.msky130_fd_pr__nfet_01v8[id]",
        "@m.xtop.xxdut.xmnb3_r.msky130_fd_pr__nfet_01v8[id]",
        "@m.xtop.xxdut.xmn23.msky130_fd_pr__nfet_01v8[id]",
        "@m.xtop.xxdut.xmp34.msky130_fd_pr__pfet_01v8[id]",
        "@m.xtop.xxdut.xm24.msky130_fd_pr__nfet_01v8[id]",
        "@m.xtop.xxdut.xm35.msky130_fd_pr__pfet_01v8[id]",
        "@m.xtop.xxdut.xm1.msky130_fd_pr__nfet_01v8[id]",
        "@m.xtop.xxdut.xm2.msky130_fd_pr__pfet_01v8[id]",
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
        "frontend_pinp_l_A": abs(float(d["i(@m.xtop.xxdut.xpinp_l.msky130_fd_pr__pfet_01v8[id])"])),
        "frontend_pinp_r_A": abs(float(d["i(@m.xtop.xxdut.xpinp_r.msky130_fd_pr__pfet_01v8[id])"])),
        "frontend_ninp_l_A": abs(float(d["i(@m.xtop.xxdut.xninp_l.msky130_fd_pr__nfet_01v8[id])"])),
        "frontend_ninp_r_A": abs(float(d["i(@m.xtop.xxdut.xninp_r.msky130_fd_pr__nfet_01v8[id])"])),
        "frontend_mpb1_l_A": abs(float(d["i(@m.xtop.xxdut.xmpb1_l.msky130_fd_pr__pfet_01v8[id])"])),
        "frontend_mpb1_r_A": abs(float(d["i(@m.xtop.xxdut.xmpb1_r.msky130_fd_pr__pfet_01v8[id])"])),
        "frontend_mnb3_l_A": abs(float(d["i(@m.xtop.xxdut.xmnb3_l.msky130_fd_pr__nfet_01v8[id])"])),
        "frontend_mnb3_r_A": abs(float(d["i(@m.xtop.xxdut.xmnb3_r.msky130_fd_pr__nfet_01v8[id])"])),
        "mont_stack_n_A": abs(float(d["i(@m.xtop.xxdut.xmn23.msky130_fd_pr__nfet_01v8[id])"])),
        "mont_stack_p_A": abs(float(d["i(@m.xtop.xxdut.xmp34.msky130_fd_pr__pfet_01v8[id])"])),
        "mont_n_bridge_A": abs(float(d["i(@m.xtop.xxdut.xm24.msky130_fd_pr__nfet_01v8[id])"])),
        "mont_p_bridge_A": abs(float(d["i(@m.xtop.xxdut.xm35.msky130_fd_pr__pfet_01v8[id])"])),
        "out_n_A": abs(float(d["i(@m.xtop.xxdut.xm1.msky130_fd_pr__nfet_01v8[id])"])),
        "out_p_A": abs(float(d["i(@m.xtop.xxdut.xm2.msky130_fd_pr__pfet_01v8[id])"])),
        "iq_total_A": abs(float(d["i(v.xtop.vvvdd)"])),
    }
    payload["summary"] = {
        "frontend_p_balance": payload["frontend_pinp_l_A"] / max(payload["frontend_pinp_r_A"], 1e-30),
        "frontend_n_balance": payload["frontend_ninp_l_A"] / max(payload["frontend_ninp_r_A"], 1e-30),
        "output_balance": payload["out_p_A"] / max(payload["out_n_A"], 1e-30),
    }
    return payload


class TestV4ProbeCurrentMap(BaseV4SimTest):
    def test_probe_current_map(self) -> None:
        payload = measure_current_map()
        write_metrics_json(METRICS_PATH, payload)

        for key, value in payload.items():
            if key == "summary":
                continue
            self.assertFinite(value, key)
        self.assertGreater(payload["iq_total_A"], 0.0)
        self.assertGreater(payload["mont_stack_n_A"], 0.0)
        self.assertGreater(payload["out_n_A"], 0.0)
