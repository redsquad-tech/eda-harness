from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21 as sky130
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import ResultFormat

from devices.hogervorst_page12_sky130_opa.common import default_ngspice_options, run_ngspice_sim
from devices.hogervorst_page12_sky130_opa.opamp import NeuronOaParams, compile_for_sky130, neuron_core_oa_sky130
from devices.hogervorst_page12_sky130_opa.tests._helpers import BaseV4SimTest, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_probe_current_replicas_metrics.json")


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
        vvinn = h.Vdc(dc=0.9)(p=vinn_sig, n=VSS)
        ven = h.Vdc(dc=en_v)(p=d_en_oa, n=VSS)
        vaz = h.Vdc(dc=0.0)(p=d_az_oa, n=VSS)
        vinf = h.Vdc(dc=inf_v)(p=d_inf_oa, n=VSS)
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


def _run_case(*, en_v: float, inf_v: float, label: str) -> dict[str, float]:
    dut = h.elaborate(neuron_core_oa_sky130(NeuronOaParams()))
    compile_for_sky130(dut)
    sim = Sim(
        tb=_build_tb(dut, en_v=en_v, inf_v=inf_v),
        attrs=[
            Op(),
            Save(
                "i(v.xtop.xxdut.vis_core_replica), i(v.xtop.xxdut.vis_bias_p_replica), "
                "i(v.xtop.xxdut.vis_bias_n_replica), i(v.xtop.xxdut.vis_out_pq_replica), "
                "i(v.xtop.xxdut.vis_out_nq_replica)"
            ),
            h.sim.Literal(".temp 27"),
            sky130.install.include(h.pdk.Corner.TYP),
        ],
    )
    result = run_ngspice_sim(
        sim,
        default_ngspice_options(f"opamp_v4_probe_replicas_{label}_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
    )
    d = result.an[0].data
    return {
        "is_core_replica_A": abs(float(d["i(v.xtop.xxdut.vis_core_replica)"])),
        "is_bias_p_replica_A": abs(float(d["i(v.xtop.xxdut.vis_bias_p_replica)"])),
        "is_bias_n_replica_A": abs(float(d["i(v.xtop.xxdut.vis_bias_n_replica)"])),
        "is_out_pq_replica_A": abs(float(d["i(v.xtop.xxdut.vis_out_pq_replica)"])),
        "is_out_nq_replica_A": abs(float(d["i(v.xtop.xxdut.vis_out_nq_replica)"])),
    }


class TestV4ProbeCurrentReplicas(BaseV4SimTest):
    def test_probe_current_replicas(self) -> None:
        inference = _run_case(en_v=1.8, inf_v=1.8, label="inf")
        disabled = _run_case(en_v=0.0, inf_v=0.0, label="dis")
        payload = {"inference": inference, "disabled": disabled}
        write_metrics_json(METRICS_PATH, payload)

        for mode in ("inference", "disabled"):
            for key, value in payload[mode].items():
                self.assertFinite(value, f"{mode}:{key}")
                self.assertGreaterEqual(value, 0.0)
        self.assertGreater(inference["is_core_replica_A"], 0.0)
        self.assertGreater(inference["is_bias_n_replica_A"], 0.0)
