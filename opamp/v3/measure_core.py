import math
import traceback
from datetime import datetime, timezone
from dataclasses import fields

import hdl21 as h
import numpy as np
from hdl21.sim import Ac, LogSweep, Op, Save, Sim
from vlsirtools.spice import ResultFormat, SimOptions

from .common import (
    extract_ac_trace,
    interp_crossing,
    interp_value,
    make_test_result,
    negative_feedback_phase_trace,
    op_scalar,
    require_sky130_install,
    run_ngspice_sim,
    unique_ngspice_options,
)
from .opamp_core import OpampCoreParams, opamp_core
from .specs import OpampAzV3MaximumSpec, OpampAzV3TargetSpec, max_required_output_high, min_required_output_high


def _reset_generator_cache() -> None:
    try:
        h.generator.cache.reset()
    except Exception:
        pass


@h.paramclass
class OpampCoreOpenLoopTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    c_load = h.Param(dtype=h.Scalar, desc="Load capacitance in F", default=1e-12)
    r_probe = h.Param(dtype=h.Scalar, desc="Weak output probe resistance in ohm", default=1e12)
    v_cm = h.Param(dtype=h.Scalar, desc="Input common-mode voltage in V", default=0.9)
    dc_v_diff = h.Param(dtype=h.Scalar, desc="Differential DC excitation in V", default=100e-6)
    f_start = h.Param(dtype=h.Scalar, desc="AC sweep start frequency in Hz", default=1.0)
    f_stop = h.Param(dtype=h.Scalar, desc="AC sweep stop frequency in Hz", default=1e9)
    npts = h.Param(dtype=int, desc="AC sweep points per decade", default=40)
    temp_c = h.Param(dtype=h.Scalar, desc="Simulation temperature in degC", default=27.0)


@h.paramclass
class OpampCoreFollowerTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    c_load = h.Param(dtype=h.Scalar, desc="Load capacitance in F", default=1e-12)
    r_probe = h.Param(dtype=h.Scalar, desc="Weak probe resistance in ohm", default=1e12)
    vout_low_target = h.Param(dtype=h.Scalar, desc="Low output target in V", default=0.1)
    vout_high_target = h.Param(dtype=h.Scalar, desc="High output target in V", default=1.6)
    vout_mid_target = h.Param(dtype=h.Scalar, desc="Mid output target in V", default=0.9)
    drive_current_uA = h.Param(dtype=h.Scalar, desc="Forced current target in uA", default=20.0)
    f_start = h.Param(dtype=h.Scalar, desc="AC sweep start frequency in Hz", default=1.0)
    f_stop = h.Param(dtype=h.Scalar, desc="AC sweep stop frequency in Hz", default=1e9)
    npts = h.Param(dtype=int, desc="AC sweep points per decade", default=40)
    temp_c = h.Param(dtype=h.Scalar, desc="Simulation temperature in degC", default=27.0)


@h.paramclass
class OpampCoreDisabledTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    c_load = h.Param(dtype=h.Scalar, desc="Load capacitance in F", default=1e-12)
    r_probe = h.Param(dtype=h.Scalar, desc="Weak probe resistance in ohm", default=1e12)
    v_cm = h.Param(dtype=h.Scalar, desc="Common-mode voltage in V", default=0.4)
    temp_c = h.Param(dtype=h.Scalar, desc="Simulation temperature in degC", default=27.0)


def _core_params_with(dut_params: OpampCoreParams, **updates) -> OpampCoreParams:
    payload = {field.name: getattr(dut_params, field.name) for field in fields(dut_params)}
    payload.update(updates)
    return OpampCoreParams(**payload)


def _build_direct_gain_op_tb(dut_params: OpampCoreParams, *, vdd: float, c_load: float, r_probe: float, v_cm: float, v_diff: float, temp_c: float, corner) -> Sim:
    install = require_sky130_install()
    dut = opamp_core(dut_params)

    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, en, vdd_sig = h.Signals(5)
        vvdd = h.Vdc(dc=vdd)(p=vdd_sig, n=VSS)
        ven = h.Vdc(dc=vdd)(p=en, n=VSS)
        vvinp = h.Vdc(dc=v_cm + 0.5 * v_diff)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=v_cm - 0.5 * v_diff)(p=vinn_sig, n=VSS)
        cload = h.Cap(c=c_load)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, EN=en, VDD=vdd_sig, VSS=VSS)

    return Sim(tb=Tb, attrs=[Op(), Save("i(v.xtop.vvvdd), v(xtop.vout)"), h.sim.Literal(f".temp {temp_c}"), install.include(corner)])


def _build_direct_gain_ac_tb(dut_params: OpampCoreParams, *, vdd: float, c_load: float, r_probe: float, v_cm: float, v_diff: float, temp_c: float, corner) -> Sim:
    install = require_sky130_install()
    dut = opamp_core(dut_params)

    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, en, vdd_sig = h.Signals(5)
        vvdd = h.Vdc(dc=vdd)(p=vdd_sig, n=VSS)
        ven = h.Vdc(dc=vdd)(p=en, n=VSS)
        vvinp = h.Vdc(dc=v_cm, ac=0.5 * v_diff)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=v_cm, ac=-0.5 * v_diff)(p=vinn_sig, n=VSS)
        cload = h.Cap(c=c_load)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, EN=en, VDD=vdd_sig, VSS=VSS)

    return Sim(tb=Tb, attrs=[Ac(sweep=LogSweep(1.0, 10.0, 2)), Save("v(xtop.vout)"), h.sim.Literal(f".temp {temp_c}"), install.include(corner)])


def _build_open_loop_biased_op_tb(
    dut_params: OpampCoreParams,
    *,
    vdd: float,
    c_load: float,
    r_probe: float,
    v_cm: float,
    temp_c: float,
    corner,
) -> Sim:
    install = require_sky130_install()
    dut = opamp_core(dut_params)

    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, en, vdd_sig = h.Signals(5)
        vvdd = h.Vdc(dc=vdd)(p=vdd_sig, n=VSS)
        ven = h.Vdc(dc=vdd)(p=en, n=VSS)
        vvinp = h.Vdc(dc=v_cm)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=v_cm)(p=vinn_sig, n=VSS)
        # DC-bias the output near nominal follower equilibrium while leaving the
        # feedback path effectively open for AC.
        lfb = h.Ind(l=1e9)(p=vout, n=vinn_sig)
        cload = h.Cap(c=c_load)(p=vout, n=VSS)
        rload = h.Res(r=r_probe)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, EN=en, VDD=vdd_sig, VSS=VSS)

    return Sim(tb=Tb, attrs=[Op(), Save("i(v.xtop.vvvdd), v(xtop.vout)"), h.sim.Literal(f".temp {temp_c}"), install.include(corner)])


