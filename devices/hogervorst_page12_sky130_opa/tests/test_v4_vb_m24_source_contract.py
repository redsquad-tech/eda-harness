from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21 as sky130
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import ResultFormat

from devices.hogervorst_page12_sky130_opa.opamp import NeuronOaParams, compile_for_sky130, neuron_core_oa_sky130
from devices.hogervorst_page12_sky130_opa.source.common import default_ngspice_options, run_ngspice_sim
from devices.hogervorst_page12_sky130_opa.source.measure import run_open_loop_test
from devices.hogervorst_page12_sky130_opa.tests._helpers import BaseV4SimTest, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_vb_m24_source_contract_metrics.json")


def _build_tb(dut):
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


def _probe_local_state(dut_params: NeuronOaParams) -> dict:
    dut = h.elaborate(neuron_core_oa_sky130(dut_params))
    compile_for_sky130(dut)
    op_save = [
        "v(xtop.xxdut.vb_m24)",
        "v(xtop.xxdut.vgn)",
        "v(xtop.xxdut.vgp)",
        "v(xtop.xxdut.vb_m35)",
        "@m.xtop.xxdut.xm23.msky130_fd_pr__nfet_01v8[id]",
        "@m.xtop.xxdut.xm24.msky130_fd_pr__nfet_01v8[id]",
        "@m.xtop.xxdut.xm35.msky130_fd_pr__pfet_01v8[id]",
    ]
    sim = Sim(
        tb=_build_tb(dut),
        attrs=[Op(), Save(", ".join(op_save)), h.sim.Literal(".temp 27"), sky130.install.include(h.pdk.Corner.TYP)],
    )
    result = run_ngspice_sim(
        sim,
        default_ngspice_options(f"opamp_v4_vb_m24_contract_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
    )
    d = result.an[0].data
    vb_m24 = float(d["v(xtop.xxdut.vb_m24)"])
    vgn = float(d["v(xtop.xxdut.vgn)"])
    vgp = float(d["v(xtop.xxdut.vgp)"])
    vb_m35 = float(d["v(xtop.xxdut.vb_m35)"])
    return {
        "vb_m24_V": vb_m24,
        "vgn_V": vgn,
        "vgp_V": vgp,
        "vb_m35_V": vb_m35,
        "vgs23_V": vb_m24 - vgn,
        "vgs24_V": vb_m24 - vgn,
        "id23_A": float(d["i(@m.xtop.xxdut.xm23.msky130_fd_pr__nfet_01v8[id])"]),
        "id24_A": float(d["i(@m.xtop.xxdut.xm24.msky130_fd_pr__nfet_01v8[id])"]),
        "id35_A": float(d["i(@m.xtop.xxdut.xm35.msky130_fd_pr__pfet_01v8[id])"]),
    }


def measure_vb_m24_source_contract() -> dict:
    ideal = NeuronOaParams(use_real_vb_m24_bias=False)
    real = NeuronOaParams(use_real_vb_m24_bias=True)
    cascoded = NeuronOaParams(use_real_vb_m24_bias=True, use_cascoded_vb_m24_bias=True)
    local_vgp = NeuronOaParams(use_real_vb_m24_bias=True, use_local_vgp_vb_m24_bias=True)

    ideal_local = _probe_local_state(ideal)
    real_local = _probe_local_state(real)
    cascoded_local = _probe_local_state(cascoded)
    local_vgp_local = _probe_local_state(local_vgp)
    ideal_open = run_open_loop_test(dut_params=ideal)["metrics"]
    real_open = run_open_loop_test(dut_params=real)["metrics"]
    cascoded_open = run_open_loop_test(dut_params=cascoded)["metrics"]
    local_vgp_open = run_open_loop_test(dut_params=local_vgp)["metrics"]

    payload = {
        "ideal": {
            "local": ideal_local,
            "open_loop": ideal_open,
        },
        "real": {
            "local": real_local,
            "open_loop": real_open,
        },
        "cascoded": {
            "local": cascoded_local,
            "open_loop": cascoded_open,
        },
        "local_vgp": {
            "local": local_vgp_local,
            "open_loop": local_vgp_open,
        },
    }
    payload["delta"] = {
        "vb_m24_shift_V": real_local["vb_m24_V"] - ideal_local["vb_m24_V"],
        "vgn_shift_V": real_local["vgn_V"] - ideal_local["vgn_V"],
        "vgp_shift_V": real_local["vgp_V"] - ideal_local["vgp_V"],
        "aol_shift_dB": float(real_open["aol_db"]) - float(ideal_open["aol_db"]),
        "gbw_shift_Hz": float(real_open["gbw_hz"]) - float(ideal_open["gbw_hz"]),
        "iq_shift_uA": float(real_open["iq_uA"]) - float(ideal_open["iq_uA"]),
        "cascoded_vb_m24_shift_V": cascoded_local["vb_m24_V"] - ideal_local["vb_m24_V"],
        "cascoded_vgn_shift_V": cascoded_local["vgn_V"] - ideal_local["vgn_V"],
        "cascoded_vgp_shift_V": cascoded_local["vgp_V"] - ideal_local["vgp_V"],
        "cascoded_aol_shift_dB": float(cascoded_open["aol_db"]) - float(ideal_open["aol_db"]),
        "cascoded_gbw_shift_Hz": float(cascoded_open["gbw_hz"]) - float(ideal_open["gbw_hz"]),
        "cascoded_iq_shift_uA": float(cascoded_open["iq_uA"]) - float(ideal_open["iq_uA"]),
        "local_vgp_vb_m24_shift_V": local_vgp_local["vb_m24_V"] - ideal_local["vb_m24_V"],
        "local_vgp_vgn_shift_V": local_vgp_local["vgn_V"] - ideal_local["vgn_V"],
        "local_vgp_vgp_shift_V": local_vgp_local["vgp_V"] - ideal_local["vgp_V"],
        "local_vgp_aol_shift_dB": float(local_vgp_open["aol_db"]) - float(ideal_open["aol_db"]),
        "local_vgp_gbw_shift_Hz": float(local_vgp_open["gbw_hz"]) - float(ideal_open["gbw_hz"]),
        "local_vgp_iq_shift_uA": float(local_vgp_open["iq_uA"]) - float(ideal_open["iq_uA"]),
    }
    return payload


class TestV4VbM24SourceContract(BaseV4SimTest):
    def test_vb_m24_replacement_contract(self) -> None:
        payload = measure_vb_m24_source_contract()
        write_metrics_json(METRICS_PATH, payload)

        ideal = payload["ideal"]
        real = payload["real"]
        cascoded = payload["cascoded"]
        local_vgp = payload["local_vgp"]
        delta = payload["delta"]

        self.assertFinite(float(ideal["open_loop"]["aol_db"]))
        self.assertFinite(float(real["open_loop"]["aol_db"]))
        self.assertFinite(float(cascoded["open_loop"]["aol_db"]))
        self.assertFinite(float(local_vgp["open_loop"]["aol_db"]))
        self.assertGreater(ideal["local"]["id23_A"], 0.0)
        self.assertGreater(real["local"]["id23_A"], 0.0)
        self.assertGreater(cascoded["local"]["id23_A"], 0.0)
        self.assertGreater(local_vgp["local"]["id23_A"], 0.0)

        # Contract for a realistic replacement of the ideal vb_m24 source:
        # keep the local operating point close and avoid large top-level degradation.
        self.assertMetricAtMost("vb_m24_shift_abs_V", abs(delta["vb_m24_shift_V"]), 0.05)
        self.assertMetricAtMost("vgn_shift_abs_V", abs(delta["vgn_shift_V"]), 0.05)
        self.assertMetricAtMost("vgp_shift_abs_V", abs(delta["vgp_shift_V"]), 0.05)
        self.assertMetricAtMost("aol_drop_abs_dB", abs(delta["aol_shift_dB"]), 3.0)
        self.assertMetricAtMost("gbw_drop_abs_MHz", abs(delta["gbw_shift_Hz"]) / 1e6, 1.0)
        self.assertMetricAtMost("iq_rise_abs_uA", abs(delta["iq_shift_uA"]), 2.0)
