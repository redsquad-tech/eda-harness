from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21 as sky130
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import ResultFormat

from devices.hogervorst_page12_sky130_opa.source.common import default_ngspice_options, run_ngspice_sim
from devices.hogervorst_page12_sky130_opa.opamp import NeuronOaParams, compile_for_sky130, neuron_core_oa_sky130
from devices.hogervorst_page12_sky130_opa.tests._helpers import BaseV4SimTest, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_probe_internal_taps_metrics.json")


def _build_tb(dut, *, inf_v: float, tdi_v: float):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, avdd = h.Signals(4)
        iref, vbase, vfeed, vtest = h.Signals(4)
        d_en_oa, d_az_oa, d_inf_oa = h.Signals(3)
        d_treset_oa, d_tcki, d_tcko, d_tdi, d_tdo = h.Signals(5)
        vbase_ref, vfeed_ref = h.Signals(2)

        vvdd = h.Vdc(dc=1.8)(p=avdd, n=VSS)
        vvinp = h.Vdc(dc=0.9)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=0.9)(p=vinn_sig, n=VSS)
        ven = h.Vdc(dc=1.8)(p=d_en_oa, n=VSS)
        vaz = h.Vdc(dc=0.0)(p=d_az_oa, n=VSS)
        vinf = h.Vdc(dc=inf_v)(p=d_inf_oa, n=VSS)
        vtreset = h.Vdc(dc=0.0)(p=d_treset_oa, n=VSS)
        vtcki = h.Vdc(dc=0.0)(p=d_tcki, n=VSS)
        vtdi = h.Vdc(dc=tdi_v)(p=d_tdi, n=VSS)
        iiref = h.Idc(dc=0.25e-6)(p=iref, n=VSS)
        vvbase_ref = h.Vdc(dc=0.9)(p=vbase_ref, n=VSS)
        vvfeed_ref = h.Vdc(dc=0.0)(p=vfeed_ref, n=VSS)
        rvbase = h.Res(r=1e6)(p=vbase, n=vbase_ref)
        rvfeed = h.Res(r=1e6)(p=vfeed, n=vfeed_ref)
        rvtest = h.Res(r=1e6)(p=vtest, n=VSS)
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


def _run_case(*, inf_v: float, tdi_v: float, label: str) -> dict[str, float]:
    dut = h.elaborate(neuron_core_oa_sky130(NeuronOaParams()))
    compile_for_sky130(dut)
    sim = Sim(
        tb=_build_tb(dut, inf_v=inf_v, tdi_v=tdi_v),
        attrs=[Op(), Save("v(xtop.vbase), v(xtop.xxdut.vbase_int), v(xtop.vfeed), v(xtop.xxdut.vfeed_int), v(xtop.vtest), v(xtop.xxdut.vtest_postsw), v(xtop.xxdut.vout_int)"), h.sim.Literal(".temp 27"), sky130.install.include(h.pdk.Corner.TYP)],
    )
    result = run_ngspice_sim(
        sim,
        default_ngspice_options(f"opamp_v4_probe_taps_{label}_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
    )
    d = result.an[0].data
    return {
        "vbase_V": float(d["v(xtop.vbase)"]),
        "vbase_int_V": float(d["v(xtop.xxdut.vbase_int)"]),
        "vfeed_V": float(d["v(xtop.vfeed)"]),
        "vfeed_int_V": float(d["v(xtop.xxdut.vfeed_int)"]),
        "vtest_V": float(d["v(xtop.vtest)"]),
        "vtest_postsw_V": float(d["v(xtop.xxdut.vtest_postsw)"]),
        "vout_int_V": float(d["v(xtop.xxdut.vout_int)"]),
    }


class TestV4ProbeInternalTaps(BaseV4SimTest):
    def test_probe_internal_taps(self) -> None:
        off = _run_case(inf_v=1.8, tdi_v=0.0, label="off")
        on = _run_case(inf_v=1.8, tdi_v=1.8, label="on")
        payload = {"off": off, "on": on}
        payload["summary"] = {
            "vbase_tap_error_V": off["vbase_V"] - off["vbase_int_V"],
            "vfeed_tap_error_V": off["vfeed_V"] - off["vfeed_int_V"],
            "vtest_link_error_V": on["vtest_V"] - on["vtest_postsw_V"],
            "vtest_to_vout_error_V": on["vtest_postsw_V"] - on["vout_int_V"],
        }
        write_metrics_json(METRICS_PATH, payload)

        self.assertLess(abs(payload["summary"]["vbase_tap_error_V"]), 1e-2)
        self.assertLess(abs(payload["summary"]["vfeed_tap_error_V"]), 1e-2)
        self.assertLess(abs(payload["summary"]["vtest_link_error_V"]), 1e-2)
        self.assertLess(abs(payload["summary"]["vtest_to_vout_error_V"]), 0.1)