def _build_open_loop_biased_ac_tb(
    dut_params: OpampCoreParams,
    *,
    vdd: float,
    c_load: float,
    r_probe: float,
    v_cm: float,
    f_start: float,
    f_stop: float,
    npts: int,
    temp_c: float,
    corner,
) -> Sim:
    install = require_sky130_install()
    dut = opamp_core(dut_params)

    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, en, vdd_sig = h.Signals(5)
        vvdd = h.Vdc(dc=vdd)(p=vdd_sig, n=VSS)
        ven = h.Vdc(dc=vdd)(p=en, n=VSS)
        vvinp = h.Vdc(dc=v_cm, ac=1.0)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=v_cm)(p=vinn_sig, n=VSS)
        lfb = h.Ind(l=1e9)(p=vout, n=vinn_sig)
        cload = h.Cap(c=c_load)(p=vout, n=VSS)
        rload = h.Res(r=r_probe)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, EN=en, VDD=vdd_sig, VSS=VSS)

    return Sim(
        tb=Tb,
        attrs=[
            Ac(sweep=LogSweep(f_start, f_stop, npts)),
            Save("v(xtop.vout), v(xtop.vinn_sig)"),
            h.sim.Literal(f".temp {temp_c}"),
            install.include(corner),
        ],
    )


def _build_follower_op_tb(
    dut_params: OpampCoreParams,
    *,
    vdd: float,
    vin: float,
    c_load: float,
    r_probe: float,
    en_voltage: float,
    temp_c: float,
    corner,
    current_load_uA: float = 0.0,
    load_mode: str = "none",
) -> Sim:
    install = require_sky130_install()
    dut = opamp_core(dut_params)
    current_load = 1e-6 * current_load_uA

    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, en, vdd_sig = h.Signals(5)
        vvdd = h.Vdc(dc=vdd)(p=vdd_sig, n=VSS)
        ven = h.Vdc(dc=en_voltage)(p=en, n=VSS)
        vvinp = h.Vdc(dc=vin)(p=vinp_sig, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinn_sig)
        cload = h.Cap(c=c_load)(p=vout, n=VSS)
        rload = h.Res(r=r_probe)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, EN=en, VDD=vdd_sig, VSS=VSS)
        if load_mode == "source":
            iload = h.Idc(dc=current_load)(p=vout, n=VSS)
        elif load_mode == "sink":
            iload = h.Idc(dc=current_load)(p=vdd_sig, n=vout)

    return Sim(tb=Tb, attrs=[Op(), Save("i(v.xtop.vvvdd), v(xtop.vout)"), h.sim.Literal(f".temp {temp_c}"), install.include(corner)])


def _build_follower_ac_tb(dut_params: OpampCoreParams, *, vdd: float, vin: float, c_load: float, r_probe: float, en_voltage: float, f_start: float, f_stop: float, npts: int, temp_c: float, corner) -> Sim:
    install = require_sky130_install()
    dut = opamp_core(dut_params)

    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, en, vdd_sig = h.Signals(5)
        vvdd = h.Vdc(dc=vdd)(p=vdd_sig, n=VSS)
        ven = h.Vdc(dc=en_voltage)(p=en, n=VSS)
        vvinp = h.Vdc(dc=vin, ac=1.0)(p=vinp_sig, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinn_sig)
        cload = h.Cap(c=c_load)(p=vout, n=VSS)
        rload = h.Res(r=r_probe)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, EN=en, VDD=vdd_sig, VSS=VSS)

    return Sim(tb=Tb, attrs=[Ac(sweep=LogSweep(f_start, f_stop, npts)), Save("v(xtop.vout), v(xtop.vinp_sig)"), h.sim.Literal(f".temp {temp_c}"), install.include(corner)])


def run_direct_dc_gain_test(dut_params: OpampCoreParams | None = None, tb_params: OpampCoreOpenLoopTbParams | None = None, *, corner=h.pdk.Corner.TYP):
    _reset_generator_cache()
    dut_params = dut_params or OpampCoreParams()
    tb_params = tb_params or OpampCoreOpenLoopTbParams()
    ac_result = run_ngspice_sim(
        _build_direct_gain_ac_tb(dut_params, vdd=float(tb_params.vdd), c_load=float(tb_params.c_load), r_probe=float(tb_params.r_probe), v_cm=float(tb_params.v_cm), v_diff=float(tb_params.dc_v_diff), temp_c=float(tb_params.temp_c), corner=corner),
        unique_ngspice_options("opamp_core_v3_direct_dc_gain_ac", fmt=ResultFormat.SIM_DATA),
    )
    op_result = run_ngspice_sim(
        _build_direct_gain_op_tb(dut_params, vdd=float(tb_params.vdd), c_load=float(tb_params.c_load), r_probe=float(tb_params.r_probe), v_cm=float(tb_params.v_cm), v_diff=0.0, temp_c=float(tb_params.temp_c), corner=corner),
        unique_ngspice_options("opamp_core_v3_direct_dc_gain_bias", fmt=ResultFormat.SIM_DATA),
    )
    _, vout_amp = extract_ac_trace(ac_result, "v(xtop.vout)")
    low_freq_vout = complex(np.asarray(vout_amp)[0])
    direct_gain_vv = abs(low_freq_vout) / max(abs(float(tb_params.dc_v_diff)), 1e-18)
    direct_gain_db = 20.0 * math.log10(max(direct_gain_vv, 1e-30))
    iq_abs = abs(op_scalar(op_result, "i(v.xtop.vvvdd)"))
    return make_test_result(
        component="opamp_core_v3",
        category="char",
        purpose="direct_dc_gain",
        metrics={
            "vout_dc": op_scalar(op_result, "v(xtop.vout)"),
            "direct_gain_vv": direct_gain_vv,
            "direct_gain_db": direct_gain_db,
            "iq_uA": 1e6 * iq_abs,
        },
    )


