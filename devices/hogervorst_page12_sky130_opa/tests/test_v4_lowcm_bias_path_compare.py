import json
import math
from pathlib import Path
from uuid import uuid4

import hdl21 as h
import numpy as np
import sky130_hdl21 as sky130
from hdl21.sim import Ac, LogSweep, Op, Save, Sim
from vlsirtools.spice import ResultFormat

from devices.hogervorst_page12_sky130_opa.common import (
    default_ngspice_options,
    extract_ac_trace,
    interp_crossing,
    interp_value,
    negative_feedback_phase_trace,
    run_ngspice_sim,
)
from devices.hogervorst_page12_sky130_opa.opamp import (
    NeuronOaParams,
    Page12CoreParams,
    compile_for_sky130,
    neuron_core_oa_sky130,
    page12_analog_core,
)
from devices.hogervorst_page12_sky130_opa.opa_bias import OpaBiasGen
from devices.hogervorst_page12_sky130_opa.tests._helpers import BaseV4SimTest, find_signal, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_lowcm_bias_path_compare_metrics.json")
VIN_POINTS = (0.0, 0.05, 0.1, 0.2, 0.5, 0.9)
AC_POINTS = (0.1, 0.9)


def _ideal_bias_values() -> dict[str, float]:
    return {
        "tail_p_A": 1.6e-6,
        "tail_n_A": 1.6e-6,
        "ibias_p_A": 0.45e-6,
        "ibias_n_A": 0.45e-6,
        "vbias1_V": 0.824,
        "vbias2_V": 0.891,
        "vbias3_V": 0.634,
    }


def _safe_float(value: float) -> float | None:
    value = float(value)
    return value if math.isfinite(value) else None


def _derive_ac_metrics(ac_result) -> dict[str, float | None]:
    freq, vout_amp = extract_ac_trace(ac_result, "v(xtop.vout)")
    _, vin_amp = extract_ac_trace(ac_result, "v(xtop.vinp_sig)")
    freq = np.asarray(freq, dtype=float)
    vout_amp = np.asarray(vout_amp)
    vin_amp = np.asarray(vin_amp)
    closed_loop_gain = vout_amp / np.where(np.abs(vin_amp) > 1e-30, vin_amp, 1e-30 + 0j)
    loop_gain = closed_loop_gain / np.where(np.abs(1.0 - closed_loop_gain) > 1e-30, 1.0 - closed_loop_gain, 1e-30 + 0j)
    mag = np.abs(loop_gain)
    mag_db = 20.0 * np.log10(np.maximum(mag, 1e-30))
    phase_deg, _ = negative_feedback_phase_trace(loop_gain)

    aol_db = float(mag_db[0]) if len(mag_db) else float("nan")
    gbw_hz, _ = interp_crossing(freq, mag, 1.0)
    phase_margin_deg = float("nan")
    if np.isfinite(gbw_hz):
        phase_at_unity_deg_raw = interp_value(freq, phase_deg, gbw_hz)
        if np.isfinite(phase_at_unity_deg_raw):
            phase_margin_deg = 180.0 + phase_at_unity_deg_raw

    phase_cross_hz = float("nan")
    for idx in range(1, len(phase_deg)):
        p0 = float(phase_deg[idx - 1])
        p1 = float(phase_deg[idx])
        if (p0 + 180.0) == 0.0:
            phase_cross_hz = float(freq[idx - 1])
            break
        if (p0 + 180.0) * (p1 + 180.0) <= 0.0 and p1 != p0:
            frac = (-180.0 - p0) / (p1 - p0)
            phase_cross_hz = float(freq[idx - 1] + frac * (freq[idx] - freq[idx - 1]))
            break

    gain_margin_db = float("nan")
    if np.isfinite(phase_cross_hz):
        mag_at_phase_cross = interp_value(freq, mag_db, phase_cross_hz)
        if np.isfinite(mag_at_phase_cross):
            gain_margin_db = -float(mag_at_phase_cross)

    return {
        "aol_db": _safe_float(aol_db),
        "gbw_hz": _safe_float(gbw_hz),
        "phase_margin_deg": _safe_float(phase_margin_deg),
        "gain_margin_db": _safe_float(gain_margin_db),
    }


