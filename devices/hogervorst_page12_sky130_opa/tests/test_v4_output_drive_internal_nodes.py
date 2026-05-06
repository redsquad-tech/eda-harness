from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21 as sky130
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import ResultFormat

from devices.hogervorst_page12_sky130_opa.common import default_ngspice_options, run_ngspice_sim
from devices.hogervorst_page12_sky130_opa.opamp import NeuronOaParams, compile_for_sky130, neuron_core_oa_sky130
from devices.hogervorst_page12_sky130_opa.tests._helpers import BaseV4SimTest, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_output_drive_internal_nodes_metrics.json")


def _build_tb(*, load_current_uA: float, direction: str):
    if direction not in {"source", "sink"}:
        raise ValueError(f"Unsupported direction: {direction}")
    current_a = abs(load_current_uA) * 1e-6

    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, avdd = h.Signals(4)
        iref, vbase, vfeed, vtest = h.Signals(4)
        d_en_oa, d_az_oa, d_inf_oa = h.Signals(3)
        d_treset_oa, d_tcki, d_tcko, d_tdi, d_tdo = h.Signals(5)

        vvdd = h.Vdc(dc=1.8)(p=avdd, n=VSS)
        vvinp = h.Vdc(dc=0.9)(p=vinp_sig, n=VSS)
        ven = h.Vdc(dc=1.8)(p=d_en_oa, n=VSS)
        vaz = h.Vdc(dc=0.0)(p=d_az_oa, n=VSS)
        vinf = h.Vdc(dc=1.8)(p=d_inf_oa, n=VSS)
        vtreset = h.Vdc(dc=0.0)(p=d_treset_oa, n=VSS)
        vtcki = h.Vdc(dc=0.0)(p=d_tcki, n=VSS)
        vtdi = h.Vdc(dc=0.0)(p=d_tdi, n=VSS)
        iiref = h.Idc(dc=0.25e-6)(p=iref, n=VSS)

        rfb = h.Res(r=1.0)(p=vout, n=vinn_sig)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        rload = h.Res(r=1e9)(p=vout, n=VSS)
        if direction == "source":
            iload = h.Idc(dc=current_a)(p=vout, n=VSS)
        else:
            iload = h.Idc(dc=current_a)(p=avdd, n=vout)

        xdut = neuron_core_oa_sky130(NeuronOaParams())(
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


def _run_case(*, load_current_uA: float, direction: str) -> dict[str, float]:
    dut = h.elaborate(neuron_core_oa_sky130(NeuronOaParams()))
    compile_for_sky130(dut)
    save = [
        "v(xtop.vout)",
        "v(xtop.xxdut.vgp)",
        "v(xtop.xxdut.vgn)",
        "@m.xtop.xxdut.xanalog_core.xm1.msky130_fd_pr__nfet_01v8[id]",
        "@m.xtop.xxdut.xanalog_core.xm2.msky130_fd_pr__pfet_01v8[id]",
        "i(v.xtop.vvvdd)",
    ]
    sim = Sim(
        tb=_build_tb(load_current_uA=load_current_uA, direction=direction),
        attrs=[Op(), Save(", ".join(save)), h.sim.Literal(".temp 27"), sky130.install.include(h.pdk.Corner.TYP)],
    )
    result = run_ngspice_sim(
        sim,
        default_ngspice_options(
            f"opamp_v4_out_nodes_{direction}_{uuid4().hex[:8]}",
            fmt=ResultFormat.SIM_DATA,
        ),
    )
    data = result.an[0].data
    vgp = float(data["v(xtop.xxdut.vgp)"])
    vgn = float(data["v(xtop.xxdut.vgn)"])
    return {
        "load_current_uA": float(load_current_uA),
        "vout_V": float(data["v(xtop.vout)"]),
        "vgp_V": vgp,
        "vgn_V": vgn,
        "gate_span_mV": 1e3 * abs(vgp - vgn),
        "id_out_n_A": float(data["i(@m.xtop.xxdut.xanalog_core.xm1.msky130_fd_pr__nfet_01v8[id])"]),
        "id_out_p_A": float(data["i(@m.xtop.xxdut.xanalog_core.xm2.msky130_fd_pr__pfet_01v8[id])"]),
        "iq_total_A": abs(float(data["i(v.xtop.vvvdd)"])),
    }


def measure_output_drive_internal_nodes() -> dict:
    source = _run_case(load_current_uA=25.0, direction="source")
    sink = _run_case(load_current_uA=25.0, direction="sink")
    summary = {
        "source_gate_span_mV": source["gate_span_mV"],
        "sink_gate_span_mV": sink["gate_span_mV"],
        "source_minus_sink_vout_mV": 1e3 * (source["vout_V"] - sink["vout_V"]),
    }
    return {"source_25uA": source, "sink_25uA": sink, "summary": summary}


class TestV4OutputDriveInternalNodes(BaseV4SimTest):
    def test_output_drive_internal_nodes(self) -> None:
        payload = measure_output_drive_internal_nodes()
        write_metrics_json(METRICS_PATH, payload)

        self.assertGreater(payload["summary"]["source_minus_sink_vout_mV"], 0.0)
