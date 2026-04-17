from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21 as sky130
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import ResultFormat

from devices.hogervorst_page12_sky130_opa.source.common import default_ngspice_options, run_ngspice_sim
from devices.hogervorst_page12_sky130_opa.opamp import NeuronOaParams, compile_for_sky130, neuron_core_oa_sky130
from devices.hogervorst_page12_sky130_opa.tests._helpers import BaseV4SimTest, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_probe_az_hold_metrics.json")


def _build_tb(dut, *, az_v: float):
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
        vaz = h.Vdc(dc=az_v)(p=d_az_oa, n=VSS)
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


def _run_case(*, az_v: float, label: str) -> dict[str, float]:
    dut = h.elaborate(neuron_core_oa_sky130(NeuronOaParams()))
    compile_for_sky130(dut)
    sim = Sim(
        tb=_build_tb(dut, az_v=az_v),
        attrs=[
            Op(),
            Save("v(xtop.xxdut.vgp), v(xtop.xxdut.vgn)"),
            h.sim.Literal(".temp 27"),
            sky130.install.include(h.pdk.Corner.TYP),
        ],
    )
    result = run_ngspice_sim(
        sim,
        default_ngspice_options(f"opamp_v4_probe_azhold_{label}_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
    )
    d = result.an[0].data
    return {
        "vgp_V": float(d["v(xtop.xxdut.vgp)"]),
        "vgn_V": float(d["v(xtop.xxdut.vgn)"]),
    }


class TestV4ProbeAzHold(BaseV4SimTest):
    def test_probe_az_hold(self) -> None:
        inference = _run_case(az_v=0.0, label="inf")
        calibration = _run_case(az_v=1.8, label="cal")
        payload = {"inference": inference, "calibration": calibration}
        payload["summary"] = {
            "inference_gate_diff_V": inference["vgp_V"] - inference["vgn_V"],
            "calibration_gate_diff_V": calibration["vgp_V"] - calibration["vgn_V"],
        }
        write_metrics_json(METRICS_PATH, payload)

        self.assertLess(
            abs(payload["summary"]["calibration_gate_diff_V"]),
            abs(payload["summary"]["inference_gate_diff_V"]),
        )
        self.assertLess(abs(payload["summary"]["calibration_gate_diff_V"]), 0.05)
        self.assertGreaterEqual(inference["vgp_V"], 0.0)
        self.assertLessEqual(inference["vgp_V"], 1.8)
        self.assertGreaterEqual(inference["vgn_V"], 0.0)
        self.assertLessEqual(inference["vgn_V"], 1.8)
