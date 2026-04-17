from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21 as sky130
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import ResultFormat

from devices.hogervorst_page12_sky130_opa.source.common import default_ngspice_options, run_ngspice_sim
from devices.hogervorst_page12_sky130_opa.opamp import NeuronOaParams, compile_for_sky130, neuron_core_oa_sky130
from devices.hogervorst_page12_sky130_opa.tests._helpers import BaseV4SimTest, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_probe_mode_matrix_metrics.json")


def _build_tb(dut, *, en_v: float, az_v: float, inf_v: float, tdi_v: float):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, avdd = h.Signals(4)
        iref, vbase, vfeed, vtest = h.Signals(4)
        d_en_oa, d_az_oa, d_inf_oa = h.Signals(3)
        d_treset_oa, d_tcki, d_tcko, d_tdi, d_tdo = h.Signals(5)
        vbase_ref, vfeed_ref, vtest_ref, vout_ref = h.Signals(4)

        vvdd = h.Vdc(dc=1.8)(p=avdd, n=VSS)
        vvinp = h.Vdc(dc=0.9)(p=vinp_sig, n=VSS)
        ven = h.Vdc(dc=en_v)(p=d_en_oa, n=VSS)
        vaz = h.Vdc(dc=az_v)(p=d_az_oa, n=VSS)
        vinf = h.Vdc(dc=inf_v)(p=d_inf_oa, n=VSS)
        vtreset = h.Vdc(dc=0.0)(p=d_treset_oa, n=VSS)
        vtcki = h.Vdc(dc=0.0)(p=d_tcki, n=VSS)
        vtdi = h.Vdc(dc=tdi_v)(p=d_tdi, n=VSS)
        iiref = h.Idc(dc=0.25e-6)(p=iref, n=VSS)

        vvbase_ref = h.Vdc(dc=0.9)(p=vbase_ref, n=VSS)
        vvfeed_ref = h.Vdc(dc=0.0)(p=vfeed_ref, n=VSS)
        vvtest_ref = h.Vdc(dc=0.15)(p=vtest_ref, n=VSS)
        vvout_ref = h.Vdc(dc=0.2)(p=vout_ref, n=VSS)
        rvbase = h.Res(r=1e6)(p=vbase, n=vbase_ref)
        rvfeed = h.Res(r=1e6)(p=vfeed, n=vfeed_ref)
        rvtest = h.Res(r=1e6)(p=vtest, n=vtest_ref)
        rvout = h.Res(r=1e6)(p=vout, n=vout_ref)
        rfb = h.Res(r=1.0)(p=vout, n=vinn_sig)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)

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


def _run_case(*, en_v: float, az_v: float, inf_v: float, tdi_v: float, label: str) -> dict[str, float]:
    dut = h.elaborate(neuron_core_oa_sky130(NeuronOaParams()))
    compile_for_sky130(dut)
    sim = Sim(
        tb=_build_tb(dut, en_v=en_v, az_v=az_v, inf_v=inf_v, tdi_v=tdi_v),
        attrs=[
            Op(),
            Save("v(xtop.vout), v(xtop.vtest), v(xtop.vbase), v(xtop.vfeed)"),
            h.sim.Literal(".temp 27"),
            sky130.install.include(h.pdk.Corner.TYP),
        ],
    )
    result = run_ngspice_sim(
        sim,
        default_ngspice_options(f"opamp_v4_probe_matrix_{label}_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
    )
    d = result.an[0].data
    return {
        "vout_V": float(d["v(xtop.vout)"]),
        "vtest_V": float(d["v(xtop.vtest)"]),
        "vbase_V": float(d["v(xtop.vbase)"]),
        "vfeed_V": float(d["v(xtop.vfeed)"]),
    }


class TestV4ProbeModeMatrix(BaseV4SimTest):
    def test_probe_mode_matrix(self) -> None:
        disabled = _run_case(en_v=0.0, az_v=0.0, inf_v=0.0, tdi_v=0.0, label="disabled")
        latching = _run_case(en_v=1.8, az_v=0.0, inf_v=0.0, tdi_v=0.0, label="latching")
        calibration = _run_case(en_v=1.8, az_v=1.8, inf_v=0.0, tdi_v=0.0, label="calibration")
        inference = _run_case(en_v=1.8, az_v=0.0, inf_v=1.8, tdi_v=0.0, label="inference")
        payload = {
            "disabled": disabled,
            "latching": latching,
            "calibration": calibration,
            "inference": inference,
            "summary": {},
        }
        write_metrics_json(METRICS_PATH, payload)

        self.assertGreater(disabled["vbase_V"], 0.7)
        self.assertGreater(latching["vbase_V"], 0.7)
        self.assertGreater(calibration["vbase_V"], 0.7)
        self.assertLess(inference["vbase_V"], 0.2)
        self.assertLess(disabled["vfeed_V"], 0.2)
        self.assertLess(latching["vfeed_V"], 0.2)
        self.assertLess(calibration["vfeed_V"], 0.2)
        self.assertGreater(inference["vfeed_V"], 1.5)
