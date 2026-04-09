from pathlib import Path
import math
import re

import hdl21 as h
import numpy as np
from hdl21.sim import Ac, LogSweep, Op, Save, SaveMode, Sim, Tran
from vlsirtools.spice import ResultFormat, SimOptions

from .bias_gen import run_current_accuracy_test
from .common import (
    default_ngspice_options,
    extract_ac_trace,
    extract_ac_trace_suffix,
    extract_subckt_name,
    interp_crossing,
    interp_value,
    make_test_result,
    negative_feedback_phase_trace,
    op_scalar,
    op_scalar_suffix,
    print_metrics_table,
    require_sky130_install,
    run_ngspice_sim,
    tran_waveform,
    unique_ngspice_options,
)
from .opamp_core import (
    OpampCoreClosedLoopStepTbParams,
    OpampCoreDisabledTbParams,
    OpampCoreFollowerTbParams,
    OpampCoreOpenLoopTbParams,
    OpampCoreParams,
    opamp_core,
)

def _build_open_loop_tb(
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
        vvinp = h.Vdc(dc=v_cm)(p=vinp_sig, n=VSS)
        vtest = h.Vdc(dc=0.0, ac=1.0)(p=vout, n=vinn_sig)
        lbreak = h.Ind(l=1e9)(p=vout, n=vinn_sig)
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


def _build_open_loop_op_tb(
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
        vtest = h.Vdc(dc=0.0)(p=vout, n=vinn_sig)
        lbreak = h.Ind(l=1e9)(p=vout, n=vinn_sig)
        cload = h.Cap(c=c_load)(p=vout, n=VSS)
        rload = h.Res(r=r_probe)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, EN=en, VDD=vdd_sig, VSS=VSS)

    return Sim(
        tb=Tb,
        attrs=[
            Op(),
            Save("i(v.xtop.vvvdd), v(xtop.vout), v(xtop.vinn_sig), v(xtop.xdut.vx), v(xtop.xdut.vref), v(xtop.xdut.ibias1), v(xtop.xdut.ibias2)"),
            h.sim.Literal(f".temp {temp_c}"),
            install.include(corner),
        ],
    )


def _build_internal_nodes_op_tb(
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
        vtest = h.Vdc(dc=0.0)(p=vout, n=vinn_sig)
        lbreak = h.Ind(l=1e9)(p=vout, n=vinn_sig)
        cload = h.Cap(c=c_load)(p=vout, n=VSS)
        rload = h.Res(r=r_probe)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, EN=en, VDD=vdd_sig, VSS=VSS)

    return Sim(
        tb=Tb,
        attrs=[
            Op(),
            Save(SaveMode.ALL),
            h.sim.Literal(f".temp {temp_c}"),
            install.include(corner),
        ],
    )


def _build_disabled_nodes_op_tb(
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
        ven = h.Vdc(dc=0.0)(p=en, n=VSS)
        vvinp = h.Vdc(dc=v_cm)(p=vinp_sig, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinn_sig)
        cload = h.Cap(c=c_load)(p=vout, n=VSS)
        rload = h.Res(r=r_probe)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, EN=en, VDD=vdd_sig, VSS=VSS)

    return Sim(
        tb=Tb,
        attrs=[
            Op(),
            Save(SaveMode.ALL),
            h.sim.Literal(f".temp {temp_c}"),
            install.include(corner),
        ],
    )


def _build_direct_gain_op_tb(
    dut_params: OpampCoreParams,
    *,
    vdd: float,
    c_load: float,
    r_probe: float,
    v_cm: float,
    v_diff: float,
    save_node: str,
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
        vvinp = h.Vdc(dc=v_cm + 0.5 * v_diff)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=v_cm - 0.5 * v_diff)(p=vinn_sig, n=VSS)
        cload = h.Cap(c=c_load)(p=vout, n=VSS)
        rload = h.Res(r=r_probe)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, EN=en, VDD=vdd_sig, VSS=VSS)

    return Sim(
        tb=Tb,
        attrs=[
            Op(),
            Save(f"i(v.xtop.vvvdd), v(xtop.{save_node})"),
            h.sim.Literal(f".temp {temp_c}"),
            install.include(corner),
        ],
    )


def _build_direct_gain_ac_tb(
    dut_params: OpampCoreParams,
    *,
    vdd: float,
    c_load: float,
    r_probe: float,
    v_cm: float,
    v_diff: float,
    save_node: str,
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
        vvinp = h.Vdc(dc=v_cm, ac=0.5 * v_diff)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=v_cm, ac=-0.5 * v_diff)(p=vinn_sig, n=VSS)
        cload = h.Cap(c=c_load)(p=vout, n=VSS)
        rload = h.Res(r=r_probe)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, EN=en, VDD=vdd_sig, VSS=VSS)

    return Sim(
        tb=Tb,
        attrs=[
            Ac(sweep=LogSweep(1.0, 10.0, 2)),
            Save(f"v(xtop.{save_node})"),
            h.sim.Literal(f".temp {temp_c}"),
            install.include(corner),
        ],
    )


def _build_internal_direct_gain_ac_tb(
    dut_params: OpampCoreParams,
    *,
    vdd: float,
    c_load: float,
    r_probe: float,
    v_cm: float,
    v_diff: float,
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
        vvinp = h.Vdc(dc=v_cm, ac=0.5 * v_diff)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=v_cm, ac=-0.5 * v_diff)(p=vinn_sig, n=VSS)
        cload = h.Cap(c=c_load)(p=vout, n=VSS)
        rload = h.Res(r=r_probe)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, EN=en, VDD=vdd_sig, VSS=VSS)

    return Sim(
        tb=Tb,
        attrs=[
            Ac(sweep=LogSweep(1.0, 10.0, 2)),
            Save(SaveMode.ALL),
            h.sim.Literal(f".temp {temp_c}"),
            install.include(corner),
        ],
    )


