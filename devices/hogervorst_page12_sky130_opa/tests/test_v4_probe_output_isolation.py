from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21 as sky130
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import ResultFormat

from devices.hogervorst_page12_sky130_opa.source.common import default_ngspice_options, run_ngspice_sim
from devices.hogervorst_page12_sky130_opa.opamp import NeuronOaParams, compile_for_sky130, neuron_core_oa_sky130
from devices.hogervorst_page12_sky130_opa.tests._helpers import BaseV4SimTest, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_probe_output_isolation_metrics.json")


def _build_tb(dut, *, en_v: float, inf_v: float, vout_force_v: float):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, avdd = h.Signals(4)
        iref, vbase, vfeed, vtest, vout_force = h.Signals(5)
        d_en_oa, d_az_oa, d_inf_oa = h.Signals(3)
        d_treset_oa, d_tcki, d_tcko, d_tdi, d_tdo = h.Signals(5)

        vvdd = h.Vdc(dc=1.8)(p=avdd, n=VSS)
        vvinp = h.Vdc(dc=0.9)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=0.9)(p=vinn_sig, n=VSS)
        ven = h.Vdc(dc=en_v)(p=d_en_oa, n=VSS)
        vaz = h.Vdc(dc=0.0)(p=d_az_oa, n=VSS)
        vinf = h.Vdc(dc=inf_v)(p=d_inf_oa, n=VSS)
        vtreset = h.Vdc(dc=0.0)(p=d_treset_oa, n=VSS)
        vtcki = h.Vdc(dc=0.0)(p=d_tcki, n=VSS)
        vtdi = h.Vdc(dc=0.0)(p=d_tdi, n=VSS)
        iiref = h.Idc(dc=0.25e-6)(p=iref, n=VSS)
        vvout_force = h.Vdc(dc=vout_force_v)(p=vout_force, n=VSS)
        rout_force = h.Res(r=1e5)(p=vout_force, n=vout)
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


def _run_case(*, en_v: float, inf_v: float, vout_force_v: float, label: str) -> dict[str, float]:
    dut = h.elaborate(neuron_core_oa_sky130(NeuronOaParams()))
    compile_for_sky130(dut)
    sim = Sim(
        tb=_build_tb(dut, en_v=en_v, inf_v=inf_v, vout_force_v=vout_force_v),
        attrs=[Op(), Save("v(xtop.vout), v(xtop.xxdut.vout_int)"), h.sim.Literal(".temp 27"), sky130.install.include(h.pdk.Corner.TYP)],
    )
    result = run_ngspice_sim(
        sim,
        default_ngspice_options(f"opamp_v4_probe_outiso_{label}_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
    )
    d = result.an[0].data
    return {
        "vout_V": float(d["v(xtop.vout)"]),
        "vout_int_V": float(d["v(xtop.xxdut.vout_int)"]),
    }


class TestV4ProbeOutputIsolation(BaseV4SimTest):
    def test_probe_output_isolation_hiz(self) -> None:
        disabled = _run_case(en_v=0.0, inf_v=0.0, vout_force_v=0.6, label="disabled")
        inference = _run_case(en_v=1.8, inf_v=1.8, vout_force_v=0.6, label="inference")
        payload = {"disabled": disabled, "inference": inference}
        payload["summary"] = {
            "disabled_delta_V": disabled["vout_V"] - disabled["vout_int_V"],
            "inference_delta_V": inference["vout_V"] - inference["vout_int_V"],
        }
        write_metrics_json(METRICS_PATH, payload)

        self.assertGreater(abs(payload["summary"]["disabled_delta_V"]), 0.1)
        self.assertLess(abs(payload["summary"]["inference_delta_V"]), 0.05)
