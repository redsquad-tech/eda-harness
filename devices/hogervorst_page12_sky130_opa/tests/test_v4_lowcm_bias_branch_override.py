from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21 as sky130
from hdl21.sim import Ac, LogSweep, Op, Save, Sim
from vlsirtools.spice import ResultFormat

from devices.hogervorst_page12_sky130_opa.common import default_ngspice_options, run_ngspice_sim
from devices.hogervorst_page12_sky130_opa.opamp import NeuronOaParams, Page12CoreParams, compile_for_sky130, page12_analog_core
from devices.hogervorst_page12_sky130_opa.opa_bias import OpaBiasGen
from devices.hogervorst_page12_sky130_opa.tests._helpers import BaseV4SimTest, write_metrics_json
from devices.hogervorst_page12_sky130_opa.tests.test_v4_lowcm_bias_path_compare import _derive_ac_metrics


METRICS_PATH = Path(__file__).with_name("v4_lowcm_bias_branch_override_metrics.json")
VIN_POINTS = (0.0, 0.1)
OVERRIDES = ("i0_p", "i0_n", "ibias_p", "ibias_n")


def _build_tb(params: NeuronOaParams, vin_v: float, override: str, *, ac: bool = False):
    core = page12_analog_core(Page12CoreParams(frontend=params.frontend, monticelli=params.monticelli, output=params.output))
    bias = OpaBiasGen(params.bias)

    @h.module
    class Tb:
        VSS = h.Port()
        avdd, vinp_sig, vinn_sig, vout, iref = h.Signals(5)
        tail_p, tail_n = h.Signals(2)
        vbias1, vbias2, vbias3 = h.Signals(3)
        m24_gate_mid, m35_gate_mid = h.Signals(2)
        pnode_l, pnode_r, nnode_l, nnode_r = h.Signals(4)
        vref_mid, vgp, vgn = h.Signals(3)
        i0_p_real, i0_n_real, ibias_p_real, ibias_n_real = h.Signals(4)

        vvdd = h.Vdc(dc=1.8)(p=avdd, n=VSS)
        if ac:
            vvinp = h.Vdc(dc=vin_v, ac=1.0)(p=vinp_sig, n=VSS)
        else:
            vvinp = h.Vdc(dc=vin_v)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=vin_v)(p=vinn_sig, n=VSS)
        iiref = h.Idc(dc=0.25e-6)(p=iref, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinn_sig)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        rload = h.Res(r=1e9)(p=vout, n=VSS)

        xbias = bias(
            avdd=avdd,
            agnd=VSS,
            iref=iref,
            i0_p=i0_p_real,
            i0_n=i0_n_real,
            ibias_p=ibias_p_real,
            ibias_n=ibias_n_real,
            vbias1=vbias1,
            vbias2=vbias2,
            vbias3=vbias3,
        )

        # Default: connect real bias outputs to core.
        ri0p = h.Res(r=1e-3)(p=i0_p_real, n=tail_p)
        ri0n = h.Res(r=1e-3)(p=i0_n_real, n=tail_n)
        ribp = h.Res(r=1e-3)(p=ibias_p_real, n=m24_gate_mid)
        ribn = h.Res(r=1e-3)(p=ibias_n_real, n=m35_gate_mid)

        # Dummy landing resistors for disconnected outputs.
        rd_i0p = h.Res(r=100_000)(p=i0_p_real, n=VSS)
        rd_i0n = h.Res(r=100_000)(p=i0_n_real, n=avdd)
        rd_ibp = h.Res(r=100_000)(p=ibias_p_real, n=VSS)
        rd_ibn = h.Res(r=100_000)(p=ibias_n_real, n=avdd)

        if override == "i0_p":
            ri0p = h.Res(r=1e12)(p=i0_p_real, n=tail_p)
            itailp = h.Idc(dc=1.6e-6)(p=avdd, n=tail_p)
        elif override == "i0_n":
            ri0n = h.Res(r=1e12)(p=i0_n_real, n=tail_n)
            itailn = h.Idc(dc=1.6e-6)(p=tail_n, n=VSS)
        elif override == "ibias_p":
            ribp = h.Res(r=1e12)(p=ibias_p_real, n=m24_gate_mid)
            iibp = h.Idc(dc=0.45e-6)(p=avdd, n=m24_gate_mid)
        elif override == "ibias_n":
            ribn = h.Res(r=1e12)(p=ibias_n_real, n=m35_gate_mid)
            iibn = h.Idc(dc=0.45e-6)(p=m35_gate_mid, n=VSS)
        else:
            raise ValueError(override)

        xcore = core(
            vinp=vinp_sig,
            vinn=vinn_sig,
            avdd=avdd,
            agnd=VSS,
            vout=vout,
            tail_p=tail_p,
            tail_n=tail_n,
            vbias1=vbias1,
            vbias2=vbias2,
            vbias3=vbias3,
            m24_gate_mid=m24_gate_mid,
            m35_gate_mid=m35_gate_mid,
            pnode_l=pnode_l,
            pnode_r=pnode_r,
            nnode_l=nnode_l,
            nnode_r=nnode_r,
            vref_mid=vref_mid,
            vgp=vgp,
            vgn=vgn,
        )

    return Tb