def _build_internal_direct_gain_op_tb(
    dut_params: OpampCoreParams,
    *,
    vdd: float,
    c_load: float,
    r_probe: float,
    v_cm: float,
    v_diff: float,
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
        vvinp = h.Vdc(dc=v_cm + 0.5 * v_diff)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=v_cm - 0.5 * v_diff)(p=vinn_sig, n=VSS)
        cload = h.Cap(c=c_load)(p=vout, n=VSS)
        rload = h.Res(r=r_probe)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, EN=en, VDD=vdd_sig, VSS=VSS)

    return Sim(
        tb=Tb,
        attrs=[
            Op(),
            Save(SaveMode.ALL),
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

    return Sim(
        tb=Tb,
        attrs=[
            Op(),
            Save("i(v.xtop.vvvdd), v(xtop.vout)"),
            h.sim.Literal(f".temp {temp_c}"),
            install.include(corner),
        ],
    )


def build_open_loop_test(
    dut_params: OpampCoreParams,
    tb_params: OpampCoreOpenLoopTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    tb_params = tb_params or OpampCoreOpenLoopTbParams()
    return _build_open_loop_tb(
        dut_params,
        vdd=float(tb_params.vdd),
        c_load=float(tb_params.c_load),
        r_probe=float(tb_params.r_probe),
        v_cm=float(tb_params.v_cm),
        f_start=float(tb_params.f_start),
        f_stop=float(tb_params.f_stop),
        npts=int(tb_params.npts),
        temp_c=float(tb_params.temp_c),
        corner=corner,
    )


def run_direct_dc_gain_test(
    dut_params: OpampCoreParams | None = None,
    tb_params: OpampCoreOpenLoopTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    dut_params = dut_params or OpampCoreParams()
    tb_params = tb_params or OpampCoreOpenLoopTbParams()
    ac_result = run_ngspice_sim(
        _build_direct_gain_ac_tb(
            dut_params,
            vdd=float(tb_params.vdd),
            c_load=float(tb_params.c_load),
            r_probe=float(tb_params.r_probe),
            v_cm=float(tb_params.v_cm),
            v_diff=float(tb_params.dc_v_diff),
            save_node="vout",
            temp_c=float(tb_params.temp_c),
            corner=corner,
        ),
        default_ngspice_options("opamp_core_direct_dc_gain_ac", fmt=ResultFormat.SIM_DATA),
    )
    op_result = run_ngspice_sim(
        _build_direct_gain_op_tb(
            dut_params,
            vdd=float(tb_params.vdd),
            c_load=float(tb_params.c_load),
            r_probe=float(tb_params.r_probe),
            v_cm=float(tb_params.v_cm),
            v_diff=0.0,
            save_node="vout",
            temp_c=float(tb_params.temp_c),
            corner=corner,
        ),
        default_ngspice_options("opamp_core_direct_dc_gain_bias", fmt=ResultFormat.SIM_DATA),
    )
    _, vout_amp = extract_ac_trace(ac_result, "v(xtop.vout)")
    low_freq_vout = complex(np.asarray(vout_amp)[0])
    direct_gain_vv = abs(low_freq_vout) / max(abs(float(tb_params.dc_v_diff)), 1e-18)
    direct_gain_db = 20.0 * math.log10(max(direct_gain_vv, 1e-30))
    iq_abs = abs(op_scalar(op_result, "i(v.xtop.vvvdd)"))
    return make_test_result(
        component="opamp_core",
        category="char",
        purpose="direct_dc_gain",
        metrics={
            "vout_dc": op_scalar(op_result, "v(xtop.vout)"),
            "low_freq_vout_mag": abs(low_freq_vout),
            "direct_gain_vv": direct_gain_vv,
            "direct_gain_db": direct_gain_db,
            "iq_uA": 1e6 * iq_abs,
        },
    )


def run_internal_direct_gain_test(
    dut_params: OpampCoreParams | None = None,
    tb_params: OpampCoreOpenLoopTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    dut_params = dut_params or OpampCoreParams()
    tb_params = tb_params or OpampCoreOpenLoopTbParams()
    ac_result = run_ngspice_sim(
        _build_internal_direct_gain_ac_tb(
            dut_params,
            vdd=float(tb_params.vdd),
            c_load=float(tb_params.c_load),
            r_probe=float(tb_params.r_probe),
            v_cm=float(tb_params.v_cm),
            v_diff=float(tb_params.dc_v_diff),
            temp_c=float(tb_params.temp_c),
            corner=corner,
        ),
        default_ngspice_options("opamp_core_internal_direct_gain_ac", fmt=ResultFormat.SIM_DATA),
    )
    op_result = run_ngspice_sim(
        _build_internal_direct_gain_op_tb(
            dut_params,
            vdd=float(tb_params.vdd),
            c_load=float(tb_params.c_load),
            r_probe=float(tb_params.r_probe),
            v_cm=float(tb_params.v_cm),
            v_diff=0.0,
            temp_c=float(tb_params.temp_c),
            corner=corner,
        ),
        default_ngspice_options("opamp_core_internal_direct_gain_bias", fmt=ResultFormat.SIM_DATA),
    )
    _, vx_amp = extract_ac_trace_suffix(ac_result, ".vx)")
    low_freq_vx = complex(np.asarray(vx_amp)[0])
    direct_gain_vv = abs(low_freq_vx) / max(abs(float(tb_params.dc_v_diff)), 1e-18)
    direct_gain_db = 20.0 * math.log10(max(direct_gain_vv, 1e-30))
    return make_test_result(
        component="opamp_core",
        category="char",
        purpose="internal_direct_gain",
        metrics={
            "vx_dc": op_scalar_suffix(op_result, ".vx)"),
            "low_freq_vx_mag": abs(low_freq_vx),
            "direct_gain_vv": direct_gain_vv,
            "direct_gain_db": direct_gain_db,
        },
    )


def run_direct_dc_gain_sweep_test(
    dut_params: OpampCoreParams | None = None,
    tb_params: OpampCoreOpenLoopTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    vdiff_values: tuple[float, ...] = (1e-3, 1e-4, 1e-5),
):
    dut_params = dut_params or OpampCoreParams()
    base_tb = tb_params or OpampCoreOpenLoopTbParams()
    cases = []
    for vdiff in vdiff_values:
        case_tb = OpampCoreOpenLoopTbParams(
            vdd=base_tb.vdd,
            c_load=base_tb.c_load,
            r_probe=base_tb.r_probe,
            v_cm=base_tb.v_cm,
            v_diff=base_tb.v_diff,
            dc_v_diff=vdiff,
            f_start=base_tb.f_start,
            f_stop=base_tb.f_stop,
            npts=base_tb.npts,
            temp_c=base_tb.temp_c,
        )
        out_gain = run_direct_dc_gain_test(dut_params, case_tb, corner=corner)
        drv_gain = run_internal_direct_gain_test(dut_params, case_tb, corner=corner)
        cases.append(
            {
                "v_diff": float(vdiff),
                "vout_direct_gain_db": float(out_gain["metrics"]["direct_gain_db"]),
                "vout_direct_gain_vv": float(out_gain["metrics"]["direct_gain_vv"]),
                "vdrv_direct_gain_db": float(drv_gain["metrics"]["direct_gain_db"]),
                "vdrv_direct_gain_vv": float(drv_gain["metrics"]["direct_gain_vv"]),
            }
        )
    vout_gains = [case["vout_direct_gain_db"] for case in cases]
    vdrv_gains = [case["vdrv_direct_gain_db"] for case in cases]
    return make_test_result(
        component="opamp_core",
        category="char",
        purpose="direct_dc_gain_sweep",
        metrics={
            "cases": cases,
            "best_direct_gain_db": max(vout_gains),
            "worst_direct_gain_db": min(vout_gains),
            "best_internal_direct_gain_db": max(vdrv_gains),
            "worst_internal_direct_gain_db": min(vdrv_gains),
        },
    )


def _build_follower_ac_tb(
    dut_params: OpampCoreParams,
    *,
    vdd: float,
    vin: float,
    c_load: float,
    r_probe: float,
    en_voltage: float,
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
        ven = h.Vdc(dc=en_voltage)(p=en, n=VSS)
        vvinp = h.Vdc(dc=vin, ac=1.0)(p=vinp_sig, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinn_sig)
        cload = h.Cap(c=c_load)(p=vout, n=VSS)
        rload = h.Res(r=r_probe)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, EN=en, VDD=vdd_sig, VSS=VSS)

    return Sim(
        tb=Tb,
        attrs=[
            Ac(sweep=LogSweep(f_start, f_stop, npts)),
            Save("v(xtop.vout), v(xtop.vinp_sig)"),
            h.sim.Literal(f".temp {temp_c}"),
            install.include(corner),
        ],
    )


def run_open_loop_test(
    dut_params: OpampCoreParams | None = None,
    tb_params: OpampCoreOpenLoopTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
    include_bias_char: bool = False,
):
    dut_params = dut_params or OpampCoreParams()
    tb_params = tb_params or OpampCoreOpenLoopTbParams()
    direct_gain = run_direct_dc_gain_test(dut_params, tb_params, corner=corner)
    direct_gain_est = float(direct_gain["metrics"]["direct_gain_vv"])
    direct_dc_gain_db = float(direct_gain["metrics"]["direct_gain_db"])
    direct_iq_uA = float(direct_gain["metrics"]["iq_uA"])
    direct_vout_dc = float(direct_gain["metrics"]["vout_dc"])
    follower_tb = OpampCoreFollowerTbParams(
        vdd=float(tb_params.vdd),
        c_load=float(tb_params.c_load),
        r_probe=float(tb_params.r_probe),
        f_start=float(tb_params.f_start),
        f_stop=float(tb_params.f_stop),
        npts=int(tb_params.npts),
        temp_c=float(tb_params.temp_c),
    )
    stability = run_loop_stability_test(dut_params, follower_tb, corner=corner, sim_options=sim_options)
    stability_metrics = stability["metrics"]
    metrics = {
        "gain_est": direct_gain_est,
        "aol_db": direct_dc_gain_db,
        "direct_dc_gain_db": direct_dc_gain_db,
        "gbw_hz": stability_metrics["gbw_hz"],
        "phase_margin_deg": stability_metrics["phase_margin_deg"],
        "gain_margin_db": stability_metrics["gain_margin_db"],
        "phase_at_unity_deg_raw": stability_metrics["phase_at_unity_deg_raw"],
        "low_freq_phase_deg_raw": stability_metrics["low_freq_phase_deg_raw"],
        "iq_uA": direct_iq_uA,
        "direct_vout_dc": direct_vout_dc,
        "ac_fixture_ok": bool(stability_metrics["ac_fixture_ok"]),
    }
    if include_bias_char:
        try:
            bias = run_current_accuracy_test(dut_params.bias_gen_params, corner=corner)
            bias_metrics = bias["metrics"]
        except Exception:
            bias_metrics = {
                "ratio_est": float("nan"),
                "i_ibias1_est": float("nan"),
                "i_ibias2_est": float("nan"),
            }
        metrics["bias_ratio_est"] = bias_metrics["ratio_est"]
        metrics["bias_i1_est"] = bias_metrics["i_ibias1_est"]
        metrics["bias_i2_est"] = bias_metrics["i_ibias2_est"]
    return make_test_result(component="opamp_core", category="char", purpose="open_loop", metrics=metrics)


def run_loop_stability_test(
    dut_params: OpampCoreParams | None = None,
    tb_params: OpampCoreFollowerTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or OpampCoreParams()
    tb_params = tb_params or OpampCoreFollowerTbParams()
    ac_failed = False
    phase_at_unity_deg_raw = float("nan")
    low_freq_phase_deg_raw = float("nan")
    loop_gain_dc_db = float("nan")
    gbw_hz = float("nan")
    phase_margin_deg = float("nan")
    gain_margin_db = float("nan")
    try:
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
            sim_options if sim_options is not None else unique_ngspice_options("opamp_core_closed_loop_stability_ac", fmt=ResultFormat.SIM_DATA),
        )
    except Exception:
        ac_failed = True
        ac_result = None
    op_result = run_ngspice_sim(
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
        unique_ngspice_options("opamp_core_closed_loop_stability_bias", fmt=ResultFormat.SIM_DATA),
    )
    if not ac_failed:
        try:
            freq, vout_amp = extract_ac_trace(ac_result, "v(xtop.vout)")
            _, vin_amp = extract_ac_trace(ac_result, "v(xtop.vinp_sig)")
            freq = np.asarray(freq, dtype=float)
            vout_amp = np.asarray(vout_amp)
            vin_amp = np.asarray(vin_amp)
            closed_loop_gain = vout_amp / np.where(np.abs(vin_amp) > 1e-30, vin_amp, 1e-30 + 0j)
            loop_gain = closed_loop_gain / np.where(np.abs(1.0 - closed_loop_gain) > 1e-30, 1.0 - closed_loop_gain, 1e-30 + 0j)
            mag = np.abs(loop_gain)
            mag_db = 20.0 * np.log10(np.maximum(mag, 1e-30))
            phase_deg, low_freq_phase_deg_raw = negative_feedback_phase_trace(loop_gain)
            loop_gain_dc_db = float(mag_db[0]) if len(mag_db) else float("nan")
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
        except Exception:
            ac_failed = True
    iq_abs = abs(op_scalar(op_result, "i(v.xtop.vvvdd)"))
    return make_test_result(
        component="opamp_core",
        category="char",
        purpose="closed_loop_stability",
        metrics={
            "loop_gain_dc_db": loop_gain_dc_db,
            "gbw_hz": gbw_hz,
            "phase_margin_deg": phase_margin_deg,
            "gain_margin_db": gain_margin_db,
            "phase_at_unity_deg_raw": phase_at_unity_deg_raw,
            "low_freq_phase_deg_raw": low_freq_phase_deg_raw,
            "iq_uA": 1e6 * iq_abs,
            "loop_vout_dc": op_scalar(op_result, "v(xtop.vout)"),
            "ac_fixture_ok": not ac_failed,
        },
    )


def run_open_loop_fast_test(
    dut_params: OpampCoreParams | None = None,
    tb_params: OpampCoreOpenLoopTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
):
    """Fast TT screen for core AC behavior.

    Uses the direct differential-gain bench for AOL plus the loop-break AC bench
    for GBW/ PM/ GM and the matching OP bias-point bench.
    This keeps the runtime low enough for iterative work while preserving one
    consistent public definition of AOL across the codebase.
    """
    dut_params = dut_params or OpampCoreParams()
    tb_params = tb_params or OpampCoreOpenLoopTbParams()
    direct_gain = run_direct_dc_gain_test(dut_params, tb_params, corner=corner)
    direct_dc_gain_db = float(direct_gain["metrics"]["direct_gain_db"])
    follower_tb = OpampCoreFollowerTbParams(
        vdd=float(tb_params.vdd),
        c_load=float(tb_params.c_load),
        r_probe=float(tb_params.r_probe),
        f_start=float(tb_params.f_start),
        f_stop=float(tb_params.f_stop),
        npts=int(tb_params.npts),
        temp_c=float(tb_params.temp_c),
    )
    stability = run_loop_stability_test(dut_params, follower_tb, corner=corner, sim_options=sim_options)
    stability_metrics = stability["metrics"]
    return make_test_result(
        component="opamp_core",
        category="char",
        purpose="open_loop_fast",
        metrics={
            "aol_db": direct_dc_gain_db,
            "direct_dc_gain_db": direct_dc_gain_db,
            "gbw_hz": stability_metrics["gbw_hz"],
            "phase_margin_deg": stability_metrics["phase_margin_deg"],
            "gain_margin_db": stability_metrics["gain_margin_db"],
            "phase_at_unity_deg_raw": stability_metrics["phase_at_unity_deg_raw"],
            "low_freq_phase_deg_raw": stability_metrics["low_freq_phase_deg_raw"],
            "iq_uA": float(direct_gain["metrics"]["iq_uA"]),
            "ac_fixture_ok": bool(stability_metrics["ac_fixture_ok"]),
        },
    )


def run_bias_characterization_test(
    dut_params: OpampCoreParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    dut_params = dut_params or OpampCoreParams()
    result = run_current_accuracy_test(dut_params.bias_gen_params, corner=corner)
    metrics = result["metrics"]
    return make_test_result(
        component="opamp_core",
        category="char",
        purpose="bias_characterization",
        metrics={
            "bias_ratio_est": metrics["ratio_est"],
            "bias_i1_est": metrics["i_ibias1_est"],
            "bias_i2_est": metrics["i_ibias2_est"],
        },
    )


def run_internal_nodes_test(
    dut_params: OpampCoreParams | None = None,
    tb_params: OpampCoreOpenLoopTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or OpampCoreParams()
    tb_params = tb_params or OpampCoreOpenLoopTbParams()
    result = run_ngspice_sim(
        _build_internal_nodes_op_tb(
            dut_params,
            vdd=float(tb_params.vdd),
            c_load=float(tb_params.c_load),
            r_probe=float(tb_params.r_probe),
            v_cm=float(tb_params.v_cm),
            temp_c=float(tb_params.temp_c),
            corner=corner,
        ),
        sim_options if sim_options is not None else unique_ngspice_options("opamp_core_internal_nodes", fmt=ResultFormat.SIM_DATA),
    )
    iq_abs = abs(op_scalar(result, "i(v.xtop.vvvdd)"))
    metrics = {
        "vx_dc": op_scalar_suffix(result, ".vx)"),
        "vref_dc": op_scalar_suffix(result, ".vref)"),
        "ibias1_dc": op_scalar_suffix(result, ".ibias1)"),
        "ibias2_dc": op_scalar_suffix(result, ".ibias2)"),
        "vout_dc": op_scalar(result, "v(xtop.vout)"),
        "iq_uA": 1e6 * iq_abs,
    }
    return make_test_result(component="opamp_core", category="char", purpose="internal_nodes", metrics=metrics)


def run_disable_nodes_test(
    dut_params: OpampCoreParams | None = None,
    tb_params: OpampCoreDisabledTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or OpampCoreParams()
    tb_params = tb_params or OpampCoreDisabledTbParams()
    result = run_ngspice_sim(
        _build_disabled_nodes_op_tb(
            dut_params,
            vdd=float(tb_params.vdd),
            c_load=float(tb_params.c_load),
            r_probe=float(tb_params.r_probe),
            v_cm=float(tb_params.v_cm),
            temp_c=float(tb_params.temp_c),
            corner=corner,
        ),
        sim_options if sim_options is not None else unique_ngspice_options("opamp_core_disable_nodes", fmt=ResultFormat.SIM_DATA),
    )
    iq_abs = abs(op_scalar(result, "i(v.xtop.vvvdd)"))
    metrics = {
        "vx_dc": op_scalar_suffix(result, ".vx)"),
        "vref_dc": op_scalar_suffix(result, ".vref)"),
        "ibias1_dc": op_scalar_suffix(result, ".ibias1)"),
        "ibias2_dc": op_scalar_suffix(result, ".ibias2)"),
        "vbp_dc": op_scalar_suffix(result, ".vbp)"),
        "vout_dc": op_scalar(result, "v(xtop.vout)"),
        "iq_uA": 1e6 * iq_abs,
    }
    return make_test_result(component="opamp_core", category="char", purpose="disable_nodes", metrics=metrics)


def build_closed_loop_step_test(
    dut_params: OpampCoreParams,
    tb_params: OpampCoreClosedLoopStepTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    tb_params = tb_params or OpampCoreClosedLoopStepTbParams()
    install = require_sky130_install()
    dut = opamp_core(dut_params)

    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, en, vdd_sig = h.Signals(5)
        vvdd = h.Vdc(dc=tb_params.vdd)(p=vdd_sig, n=VSS)
        ven = h.Vdc(dc=tb_params.vdd)(p=en, n=VSS)
        vstep = h.Vpulse(v1=0.0, v2=tb_params.v_step, delay=1e-6, rise=100e-9, fall=100e-9, width=tb_params.tstop, period=2 * tb_params.tstop)(p=vinp_sig, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinn_sig)
        cload = h.Cap(c=tb_params.c_load)(p=vout, n=VSS)
        rload = h.Res(r=1e6)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, EN=en, VDD=vdd_sig, VSS=VSS)

    return Sim(
        tb=Tb,
        attrs=[
            Tran(tstop=tb_params.tstop, tstep=tb_params.tstep),
            h.sim.Options(name="method", value="gear"),
            h.sim.Options(name="reltol", value=1e-3),
            Save("v(xtop.vout)"),
            h.sim.Literal(f".temp {float(tb_params.temp_c)}"),
            install.include(corner),
        ],
    )


def run_closed_loop_step_test(
    dut_params: OpampCoreParams | None = None,
    tb_params: OpampCoreClosedLoopStepTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or OpampCoreParams()
    tb_params = tb_params or OpampCoreClosedLoopStepTbParams()
    result = run_ngspice_sim(
        build_closed_loop_step_test(dut_params, tb_params, corner=corner),
        sim_options if sim_options is not None else unique_ngspice_options("opamp_core_closed_loop_step", fmt=ResultFormat.SIM_DATA),
    )
    vout = tran_waveform(result, "v(xtop.vout)")
    vfinal = float(vout[-1])
    vmax = float(max(vout))
    metrics = {
        "vout_final": vfinal,
        "vout_peak": vmax,
        "overshoot": max(vmax - max(float(tb_params.v_step), vfinal), 0.0),
        "target_step": float(tb_params.v_step),
    }
    return make_test_result(
        component="opamp_core",
        category="contract",
        purpose="closed_loop_step",
        metrics=metrics,
        passed=bool(metrics["vout_final"] > 0.0 and metrics["overshoot"] <= metrics["target_step"]),
        margin={"overshoot_margin": metrics["target_step"] - metrics["overshoot"]},
    )


def run_output_swing_test(
    dut_params: OpampCoreParams | None = None,
    tb_params: OpampCoreFollowerTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or OpampCoreParams()
    tb_params = tb_params or OpampCoreFollowerTbParams()
    low_result = run_ngspice_sim(
        _build_follower_op_tb(
            dut_params,
            vdd=float(tb_params.vdd),
            vin=float(tb_params.vout_low_target),
            c_load=float(tb_params.c_load),
            r_probe=float(tb_params.r_probe),
            en_voltage=float(tb_params.vdd),
            temp_c=float(tb_params.temp_c),
            corner=corner,
        ),
        sim_options if sim_options is not None else unique_ngspice_options("opamp_core_output_swing_low", fmt=ResultFormat.SIM_DATA),
    )
    high_result = run_ngspice_sim(
        _build_follower_op_tb(
            dut_params,
            vdd=float(tb_params.vdd),
            vin=float(tb_params.vout_high_target),
            c_load=float(tb_params.c_load),
            r_probe=float(tb_params.r_probe),
            en_voltage=float(tb_params.vdd),
            temp_c=float(tb_params.temp_c),
            corner=corner,
        ),
        unique_ngspice_options("opamp_core_output_swing_high", fmt=ResultFormat.SIM_DATA),
    )
    metrics = {
        "vout_low_target": float(tb_params.vout_low_target),
        "vout_low_actual": op_scalar(low_result, "v(xtop.vout)"),
        "vout_high_target": float(tb_params.vout_high_target),
        "vout_high_actual": op_scalar(high_result, "v(xtop.vout)"),
    }
    return make_test_result(component="opamp_core", category="char", purpose="output_swing", metrics=metrics)


def run_output_drive_test(
    dut_params: OpampCoreParams | None = None,
    tb_params: OpampCoreFollowerTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or OpampCoreParams()
    tb_params = tb_params or OpampCoreFollowerTbParams()
    source_result = run_ngspice_sim(
        _build_follower_op_tb(
            dut_params,
            vdd=float(tb_params.vdd),
            vin=float(tb_params.vout_mid_target),
            c_load=float(tb_params.c_load),
            r_probe=float(tb_params.r_probe),
            en_voltage=float(tb_params.vdd),
            temp_c=float(tb_params.temp_c),
            corner=corner,
            current_load_uA=float(tb_params.drive_current_uA),
            load_mode="source",
        ),
        sim_options if sim_options is not None else unique_ngspice_options("opamp_core_output_drive_source", fmt=ResultFormat.SIM_DATA),
    )
    sink_result = run_ngspice_sim(
        _build_follower_op_tb(
            dut_params,
            vdd=float(tb_params.vdd),
            vin=float(tb_params.vout_mid_target),
            c_load=float(tb_params.c_load),
            r_probe=float(tb_params.r_probe),
            en_voltage=float(tb_params.vdd),
            temp_c=float(tb_params.temp_c),
            corner=corner,
            current_load_uA=float(tb_params.drive_current_uA),
            load_mode="sink",
        ),
        unique_ngspice_options("opamp_core_output_drive_sink", fmt=ResultFormat.SIM_DATA),
    )
    metrics = {
        "requested_source_load_uA": float(tb_params.drive_current_uA),
        "requested_sink_load_uA": float(tb_params.drive_current_uA),
        "vout_source": op_scalar(source_result, "v(xtop.vout)"),
        "vout_sink": op_scalar(sink_result, "v(xtop.vout)"),
        "target_vout": float(tb_params.vout_mid_target),
    }
    return make_test_result(component="opamp_core", category="char", purpose="output_drive", metrics=metrics)


def run_disabled_leakage_test(
    dut_params: OpampCoreParams | None = None,
    tb_params: OpampCoreDisabledTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or OpampCoreParams()
    tb_params = tb_params or OpampCoreDisabledTbParams()
    result = run_ngspice_sim(
        _build_follower_op_tb(
            dut_params,
            vdd=float(tb_params.vdd),
            vin=float(tb_params.v_cm),
            c_load=float(tb_params.c_load),
            r_probe=float(tb_params.r_probe),
            en_voltage=0.0,
            temp_c=float(tb_params.temp_c),
            corner=corner,
        ),
        sim_options if sim_options is not None else unique_ngspice_options("opamp_core_disabled_leakage", fmt=ResultFormat.SIM_DATA),
    )
    iq_abs = abs(op_scalar(result, "i(v.xtop.vvvdd)"))
    metrics = {
        "disabled_leakage_nA": 1e9 * iq_abs,
        "vout_disabled_dc": op_scalar(result, "v(xtop.vout)"),
    }
    return make_test_result(component="opamp_core", category="char", purpose="disabled_leakage", metrics=metrics)


def run_output_current_limit_test(
    dut_params: OpampCoreParams | None = None,
    tb_params: OpampCoreFollowerTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    dut_params = dut_params or OpampCoreParams()
    tb_params = tb_params or OpampCoreFollowerTbParams()
    compliant_low = float(tb_params.vout_low_target)
    compliant_high = float(tb_params.vout_high_target)
    sweep_stop = float(tb_params.drive_sweep_stop_uA)
    sweep_step = float(tb_params.drive_sweep_step_uA)
    currents = np.arange(sweep_step, sweep_stop + 0.5 * sweep_step, sweep_step)

    max_source = 0.0
    max_sink = 0.0

    for current_uA in currents:
        source_result = run_ngspice_sim(
            _build_follower_op_tb(
                dut_params,
                vdd=float(tb_params.vdd),
                vin=float(tb_params.vout_mid_target),
                c_load=float(tb_params.c_load),
                r_probe=float(tb_params.r_probe),
                en_voltage=float(tb_params.vdd),
                temp_c=float(tb_params.temp_c),
                corner=corner,
                current_load_uA=float(current_uA),
                load_mode="source",
            ),
            unique_ngspice_options(f"opamp_core_output_current_source_{current_uA:g}uA", fmt=ResultFormat.SIM_DATA),
        )
        vout_source = op_scalar(source_result, "v(xtop.vout)")
        if compliant_low <= vout_source <= compliant_high:
            max_source = float(current_uA)
        else:
            break

    for current_uA in currents:
        sink_result = run_ngspice_sim(
            _build_follower_op_tb(
                dut_params,
                vdd=float(tb_params.vdd),
                vin=float(tb_params.vout_mid_target),
                c_load=float(tb_params.c_load),
                r_probe=float(tb_params.r_probe),
                en_voltage=float(tb_params.vdd),
                temp_c=float(tb_params.temp_c),
                corner=corner,
                current_load_uA=float(current_uA),
                load_mode="sink",
            ),
            unique_ngspice_options(f"opamp_core_output_current_sink_{current_uA:g}uA", fmt=ResultFormat.SIM_DATA),
        )
        vout_sink = op_scalar(sink_result, "v(xtop.vout)")
        if compliant_low <= vout_sink <= compliant_high:
            max_sink = float(current_uA)
        else:
            break

    return make_test_result(
        component="opamp_core",
        category="char",
        purpose="output_current_limit",
        metrics={
            "max_source_current_uA": max_source,
            "max_sink_current_uA": max_sink,
            "compliant_low_v": compliant_low,
            "compliant_high_v": compliant_high,
        },
    )


def run_output_source_sweep_test(
    dut_params: OpampCoreParams | None = None,
    tb_params: OpampCoreFollowerTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    dut_params = dut_params or OpampCoreParams()
    tb_params = tb_params or OpampCoreFollowerTbParams()
    sweep_stop = float(tb_params.drive_current_uA)
    sweep_step = min(max(float(tb_params.drive_sweep_step_uA), 5.0), sweep_stop)
    currents = np.arange(sweep_step, sweep_stop + 0.5 * sweep_step, sweep_step)
    cases = []
    for current_uA in currents:
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
                current_load_uA=float(current_uA),
                load_mode="source",
            ),
            unique_ngspice_options(f"opamp_core_output_source_sweep_{current_uA:g}uA", fmt=ResultFormat.SIM_DATA),
        )
        cases.append(
            {
                "current_uA": float(current_uA),
                "vout_source": op_scalar(result, "v(xtop.vout)"),
            }
        )
    worst_case = min(cases, key=lambda case: case["vout_source"]) if cases else None
    return make_test_result(
        component="opamp_core",
        category="char",
        purpose="output_source_sweep",
        metrics={
            "cases": cases,
            "worst_vout_source": None if worst_case is None else worst_case["vout_source"],
            "worst_current_uA": None if worst_case is None else worst_case["current_uA"],
        },
    )


def run_load_sweep_test(
    dut_params: OpampCoreParams | None = None,
    tb_params: OpampCoreOpenLoopTbParams | None = None,
):
    dut_params = dut_params or OpampCoreParams()
    tb_params = tb_params or OpampCoreOpenLoopTbParams()
    cases = {}
    worst_aol_db = float("inf")
    worst_phase_margin_deg = float("inf")
    worst_iq_uA = -float("inf")
    for c_load in (0.0, 1e-12, 2e-12):
        case_tb = OpampCoreOpenLoopTbParams(
            vdd=tb_params.vdd,
            c_load=c_load,
            r_probe=tb_params.r_probe,
            v_cm=tb_params.v_cm,
            v_diff=tb_params.v_diff,
            f_start=tb_params.f_start,
            f_stop=tb_params.f_stop,
            npts=tb_params.npts,
            temp_c=tb_params.temp_c,
        )
        result = run_open_loop_test(dut_params, case_tb)
        label = f"c_load_{int(round(c_load * 1e15))}fF"
        cases[label] = result["metrics"]
        worst_aol_db = min(worst_aol_db, float(result["metrics"]["aol_db"]))
        worst_phase_margin_deg = min(worst_phase_margin_deg, float(result["metrics"]["phase_margin_deg"]))
        worst_iq_uA = max(worst_iq_uA, float(result["metrics"]["iq_uA"]))
    return make_test_result(
        component="opamp_core",
        category="char",
        purpose="load_sweep",
        metrics={"cases": cases, "worst_aol_db": worst_aol_db, "worst_phase_margin_deg": worst_phase_margin_deg, "worst_iq_uA": worst_iq_uA},
    )


def run_pvt_test(
    dut_params: OpampCoreParams | None = None,
    tb_params: OpampCoreOpenLoopTbParams | None = None,
):
    dut_params = dut_params or OpampCoreParams()
    tb_params = tb_params or OpampCoreOpenLoopTbParams()
    corners = {"TT": h.pdk.Corner.TYP, "FF": h.pdk.Corner.FAST, "SS": h.pdk.Corner.SLOW}
    vdds = (1.6, 1.8, 1.98)
    temps = (-40.0, 27.0, 125.0)
    cases = {}
    worst_aol_db = float("inf")
    worst_gbw_hz = float("inf")
    worst_phase_margin_deg = float("inf")
    worst_iq_uA = -float("inf")
    for cname, corner in corners.items():
        for vdd in vdds:
            for temp_c in temps:
                case_tb = OpampCoreOpenLoopTbParams(
                    vdd=vdd,
                    c_load=tb_params.c_load,
                    r_probe=tb_params.r_probe,
                    v_cm=min(float(tb_params.v_cm), 0.5 * vdd),
                    v_diff=tb_params.v_diff,
                    f_start=tb_params.f_start,
                    f_stop=tb_params.f_stop,
                    npts=tb_params.npts,
                    temp_c=temp_c,
                )
                result = run_open_loop_test(dut_params, case_tb, corner=corner)
                label = f"{cname}_V{vdd:.2f}_T{temp_c:.0f}C"
                cases[label] = result["metrics"]
                worst_aol_db = min(worst_aol_db, float(result["metrics"]["aol_db"]))
                worst_gbw_hz = min(worst_gbw_hz, float(result["metrics"]["gbw_hz"]))
                worst_phase_margin_deg = min(worst_phase_margin_deg, float(result["metrics"]["phase_margin_deg"]))
                worst_iq_uA = max(worst_iq_uA, float(result["metrics"]["iq_uA"]))
    return make_test_result(
        component="opamp_core",
        category="char",
        purpose="pvt",
        metrics={"cases": cases, "worst_aol_db": worst_aol_db, "worst_gbw_hz": worst_gbw_hz, "worst_phase_margin_deg": worst_phase_margin_deg, "worst_iq_uA": worst_iq_uA},
    )


def run_area_estimate(dut_params: OpampCoreParams | None = None):
    dut_params = dut_params or OpampCoreParams()

    def mos_area(w: float, l: float, nf: int, mult: int, count: int = 1) -> float:
        return float(w) * float(l) * int(nf) * int(mult) * int(count)

    bias = dut_params.bias_gen_params
    gain = dut_params.gain_stage_params
    second = dut_params.second_stage_params
    comp = dut_params.freq_comp_params

    bias_area = (
        mos_area(bias.w_ref, bias.l_ref, bias.nf_ref, bias.m_ref)
        + mos_area(bias.w_out * bias.ratio_stage1, bias.l_out, bias.nf_out, bias.m_out)
        + mos_area(bias.w_out * bias.ratio_stage2, bias.l_out, bias.nf_out, bias.m_out)
    )
    gain_area = (
        mos_area(gain.w_in, gain.l_in, gain.nf_in, gain.m_in, count=2)
        + mos_area(gain.w_load, gain.l_load, gain.nf_load, gain.m_load, count=2 if gain.load_style != "cascoded" else 4)
    )
    second_area = mos_area(second.w_amp, second.l_amp, second.nf_amp, second.m_amp) + mos_area(
        second.w_amp * second.w_load_scale, second.l_load, second.nf_amp, second.m_amp
    )
    bias2_ref_area = mos_area(second.w_amp, second.l_amp, second.nf_amp, second.m_amp)
    total_device_count = 3 + 4 + 2 + 1
    if gain.load_style == "cascoded":
        total_device_count += 2
    transistor_area_um2 = bias_area + gain_area + second_area + bias2_ref_area
    return make_test_result(
        component="opamp_core",
        category="char",
        purpose="area_estimate",
        metrics={"transistor_area_um2": transistor_area_um2, "comp_cap_fF": 1e15 * float(comp.c_comp), "total_device_count": total_device_count},
    )


def run_all_tests(
    dut_params: OpampCoreParams | None = None,
    *,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or OpampCoreParams()
    return {
        "structural": make_test_result(component="opamp_core", category="smoke", purpose="basic", metrics=run_structural_checks(dut_params), passed=True),
        "open_loop": run_open_loop_test(dut_params, sim_options=sim_options),
        "internal_nodes": run_internal_nodes_test(dut_params, sim_options=sim_options),
        "closed_loop_step": run_closed_loop_step_test(dut_params, sim_options=sim_options),
        "area_estimate": run_area_estimate(dut_params),
    }


def run_fast_checks(
    dut_params: OpampCoreParams | None = None,
    *,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or OpampCoreParams()
    open_loop_tb = OpampCoreOpenLoopTbParams(
        vdd=1.8,
        c_load=1e-12,
        r_probe=1e12,
        v_cm=0.4,
        v_diff=1.0,
        dc_v_diff=100e-6,
        f_start=10.0,
        f_stop=1e8,
        npts=20,
        temp_c=27.0,
    )
    return {
        "structural": make_test_result(component="opamp_core", category="smoke", purpose="fast_structural", metrics=run_structural_checks(dut_params), passed=True),
        "open_loop": run_open_loop_fast_test(dut_params, open_loop_tb, sim_options=sim_options),
    }


def print_test_report(
    dut_params: OpampCoreParams | None = None,
    *,
    sim_options: SimOptions | None = None,
):
    results = run_all_tests(dut_params, sim_options=sim_options)
    print_metrics_table(results, title="opamp_core")
    return results


def elaborate_dut(params: OpampCoreParams | None = None) -> h.Module:
    params = params or OpampCoreParams()
    return h.elaborate(opamp_core(params))


def export_spice(path: str | Path, params: OpampCoreParams | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mod = elaborate_dut(params)
    with path.open("w") as f:
        h.netlist(mod, f, fmt="spice")
    return path


def run_structural_checks(params: OpampCoreParams | None = None):
    params = params or OpampCoreParams()
    dut = opamp_core(params)
    mod = elaborate_dut(params)
    netlist_path = Path("./tmp/opamp_core_structural/opamp_core.sp")
    export_spice(netlist_path, params)
    text = netlist_path.read_text()
    subckt_name = extract_subckt_name(text)
    top_level_prefix = mod.name.split("(", 1)[0]
    top_level_present = re.search(rf"^\.SUBCKT\s+{re.escape(top_level_prefix)}", text, flags=re.MULTILINE) is not None

    checks = {
        "generator_call": dut is not None,
        "elaboration": mod is not None,
        "subckt_name": subckt_name is not None,
        "top_level_subckt": top_level_present,
        "contains_bias_gen": "BiasGen" in text,
        "contains_input_stage": "GainStage" in text,
        "contains_gm_stage": "SecondStage" in text,
        "contains_freq_comp": "FreqComp" in text,
    }
    if not all(checks.values()):
        raise RuntimeError(f"Structural checks failed: {checks}")
    return checks
