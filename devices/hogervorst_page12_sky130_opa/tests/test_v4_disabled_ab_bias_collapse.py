from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21 as sky130
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import ResultFormat

from devices.hogervorst_page12_sky130_opa.common import default_ngspice_options, run_ngspice_sim
from devices.hogervorst_page12_sky130_opa.opamp import NeuronOaParams, compile_for_sky130, neuron_core_oa_sky130
from devices.hogervorst_page12_sky130_opa.tests._helpers import BaseV4SimTest, find_signal, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_disabled_ab_bias_collapse_metrics.json")


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
        vaz = h.Vdc(dc=0.0)(p=d_az_oa, n=VSS)
        ven = h.Vdc(dc=en_v)(p=d_en_oa, n=VSS)
        vinf = h.Vdc(dc=inf_v)(p=d_inf_oa, n=VSS)
        vtreset = h.Vdc(dc=0.0)(p=d_treset_oa, n=VSS)
        vtcki = h.Vdc(dc=0.0)(p=d_tcki, n=VSS)
        vtdi = h.Vdc(dc=0.0)(p=d_tdi, n=VSS)
        iiref = h.Idc(dc=0.25e-6)(p=iref, n=VSS)
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
    sim = Sim(
        tb=_build_tb(dut, en_v=en_v, inf_v=inf_v),
        attrs=[
            Op(),
            Save(
                "v(xtop.avdd), v(xtop.xxdut.vgp), v(xtop.xxdut.vgn), i(v.xtop.vvvdd)"
            ),
            h.sim.Literal(".temp 27"),
            sky130.install.include(h.pdk.Corner.TYP),
        ],
    )
    result = run_ngspice_sim(
        sim,
        default_ngspice_options(f"opamp_v4_abcollapse_{label}_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
    )
    d = result.an[0].data
    avdd = find_signal(d, exact="v(xtop.avdd)")
    return {
        "avdd_V": avdd,
        "vgp_V": find_signal(d, exact="v(xtop.xxdut.vgp)"),
        "vgn_V": find_signal(d, exact="v(xtop.xxdut.vgn)"),
        "iq_uA": 1e6 * abs(find_signal(d, exact="i(v.xtop.vvvdd)")),
    }


class TestV4DisabledAbBiasCollapse(BaseV4SimTest):
    def test_disabled_ab_bias_collapse(self) -> None:
        enabled = _run_case(en_v=1.8, inf_v=1.8, label="enabled")
        disabled = _run_case(en_v=0.0, inf_v=0.0, label="disabled")
        payload = {
            "enabled": enabled,
            "disabled": disabled,
            "summary": {
                "disabled_to_enabled_ratio": disabled["iq_uA"] / max(enabled["iq_uA"], 1e-30),
                "vgp_closer_to_avdd": abs(disabled["avdd_V"] - disabled["vgp_V"]) <= abs(enabled["avdd_V"] - enabled["vgp_V"]),
                "vgn_closer_to_agnd": abs(disabled["vgn_V"]) <= abs(enabled["vgn_V"]),
            },
        }
        write_metrics_json(METRICS_PATH, payload)

        self.assertGreater(enabled["iq_uA"], disabled["iq_uA"])
        self.assertTrue(payload["summary"]["vgp_closer_to_avdd"])
        self.assertTrue(payload["summary"]["vgn_closer_to_agnd"])
