from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21 as sky130
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import ResultFormat

from opamp.v4.common import default_ngspice_options, run_ngspice_sim
from opamp.v4.opamp import NeuronOaParams, compile_for_sky130, neuron_core_oa_sky130
from opamp.v4.tests._helpers import BaseV4SimTest, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_probe_reference_gating_metrics.json")


def _build_tb(dut, *, en_v: float, iref_force_v: float):
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
        vinf = h.Vdc(dc=1.8)(p=d_inf_oa, n=VSS)
        vtreset = h.Vdc(dc=0.0)(p=d_treset_oa, n=VSS)
        vtcki = h.Vdc(dc=0.0)(p=d_tcki, n=VSS)
        vtdi = h.Vdc(dc=0.0)(p=d_tdi, n=VSS)
        viref = h.Vdc(dc=iref_force_v)(p=iref, n=VSS)

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


def _run_case(*, en_v: float, iref_force_v: float, label: str) -> dict[str, float]:
    dut = h.elaborate(neuron_core_oa_sky130(NeuronOaParams()))
    compile_for_sky130(dut)
    sim = Sim(
        tb=_build_tb(dut, en_v=en_v, iref_force_v=iref_force_v),
        attrs=[Op(), Save("v(xtop.iref), v(xtop.xxdut.iref_int), v(xtop.xxdut.d_en_b)"), h.sim.Literal(".temp 27"), sky130.install.include(h.pdk.Corner.TYP)],
    )
    result = run_ngspice_sim(
        sim,
        default_ngspice_options(f"opamp_v4_probe_iref_{label}_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
    )
    d = result.an[0].data
    return {
        "iref_ext_V": float(d["v(xtop.iref)"]),
        "iref_postsw_V": float(d["v(xtop.xxdut.iref_int)"]),
        "d_en_b_V": float(d["v(xtop.xxdut.d_en_b)"]),
    }


class TestV4ProbeReferenceGating(BaseV4SimTest):
    def test_probe_reference_gating_sensitivity(self) -> None:
        enabled_lo = _run_case(en_v=1.8, iref_force_v=0.2, label="en_lo")
        enabled_hi = _run_case(en_v=1.8, iref_force_v=1.0, label="en_hi")
        disabled_lo = _run_case(en_v=0.0, iref_force_v=0.2, label="dis_lo")
        disabled_hi = _run_case(en_v=0.0, iref_force_v=1.0, label="dis_hi")

        payload = {
            "enabled_lo": enabled_lo,
            "enabled_hi": enabled_hi,
            "disabled_lo": disabled_lo,
            "disabled_hi": disabled_hi,
            "summary": {
                "enabled_swing_V": enabled_hi["iref_postsw_V"] - enabled_lo["iref_postsw_V"],
                "disabled_swing_V": disabled_hi["iref_postsw_V"] - disabled_lo["iref_postsw_V"],
            },
        }
        write_metrics_json(METRICS_PATH, payload)

        self.assertLess(enabled_lo["d_en_b_V"], 0.1)
        self.assertGreater(disabled_lo["d_en_b_V"], 1.7)
        self.assertGreater(abs(payload["summary"]["enabled_swing_V"]), abs(payload["summary"]["disabled_swing_V"]))

