from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21 as sky130
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import ResultFormat

from opamp.v4.common import default_ngspice_options, run_ngspice_sim
from opamp.v4.opamp import NeuronOaParams, compile_for_sky130, neuron_core_oa_sky130
from opamp.v4.tests._helpers import BaseV4SimTest, find_signal, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_probe_stage1_nodes_metrics.json")


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


class TestV4ProbeStage1Nodes(BaseV4SimTest):
    def test_probe_stage1_nodes(self) -> None:
        dut = h.elaborate(neuron_core_oa_sky130(NeuronOaParams()))
        compile_for_sky130(dut)
        sim = Sim(tb=_build_tb(dut), attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), sky130.install.include(h.pdk.Corner.TYP)])
        result = run_ngspice_sim(
            sim,
            default_ngspice_options(f"opamp_v4_probe_stage1_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
        )
        data = result.an[0].data
        vdd = find_signal(data, exact="v(xtop.avdd)")

        payload = {
            "tail_p_V": find_signal(data, exact="v(xtop.xxdut.tail_p)"),
            "tail_n_V": find_signal(data, exact="v(xtop.xxdut.tail_n)"),
            "vb_m24_V": find_signal(data, exact="v(xtop.xxdut.vb_m24)"),
            "vb_m35_V": find_signal(data, exact="v(xtop.xxdut.vb_m35)"),
            "vgp_V": find_signal(data, exact="v(xtop.xxdut.vgp)"),
            "vgn_V": find_signal(data, exact="v(xtop.xxdut.vgn)"),
            "pnode_l_V": find_signal(data, exact="v(xtop.xxdut.xfrontend.pnode_l)"),
            "pnode_r_V": find_signal(data, exact="v(xtop.xxdut.xfrontend.pnode_r)"),
            "nnode_l_V": find_signal(data, exact="v(xtop.xxdut.xfrontend.nnode_l)"),
            "nnode_r_V": find_signal(data, exact="v(xtop.xxdut.xfrontend.nnode_r)"),
            "vref_mid_V": find_signal(data, exact="v(xtop.xxdut.xfrontend.vref_mid)"),
        }
        payload["derived"] = {
            "stage1_cm_V": 0.5 * (payload["vgp_V"] + payload["vgn_V"]),
            "stage1_diff_V": payload["vgp_V"] - payload["vgn_V"],
            "outputs_within_rails": all(0.0 <= payload[key] <= vdd for key in ["vgp_V", "vgn_V", "vb_m24_V", "vb_m35_V"]),
            "internal_nodes_finite": all(abs(payload[key]) < 10.0 for key in payload if key.endswith("_V")),
            "outputs_resolved": abs(payload["vgp_V"] - payload["vgn_V"]) > 1e-6,
        }
        write_metrics_json(METRICS_PATH, payload)

        self.assertTrue(payload["derived"]["outputs_within_rails"])
        self.assertTrue(payload["derived"]["internal_nodes_finite"])
        self.assertGreater(payload["tail_p_V"], payload["tail_n_V"])
        self.assertTrue(payload["derived"]["outputs_resolved"], f"stage1_diff_V={payload['derived']['stage1_diff_V']:.6g} must resolve above 1e-6 V")
