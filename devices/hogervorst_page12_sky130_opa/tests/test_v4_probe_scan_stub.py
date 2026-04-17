from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21 as sky130
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import ResultFormat

from devices.hogervorst_page12_sky130_opa.source.common import default_ngspice_options, run_ngspice_sim
from devices.hogervorst_page12_sky130_opa.opamp import NeuronOaParams, compile_for_sky130, neuron_core_oa_sky130
from devices.hogervorst_page12_sky130_opa.tests._helpers import BaseV4SimTest, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_probe_scan_stub_metrics.json")


def _build_tb(dut, *, tcki_v: float, tdi_v: float, treset_v: float):
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
        vaz = h.Vdc(dc=0.0)(p=d_az_oa, n=VSS)
        vinf = h.Vdc(dc=1.8)(p=d_inf_oa, n=VSS)
        vtreset = h.Vdc(dc=treset_v)(p=d_treset_oa, n=VSS)
        vtcki = h.Vdc(dc=tcki_v)(p=d_tcki, n=VSS)
        vtdi = h.Vdc(dc=tdi_v)(p=d_tdi, n=VSS)
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


def _run_case(*, tcki_v: float, tdi_v: float, treset_v: float, label: str) -> dict[str, float]:
    dut = h.elaborate(neuron_core_oa_sky130(NeuronOaParams()))
    compile_for_sky130(dut)
    sim = Sim(
        tb=_build_tb(dut, tcki_v=tcki_v, tdi_v=tdi_v, treset_v=treset_v),
        attrs=[
            Op(),
            Save("v(xtop.d_tcki), v(xtop.d_tcko), v(xtop.d_tdi), v(xtop.d_tdo), v(xtop.d_treset_oa)"),
            h.sim.Literal(".temp 27"),
            sky130.install.include(h.pdk.Corner.TYP),
        ],
    )
    result = run_ngspice_sim(
        sim,
        default_ngspice_options(f"opamp_v4_probe_scan_{label}_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
    )
    d = result.an[0].data
    return {
        "d_tcki_V": float(d["v(xtop.d_tcki)"]),
        "d_tcko_V": float(d["v(xtop.d_tcko)"]),
        "d_tdi_V": float(d["v(xtop.d_tdi)"]),
        "d_tdo_V": float(d["v(xtop.d_tdo)"]),
        "d_treset_oa_V": float(d["v(xtop.d_treset_oa)"]),
    }


class TestV4ProbeScanStub(BaseV4SimTest):
    def test_probe_scan_stub_passthrough(self) -> None:
        lo = _run_case(tcki_v=0.0, tdi_v=0.0, treset_v=0.0, label="lo")
        hi = _run_case(tcki_v=1.8, tdi_v=1.8, treset_v=1.8, label="hi")
        mixed = _run_case(tcki_v=1.8, tdi_v=0.0, treset_v=0.0, label="mixed")
        payload = {"lo": lo, "hi": hi, "mixed": mixed}
        write_metrics_json(METRICS_PATH, payload)

        self.assertLess(abs(lo["d_tcki_V"] - lo["d_tcko_V"]), 1e-3)
        self.assertLess(abs(lo["d_tdi_V"] - lo["d_tdo_V"]), 1e-3)
        self.assertLess(abs(hi["d_tcki_V"] - hi["d_tcko_V"]), 1e-3)
        self.assertLess(abs(hi["d_tdi_V"] - hi["d_tdo_V"]), 1e-3)
        self.assertLess(abs(mixed["d_tcki_V"] - mixed["d_tcko_V"]), 1e-3)
        self.assertLess(abs(mixed["d_tdi_V"] - mixed["d_tdo_V"]), 1e-3)
