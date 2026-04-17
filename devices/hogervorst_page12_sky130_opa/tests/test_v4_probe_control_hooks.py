from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21 as sky130
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import ResultFormat

from devices.hogervorst_page12_sky130_opa.source.common import default_ngspice_options, run_ngspice_sim
from devices.hogervorst_page12_sky130_opa.opamp import NeuronOaParams, compile_for_sky130, neuron_core_oa_sky130
from devices.hogervorst_page12_sky130_opa.tests._helpers import BaseV4SimTest, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_probe_control_hooks_metrics.json")


def _build_tb(dut, *, en_v: float, az_v: float, inf_v: float):
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
        vaz = h.Vdc(dc=az_v)(p=d_az_oa, n=VSS)
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


def _run_case(*, en_v: float, az_v: float, inf_v: float, label: str) -> dict[str, float]:
    dut = h.elaborate(neuron_core_oa_sky130(NeuronOaParams()))
    compile_for_sky130(dut)
    sim = Sim(
        tb=_build_tb(dut, en_v=en_v, az_v=az_v, inf_v=inf_v),
        attrs=[
            Op(),
            Save(
                "v(xtop.xxdut.ref_hiz_ctrl), "
                "v(xtop.xxdut.out_hiz_ctrl_dis), "
                "v(xtop.xxdut.out_hiz_ctrl_inf), "
                "v(xtop.xxdut.az_short_ctrl), "
                "v(xtop.xxdut.mode_latched_en), "
                "v(xtop.xxdut.mode_latched_az), "
                "v(xtop.xxdut.mode_latched_inf), "
                "v(xtop.xxdut.d_en_b), "
                "v(xtop.xxdut.d_az_b), "
                "v(xtop.xxdut.d_inf_b)"
            ),
            h.sim.Literal(".temp 27"),
            sky130.install.include(h.pdk.Corner.TYP),
        ],
    )
    result = run_ngspice_sim(
        sim,
        default_ngspice_options(f"opamp_v4_probe_ctrl_{label}_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
    )
    d = result.an[0].data
    return {
        "ref_hiz_ctrl_V": float(d["v(xtop.xxdut.ref_hiz_ctrl)"]),
        "out_hiz_ctrl_dis_V": float(d["v(xtop.xxdut.out_hiz_ctrl_dis)"]),
        "out_hiz_ctrl_inf_V": float(d["v(xtop.xxdut.out_hiz_ctrl_inf)"]),
        "az_short_ctrl_V": float(d["v(xtop.xxdut.az_short_ctrl)"]),
        "mode_latched_en_V": float(d["v(xtop.xxdut.mode_latched_en)"]),
        "mode_latched_az_V": float(d["v(xtop.xxdut.mode_latched_az)"]),
        "mode_latched_inf_V": float(d["v(xtop.xxdut.mode_latched_inf)"]),
        "d_en_b_V": float(d["v(xtop.xxdut.d_en_b)"]),
        "d_az_b_V": float(d["v(xtop.xxdut.d_az_b)"]),
        "d_inf_b_V": float(d["v(xtop.xxdut.d_inf_b)"]),
    }


class TestV4ProbeControlHooks(BaseV4SimTest):
    def test_probe_control_hooks(self) -> None:
        disabled = _run_case(en_v=0.0, az_v=0.0, inf_v=0.0, label="disabled")
        inference = _run_case(en_v=1.8, az_v=0.0, inf_v=1.8, label="inference")
        calibration = _run_case(en_v=1.8, az_v=1.8, inf_v=0.0, label="calibration")
        payload = {"disabled": disabled, "inference": inference, "calibration": calibration}
        write_metrics_json(METRICS_PATH, payload)

        self.assertGreater(disabled["ref_hiz_ctrl_V"], 1.7)
        self.assertLess(inference["ref_hiz_ctrl_V"], 0.1)
        self.assertGreater(disabled["out_hiz_ctrl_dis_V"], 1.7)
        self.assertLess(inference["out_hiz_ctrl_dis_V"], 0.1)
        self.assertGreater(calibration["out_hiz_ctrl_inf_V"], 1.7)
        self.assertLess(inference["out_hiz_ctrl_inf_V"], 0.1)
        self.assertLess(inference["az_short_ctrl_V"], 0.1)
        self.assertGreater(calibration["az_short_ctrl_V"], 1.7)
        self.assertLess(abs(inference["mode_latched_en_V"] - 1.8), 1e-2)
        self.assertLess(abs(calibration["mode_latched_az_V"] - 1.8), 1e-2)
        self.assertLess(abs(inference["mode_latched_inf_V"] - 1.8), 1e-2)
