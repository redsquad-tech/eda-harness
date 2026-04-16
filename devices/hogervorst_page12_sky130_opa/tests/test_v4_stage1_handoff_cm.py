from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21 as sky130
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import ResultFormat

from devices.hogervorst_page12_sky130_opa.common import default_ngspice_options, run_ngspice_sim
from devices.hogervorst_page12_sky130_opa.opamp import NeuronOaParams, compile_for_sky130, neuron_core_oa_sky130
from devices.hogervorst_page12_sky130_opa.tests._helpers import BaseV4SimTest, find_signal, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_stage1_handoff_cm_metrics.json")


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


class TestV4Stage1HandoffCm(BaseV4SimTest):
    def test_stage1_handoff_operating_point(self) -> None:
        dut = h.elaborate(neuron_core_oa_sky130(NeuronOaParams()))
        compile_for_sky130(dut)
        sim = Sim(
            tb=_build_tb(dut),
            attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), sky130.install.include(h.pdk.Corner.TYP)],
        )
        result = run_ngspice_sim(
            sim,
            default_ngspice_options(f"opamp_v4_stage1_handoff_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
        )
        d = result.an[0].data
        vdd = find_signal(d, exact="v(xtop.avdd)")
        payload = {
            "vgp_V": find_signal(d, exact="v(xtop.xxdut.vgp)"),
            "vgn_V": find_signal(d, exact="v(xtop.xxdut.vgn)"),
            "tail_p_V": find_signal(d, exact="v(xtop.xxdut.tail_p)"),
            "tail_n_V": find_signal(d, exact="v(xtop.xxdut.tail_n)"),
            "vb_m24_V": find_signal(d, exact="v(xtop.xxdut.vb_m24)"),
            "vb_m35_V": find_signal(d, exact="v(xtop.xxdut.vb_m35)"),
            "vout_V": find_signal(d, exact="v(xtop.vout)"),
        }
        payload["derived"] = {
            "stage1_cm_V": 0.5 * (payload["vgp_V"] + payload["vgn_V"]),
            "stage1_diff_V": payload["vgp_V"] - payload["vgn_V"],
            "gates_within_rails": 0.0 <= payload["vgp_V"] <= vdd and 0.0 <= payload["vgn_V"] <= vdd,
            "bias_nodes_within_rails": all(0.0 <= payload[key] <= vdd for key in ["tail_p_V", "tail_n_V", "vb_m24_V", "vb_m35_V"]),
        }
        write_metrics_json(METRICS_PATH, payload)

        self.assertFinite(payload["derived"]["stage1_cm_V"])
        self.assertTrue(payload["derived"]["gates_within_rails"])
        self.assertTrue(payload["derived"]["bias_nodes_within_rails"])
        self.assertFinite(payload["vout_V"])