def run_loop_stability_test(dut_params: OpampCoreParams | None = None, tb_params: OpampCoreFollowerTbParams | None = None, *, corner=h.pdk.Corner.TYP):
    _reset_generator_cache()
    dut_params = dut_params or OpampCoreParams()
    tb_params = tb_params or OpampCoreFollowerTbParams()
    ac_failed = False
    low_freq_loop_gain_db = float("nan")
    low_freq_loop_gain_vv = float("nan")
    gbw_hz = float("nan")
    phase_margin_deg = float("nan")
    gain_margin_db = float("nan")
    phase_at_unity_deg_raw = float("nan")
    low_freq_phase_deg_raw = float("nan")
    ac_error = ""
    try:
        ac_result = run_ngspice_sim(
            _build_open_loop_biased_ac_tb(
                dut_params,
                vdd=float(tb_params.vdd),
                c_load=float(tb_params.c_load),
                r_probe=float(tb_params.r_probe),
                v_cm=float(tb_params.vout_mid_target),
                f_start=float(tb_params.f_start),
                f_stop=float(tb_params.f_stop),
                npts=int(tb_params.npts),
                temp_c=float(tb_params.temp_c),
                corner=corner,
            ),
            unique_ngspice_options("opamp_core_v3_open_loop_biased_ac", fmt=ResultFormat.SIM_DATA),
        )
    except Exception as exc:
        ac_failed = True
        ac_result = None
        ac_error = f"{type(exc).__name__}: {exc}"
    op_result = run_ngspice_sim(
        _build_open_loop_biased_op_tb(
            dut_params,
            vdd=float(tb_params.vdd),
            c_load=float(tb_params.c_load),
            r_probe=float(tb_params.r_probe),
            v_cm=float(tb_params.vout_mid_target),
            temp_c=float(tb_params.temp_c),
            corner=corner,
        ),
        unique_ngspice_options("opamp_core_v3_open_loop_biased_bias", fmt=ResultFormat.SIM_DATA),
    )
    if not ac_failed:
        try:
            freq, vout_amp = extract_ac_trace(ac_result, "v(xtop.vout)")
            freq = np.asarray(freq, dtype=float)
            vout_amp = np.asarray(vout_amp)
            # The biased-open-loop fixture AC-drives VINP with 1 V, keeps VINN DC-biased
            # through a huge inductor, and leaves the loop effectively open for AC.
            # The core is inverting, so use `-A(s)` for conventional PM/GM extraction.
            loop_gain = -vout_amp
            mag = np.abs(loop_gain)
            mag_db = 20.0 * np.log10(np.maximum(mag, 1e-30))
            if len(mag):
                low_freq_loop_gain_vv = float(mag[0])
                low_freq_loop_gain_db = float(mag_db[0])
            phase_deg = np.unwrap(np.angle(loop_gain)) * 180.0 / math.pi
            low_freq_phase_deg_raw = float(phase_deg[0]) if len(phase_deg) else float("nan")
            gbw_hz, _ = interp_crossing(freq, mag, 1.0)
            if math.isfinite(gbw_hz):
                phase_at_unity = interp_value(freq, phase_deg, gbw_hz)
                if math.isfinite(phase_at_unity):
                    phase_at_unity_deg_raw = phase_at_unity
                    phase_margin_deg = 180.0 + phase_at_unity
            phase_cross_hz, _ = interp_crossing(freq, phase_deg, -180.0)
            if math.isfinite(phase_cross_hz):
                mag_db_at_phase_cross = interp_value(freq, mag_db, phase_cross_hz)
                if math.isfinite(mag_db_at_phase_cross):
                    gain_margin_db = -mag_db_at_phase_cross
            elif len(phase_deg) and float(np.min(phase_deg)) > -180.0:
                gain_margin_db = float("inf")
        except Exception as exc:
            ac_failed = True
            ac_error = f"{type(exc).__name__}: {exc}"
    iq_abs = abs(op_scalar(op_result, "i(v.xtop.vvvdd)"))
    return make_test_result(
        component="opamp_core_v3",
        category="char",
        purpose="closed_loop_stability",
        metrics={
            "low_freq_loop_gain_vv": low_freq_loop_gain_vv,
            "low_freq_loop_gain_db": low_freq_loop_gain_db,
            "gbw_hz": gbw_hz,
            "phase_margin_deg": phase_margin_deg,
            "gain_margin_db": gain_margin_db,
            "phase_at_unity_deg_raw": phase_at_unity_deg_raw,
            "low_freq_phase_deg_raw": low_freq_phase_deg_raw,
            "iq_uA": 1e6 * iq_abs,
            "loop_vout_dc": op_scalar(op_result, "v(xtop.vout)"),
            "ac_fixture_ok": not ac_failed,
            "ac_error": ac_error,
        },
    )


def run_open_loop_test(dut_params: OpampCoreParams | None = None, tb_params: OpampCoreOpenLoopTbParams | None = None, *, corner=h.pdk.Corner.TYP):
    _reset_generator_cache()
    dut_params = dut_params or OpampCoreParams()
    tb_params = tb_params or OpampCoreOpenLoopTbParams()

    direct = run_direct_dc_gain_test(dut_params, tb_params, corner=corner)["metrics"]
    loop = run_loop_stability_test(
        dut_params,
        OpampCoreFollowerTbParams(
            vdd=tb_params.vdd,
            c_load=tb_params.c_load,
            r_probe=tb_params.r_probe,
            vout_mid_target=tb_params.v_cm,
            f_start=tb_params.f_start,
            f_stop=tb_params.f_stop,
            npts=tb_params.npts,
            temp_c=tb_params.temp_c,
        ),
        corner=corner,
    )["metrics"]

    aol_db = float(direct["direct_gain_db"])
    gbw_hz = float(loop["gbw_hz"])
    phase_margin_deg = float(loop["phase_margin_deg"])
    gain_margin_db = float(loop["gain_margin_db"])
    aol_estimate_valid = (
        math.isfinite(aol_db)
        and math.isfinite(gbw_hz)
        and math.isfinite(phase_margin_deg)
        and aol_db > 0.0
        and aol_db < 160.0
    )
    iq_uA = float(loop["iq_uA"])
    return make_test_result(
        component="opamp_core_v3",
        category="char",
        purpose="open_loop",
        metrics={
            "aol_db": aol_db if aol_estimate_valid else float("nan"),
            "direct_dc_gain_db": aol_db,
            "iq_uA": iq_uA,
            "direct_vout_dc": float(loop["loop_vout_dc"]),
            "gbw_hz": gbw_hz,
            "phase_margin_deg": phase_margin_deg,
            "gain_margin_db": gain_margin_db,
            "low_freq_loop_gain_db": aol_db,
            "low_freq_loop_gain_vv": float(10 ** (aol_db / 20.0)) if math.isfinite(aol_db) else float("nan"),
            "ac_fixture_ok": bool(loop["ac_fixture_ok"]),
            "aol_estimate_valid": bool(aol_estimate_valid),
        },
    )


