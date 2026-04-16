from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21 as sky130
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import ResultFormat

from opamp.v4.common import default_ngspice_options, run_ngspice_sim
from opamp.v4.opamp import NeuronOaParams, compile_for_sky130, neuron_core_oa_sky130
from opamp.v4.tests._helpers import BaseV4SimTest, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_probe_monticelli_bias_metrics.json")


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


class TestV4ProbeMonticelliBias(BaseV4SimTest):
    def test_probe_monticelli_bias_relations(self) -> None:
        dut = h.elaborate(neuron_core_oa_sky130(NeuronOaParams()))
        compile_for_sky130(dut)
        op_save = [
            "v(xtop.xxdut.vb_m24)",
            "v(xtop.xxdut.vgn)",
            "v(xtop.xxdut.vgp)",
            "v(xtop.xxdut.vb_m35)",
            "v(xtop.xxdut.xmont.n_mid)",
            "v(xtop.xxdut.xmont.p_mid)",
            "@m.xtop.xxdut.xmont.xmn23.msky130_fd_pr__nfet_01v8[id]",
            "@m.xtop.xxdut.xmont.xm24.msky130_fd_pr__nfet_01v8[id]",
            "@m.xtop.xxdut.xmont.xmp34.msky130_fd_pr__pfet_01v8[id]",
            "@m.xtop.xxdut.xmont.xm35.msky130_fd_pr__pfet_01v8[id]",
        ]
        sim = Sim(
            tb=_build_tb(dut),
            attrs=[Op(), Save(", ".join(op_save)), h.sim.Literal(".temp 27"), sky130.install.include(h.pdk.Corner.TYP)],
        )
        result = run_ngspice_sim(
            sim,
            default_ngspice_options(f"opamp_v4_probe_mont_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
        )
        d = result.an[0].data

        vb_m24 = float(d["v(xtop.xxdut.vb_m24)"])
        vgn = float(d["v(xtop.xxdut.vgn)"])
        vgp = float(d["v(xtop.xxdut.vgp)"])
        vb_m35 = float(d["v(xtop.xxdut.vb_m35)"])
        n_mid = float(d["v(xtop.xxdut.xmont.n_mid)"])
        p_mid = float(d["v(xtop.xxdut.xmont.p_mid)"])

        payload = {
            "vgs22_V": vb_m24 - n_mid,
            "vgs23_V": n_mid,
            "vgs24_V": vb_m24 - vgn,
            "vsg33_V": 1.8 - vgp,
            "vsg34_V": p_mid - vb_m35,
            "vsg35_V": vgp - vb_m35,
            "id23_A": float(d["i(@m.xtop.xxdut.xmont.xmn23.msky130_fd_pr__nfet_01v8[id])"]),
            "id24_A": float(d["i(@m.xtop.xxdut.xmont.xm24.msky130_fd_pr__nfet_01v8[id])"]),
            "id34_A": float(d["i(@m.xtop.xxdut.xmont.xmp34.msky130_fd_pr__pfet_01v8[id])"]),
            "id35_A": float(d["i(@m.xtop.xxdut.xmont.xm35.msky130_fd_pr__pfet_01v8[id])"]),
            "vgn_V": vgn,
            "vgp_V": vgp,
            "vb_m24_V": vb_m24,
            "vb_m35_V": vb_m35,
            "n_mid_V": n_mid,
            "p_mid_V": p_mid,
        }
        payload["derived"] = {
            "nm_stack_order_ok": payload["vb_m24_V"] > payload["n_mid_V"] > 0.0,
            "pm_stack_order_ok": payload["p_mid_V"] > payload["vb_m35_V"] >= 0.0,
            "gates_within_rails": 0.0 <= payload["vgn_V"] <= 1.8 and 0.0 <= payload["vgp_V"] <= 1.8,
        }
        write_metrics_json(METRICS_PATH, payload)

        self.assertFinite(payload["vgs23_V"])
        self.assertFinite(payload["vsg34_V"])
        self.assertTrue(payload["derived"]["nm_stack_order_ok"], f"Expected vb_m24_V={payload['vb_m24_V']:.6g} > n_mid_V={payload['n_mid_V']:.6g} > 0")
        self.assertTrue(payload["derived"]["pm_stack_order_ok"], f"Expected p_mid_V={payload['p_mid_V']:.6g} > vb_m35_V={payload['vb_m35_V']:.6g} >= 0")
        self.assertTrue(payload["derived"]["gates_within_rails"])