def _make_failure_flags(row: dict, ac_metrics: dict | None) -> dict[str, bool]:
    flags = {
        "track_error_gt_50mV": abs(float(row["vout_V"]) - float(row["vin_V"])) > 0.05,
        "iq_lt_10uA": float(row["iq_uA"]) < 10.0,
    }
    if ac_metrics is not None:
        flags["ac_nonfinite"] = any(ac_metrics[key] is None for key in ("aol_db", "gbw_hz", "phase_margin_deg"))
    else:
        flags["ac_nonfinite"] = False
    flags["low_cm_failure"] = flags["track_error_gt_50mV"] or flags["ac_nonfinite"]
    return flags


def _build_core_ideal_op_tb(params: Page12CoreParams, vin_v: float):
    dut = page12_analog_core(params)
    bias = _ideal_bias_values()

    @h.module
    class Tb:
        VSS = h.Port()
        avdd, vinp_sig, vinn_sig, vout = h.Signals(4)
        tail_p, tail_n = h.Signals(2)
        vbias1, vbias2, vbias3 = h.Signals(3)
        m24_gate_mid, m35_gate_mid = h.Signals(2)
        pnode_l, pnode_r, nnode_l, nnode_r = h.Signals(4)
        vref_mid, vgp, vgn = h.Signals(3)

        vvdd = h.Vdc(dc=1.8)(p=avdd, n=VSS)
        vvinp = h.Vdc(dc=vin_v)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=vin_v)(p=vinn_sig, n=VSS)
        itail_p = h.Idc(dc=bias["tail_p_A"])(p=avdd, n=tail_p)
        itail_n = h.Idc(dc=bias["tail_n_A"])(p=tail_n, n=VSS)
        ibias_p = h.Idc(dc=bias["ibias_p_A"])(p=avdd, n=m24_gate_mid)
        ibias_n = h.Idc(dc=bias["ibias_n_A"])(p=m35_gate_mid, n=VSS)
        vb1 = h.Vdc(dc=bias["vbias1_V"])(p=vbias1, n=VSS)
        vb2 = h.Vdc(dc=bias["vbias2_V"])(p=vbias2, n=VSS)
        vb3 = h.Vdc(dc=bias["vbias3_V"])(p=vbias3, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinn_sig)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        rload = h.Res(r=1e9)(p=vout, n=VSS)

        xcore = dut(
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


def _build_core_real_bias_op_tb(params: NeuronOaParams, vin_v: float):
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

        vvdd = h.Vdc(dc=1.8)(p=avdd, n=VSS)
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
            i0_p=tail_p,
            i0_n=tail_n,
            ibias_p=m24_gate_mid,
            ibias_n=m35_gate_mid,
            vbias1=vbias1,
            vbias2=vbias2,
            vbias3=vbias3,
        )
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


def _build_full_dut_op_tb(params: NeuronOaParams, vin_v: float):
    dut = h.elaborate(neuron_core_oa_sky130(params))
    compile_for_sky130(dut)

    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, avdd = h.Signals(4)
        iref, vbase, vfeed, vtest = h.Signals(4)
        d_en_oa, d_az_oa, d_inf_oa = h.Signals(3)
        d_treset_oa, d_tcki, d_tcko, d_tdi, d_tdo = h.Signals(5)

        vvdd = h.Vdc(dc=1.8)(p=avdd, n=VSS)
        vvinp = h.Vdc(dc=vin_v)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=vin_v)(p=vinn_sig, n=VSS)
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