def run_output_swing_test(dut_params: OpampCoreParams | None = None, tb_params: OpampCoreFollowerTbParams | None = None, *, corner=h.pdk.Corner.TYP):
    dut_params = dut_params or OpampCoreParams()
    tb_params = tb_params or OpampCoreFollowerTbParams()
    low = run_ngspice_sim(
        _build_follower_op_tb(dut_params, vdd=float(tb_params.vdd), vin=float(tb_params.vout_low_target), c_load=float(tb_params.c_load), r_probe=float(tb_params.r_probe), en_voltage=float(tb_params.vdd), temp_c=float(tb_params.temp_c), corner=corner),
        unique_ngspice_options("opamp_core_v3_output_swing_low", fmt=ResultFormat.SIM_DATA),
    )
    high = run_ngspice_sim(
        _build_follower_op_tb(dut_params, vdd=float(tb_params.vdd), vin=float(tb_params.vout_high_target), c_load=float(tb_params.c_load), r_probe=float(tb_params.r_probe), en_voltage=float(tb_params.vdd), temp_c=float(tb_params.temp_c), corner=corner),
        unique_ngspice_options("opamp_core_v3_output_swing_high", fmt=ResultFormat.SIM_DATA),
    )
    return make_test_result(
        component="opamp_core_v3",
        category="char",
        purpose="output_swing",
        metrics={
            "vout_low_actual": op_scalar(low, "v(xtop.vout)"),
            "vout_high_actual": op_scalar(high, "v(xtop.vout)"),
        },
    )


def run_output_drive_test(dut_params: OpampCoreParams | None = None, tb_params: OpampCoreFollowerTbParams | None = None, *, corner=h.pdk.Corner.TYP):
    dut_params = dut_params or OpampCoreParams()
    tb_params = tb_params or OpampCoreFollowerTbParams()
    source = run_ngspice_sim(
        _build_follower_op_tb(
            dut_params,
            vdd=float(tb_params.vdd),
            vin=float(tb_params.vout_low_target),
            c_load=float(tb_params.c_load),
            r_probe=float(tb_params.r_probe),
            en_voltage=float(tb_params.vdd),
            temp_c=float(tb_params.temp_c),
            corner=corner,
            current_load_uA=float(tb_params.drive_current_uA),
            load_mode="source",
        ),
        unique_ngspice_options("opamp_core_v3_output_drive_source", fmt=ResultFormat.SIM_DATA),
    )
    sink = run_ngspice_sim(
        _build_follower_op_tb(
            dut_params,
            vdd=float(tb_params.vdd),
            vin=float(tb_params.vout_high_target),
            c_load=float(tb_params.c_load),
            r_probe=float(tb_params.r_probe),
            en_voltage=float(tb_params.vdd),
            temp_c=float(tb_params.temp_c),
            corner=corner,
            current_load_uA=float(tb_params.drive_current_uA),
            load_mode="sink",
        ),
        unique_ngspice_options("opamp_core_v3_output_drive_sink", fmt=ResultFormat.SIM_DATA),
    )
    return make_test_result(
        component="opamp_core_v3",
        category="char",
        purpose="output_drive",
        metrics={
            "requested_source_load_uA": float(tb_params.drive_current_uA),
            "requested_sink_load_uA": float(tb_params.drive_current_uA),
            "vout_source": op_scalar(source, "v(xtop.vout)"),
            "vout_sink": op_scalar(sink, "v(xtop.vout)"),
        },
    )


def run_disabled_leakage_test(dut_params: OpampCoreParams | None = None, tb_params: OpampCoreDisabledTbParams | None = None, *, corner=h.pdk.Corner.TYP):
    dut_params = dut_params or OpampCoreParams()
    tb_params = tb_params or OpampCoreDisabledTbParams()
    result = run_ngspice_sim(
        _build_follower_op_tb(dut_params, vdd=float(tb_params.vdd), vin=float(tb_params.v_cm), c_load=float(tb_params.c_load), r_probe=float(tb_params.r_probe), en_voltage=0.0, temp_c=float(tb_params.temp_c), corner=corner),
        unique_ngspice_options("opamp_core_v3_disabled_leakage", fmt=ResultFormat.SIM_DATA),
    )
    iq_abs = abs(op_scalar(result, "i(v.xtop.vvvdd)"))
    return make_test_result(
        component="opamp_core_v3",
        category="char",
        purpose="disabled_leakage",
        metrics={
            "disabled_leakage_nA": 1e9 * iq_abs,
            "vout_disabled_dc": op_scalar(result, "v(xtop.vout)"),
        },
    )


