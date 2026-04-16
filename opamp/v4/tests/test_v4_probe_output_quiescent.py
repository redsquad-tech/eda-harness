from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21 as sky130
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import ResultFormat

from opamp.v4.common import default_ngspice_options, run_ngspice_sim
from opamp.v4.opamp import NeuronOaParams, compile_for_sky130, neuron_core_oa_sky130
from opamp.v4.tests._helpers import BaseV4SimTest, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_probe_output_quiescent_metrics.json")


def _build_tb(dut, *, en_v: float, inf_v: float):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, avdd = h.Signals(4)
        iref, vbase, vfeed, vtest = h.Signals(4)
        d_en_oa, d_az_oa, d_inf_oa = h.Signals(3)
        d_treset_oa, d_tcki, d_tcko, d_tdi, d_tdo = h.Signals(5)

        vvdd = h.Vdc(dc=1.8)(p=avdd, n=VSS)
        vvinp = h.Vdc(dc=0.9)(p=vinp_sig, n=VSS)
        ven = h.Vdc(dc=en_v)(p=d_en_oa, n=VSS)
        vaz = h.Vdc(dc=0.0)(p=d_az_oa, n=VSS)
        vinf = h.Vdc(dc=inf_v)(p=d_inf_oa, n=VSS)
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


def _run_case(*, en_v: float, inf_v: float, label: str) -> dict[str, float]:
    dut = h.elaborate(neuron_core_oa_sky130(NeuronOaParams()))
    compile_for_sky130(dut)
    op_save = [
        "v(xtop.avdd)",
        "v(xtop.xxdut.vgp)",
        "v(xtop.xxdut.vgn)",
        "v(xtop.vout)",
        "@m.xtop.xxdut.xoutput_stage.xm1.msky130_fd_pr__nfet_01v8[id]",
        "@m.xtop.xxdut.xoutput_stage.xm2.msky130_fd_pr__pfet_01v8[id]",
        "i(v.xtop.vvvdd)",
    ]
    sim = Sim(
        tb=_build_tb(dut, en_v=en_v, inf_v=inf_v),
        attrs=[Op(), Save(", ".join(op_save)), h.sim.Literal(".temp 27"), sky130.install.include(h.pdk.Corner.TYP)],
    )
    result = run_ngspice_sim(
        sim,
        default_ngspice_options(f"opamp_v4_probe_outq_{label}_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
    )
    d = result.an[0].data
    avdd = float(d["v(xtop.avdd)"])
    return {
        "avdd_V": avdd,
        "vgp_V": float(d["v(xtop.xxdut.vgp)"]),
        "vgn_V": float(d["v(xtop.xxdut.vgn)"]),
        "vout_V": float(d["v(xtop.vout)"]),
        "id_out_n_A": float(d["i(@m.xtop.xxdut.xoutput_stage.xm1.msky130_fd_pr__nfet_01v8[id])"]),
        "id_out_p_A": float(d["i(@m.xtop.xxdut.xoutput_stage.xm2.msky130_fd_pr__pfet_01v8[id])"]),
        "iq_total_A": abs(float(d["i(v.xtop.vvvdd)"])),
    }


class TestV4ProbeOutputQuiescent(BaseV4SimTest):
    def test_probe_output_quiescent_currents(self) -> None:
        inference = _run_case(en_v=1.8, inf_v=1.8, label="inf")
        disabled = _run_case(en_v=0.0, inf_v=0.0, label="dis")
        payload = {"inference": inference, "disabled": disabled}
        payload["summary"] = {
            "inference_balance_ratio": abs(inference["id_out_p_A"]) / max(abs(inference["id_out_n_A"]), 1e-30),
            "disabled_current_ratio": abs(disabled["iq_total_A"]) / max(abs(inference["iq_total_A"]), 1e-30),
            "gates_within_rails": 0.0 <= inference["vgn_V"] <= inference["avdd_V"] and 0.0 <= inference["vgp_V"] <= inference["avdd_V"],
            "vout_within_rails": 0.0 <= inference["vout_V"] <= inference["avdd_V"],
        }
        write_metrics_json(METRICS_PATH, payload)

        self.assertTrue(payload["summary"]["gates_within_rails"])
        self.assertTrue(payload["summary"]["vout_within_rails"])
        self.assertGreater(abs(inference["id_out_p_A"]), 0.0)
        self.assertGreater(abs(inference["id_out_n_A"]), 0.0)
        self.assertLess(payload["summary"]["inference_balance_ratio"], 10.0)
