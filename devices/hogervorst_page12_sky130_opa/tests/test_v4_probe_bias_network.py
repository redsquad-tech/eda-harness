from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21 as sky130
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import ResultFormat

from devices.hogervorst_page12_sky130_opa.common import default_ngspice_options, run_ngspice_sim
from devices.hogervorst_page12_sky130_opa.opamp import NeuronOaParams, compile_for_sky130, neuron_core_oa_sky130
from devices.hogervorst_page12_sky130_opa.tests._helpers import BaseV4SimTest, find_signal, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_probe_bias_network_metrics.json")


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


class TestV4ProbeBiasNetwork(BaseV4SimTest):
    def test_probe_bias_network(self) -> None:
        dut = h.elaborate(neuron_core_oa_sky130(NeuronOaParams()))
        compile_for_sky130(dut)
        sim = Sim(tb=_build_tb(dut), attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), sky130.install.include(h.pdk.Corner.TYP)])
        result = run_ngspice_sim(
            sim,
            default_ngspice_options(f"opamp_v4_probe_bias_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
        )
        data = result.an[0].data
        vdd = find_signal(data, exact="v(xtop.avdd)")

        payload = {
            "iq_uA": 1e6 * abs(find_signal(data, exact="i(v.xtop.vvvdd)")),
            "iref_postsw_V": find_signal(data, exact="v(xtop.xxdut.iref_int)"),
            "vbias1_V": find_signal(data, exact="v(xtop.xxdut.vbias1)"),
            "vbias2_V": find_signal(data, exact="v(xtop.xxdut.vbias2)"),
            "vbias3_V": find_signal(data, exact="v(xtop.xxdut.vbias3)"),
            "tail_p_V": find_signal(data, exact="v(xtop.xxdut.tail_p)"),
            "tail_n_V": find_signal(data, exact="v(xtop.xxdut.tail_n)"),
            "vb_m24_V": find_signal(data, exact="v(xtop.xxdut.vb_m24)"),
            "vb_m35_V": find_signal(data, exact="v(xtop.xxdut.vb_m35)"),
            "vgp_V": find_signal(data, exact="v(xtop.xxdut.vgp)"),
            "vgn_V": find_signal(data, exact="v(xtop.xxdut.vgn)"),
            "mont_n_mid_V": find_signal(data, exact="v(xtop.xxdut.xmont.n_mid)"),
            "mont_p_mid_V": find_signal(data, exact="v(xtop.xxdut.xmont.p_mid)"),
            "vout_V": find_signal(data, exact="v(xtop.vout)"),
        }
        payload["derived"] = {
            "gate_spread_V": payload["vgp_V"] - payload["vgn_V"],
            "observable_nodes_within_rails": all(
                0.0 <= payload[key] <= vdd
                for key in [
                    "iref_postsw_V",
                    "vbias1_V",
                    "vbias2_V",
                    "vbias3_V",
                    "tail_p_V",
                    "tail_n_V",
                    "vb_m24_V",
                    "vb_m35_V",
                    "vgp_V",
                    "vgn_V",
                    "vout_V",
                ]
            ),
            "mont_n_separated": abs(payload["vb_m24_V"] - payload["mont_n_mid_V"]) > 1e-3,
            "mont_p_separated": abs(payload["vb_m35_V"] - payload["mont_p_mid_V"]) > 1e-3,
        }
        write_metrics_json(METRICS_PATH, payload)

        self.assertGreater(payload["iq_uA"], 0.0)
        self.assertTrue(payload["derived"]["observable_nodes_within_rails"])
        self.assertTrue(payload["derived"]["mont_n_separated"], f"|vb_m24_V-mont_n_mid_V|={abs(payload['vb_m24_V'] - payload['mont_n_mid_V']):.6g} must be > 1e-3")
        self.assertTrue(payload["derived"]["mont_p_separated"], f"|vb_m35_V-mont_p_mid_V|={abs(payload['vb_m35_V'] - payload['mont_p_mid_V']):.6g} must be > 1e-3")
