from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21 as sky130
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import ResultFormat

from opamp.v4.common import default_ngspice_options, run_ngspice_sim
from opamp.v4.opamp import NeuronOaParams, compile_for_sky130, neuron_core_oa_sky130
from opamp.v4.tests._helpers import BaseV4SimTest, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_probe_vtest_isolation_metrics.json")


def _build_tb(dut, *, tdi_v: float, vtest_bias_v: float):
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
        vaz = h.Vdc(dc=0.0)(p=d_az_oa, n=VSS)
        vinf = h.Vdc(dc=1.8)(p=d_inf_oa, n=VSS)
        vtreset = h.Vdc(dc=0.0)(p=d_treset_oa, n=VSS)
        vtcki = h.Vdc(dc=0.0)(p=d_tcki, n=VSS)
        vtdi = h.Vdc(dc=tdi_v)(p=d_tdi, n=VSS)
        iiref = h.Idc(dc=0.25e-6)(p=iref, n=VSS)

        vvtest_ref = h.Vdc(dc=vtest_bias_v)(p=vtest_ref, n=VSS)
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


def _run_case(*, tdi_v: float, vtest_bias_v: float, label: str) -> dict[str, float]:
    dut = h.elaborate(neuron_core_oa_sky130(NeuronOaParams()))
    compile_for_sky130(dut)
    sim = Sim(
        tb=_build_tb(dut, tdi_v=tdi_v, vtest_bias_v=vtest_bias_v),
        attrs=[
            Op(),
            Save("v(xtop.vtest), v(xtop.vout)"),
            h.sim.Literal(".temp 27"),
            sky130.install.include(h.pdk.Corner.TYP),
        ],
    )
    result = run_ngspice_sim(
        sim,
        default_ngspice_options(f"opamp_v4_probe_vtestiso_{label}_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
    )
    d = result.an[0].data
    return {
        "vtest_V": float(d["v(xtop.vtest)"]),
        "vout_V": float(d["v(xtop.vout)"]),
    }


class TestV4ProbeVtestIsolation(BaseV4SimTest):
    def test_probe_vtest_isolation(self) -> None:
        off_low = _run_case(tdi_v=0.0, vtest_bias_v=0.0, label="off_low")
        off_high = _run_case(tdi_v=0.0, vtest_bias_v=1.2, label="off_high")
        on_high = _run_case(tdi_v=1.8, vtest_bias_v=1.2, label="on_high")
        payload = {
            "off_low": off_low,
            "off_high": off_high,
            "on_high": on_high,
            "summary": {
                "off_vout_swing_V": off_high["vout_V"] - off_low["vout_V"],
                "on_link_error_V": on_high["vtest_V"] - on_high["vout_V"],
            },
        }
        write_metrics_json(METRICS_PATH, payload)

        self.assertLess(abs(payload["summary"]["off_vout_swing_V"]), 0.05)
        self.assertLess(abs(payload["summary"]["on_link_error_V"]), 0.1)
        self.assertLess(abs(on_high["vtest_V"] - on_high["vout_V"]), 0.1)
