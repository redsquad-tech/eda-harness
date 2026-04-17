from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21 as sky130
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import ResultFormat

from devices.hogervorst_page12_sky130_opa.source.common import default_ngspice_options, run_ngspice_sim
from devices.hogervorst_page12_sky130_opa.opamp import NeuronOaParams, compile_for_sky130, neuron_core_oa_sky130
from devices.hogervorst_page12_sky130_opa.tests._helpers import BaseV4SimTest, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_probe_debug_mux_metrics.json")


def _build_tb(dut, *, treset_v: float, tcki_v: float, tdi_v: float, az_v: float):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, avdd = h.Signals(4)
        iref, vbase, vfeed, vtest = h.Signals(4)
        d_en_oa, d_az_oa, d_inf_oa = h.Signals(3)
        d_treset_oa, d_tcki, d_tcko, d_tdi, d_tdo = h.Signals(5)
        vtest_ref = h.Signal()

        vvdd = h.Vdc(dc=1.8)(p=avdd, n=VSS)
        vvinp = h.Vdc(dc=0.9)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=0.9)(p=vinn_sig, n=VSS)
        ven = h.Vdc(dc=1.8)(p=d_en_oa, n=VSS)
        vaz = h.Vdc(dc=az_v)(p=d_az_oa, n=VSS)
        vinf = h.Vdc(dc=1.8)(p=d_inf_oa, n=VSS)
        vtreset = h.Vdc(dc=treset_v)(p=d_treset_oa, n=VSS)
        vtcki = h.Vdc(dc=tcki_v)(p=d_tcki, n=VSS)
        vtdi = h.Vdc(dc=tdi_v)(p=d_tdi, n=VSS)
        iiref = h.Idc(dc=0.25e-6)(p=iref, n=VSS)

        vvtest_ref = h.Vdc(dc=0.0)(p=vtest_ref, n=VSS)
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


def _run_case(*, treset_v: float, tcki_v: float, tdi_v: float, az_v: float, label: str) -> dict[str, float]:
    dut = h.elaborate(neuron_core_oa_sky130(NeuronOaParams()))
    compile_for_sky130(dut)
    sim = Sim(
        tb=_build_tb(dut, treset_v=treset_v, tcki_v=tcki_v, tdi_v=tdi_v, az_v=az_v),
        attrs=[
            Op(),
            Save(
                "v(xtop.vtest), v(xtop.xxdut.vtest_postsw), v(xtop.xxdut.vout_int), v(xtop.vout), "
                "v(xtop.xxdut.vgn), v(xtop.xxdut.vgp), v(xtop.xxdut.az_hold)"
            ),
            h.sim.Literal(".temp 27"),
            sky130.install.include(h.pdk.Corner.TYP),
        ],
    )
    result = run_ngspice_sim(
        sim,
        default_ngspice_options(f"opamp_v4_probe_dbgmux_{label}_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
    )
    d = result.an[0].data
    return {
        "vtest_V": float(d["v(xtop.vtest)"]),
        "vtest_postsw_V": float(d["v(xtop.xxdut.vtest_postsw)"]),
        "vout_int_V": float(d["v(xtop.xxdut.vout_int)"]),
        "vout_V": float(d["v(xtop.vout)"]),
        "vgn_V": float(d["v(xtop.xxdut.vgn)"]),
        "vgp_V": float(d["v(xtop.xxdut.vgp)"]),
        "az_hold_V": float(d["v(xtop.xxdut.az_hold)"]),
    }


class TestV4ProbeDebugMux(BaseV4SimTest):
    def test_probe_debug_mux(self) -> None:
        mux_vout = _run_case(treset_v=0.0, tcki_v=0.0, tdi_v=1.8, az_v=0.0, label="vout")
        mux_vgn = _run_case(treset_v=0.0, tcki_v=1.8, tdi_v=0.0, az_v=0.0, label="vgn")
        mux_vgp = _run_case(treset_v=1.8, tcki_v=0.0, tdi_v=0.0, az_v=0.0, label="vgp")
        mux_az = _run_case(treset_v=0.0, tcki_v=0.0, tdi_v=0.0, az_v=1.8, label="az")
        payload = {"mux_vout": mux_vout, "mux_vgn": mux_vgn, "mux_vgp": mux_vgp, "mux_az": mux_az}
        payload["summary"] = {
            "vout_err_V": mux_vout["vtest_postsw_V"] - mux_vout["vout_V"],
            "vgn_err_V": mux_vgn["vtest_postsw_V"] - mux_vgn["vgn_V"],
            "vgp_err_V": mux_vgp["vtest_postsw_V"] - mux_vgp["vgp_V"],
            "az_err_V": mux_az["vtest_postsw_V"] - mux_az["az_hold_V"],
        }
        write_metrics_json(METRICS_PATH, payload)

        self.assertLess(abs(payload["summary"]["vout_err_V"]), 0.1)
        self.assertLess(abs(payload["summary"]["vgn_err_V"]), 0.1)
        self.assertLess(abs(payload["summary"]["vgp_err_V"]), 0.1)
        self.assertLess(abs(payload["summary"]["az_err_V"]), 0.1)