def _build_core_real_bias_ac_tb(params: NeuronOaParams, vin_v: float):
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

        vvdd = h.Vdc(dc=1.8)(p=avdd, n=VSS)
        vvinp = h.Vdc(dc=vin_v, ac=1.0)(p=vinp_sig, n=VSS)
        iiref = h.Idc(dc=0.25e-6)(p=iref, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinn_sig)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        rload = h.Res(r=1e9)(p=vout, n=VSS)

        xbias = bias(
            avdd=avdd,
            agnd=VSS,
            iref=iref,
            i0_p=tail_p,
            i0_n=tail_n,
            ibias_p=m24_gate_mid,
            ibias_n=m35_gate_mid,
            vbias1=vbias1,
            vbias2=vbias2,
            vbias3=vbias3,
        )
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


def _build_full_dut_ac_tb(params: NeuronOaParams, vin_v: float):
    dut = h.elaborate(neuron_core_oa_sky130(params))
    compile_for_sky130(dut)

    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, avdd = h.Signals(4)
        iref, vbase, vfeed, vtest = h.Signals(4)
        d_en_oa, d_az_oa, d_inf_oa = h.Signals(3)
        d_treset_oa, d_tcki, d_tcko, d_tdi, d_tdo = h.Signals(5)

        vvdd = h.Vdc(dc=1.8)(p=avdd, n=VSS)
        vvinp = h.Vdc(dc=vin_v, ac=1.0)(p=vinp_sig, n=VSS)
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