def _build_input_offset_tb(
    dut_params: OpampCoreParams,
    *,
    vdd: float,
    vin: float,
    c_load: float,
    r_probe: float,
    temp_c: float,
    model_section: str,
) -> Sim:
    install = require_sky130_install()
    dut = opamp_core(dut_params)

    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, en, vdd_sig = h.Signals(5)
        vvdd = h.Vdc(dc=vdd)(p=vdd_sig, n=VSS)
        ven = h.Vdc(dc=vdd)(p=en, n=VSS)
        # Keep the MC offset fixture sign-identical to the nominal follower bench:
        # drive VINP with the target DC level and return VOUT to VINN.
        vvinp = h.Vdc(dc=vin)(p=vinp_sig, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinn_sig)
        cload = h.Cap(c=c_load)(p=vout, n=VSS)
        rload = h.Res(r=r_probe)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, EN=en, VDD=vdd_sig, VSS=VSS)

    return Sim(
        tb=Tb,
        attrs=[
            Op(),
            Save("v(xtop.vinp_sig), v(xtop.vinn_sig), v(xtop.vout), i(v.xtop.vvvdd)"),
            h.sim.Literal(f".temp {temp_c}"),
            h.sim.Lib(install.pdk_path / install.lib_path, model_section),
        ],
    )


def run_input_referred_offset_test(
    dut_params: OpampCoreParams | None = None,
    tb_params: OpampCoreFollowerTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    dut_params = dut_params or OpampCoreParams()
    tb_params = tb_params or OpampCoreFollowerTbParams()
    result = run_ngspice_sim(
        _build_follower_op_tb(
            dut_params,
            vdd=float(tb_params.vdd),
            vin=float(tb_params.vout_mid_target),
            c_load=float(tb_params.c_load),
            r_probe=float(tb_params.r_probe),
            en_voltage=float(tb_params.vdd),
            temp_c=float(tb_params.temp_c),
            corner=corner,
        ),
        unique_ngspice_options("opamp_core_v3_input_offset", fmt=ResultFormat.SIM_DATA),
    )
    vin = float(tb_params.vout_mid_target)
    vout = op_scalar(result, "v(xtop.vout)")
    iq_abs = abs(op_scalar(result, "i(v.xtop.vvvdd)"))
    vos_v = vout - vin
    return make_test_result(
        component="opamp_core_v3",
        category="char",
        purpose="input_referred_offset",
        metrics={
            "vin_dc": vin,
            "vout_dc": vout,
            "input_referred_offset_uV": 1e6 * vos_v,
            "input_referred_offset_abs_uV": 1e6 * abs(vos_v),
            "iq_uA": 1e6 * iq_abs,
        },
    )


def run_input_offset_monte_carlo(
    dut_params: OpampCoreParams | None = None,
    tb_params: OpampCoreFollowerTbParams | None = None,
    *,
    samples: int = 200,
    model_section: str = "tt_mm",
):
    dut_params = dut_params or OpampCoreParams()
    tb_params = tb_params or OpampCoreFollowerTbParams()
    if samples <= 0:
        raise ValueError("samples must be positive")

    vin = float(tb_params.vout_mid_target)
    offset_vals_uV: list[float] = []
    iq_vals_uA: list[float] = []
    failures = 0
    sample_errors: list[str] = []

    for _ in range(samples):
        try:
            result = run_ngspice_sim(
                _build_input_offset_tb(
                    dut_params,
                    vdd=float(tb_params.vdd),
                    vin=vin,
                    c_load=float(tb_params.c_load),
                    r_probe=float(tb_params.r_probe),
                    temp_c=float(tb_params.temp_c),
                    model_section=model_section,
                ),
                unique_ngspice_options("opamp_core_v3_input_offset_mc", fmt=ResultFormat.SIM_DATA),
            )
            vout = op_scalar(result, "v(xtop.vout)")
            iq_abs = abs(op_scalar(result, "i(v.xtop.vvvdd)"))
            offset_vals_uV.append(1e6 * (vout - vin))
            iq_vals_uA.append(1e6 * iq_abs)
        except Exception as exc:
            failures += 1
            if len(sample_errors) < 5:
                sample_errors.append(f"{type(exc).__name__}: {exc}")

    if not offset_vals_uV:
        raise RuntimeError("All Monte Carlo offset samples failed")

    abs_vals = [abs(v) for v in offset_vals_uV]
    percentiles = np.percentile(np.asarray(abs_vals, dtype=float), [50, 90, 95, 99])
    target = OpampAzV3TargetSpec()
    maximum = OpampAzV3MaximumSpec()
    pass_target = sum(v <= target.residual_offset_uV_max for v in abs_vals)
    pass_maximum = sum(v <= maximum.residual_offset_uV_max for v in abs_vals)
    metrics = {
        "samples_requested": int(samples),
        "samples_completed": int(len(offset_vals_uV)),
        "samples_failed": int(failures),
        "model_section": model_section,
        "input_referred_offset_mean_uV": float(np.mean(offset_vals_uV)),
        "input_referred_offset_sigma_uV": float(np.std(offset_vals_uV)),
        "input_referred_offset_abs_mean_uV": float(np.mean(abs_vals)),
        "input_referred_offset_abs_max_uV": float(np.max(abs_vals)),
        "input_referred_offset_abs_p50_uV": float(percentiles[0]),
        "input_referred_offset_abs_p90_uV": float(percentiles[1]),
        "input_referred_offset_abs_p95_uV": float(percentiles[2]),
        "input_referred_offset_abs_p99_uV": float(percentiles[3]),
        "input_referred_offset_pass_rate_vs_250uV": float(pass_target) / float(len(abs_vals)),
        "input_referred_offset_pass_rate_vs_150uV": float(pass_maximum) / float(len(abs_vals)),
        "iq_mean_uA": float(np.mean(iq_vals_uA)),
        "sample_errors": sample_errors,
    }
    return make_test_result(
        component="opamp_core_v3",
        category="mc",
        purpose="input_referred_offset",
        metrics=metrics,
        passed=bool(metrics["input_referred_offset_pass_rate_vs_250uV"] >= 0.99),
    )


def run_fast_checks(dut_params: OpampCoreParams | None = None):
    dut_params = dut_params or OpampCoreParams()
    return {
        "structural": make_test_result(component="opamp_core_v3", category="smoke", purpose="basic", metrics=run_structural_checks(dut_params), passed=True),
        "open_loop": run_open_loop_test(dut_params),
    }


def _find_op_value_by_suffix(result, suffix: str) -> float:
    op = getattr(result.an[0], "op", result.an[0])
    if not isinstance(getattr(op, "data", None), dict):
        raise RuntimeError("Unsupported OP result shape for suffix lookup")
    suffix = suffix.lower()
    for name, value in op.data.items():
        if name.lower().endswith(suffix):
            return float(value)
    raise RuntimeError(f"Signal suffix {suffix} not found in OP result")


def _build_disable_diag_tb(
    dut_params: OpampCoreParams,
    *,
    vdd: float,
    v_cm: float,
    c_load: float,
    r_probe: float,
    temp_c: float,
    corner,
    save_all: bool = True,
) -> Sim:
    install = require_sky130_install()
    dut = opamp_core(dut_params)

    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, en, vdd_sig = h.Signals(5)
        vvdd = h.Vdc(dc=vdd)(p=vdd_sig, n=VSS)
        ven = h.Vdc(dc=0.0)(p=en, n=VSS)
        vvinn = h.Vdc(dc=v_cm)(p=vinn_sig, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinp_sig)
        cload = h.Cap(c=c_load)(p=vout, n=VSS)
        rload = h.Res(r=r_probe)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, EN=en, VDD=vdd_sig, VSS=VSS)

    save_attr = Save("all") if save_all else Save("i(v.xtop.vvvdd), v(xtop.vout)")
    return Sim(tb=Tb, attrs=[Op(), save_attr, h.sim.Literal(f".temp {temp_c}"), install.include(corner)])