def _run_op(params: NeuronOaParams, vin_v: float, override: str):
    tb = h.elaborate(_build_tb(params, vin_v, override, ac=False))
    compile_for_sky130(tb)
    save_expr = ", ".join(
        [
            "all",
            "@m.xtop.xbias.xmp_i0_p_out.msky130_fd_pr__pfet_01v8[id]",
            "@m.xtop.xbias.xmn_i0_n_out.msky130_fd_pr__nfet_01v8[id]",
            "@m.xtop.xbias.xmp_ibias_p_out.msky130_fd_pr__pfet_01v8[id]",
            "@m.xtop.xbias.xmn_ibias_n_out.msky130_fd_pr__nfet_01v8[id]",
        ]
    )
    return run_ngspice_sim(
        Sim(tb=tb, attrs=[Op(), Save(save_expr), h.sim.Literal(".temp 27"), sky130.install.include(h.pdk.Corner.TYP)]),
        default_ngspice_options(f"opamp_v4_biasovr_op_{override}_{vin_v}_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
    )


def _run_ac(params: NeuronOaParams, vin_v: float, override: str):
    tb = h.elaborate(_build_tb(params, vin_v, override, ac=True))
    compile_for_sky130(tb)
    return run_ngspice_sim(
        Sim(
            tb=tb,
            attrs=[
                Ac(sweep=LogSweep(1.0, 1e9, 200)),
                Save("v(xtop.vout), v(xtop.vinp_sig)"),
                h.sim.Literal(".temp 27"),
                sky130.install.include(h.pdk.Corner.TYP),
            ],
        ),
        default_ngspice_options(f"opamp_v4_biasovr_ac_{override}_{vin_v}_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
    )


def measure_lowcm_bias_branch_override() -> dict:
    params = NeuronOaParams()
    payload = {"cases": {}}
    for override in OVERRIDES:
        payload["cases"][override] = {"rows": {}, "ac": {}}
        for vin_v in VIN_POINTS:
            res = _run_op(params, vin_v, override)
            d = res.an[0].data
            row = {
                "vin_V": vin_v,
                "iq_uA": 1e6 * abs(float(d["i(v.xtop.vvvdd)"])),
                "vout_V": float(d["v(xtop.vout)"]),
                "vgp_V": float(d["v(xtop.vgp)"]),
                "vgn_V": float(d["v(xtop.vgn)"]),
                "tail_p_V": float(d["v(xtop.tail_p)"]),
                "tail_n_V": float(d["v(xtop.tail_n)"]),
                "m24_gate_mid_V": float(d["v(xtop.m24_gate_mid)"]),
                "m35_gate_mid_V": float(d["v(xtop.m35_gate_mid)"]),
                "id_i0_p_out_A": abs(float(d["i(@m.xtop.xbias.xmp_i0_p_out.msky130_fd_pr__pfet_01v8[id])"])),
                "id_i0_n_out_A": abs(float(d["i(@m.xtop.xbias.xmn_i0_n_out.msky130_fd_pr__nfet_01v8[id])"])),
                "id_ibias_p_out_A": abs(float(d["i(@m.xtop.xbias.xmp_ibias_p_out.msky130_fd_pr__pfet_01v8[id])"])),
                "id_ibias_n_out_A": abs(float(d["i(@m.xtop.xbias.xmn_ibias_n_out.msky130_fd_pr__nfet_01v8[id])"])),
            }
            row["derived"] = {
                "track_error_mV": 1e3 * abs(row["vout_V"] - vin_v),
                "driver_span_uV": 1e6 * abs(row["vgp_V"] - row["vgn_V"]),
            }
            payload["cases"][override]["rows"][str(vin_v)] = row

        ac = _run_ac(params, 0.1, override)
        payload["cases"][override]["ac"]["0.1"] = _derive_ac_metrics(ac)

    healed = []
    for override in OVERRIDES:
        row = payload["cases"][override]["rows"]["0.1"]
        ac = payload["cases"][override]["ac"]["0.1"]
        if row["derived"]["track_error_mV"] < 50.0 and ac["gbw_hz"] is not None and ac["phase_margin_deg"] is not None:
            healed.append(override)
    payload["verdict"] = {
        "vin0p1_healed_cases": healed,
        "vin0p1_primary_culprit": healed[0] if len(healed) == 1 else ("multiple_or_none", healed),
    }
    return payload


class TestV4LowCmBiasBranchOverride(BaseV4SimTest):
    def test_lowcm_bias_branch_override(self) -> None:
        payload = measure_lowcm_bias_branch_override()
        write_metrics_json(METRICS_PATH, payload)

        self.assertEqual(set(payload["cases"].keys()), set(OVERRIDES))
        for override in OVERRIDES:
            self.assertIn("0.1", payload["cases"][override]["rows"])
            self.assertIn("0.1", payload["cases"][override]["ac"])