def _run_op(tb_builder, vin_v: float, *, name: str, save_expr: str = "all"):
    tb = h.elaborate(tb_builder(vin_v))
    compile_for_sky130(tb)
    sim = Sim(tb=tb, attrs=[Op(), Save(save_expr), h.sim.Literal(".temp 27"), sky130.install.include(h.pdk.Corner.TYP)])
    return run_ngspice_sim(
        sim,
        default_ngspice_options(f"{name}_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
    )


def _run_ac(tb_builder, vin_v: float, *, name: str):
    tb = h.elaborate(tb_builder(vin_v))
    compile_for_sky130(tb)
    sim = Sim(
        tb=tb,
        attrs=[
            Ac(sweep=LogSweep(1.0, 1e9, 200)),
            Save("v(xtop.vout), v(xtop.vinp_sig)"),
            h.sim.Literal(".temp 27"),
            sky130.install.include(h.pdk.Corner.TYP),
        ],
    )
    return run_ngspice_sim(
        sim,
        default_ngspice_options(f"{name}_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
    )


def _extract_core_row(data: dict[str, float], vin_v: float, *, supply_current_key: str) -> dict:
    row = {
        "vin_V": vin_v,
        "iq_uA": 1e6 * abs(find_signal(data, exact=supply_current_key)),
        "vout_V": find_signal(data, exact="v(xtop.vout)"),
        "tail_p_V": find_signal(data, exact="v(xtop.tail_p)"),
        "tail_n_V": find_signal(data, exact="v(xtop.tail_n)"),
        "vbias1_V": find_signal(data, exact="v(xtop.vbias1)"),
        "vbias2_V": find_signal(data, exact="v(xtop.vbias2)"),
        "vbias3_V": find_signal(data, exact="v(xtop.vbias3)"),
        "m24_gate_mid_V": find_signal(data, exact="v(xtop.m24_gate_mid)"),
        "m35_gate_mid_V": find_signal(data, exact="v(xtop.m35_gate_mid)"),
        "pnode_l_V": find_signal(data, exact="v(xtop.pnode_l)"),
        "pnode_r_V": find_signal(data, exact="v(xtop.pnode_r)"),
        "nnode_l_V": find_signal(data, exact="v(xtop.nnode_l)"),
        "nnode_r_V": find_signal(data, exact="v(xtop.nnode_r)"),
        "vref_mid_V": find_signal(data, exact="v(xtop.vref_mid)"),
        "vgp_V": find_signal(data, exact="v(xtop.vgp)"),
        "vgn_V": find_signal(data, exact="v(xtop.vgn)"),
    }
    row["derived"] = {
        "driver_diff_V": row["vgp_V"] - row["vgn_V"],
        "track_error_mV": 1e3 * abs(row["vout_V"] - row["vin_V"]),
        "driver_nodes_within_rails": all(0.0 <= row[key] <= 1.8 for key in ("vgp_V", "vgn_V", "vout_V")),
        "bias_nodes_within_rails": all(0.0 <= row[key] <= 1.8 for key in ("tail_p_V", "tail_n_V", "vbias1_V", "vbias2_V", "vbias3_V", "m24_gate_mid_V", "m35_gate_mid_V")),
    }
    return row


def _extract_real_bias_extras(data: dict[str, float]) -> dict:
    return {
        "vg_i0_p_V": find_signal(data, suffix="vg_i0_p)"),
        "vg_i0_n_V": find_signal(data, suffix="vg_i0_n)"),
        "vg_ibias_p_V": find_signal(data, suffix="vg_ibias_p)"),
        "vg_ibias_n_V": find_signal(data, suffix="vg_ibias_n)"),
        "id_i0_p_out_A": abs(find_signal(data, suffix="xmp_i0_p_out.msky130_fd_pr__pfet_01v8[id])")),
        "id_i0_n_out_A": abs(find_signal(data, suffix="xmn_i0_n_out.msky130_fd_pr__nfet_01v8[id])")),
        "id_ibias_p_out_A": abs(find_signal(data, suffix="xmp_ibias_p_out.msky130_fd_pr__pfet_01v8[id])")),
        "id_ibias_n_out_A": abs(find_signal(data, suffix="xmn_ibias_n_out.msky130_fd_pr__nfet_01v8[id])")),
    }


def _extract_full_dut_row(data: dict[str, float], vin_v: float) -> dict:
    row = {
        "vin_V": vin_v,
        "iq_uA": 1e6 * abs(find_signal(data, exact="i(v.xtop.vvvdd)")),
        "vout_V": find_signal(data, exact="v(xtop.vout)"),
        "iref_int_V": find_signal(data, exact="v(xtop.xxdut.iref_int)"),
        "tail_p_V": find_signal(data, exact="v(xtop.xxdut.tail_p)"),
        "tail_n_V": find_signal(data, exact="v(xtop.xxdut.tail_n)"),
        "vbias1_V": find_signal(data, exact="v(xtop.xxdut.vbias1)"),
        "vbias2_V": find_signal(data, exact="v(xtop.xxdut.vbias2)"),
        "vbias3_V": find_signal(data, exact="v(xtop.xxdut.vbias3)"),
        "m24_gate_mid_V": find_signal(data, exact="v(xtop.xxdut.m24_gate_mid)"),
        "m35_gate_mid_V": find_signal(data, exact="v(xtop.xxdut.m35_gate_mid)"),
        "pnode_l_V": find_signal(data, exact="v(xtop.xxdut.pnode_l)"),
        "pnode_r_V": find_signal(data, exact="v(xtop.xxdut.pnode_r)"),
        "nnode_l_V": find_signal(data, exact="v(xtop.xxdut.nnode_l)"),
        "nnode_r_V": find_signal(data, exact="v(xtop.xxdut.nnode_r)"),
        "vref_mid_V": find_signal(data, exact="v(xtop.xxdut.vref_mid)"),
        "vgp_V": find_signal(data, exact="v(xtop.xxdut.vgp)"),
        "vgn_V": find_signal(data, exact="v(xtop.xxdut.vgn)"),
    }
    row.update({
        "vg_i0_p_V": find_signal(data, exact="v(xtop.xxdut.xbias.vg_i0_p)"),
        "vg_i0_n_V": find_signal(data, exact="v(xtop.xxdut.xbias.vg_i0_n)"),
        "vg_ibias_p_V": find_signal(data, exact="v(xtop.xxdut.xbias.vg_ibias_p)"),
        "vg_ibias_n_V": find_signal(data, exact="v(xtop.xxdut.xbias.vg_ibias_n)"),
        "id_i0_p_out_A": abs(find_signal(data, suffix="xxdut.xbias.xmp_i0_p_out.msky130_fd_pr__pfet_01v8[id])")),
        "id_i0_n_out_A": abs(find_signal(data, suffix="xxdut.xbias.xmn_i0_n_out.msky130_fd_pr__nfet_01v8[id])")),
        "id_ibias_p_out_A": abs(find_signal(data, suffix="xxdut.xbias.xmp_ibias_p_out.msky130_fd_pr__pfet_01v8[id])")),
        "id_ibias_n_out_A": abs(find_signal(data, suffix="xxdut.xbias.xmn_ibias_n_out.msky130_fd_pr__nfet_01v8[id])")),
    })
    row["derived"] = {
        "driver_diff_V": row["vgp_V"] - row["vgn_V"],
        "track_error_mV": 1e3 * abs(row["vout_V"] - row["vin_V"]),
        "driver_nodes_within_rails": all(0.0 <= row[key] <= 1.8 for key in ("vgp_V", "vgn_V", "vout_V")),
        "bias_nodes_within_rails": all(0.0 <= row[key] <= 1.8 for key in ("tail_p_V", "tail_n_V", "vbias1_V", "vbias2_V", "vbias3_V", "m24_gate_mid_V", "m35_gate_mid_V")),
    }
    return row


def measure_lowcm_bias_path_compare() -> dict:
    params = NeuronOaParams()
    core_params = Page12CoreParams(frontend=params.frontend, monticelli=params.monticelli, output=params.output)
    payload = {"core_ideal": {"rows": []}, "core_real_bias": {"rows": [], "ac": {}}, "full_dut": {"rows": [], "ac": {}}}

    for vin_v in VIN_POINTS:
        ideal_op = _run_op(lambda vin: _build_core_ideal_op_tb(core_params, vin), vin_v, name="opamp_v4_cmp_core_ideal")
        ideal_row = _extract_core_row(ideal_op.an[0].data, vin_v, supply_current_key="i(v.xtop.vvvdd)")
        ideal_row["flags"] = _make_failure_flags(ideal_row, None)
        payload["core_ideal"]["rows"].append(ideal_row)

        real_op = _run_op(
            lambda vin: _build_core_real_bias_op_tb(params, vin),
            vin_v,
            name="opamp_v4_cmp_core_real",
            save_expr=(
                "all, "
                "@m.xtop.xbias.xmp_i0_p_out.msky130_fd_pr__pfet_01v8[id], "
                "@m.xtop.xbias.xmn_i0_n_out.msky130_fd_pr__nfet_01v8[id], "
                "@m.xtop.xbias.xmp_ibias_p_out.msky130_fd_pr__pfet_01v8[id], "
                "@m.xtop.xbias.xmn_ibias_n_out.msky130_fd_pr__nfet_01v8[id]"
            ),
        )
        real_row = _extract_core_row(real_op.an[0].data, vin_v, supply_current_key="i(v.xtop.vvvdd)")
        real_row.update(_extract_real_bias_extras(real_op.an[0].data))
        real_row["flags"] = _make_failure_flags(real_row, None)
        payload["core_real_bias"]["rows"].append(real_row)

        full_op = _run_op(
            lambda vin: _build_full_dut_op_tb(params, vin),
            vin_v,
            name="opamp_v4_cmp_full_dut",
            save_expr=(
                "all, "
                "@m.xtop.xxdut.xbias.xmp_i0_p_out.msky130_fd_pr__pfet_01v8[id], "
                "@m.xtop.xxdut.xbias.xmn_i0_n_out.msky130_fd_pr__nfet_01v8[id], "
                "@m.xtop.xxdut.xbias.xmp_ibias_p_out.msky130_fd_pr__pfet_01v8[id], "
                "@m.xtop.xxdut.xbias.xmn_ibias_n_out.msky130_fd_pr__nfet_01v8[id]"
            ),
        )
        full_row = _extract_full_dut_row(full_op.an[0].data, vin_v)
        full_row["flags"] = _make_failure_flags(full_row, None)
        payload["full_dut"]["rows"].append(full_row)

    for vin_v in AC_POINTS:
        real_ac = _run_ac(lambda vin: _build_core_real_bias_ac_tb(params, vin), vin_v, name="opamp_v4_cmp_core_real_ac")
        real_metrics = _derive_ac_metrics(real_ac)
        payload["core_real_bias"]["ac"][str(vin_v)] = real_metrics
        payload["core_real_bias"]["rows"][VIN_POINTS.index(vin_v)]["flags"] = _make_failure_flags(
            payload["core_real_bias"]["rows"][VIN_POINTS.index(vin_v)], real_metrics
        )

        full_ac = _run_ac(lambda vin: _build_full_dut_ac_tb(params, vin), vin_v, name="opamp_v4_cmp_full_dut_ac")
        full_metrics = _derive_ac_metrics(full_ac)
        payload["full_dut"]["ac"][str(vin_v)] = full_metrics
        payload["full_dut"]["rows"][VIN_POINTS.index(vin_v)]["flags"] = _make_failure_flags(
            payload["full_dut"]["rows"][VIN_POINTS.index(vin_v)], full_metrics
        )

    ideal_01 = payload["core_ideal"]["rows"][VIN_POINTS.index(0.1)]["flags"]["low_cm_failure"]
    real_01 = payload["core_real_bias"]["rows"][VIN_POINTS.index(0.1)]["flags"]["low_cm_failure"]
    full_01 = payload["full_dut"]["rows"][VIN_POINTS.index(0.1)]["flags"]["low_cm_failure"]

    if (not ideal_01) and real_01 and full_01:
        primary = "OpaBiasGen / bias headroom"
    elif (not ideal_01) and (not real_01) and full_01:
        primary = "wrapper path around the bias/core"
    elif (not ideal_01) and real_01 and (not full_01):
        primary = "core+real-bias interaction, wrapper not primary"
    else:
        primary = "unresolved or mixed; re-open topology hypothesis"

    payload["comparisons"] = {
        "vin0p1_failure": {
            "core_ideal": ideal_01,
            "core_real_bias": real_01,
            "full_dut": full_01,
        },
        "vin0p1_track_error_mV": {
            "core_ideal": payload["core_ideal"]["rows"][VIN_POINTS.index(0.1)]["derived"]["track_error_mV"],
            "core_real_bias": payload["core_real_bias"]["rows"][VIN_POINTS.index(0.1)]["derived"]["track_error_mV"],
            "full_dut": payload["full_dut"]["rows"][VIN_POINTS.index(0.1)]["derived"]["track_error_mV"],
        },
    }
    payload["verdict"] = {
        "vin0p1_primary_culprit": primary,
        "vin0p0_status": "separate hard lower-bound case; do not merge with VIN=0.1 diagnosis",
    }
    return payload


class TestV4LowCmBiasPathCompare(BaseV4SimTest):
    def test_lowcm_bias_path_compare(self) -> None:
        payload = measure_lowcm_bias_path_compare()
        write_metrics_json(METRICS_PATH, payload)

        self.assertEqual(len(payload["core_ideal"]["rows"]), len(VIN_POINTS))
        self.assertEqual(len(payload["core_real_bias"]["rows"]), len(VIN_POINTS))
        self.assertEqual(len(payload["full_dut"]["rows"]), len(VIN_POINTS))
        self.assertFalse(payload["core_ideal"]["rows"][VIN_POINTS.index(0.1)]["flags"]["low_cm_failure"])
        for mode in ("core_ideal", "core_real_bias", "full_dut"):
            for row in payload[mode]["rows"]:
                self.assertTrue(row["derived"]["driver_nodes_within_rails"], f"{mode} VIN={row['vin_V']}: driver nodes must stay within rails")