def run_disable_nodes_test(
    dut_params: OpampCoreParams | None = None,
    tb_params: OpampCoreDisabledTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    dut_params = dut_params or OpampCoreParams()
    debug_params = dut_params if bool(dut_params.debug_current_probes) else _core_params_with(dut_params, debug_current_probes=True)
    tb_params = tb_params or OpampCoreDisabledTbParams()
    result = run_ngspice_sim(
        _build_disable_diag_tb(
            debug_params,
            vdd=float(tb_params.vdd),
            v_cm=float(tb_params.v_cm),
            c_load=float(tb_params.c_load),
            r_probe=float(tb_params.r_probe),
            temp_c=float(tb_params.temp_c),
            corner=corner,
        ),
        unique_ngspice_options("opamp_core_v3_disable_diag", fmt=ResultFormat.SIM_DATA),
    )
    iq_abs = abs(op_scalar(result, "i(v.xtop.vvvdd)"))
    metrics = {
        "disabled_leakage_nA": 1e9 * iq_abs,
        "vout_disabled_dc": _find_op_value_by_suffix(result, "v(xtop.vout)"),
        "vbp1_dc": _find_op_value_by_suffix(result, "v(xtop.xxdut.vbp1)"),
        "ibias1_dc": _find_op_value_by_suffix(result, "v(xtop.xxdut.ibias1)"),
        "tail1_dc": _find_op_value_by_suffix(result, "v(xtop.xxdut.tail1)"),
        "ibias2_dc": _find_op_value_by_suffix(result, "v(xtop.xxdut.ibias2)"),
        "vx_dc": _find_op_value_by_suffix(result, "v(xtop.xxdut.vx)"),
        "vref_dc": _find_op_value_by_suffix(result, "v(xtop.xxdut.vref)"),
        "vdrv_dc": _find_op_value_by_suffix(result, "v(xtop.xxdut.vdrv)"),
        "gp_dc": _find_op_value_by_suffix(result, "v(xtop.xxdut.gp)"),
        "vss_bias1_dc": _find_op_value_by_suffix(result, "v(xtop.xxdut.vss_bias1)"),
        "vss_bias2_dc": _find_op_value_by_suffix(result, "v(xtop.xxdut.vss_bias2)"),
        "i_probe_tail1_nA": 1e9 * _find_op_value_by_suffix(result, "i(v.xtop.xxdut.vvprobe_tail1)"),
        "i_probe_vx_nA": 1e9 * _find_op_value_by_suffix(result, "i(v.xtop.xxdut.vvprobe_vx)"),
        "i_probe_vref_nA": 1e9 * _find_op_value_by_suffix(result, "i(v.xtop.xxdut.vvprobe_vref)"),
        "i_probe_vdrv_nA": 1e9 * _find_op_value_by_suffix(result, "i(v.xtop.xxdut.vvprobe_vdrv)"),
        "i_probe_stage2_p_nA": 1e9 * _find_op_value_by_suffix(result, "i(v.xtop.xxdut.vvprobe_stage2_p)"),
        "i_probe_stage2_n_nA": 1e9 * _find_op_value_by_suffix(result, "i(v.xtop.xxdut.vvprobe_stage2_n)"),
        "i_probe_stage2_off_nA": 1e9 * _find_op_value_by_suffix(result, "i(v.xtop.xxdut.vvprobe_stage2_off)"),
        "i_probe_vdrv_out_nA": 1e9 * _find_op_value_by_suffix(result, "i(v.xtop.xxdut.vvprobe_vdrv_out)"),
        "i_probe_vdrv_gp_nA": 1e9 * _find_op_value_by_suffix(result, "i(v.xtop.xxdut.vvprobe_vdrv_gp)"),
    }
    return make_test_result(component="opamp_core_v3", category="char", purpose="disable_nodes", metrics=metrics)


def run_disabled_leakage_shutdown_fixture_test(
    dut_params: OpampCoreParams | None = None,
    tb_params: OpampCoreDisabledTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    dut_params = dut_params or OpampCoreParams()
    tb_params = tb_params or OpampCoreDisabledTbParams()
    result = run_ngspice_sim(
        _build_disable_diag_tb(
            dut_params,
            vdd=float(tb_params.vdd),
            v_cm=float(tb_params.v_cm),
            c_load=float(tb_params.c_load),
            r_probe=float(tb_params.r_probe),
            temp_c=float(tb_params.temp_c),
            corner=corner,
            save_all=False,
        ),
        unique_ngspice_options("opamp_core_v3_disabled_leakage_structured", fmt=ResultFormat.SIM_DATA),
    )
    iq_abs = abs(op_scalar(result, "i(v.xtop.vvvdd)"))
    return make_test_result(
        component="opamp_core_v3",
        category="char",
        purpose="disabled_leakage_structured",
        metrics={
            "disabled_leakage_nA": 1e9 * iq_abs,
            "vout_disabled_dc": op_scalar(result, "v(xtop.vout)"),
        },
    )


def run_loop_stability_debug(
    dut_params: OpampCoreParams | None = None,
    tb_params: OpampCoreFollowerTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    dut_params = dut_params or OpampCoreParams()
    tb_params = tb_params or OpampCoreFollowerTbParams()
    ac_result = run_ngspice_sim(
        _build_follower_ac_tb(
            dut_params,
            vdd=float(tb_params.vdd),
            vin=float(tb_params.vout_mid_target),
            c_load=float(tb_params.c_load),
            r_probe=float(tb_params.r_probe),
            en_voltage=float(tb_params.vdd),
            f_start=float(tb_params.f_start),
            f_stop=float(tb_params.f_stop),
            npts=int(tb_params.npts),
            temp_c=float(tb_params.temp_c),
            corner=corner,
        ),
        unique_ngspice_options("opamp_core_v3_closed_loop_stability_debug", fmt=ResultFormat.SIM_DATA),
    )
    freq, vout_amp = extract_ac_trace(ac_result, "v(xtop.vout)")
    _, vin_amp = extract_ac_trace(ac_result, "v(xtop.vinp_sig)")
    freq = np.asarray(freq, dtype=float)
    vout_amp = np.asarray(vout_amp)
    vin_amp = np.asarray(vin_amp)
    closed_loop_gain = vout_amp / np.where(np.abs(vin_amp) > 1e-30, vin_amp, 1e-30 + 0j)
    loop_gain = closed_loop_gain / np.where(np.abs(1.0 - closed_loop_gain) > 1e-30, 1.0 - closed_loop_gain, 1e-30 + 0j)
    loop_mag = np.abs(loop_gain)
    loop_mag_db = 20.0 * np.log10(np.maximum(loop_mag, 1e-30))
    closed_mag_db = 20.0 * np.log10(np.maximum(np.abs(closed_loop_gain), 1e-30))
    phase_deg, _ = negative_feedback_phase_trace(loop_gain)
    return make_test_result(
        component="opamp_core_v3",
        category="char",
        purpose="loop_stability_debug",
        metrics={
            "freq_hz": freq.tolist(),
            "closed_loop_mag_db": closed_mag_db.tolist(),
            "loop_mag_db": loop_mag_db.tolist(),
            "loop_phase_deg": phase_deg.tolist(),
        },
    )


def run_full_characterization(
    dut_params: OpampCoreParams | None = None,
    *,
    vdds: tuple[float, ...] = (1.6, 1.8, 1.98),
    temps: tuple[float, ...] = (-40.0, 27.0, 125.0),
):
    dut_params = dut_params or OpampCoreParams()
    corners = {"TT": h.pdk.Corner.TYP, "FF": h.pdk.Corner.FAST, "SS": h.pdk.Corner.SLOW}
    cases: dict[str, dict[str, dict[str, float]]] = {}
    for cname, corner in corners.items():
        for vdd in vdds:
            for temp_c in temps:
                label = f"{cname}_V{vdd:.2f}_T{temp_c:.0f}C"
                open_loop_tb = OpampCoreOpenLoopTbParams(
                    vdd=vdd,
                    c_load=1e-12,
                    r_probe=1e12,
                    v_cm=0.5 * vdd,
                    dc_v_diff=100e-6,
                    f_start=1.0,
                    f_stop=1e9,
                    npts=40,
                    temp_c=temp_c,
                )
                follower_tb = OpampCoreFollowerTbParams(
                    vdd=vdd,
                    c_load=1e-12,
                    r_probe=1e12,
                    vout_low_target=0.1,
                    vout_high_target=min_required_output_high(vdd),
                    vout_mid_target=0.5 * vdd,
                    drive_current_uA=20.0,
                    f_start=1.0,
                    f_stop=1e9,
                    npts=40,
                    temp_c=temp_c,
                )
                disabled_tb = OpampCoreDisabledTbParams(
                    vdd=vdd,
                    c_load=1e-12,
                    r_probe=1e12,
                    v_cm=0.5 * vdd,
                    temp_c=temp_c,
                )
                cases[label] = {
                    "open_loop": run_open_loop_test(dut_params, open_loop_tb, corner=corner)["metrics"],
                    "swing": run_output_swing_test(dut_params, follower_tb, corner=corner)["metrics"],
                    "drive": run_output_drive_test(dut_params, follower_tb, corner=corner)["metrics"],
                    "leakage": run_disabled_leakage_shutdown_fixture_test(dut_params, disabled_tb, corner=corner)["metrics"],
                }
    return make_test_result(
        component="opamp_core_v3",
        category="char",
        purpose="full_characterization",
        metrics={"cases": cases},
    )


def summarize_full_characterization(result: dict):
    cases = result["metrics"]["cases"]
    target = OpampAzV3TargetSpec()
    maximum = OpampAzV3MaximumSpec()

    aol_vals = []
    gbw_vals = []
    pm_vals = []
    gm_vals = []
    iq_vals = []
    low_vals = []
    high_margin_min_vals = []
    high_margin_max_vals = []
    source_vals = []
    sink_vals = []
    leak_vals = []

    for label, case in cases.items():
        ol = case["open_loop"]
        sw = case["swing"]
        dr = case["drive"]
        lk = case["leakage"]
        vdd = float(label.split("_V")[1].split("_T")[0])
        aol_vals.append((label, float(ol["aol_db"])))
        gbw_vals.append((label, float(ol["gbw_hz"])))
        pm_vals.append((label, float(ol["phase_margin_deg"])))
        gm_vals.append((label, float(ol["gain_margin_db"])))
        iq_vals.append((label, float(ol["iq_uA"])))
        low_vals.append((label, float(sw["vout_low_actual"])))
        high_margin_min_vals.append((label, float(sw["vout_high_actual"]) - min_required_output_high(vdd)))
        high_margin_max_vals.append((label, float(sw["vout_high_actual"]) - max_required_output_high(vdd)))
        source_vals.append((label, float(dr["vout_source"])))
        sink_vals.append((label, float(dr["vout_sink"])))
        leak_vals.append((label, float(lk["disabled_leakage_nA"])))

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "worst_aol_db": min(aol_vals, key=lambda x: x[1]),
        "worst_gbw_hz": min(gbw_vals, key=lambda x: x[1]),
        "best_gbw_hz": max(gbw_vals, key=lambda x: x[1]),
        "worst_phase_margin_deg": min(pm_vals, key=lambda x: x[1]),
        "worst_gain_margin_db": min(gm_vals, key=lambda x: x[1]),
        "worst_iq_uA": max(iq_vals, key=lambda x: x[1]),
        "worst_vout_low_actual": max(low_vals, key=lambda x: x[1]),
        "worst_high_margin_min": min(high_margin_min_vals, key=lambda x: x[1]),
        "worst_high_margin_max": min(high_margin_max_vals, key=lambda x: x[1]),
        "worst_vout_source": min(source_vals, key=lambda x: x[1]),
        "worst_vout_sink": min(sink_vals, key=lambda x: x[1]),
        "worst_disabled_leakage_nA": max(leak_vals, key=lambda x: x[1]),
        "requirements": {
            "minimum": target.__dict__,
            "maximum": maximum.__dict__,
        },
    }
    return summary


def render_full_characterization_report(result: dict, summary: dict) -> str:
    min_spec = OpampAzV3TargetSpec()
    max_spec = OpampAzV3MaximumSpec()

    def fmt_num(value: float, digits: int = 3) -> str:
        if math.isnan(value):
            return "NaN"
        return f"{value:.{digits}f}"

    rows = [
        ("Open-loop gain (dB)", f">= {min_spec.aol_db_min}", f">= {max_spec.aol_db_min}", f"{fmt_num(summary['worst_aol_db'][1])} @ {summary['worst_aol_db'][0]}"),
        ("GBW low bound (Hz)", f">= {int(min_spec.gbw_hz_min)}", f">= {int(max_spec.gbw_hz_min)}", f"{fmt_num(summary['worst_gbw_hz'][1], 1)} @ {summary['worst_gbw_hz'][0]}"),
        ("GBW high bound (Hz)", f"<= {int(min_spec.gbw_hz_max)}", f"<= {int(max_spec.gbw_hz_max)}", f"{fmt_num(summary['best_gbw_hz'][1], 1)} @ {summary['best_gbw_hz'][0]}"),
        ("Phase margin (deg)", f">= {min_spec.phase_margin_deg_min}", f">= {max_spec.phase_margin_deg_min}", f"{fmt_num(summary['worst_phase_margin_deg'][1])} @ {summary['worst_phase_margin_deg'][0]}"),
        ("Gain margin (dB)", f">= {min_spec.gain_margin_db_min}", f">= {max_spec.gain_margin_db_min}", f"{fmt_num(summary['worst_gain_margin_db'][1])} @ {summary['worst_gain_margin_db'][0]}"),
        ("Quiescent current (uA)", f"<= {min_spec.iq_uA_max}", f"<= {max_spec.iq_uA_max}", f"{fmt_num(summary['worst_iq_uA'][1])} @ {summary['worst_iq_uA'][0]}"),
        ("Output low swing (V)", f"<= {min_spec.output_swing_low_max_v}", f"<= {max_spec.output_swing_low_max_v}", f"{fmt_num(summary['worst_vout_low_actual'][1])} @ {summary['worst_vout_low_actual'][0]}"),
        ("Output high swing margin vs min spec (V)", ">= 0.0", ">= n/a", f"{fmt_num(summary['worst_high_margin_min'][1])} @ {summary['worst_high_margin_min'][0]}"),
        ("Output high swing margin vs max spec (V)", "n/a", ">= 0.0", f"{fmt_num(summary['worst_high_margin_max'][1])} @ {summary['worst_high_margin_max'][0]}"),
        ("Output source VOUT @ +20uA (V)", "characterization", "characterization", f"{fmt_num(summary['worst_vout_source'][1])} @ {summary['worst_vout_source'][0]}"),
        ("Output sink VOUT @ -20uA (V)", "characterization", "characterization", f"{fmt_num(summary['worst_vout_sink'][1])} @ {summary['worst_vout_sink'][0]}"),
        ("Disabled leakage (nA)", f"<= {min_spec.disabled_leakage_nA_max}", f"<= {max_spec.disabled_leakage_nA_max}", f"{fmt_num(summary['worst_disabled_leakage_nA'][1])} @ {summary['worst_disabled_leakage_nA'][0]}"),
    ]

    lines = [
        "# opamp/v3 Full Characterization Report",
        "",
        f"Generated at: `{summary['generated_at_utc']}`",
        "",
        "## Requirement Summary",
        "",
        "| Requirement | Min Value | Max Value | Actual |",
        "|---|---:|---:|---:|",
    ]
    for name, min_req, max_req, actual in rows:
        lines.append(f"| {name} | `{min_req}` | `{max_req}` | `{actual}` |")

    lines += [
        "",
        "## Notes",
        "",
        "- `Actual` uses worst-case measured values across the full `TT/FF/SS x VDD x Temp` sweep.",
        "- Output high-swing requirements are supply-relative. The report therefore uses worst-case margin to the required high-swing target.",
        "- Output current is characterized as resulting `VOUT` under forced `+20 uA` and `-20 uA` load conditions.",
        "",
        "## Case Data",
        "",
        "| Case | AOL (dB) | GBW (Hz) | PM (deg) | GM (dB) | IQ (uA) | Vlow (V) | Vhigh (V) | Vsrc (V) | Vsink (V) | Ileak (nA) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, case in sorted(result["metrics"]["cases"].items()):
        ol = case["open_loop"]
        sw = case["swing"]
        dr = case["drive"]
        lk = case["leakage"]
        lines.append(
            f"| {label} | {fmt_num(float(ol['aol_db']))} | {fmt_num(float(ol['gbw_hz']),1)} | {fmt_num(float(ol['phase_margin_deg']))} | "
            f"{fmt_num(float(ol['gain_margin_db']))} | {fmt_num(float(ol['iq_uA']))} | {fmt_num(float(sw['vout_low_actual']))} | "
            f"{fmt_num(float(sw['vout_high_actual']))} | {fmt_num(float(dr['vout_source']))} | {fmt_num(float(dr['vout_sink']))} | {fmt_num(float(lk['disabled_leakage_nA']),1)} |"
        )
    return "\n".join(lines)


from .opamp_core import run_structural_checks
