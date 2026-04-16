from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21 as sky130
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import ResultFormat

from opamp.v4.common import default_ngspice_options, run_ngspice_sim
from opamp.v4.opamp import NeuronOaParams, compile_for_sky130, neuron_core_oa_sky130
from opamp.v4.tests._helpers import BaseV4SimTest, find_signal, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_probe_mode_isolation_metrics.json")


def _build_tb(dut, *, en_v: float, az_v: float, inf_v: float, tdi_v: float):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, avdd = h.Signals(4)
        iref, vbase, vfeed, vtest = h.Signals(4)
        d_en_oa, d_az_oa, d_inf_oa = h.Signals(3)
        d_treset_oa, d_tcki, d_tcko, d_tdi, d_tdo = h.Signals(5)
        vbase_ref, vfeed_ref, vtest_ref = h.Signals(3)

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
        vvtest_ref = h.Vdc(dc=0.0)(p=vtest_ref, n=VSS)
        rvbase = h.Res(r=1e6)(p=vbase, n=vbase_ref)
        rvfeed = h.Res(r=1e6)(p=vfeed, n=vfeed_ref)
        rvtest = h.Res(r=1e6)(p=vtest, n=vtest_ref)

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


def _run_case(*, en_v: float, az_v: float, inf_v: float, tdi_v: float, label: str) -> dict[str, float]:
    dut = h.elaborate(neuron_core_oa_sky130(NeuronOaParams()))
    compile_for_sky130(dut)
    sim = Sim(
        tb=_build_tb(dut, en_v=en_v, az_v=az_v, inf_v=inf_v, tdi_v=tdi_v),
        attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), sky130.install.include(h.pdk.Corner.TYP)],
    )
    result = run_ngspice_sim(
        sim,
        default_ngspice_options(f"opamp_v4_mode_{label}_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
    )
    d = result.an[0].data
    return {
        "vout_V": find_signal(d, exact="v(xtop.vout)"),
        "vtest_V": find_signal(d, exact="v(xtop.vtest)"),
        "vbase_V": find_signal(d, exact="v(xtop.vbase)"),
        "vfeed_V": find_signal(d, exact="v(xtop.vfeed)"),
        "iref_postsw_V": find_signal(d, exact="v(xtop.xxdut.iref_int)"),
        "vgp_V": find_signal(d, exact="v(xtop.xxdut.vgp)"),
        "vgn_V": find_signal(d, exact="v(xtop.xxdut.vgn)"),
        "d_en_b_V": find_signal(d, exact="v(xtop.xxdut.d_en_b)"),
        "d_az_b_V": find_signal(d, exact="v(xtop.xxdut.d_az_b)"),
        "d_inf_b_V": find_signal(d, exact="v(xtop.xxdut.d_inf_b)"),
    }


class TestV4ProbeModeIsolation(BaseV4SimTest):
    def test_probe_mode_isolation(self) -> None:
        disabled = _run_case(en_v=0.0, az_v=0.0, inf_v=0.0, tdi_v=0.0, label="disabled")
        inference = _run_case(en_v=1.8, az_v=0.0, inf_v=1.8, tdi_v=0.0, label="inference")
        calibration = _run_case(en_v=1.8, az_v=1.8, inf_v=0.0, tdi_v=0.0, label="calibration")
        testmux_on = _run_case(en_v=1.8, az_v=0.0, inf_v=1.8, tdi_v=1.8, label="testmux_on")

        payload = {
            "disabled": disabled,
            "inference": inference,
            "calibration": calibration,
            "testmux_on": testmux_on,
        }
        write_metrics_json(METRICS_PATH, payload)

        self.assertGreater(disabled["vbase_V"], 0.7)
        self.assertLess(inference["vbase_V"], 0.2)
        self.assertLess(disabled["vfeed_V"], 0.2)
        self.assertGreater(inference["vfeed_V"], 1.5)
        self.assertLess(inference["vtest_V"], 0.1)
        self.assertLess(abs(testmux_on["vtest_V"] - testmux_on["vout_V"]), 0.1)
        self.assertGreaterEqual(calibration["vgp_V"], 0.0)
        self.assertLessEqual(calibration["vgp_V"], 1.8)
        self.assertGreaterEqual(calibration["vgn_V"], 0.0)
        self.assertLessEqual(calibration["vgn_V"], 1.8)
