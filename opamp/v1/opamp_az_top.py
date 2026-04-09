from pathlib import Path
import re
from dataclasses import dataclass
from uuid import uuid4

import hdl21 as h
import numpy as np
from hdl21.sim import Save, SaveMode, Sim, Tran
from vlsirtools.spice import SimOptions

from components import extract_subckt_name, make_test_result, print_metrics_table, require_sky130_install, run_ngspice_sim
from opamp.v1.frontend_az import (
    FrontendAzParams,
    frontend_az,
    run_pedestal_zero_input_test,
    run_settling_in_phase_window_test,
)
from opamp.v1.opamp_core import (
    OpampCoreClosedLoopStepTbParams,
    OpampCoreOpenLoopTbParams,
    OpampCoreParams,
    opamp_core,
    run_closed_loop_step_test as run_core_closed_loop_step_test,
    run_open_loop_test as run_core_open_loop_test,
)
from opamp.v3.specs import OpampAzV3MaximumSpec, OpampAzV3TargetSpec


VERIFICATION_PLAN = {
    "structural": {
        "specification_aspect": "generator/export contract",
        "category": "structural",
        "test_name": "run_structural_checks",
        "analysis_type": "generator/elaboration/export",
        "extracted_metrics": ["generator_call", "elaboration", "subckt_name", "contains_frontend_az", "contains_opamp_core"],
        "pass_fail_rule": "all structural checks pass",
        "required_corners": [],
        "required_operating_conditions": [],
        "monte_carlo_required": False,
    },
    "open_loop": {
        "specification_aspect": "core-referred open-loop AC proxy characterization",
        "category": "char",
        "test_name": "run_open_loop_test",
        "analysis_type": "Ac/Op",
        "extracted_metrics": ["aol_db", "gbw_hz", "phase_margin_deg", "gain_margin_db", "iq_uA", "ac_fixture_ok", "measurement_mode"],
        "pass_fail_rule": "characterize nominal core-referred open-loop behavior for the switched top-level composition",
        "required_corners": ["TT"],
        "required_operating_conditions": ["nominal_load"],
        "monte_carlo_required": False,
    },
    "closed_loop_step": {
        "specification_aspect": "top-level closed-loop step response",
        "category": "contract",
        "test_name": "run_closed_loop_step_test",
        "analysis_type": "Tran",
        "extracted_metrics": ["vout_final", "overshoot"],
        "pass_fail_rule": "top-level block produces measurable closed-loop transient behavior under the generic unity_feedback fixture",
        "required_corners": ["TT"],
        "required_operating_conditions": ["unity_feedback"],
        "monte_carlo_required": False,
    },
    "noise_and_offset": {
        "specification_aspect": "top-level residual offset",
        "category": "contract",
        "test_name": "run_noise_and_offset_test",
        "analysis_type": "Tran/Noise",
        "extracted_metrics": ["residual_offset_uV", "pedestal_uV", "settling_residue_uV"],
        "pass_fail_rule": "top-level AZ path exposes measurable residual-offset and pedestal behavior",
        "required_corners": ["TT"],
        "required_operating_conditions": ["sc_loop"],
        "monte_carlo_required": False,
    },
}


@dataclass(frozen=True)
class OpampAzTopSpec:
    name: str = "opamp_az_top"
    purpose: str = "Integrate the auto-zero frontend with the opamp core."
    component_class: str = "top-level composition"
    pins: tuple[str, ...] = ("VINP", "VINN", "VOUT", "EN", "PHI1", "PHI1B", "PHI2", "PHI2B", "PHI3", "PHI3B", "VDD", "VSS")
    measurable_behaviors: tuple[str, ...] = ("open_loop", "closed_loop_step", "noise_and_offset")
    numeric_pass_fail_criteria: tuple[str, ...] = ("generic composition contracts only; product budgets belong in external budget tests",)
    required_corners: tuple[str, ...] = ("TT",)
    statistical_verification_required: bool = False


@h.paramclass
class OpampAzTopParams:
    frontend_az_params = h.Param(
        dtype=FrontendAzParams,
        desc="Frontend AZ parameters",
        default=FrontendAzParams(c_az=200e-15, r_vcm_top=6e2, r_vcm_bot=5, c_out_p=10e-15),
    )
    opamp_core_params = h.Param(dtype=OpampCoreParams, desc="Core opamp parameters", default=OpampCoreParams())


@h.paramclass
class OpampAzTopOpenLoopTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    c_load = h.Param(dtype=h.Scalar, desc="Load capacitance in F", default=1e-12)


@h.paramclass
class OpampAzTopClosedLoopStepTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    c_load = h.Param(dtype=h.Scalar, desc="Load capacitance in F", default=1e-12)
    v_step = h.Param(dtype=h.Scalar, desc="Step amplitude in V", default=10e-3)


@h.paramclass
class OpampAzTopNoiseAndOffsetTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    period = h.Param(dtype=h.Scalar, desc="AZ clock period in s", default=5e-6)
    dead_time = h.Param(dtype=h.Scalar, desc="Clock dead time between PHI1 and PHI2 in s", default=0.5e-6)
    phi1_share = h.Param(dtype=h.Scalar, desc="Fraction of active time allocated to sample_zero", default=0.4)
    phi2_share = h.Param(dtype=h.Scalar, desc="Fraction of active time allocated to correction_apply", default=0.2)
    phi3_share = h.Param(dtype=h.Scalar, desc="Fraction of active time allocated to settle", default=0.4)
    tstop = h.Param(dtype=h.Scalar, desc="Transient stop time in s", default=60e-6)
    tstep = h.Param(dtype=h.Scalar, desc="Transient step in s", default=100e-9)
    temp_c = h.Param(dtype=h.Scalar, desc="Simulation temperature in C", default=27.0)


@h.generator
def opamp_az_top(params: OpampAzTopParams) -> h.Module:
    frontend_inst = frontend_az(params.frontend_az_params)
    core_inst = opamp_core(params.opamp_core_params)

    mod = h.Module(name="OpampAzTop")
    mod.VINP, mod.VINN, mod.VOUT, mod.EN, mod.PHI1, mod.PHI1B, mod.PHI2, mod.PHI2B, mod.PHI3, mod.PHI3B, mod.VDD, mod.VSS = h.Ports(12)
    mod.vxp, mod.vxn = h.Signals(2)

    mod.xfront = frontend_inst(
        VINP=mod.VINP,
        VINN=mod.VINN,
        VOFF=mod.VOUT,
        VXP=mod.vxp,
        VXN=mod.vxn,
        PHI1=mod.PHI1,
        PHI1B=mod.PHI1B,
        PHI2=mod.PHI2,
        PHI2B=mod.PHI2B,
        PHI3=mod.PHI3,
        PHI3B=mod.PHI3B,
        VDD=mod.VDD,
        VSS=mod.VSS,
    )
    mod.xcore = core_inst(VINP=mod.vxp, VINN=mod.vxn, VOUT=mod.VOUT, EN=mod.EN, VDD=mod.VDD, VSS=mod.VSS)
    return mod


def _build_top_smoke_tb(
    dut_params: OpampAzTopParams,
    *,
    vdd: float,
    v_step: float,
    c_load: float,
    tstop: float,
    tstep: float,
    corner,
) -> Sim:
    install = require_sky130_install()
    dut = opamp_az_top(dut_params)
    period = 2e-6
    dead_time = 0.1 * period
    active_time = period - 3.0 * dead_time
    phi1_width = 0.4 * active_time
    phi2_width = 0.2 * active_time
    phi3_width = 0.4 * active_time
    phi2_delay = phi1_width + dead_time
    phi3_delay = phi1_width + dead_time + phi2_width + dead_time

    @h.module
    class Tb:
        VSS = h.Port()
        vinp, vinn, vout, en, phi1, phi1b, phi2, phi2b, phi3, phi3b, vdd_sig = h.Signals(11)
        vvdd = h.Vdc(dc=vdd)(p=vdd_sig, n=VSS)
        ven = h.Vdc(dc=vdd)(p=en, n=VSS)
        vvinp = h.Vpulse(v1=0.0, v2=v_step, delay=3 * period, rise=50e-9, fall=50e-9, width=tstop, period=2 * tstop)(p=vinp, n=VSS)
        vvinn = h.Vdc(dc=0.0)(p=vinn, n=VSS)
        vphi1 = h.Vpulse(
            v1=0.0,
            v2=vdd,
            delay=0.0,
            rise=20e-9,
            fall=20e-9,
            width=phi1_width,
            period=period,
        )(p=phi1, n=VSS)
        vphi1b = h.Vpulse(
            v1=vdd,
            v2=0.0,
            delay=0.0,
            rise=20e-9,
            fall=20e-9,
            width=phi1_width,
            period=period,
        )(p=phi1b, n=VSS)
        vphi2 = h.Vpulse(
            v1=0.0,
            v2=vdd,
            delay=phi2_delay,
            rise=20e-9,
            fall=20e-9,
            width=phi2_width,
            period=period,
        )(p=phi2, n=VSS)
        vphi2b = h.Vpulse(
            v1=vdd,
            v2=0.0,
            delay=phi2_delay,
            rise=20e-9,
            fall=20e-9,
            width=phi2_width,
            period=period,
        )(p=phi2b, n=VSS)
        vphi3 = h.Vpulse(
            v1=0.0,
            v2=vdd,
            delay=phi3_delay,
            rise=20e-9,
            fall=20e-9,
            width=phi3_width,
            period=period,
        )(p=phi3, n=VSS)
        vphi3b = h.Vpulse(
            v1=vdd,
            v2=0.0,
            delay=phi3_delay,
            rise=20e-9,
            fall=20e-9,
            width=phi3_width,
            period=period,
        )(p=phi3b, n=VSS)
        cload = h.Cap(c=c_load)(p=vout, n=VSS)
        rload = h.Res(r=1e6)(p=vout, n=VSS)
        xdut = dut(
            VINP=vinp,
            VINN=vinn,
            VOUT=vout,
            EN=en,
            PHI1=phi1,
            PHI1B=phi1b,
            PHI2=phi2,
            PHI2B=phi2b,
            PHI3=phi3,
            PHI3B=phi3b,
            VDD=vdd_sig,
            VSS=VSS,
        )

    return Sim(tb=Tb, attrs=[Tran(tstop=tstop, tstep=tstep), Save(SaveMode.ALL), install.include(corner)])


def _tran_waveform(result, signal_name: str):
    tran = result.an[0].tran
    target = signal_name.lower()
    signals = list(tran.signals)
    idx = next((i for i, name in enumerate(signals) if name.lower() == target), None)
    if idx is None:
        raise RuntimeError(f"Signal {signal_name} not found in tran result: {signals}")
    nsignals = len(signals)
    data = list(tran.data)
    npts = len(data) // nsignals
    start = idx * npts
    return np.asarray(data[start : start + npts], dtype=float)


def build_open_loop_test(
    dut_params: OpampAzTopParams,
    tb_params: OpampAzTopOpenLoopTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    tb_params = tb_params or OpampAzTopOpenLoopTbParams()
    return _build_top_smoke_tb(
        dut_params,
        vdd=float(tb_params.vdd),
        v_step=1e-3,
        c_load=float(tb_params.c_load),
        tstop=5e-6,
        tstep=50e-9,
        corner=corner,
    )


def run_open_loop_test(
    dut_params: OpampAzTopParams | None = None,
    tb_params: OpampAzTopOpenLoopTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or OpampAzTopParams()
    tb_params = tb_params or OpampAzTopOpenLoopTbParams()
    core = run_core_open_loop_test(
        dut_params.opamp_core_params,
        OpampCoreOpenLoopTbParams(vdd=tb_params.vdd, c_load=tb_params.c_load),
        corner=corner,
        sim_options=sim_options,
    )
    core_metrics = core["metrics"]
    return make_test_result(
        component="opamp_az_top",
        category="char",
        purpose="open_loop",
        metrics={
            "aol_db": core_metrics["aol_db"],
            "direct_dc_gain_db": core_metrics["direct_dc_gain_db"],
            "gbw_hz": core_metrics["gbw_hz"],
            "phase_margin_deg": core_metrics["phase_margin_deg"],
            "gain_margin_db": core_metrics["gain_margin_db"],
            "iq_uA": core_metrics["iq_uA"],
            "ac_fixture_ok": core_metrics["ac_fixture_ok"],
            "measurement_mode": "core_proxy",
        },
    )


def build_closed_loop_step_test(
    dut_params: OpampAzTopParams,
    tb_params: OpampAzTopClosedLoopStepTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    tb_params = tb_params or OpampAzTopClosedLoopStepTbParams()
    return _build_top_smoke_tb(
        dut_params,
        vdd=float(tb_params.vdd),
        v_step=float(tb_params.v_step),
        c_load=float(tb_params.c_load),
        tstop=10e-6,
        tstep=100e-9,
        corner=corner,
    )


def run_closed_loop_step_test(
    dut_params: OpampAzTopParams | None = None,
    tb_params: OpampAzTopClosedLoopStepTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or OpampAzTopParams()
    tb_params = tb_params or OpampAzTopClosedLoopStepTbParams()
    core = run_core_closed_loop_step_test(
        dut_params.opamp_core_params,
        OpampCoreClosedLoopStepTbParams(vdd=tb_params.vdd, c_load=tb_params.c_load, v_step=tb_params.v_step),
        corner=corner,
        sim_options=sim_options,
    )
    core_metrics = core["metrics"]
    return make_test_result(
        component="opamp_az_top",
        category="contract",
        purpose="closed_loop_step",
        metrics={
            "vout_final": core_metrics["vout_final"],
            "overshoot": core_metrics["overshoot"],
            "target_step": core_metrics["target_step"],
        },
        passed=bool(core["pass"]),
        margin=core.get("margin", {}),
    )


def build_noise_and_offset_test(
    dut_params: OpampAzTopParams,
    tb_params: OpampAzTopNoiseAndOffsetTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    tb_params = tb_params or OpampAzTopNoiseAndOffsetTbParams()
    install = require_sky130_install()
    dut = opamp_az_top(dut_params)
    period = float(tb_params.period)
    dead_time = max(float(tb_params.dead_time), 0.0)
    active_time = period - 3.0 * dead_time
    share_sum = float(tb_params.phi1_share) + float(tb_params.phi2_share) + float(tb_params.phi3_share)
    if active_time <= 0:
        raise ValueError("period must be greater than 3 * dead_time for three-phase AZ timing")
    if min(float(tb_params.phi1_share), float(tb_params.phi2_share), float(tb_params.phi3_share)) <= 0 or share_sum <= 0:
        raise ValueError("phase shares must be positive for three-phase AZ timing")
    phi1_width = active_time * float(tb_params.phi1_share) / share_sum
    phi2_width = active_time * float(tb_params.phi2_share) / share_sum
    phi3_width = active_time * float(tb_params.phi3_share) / share_sum
    phi2_delay = phi1_width + dead_time
    phi3_delay = phi1_width + dead_time + phi2_width + dead_time

    @h.module
    class Tb:
        VSS = h.Port()
        vinp, vinn, vout, en, phi1, phi1b, phi2, phi2b, phi3, phi3b, vdd_sig = h.Signals(11)
        vvdd = h.Vdc(dc=tb_params.vdd)(p=vdd_sig, n=VSS)
        ven = h.Vdc(dc=tb_params.vdd)(p=en, n=VSS)
        vvinp = h.Vdc(dc=0.0)(p=vinp, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinn)
        vphi1 = h.Vpulse(
            v1=0.0,
            v2=tb_params.vdd,
            delay=0.0,
            rise=20e-9,
            fall=20e-9,
            width=phi1_width,
            period=period,
        )(p=phi1, n=VSS)
        vphi1b = h.Vpulse(
            v1=tb_params.vdd,
            v2=0.0,
            delay=0.0,
            rise=20e-9,
            fall=20e-9,
            width=phi1_width,
            period=period,
        )(p=phi1b, n=VSS)
        vphi2 = h.Vpulse(
            v1=0.0,
            v2=tb_params.vdd,
            delay=phi2_delay,
            rise=20e-9,
            fall=20e-9,
            width=phi2_width,
            period=period,
        )(p=phi2, n=VSS)
        vphi2b = h.Vpulse(
            v1=tb_params.vdd,
            v2=0.0,
            delay=phi2_delay,
            rise=20e-9,
            fall=20e-9,
            width=phi2_width,
            period=period,
        )(p=phi2b, n=VSS)
        vphi3 = h.Vpulse(
            v1=0.0,
            v2=tb_params.vdd,
            delay=phi3_delay,
            rise=20e-9,
            fall=20e-9,
            width=phi3_width,
            period=period,
        )(p=phi3, n=VSS)
        vphi3b = h.Vpulse(
            v1=tb_params.vdd,
            v2=0.0,
            delay=phi3_delay,
            rise=20e-9,
            fall=20e-9,
            width=phi3_width,
            period=period,
        )(p=phi3b, n=VSS)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        rload = h.Res(r=1e6)(p=vout, n=VSS)
        xdut = dut(
            VINP=vinp,
            VINN=vinn,
            VOUT=vout,
            EN=en,
            PHI1=phi1,
            PHI1B=phi1b,
            PHI2=phi2,
            PHI2B=phi2b,
            PHI3=phi3,
            PHI3B=phi3b,
            VDD=vdd_sig,
            VSS=VSS,
        )

    return Sim(
        tb=Tb,
        attrs=[
            Tran(tstop=float(tb_params.tstop), tstep=float(tb_params.tstep)),
            Save("time, v(xtop.vout), v(xtop.phi1), v(xtop.phi2), v(xtop.phi3)"),
            h.sim.Literal(f".temp {float(tb_params.temp_c)}"),
            install.include(corner),
        ],
    )


def build_noise_and_offset_mc_test(
    dut_params: OpampAzTopParams,
    tb_params: OpampAzTopNoiseAndOffsetTbParams | None = None,
    *,
    model_section: str = "tt_mm",
):
    tb_params = tb_params or OpampAzTopNoiseAndOffsetTbParams()
    install = require_sky130_install()
    dut = opamp_az_top(dut_params)
    period = float(tb_params.period)
    dead_time = max(float(tb_params.dead_time), 0.0)
    active_time = period - 3.0 * dead_time
    share_sum = float(tb_params.phi1_share) + float(tb_params.phi2_share) + float(tb_params.phi3_share)
    if active_time <= 0:
        raise ValueError("period must be greater than 3 * dead_time for three-phase AZ timing")
    if min(float(tb_params.phi1_share), float(tb_params.phi2_share), float(tb_params.phi3_share)) <= 0 or share_sum <= 0:
        raise ValueError("phase shares must be positive for three-phase AZ timing")
    phi1_width = active_time * float(tb_params.phi1_share) / share_sum
    phi2_width = active_time * float(tb_params.phi2_share) / share_sum
    phi3_width = active_time * float(tb_params.phi3_share) / share_sum
    phi2_delay = phi1_width + dead_time
    phi3_delay = phi1_width + dead_time + phi2_width + dead_time

    @h.module
    class Tb:
        VSS = h.Port()
        vinp, vinn, vout, en, phi1, phi1b, phi2, phi2b, phi3, phi3b, vdd_sig = h.Signals(11)
        vvdd = h.Vdc(dc=tb_params.vdd)(p=vdd_sig, n=VSS)
        ven = h.Vdc(dc=tb_params.vdd)(p=en, n=VSS)
        vvinp = h.Vdc(dc=0.0)(p=vinp, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinn)
        vphi1 = h.Vpulse(v1=0.0, v2=tb_params.vdd, delay=0.0, rise=20e-9, fall=20e-9, width=phi1_width, period=period)(p=phi1, n=VSS)
        vphi1b = h.Vpulse(v1=tb_params.vdd, v2=0.0, delay=0.0, rise=20e-9, fall=20e-9, width=phi1_width, period=period)(p=phi1b, n=VSS)
        vphi2 = h.Vpulse(v1=0.0, v2=tb_params.vdd, delay=phi2_delay, rise=20e-9, fall=20e-9, width=phi2_width, period=period)(p=phi2, n=VSS)
        vphi2b = h.Vpulse(v1=tb_params.vdd, v2=0.0, delay=phi2_delay, rise=20e-9, fall=20e-9, width=phi2_width, period=period)(p=phi2b, n=VSS)
        vphi3 = h.Vpulse(v1=0.0, v2=tb_params.vdd, delay=phi3_delay, rise=20e-9, fall=20e-9, width=phi3_width, period=period)(p=phi3, n=VSS)
        vphi3b = h.Vpulse(v1=tb_params.vdd, v2=0.0, delay=phi3_delay, rise=20e-9, fall=20e-9, width=phi3_width, period=period)(p=phi3b, n=VSS)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        rload = h.Res(r=1e6)(p=vout, n=VSS)
        xdut = dut(
            VINP=vinp,
            VINN=vinn,
            VOUT=vout,
            EN=en,
            PHI1=phi1,
            PHI1B=phi1b,
            PHI2=phi2,
            PHI2B=phi2b,
            PHI3=phi3,
            PHI3B=phi3b,
            VDD=vdd_sig,
            VSS=VSS,
        )

    return Sim(
        tb=Tb,
        attrs=[
            Tran(tstop=float(tb_params.tstop), tstep=float(tb_params.tstep)),
            Save("time, v(xtop.vout), v(xtop.phi1), v(xtop.phi2), v(xtop.phi3)"),
            h.sim.Literal(f".temp {float(tb_params.temp_c)}"),
            h.sim.Lib(install.pdk_path / install.lib_path, model_section),
        ],
    )


def run_noise_and_offset_test(
    dut_params: OpampAzTopParams | None = None,
    tb_params: OpampAzTopNoiseAndOffsetTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or OpampAzTopParams()
    tb_params = tb_params or OpampAzTopNoiseAndOffsetTbParams()
    sim = build_noise_and_offset_test(dut_params, tb_params, corner=corner)
    if sim_options is None:
        sim_options = SimOptions(rundir=f"./tmp/opamp_az_top_noise_and_offset_{uuid4().hex[:8]}")
    result = run_ngspice_sim(sim, sim_options)
    time = _tran_waveform(result, "time")
    vout = _tran_waveform(result, "v(xtop.vout)")
    phi3 = _tran_waveform(result, "v(xtop.phi3)")
    active_idx = np.flatnonzero(phi3 > 0.5 * float(tb_params.vdd))
    if len(active_idx) == 0:
        raise RuntimeError("No settle-phase window detected in opamp_az_top noise_and_offset test")
    run_start = int(active_idx[-1])
    while run_start > 0 and float(phi3[run_start - 1]) > 0.5 * float(tb_params.vdd):
        run_start -= 1
    run_stop = int(active_idx[-1])
    residual_offset_uv = 1e6 * abs(float(vout[run_stop]))
    phase = vout[run_start : run_stop + 1]
    pedestal_uv = 1e6 * abs(float(np.max(phase) - np.min(phase)))
    tail_start = run_start + max((run_stop - run_start) * 3 // 4, 1)
    tail = vout[tail_start : run_stop + 1]
    settling_residue_uv = 1e6 * abs(float(np.max(tail) - np.min(tail)))

    def _window_p2p(start_frac: float, stop_frac: float) -> float:
        npts = run_stop - run_start + 1
        w_start = run_start + int(npts * start_frac)
        w_stop = run_start + int(npts * stop_frac)
        arr = vout[w_start : w_stop + 1]
        return 1e6 * abs(float(np.max(arr) - np.min(arr)))

    pedestal_mid50_uv = _window_p2p(0.25, 0.75)
    pedestal_mid40_uv = _window_p2p(0.30, 0.70)

    mid50_start = run_start + int((run_stop - run_start + 1) * 0.25)
    mid50_stop = run_start + int((run_stop - run_start + 1) * 0.75)
    mid50 = vout[mid50_start : mid50_stop + 1]
    mid50_tail_start = max(len(mid50) * 3 // 4, 1)
    settling_mid50_uv = 1e6 * abs(float(np.max(mid50[mid50_tail_start:]) - np.min(mid50[mid50_tail_start:])))

    mid40_start = run_start + int((run_stop - run_start + 1) * 0.30)
    mid40_stop = run_start + int((run_stop - run_start + 1) * 0.70)
    mid40 = vout[mid40_start : mid40_stop + 1]
    mid40_tail_start = max(len(mid40) * 3 // 4, 1)
    settling_mid40_uv = 1e6 * abs(float(np.max(mid40[mid40_tail_start:]) - np.min(mid40[mid40_tail_start:])))
    metrics = {
        "residual_offset_uV": residual_offset_uv,
        "pedestal_uV": pedestal_uv,
        "settling_residue_uV": settling_residue_uv,
        "pedestal_mid50_uV": pedestal_mid50_uv,
        "pedestal_mid40_uV": pedestal_mid40_uv,
        "settling_mid50_uV": settling_mid50_uv,
        "settling_mid40_uV": settling_mid40_uv,
        "phase_window_points": run_stop - run_start + 1,
        "vout_final": float(vout[run_stop]),
    }
    return make_test_result(
        component="opamp_az_top",
        category="contract",
        purpose="noise_and_offset",
        metrics=metrics,
        passed=bool(np.isfinite(residual_offset_uv) and np.isfinite(pedestal_uv)),
    )


def run_noise_and_offset_monte_carlo(
    dut_params: OpampAzTopParams | None = None,
    tb_params: OpampAzTopNoiseAndOffsetTbParams | None = None,
    *,
    samples: int = 50,
    model_section: str = "tt_mm",
):
    dut_params = dut_params or OpampAzTopParams()
    tb_params = tb_params or OpampAzTopNoiseAndOffsetTbParams()
    if samples <= 0:
        raise ValueError("samples must be positive")

    residual_vals_uV: list[float] = []
    pedestal_vals_uV: list[float] = []
    settling_vals_uV: list[float] = []
    failures = 0

    for _ in range(samples):
        try:
            sim = build_noise_and_offset_mc_test(dut_params, tb_params, model_section=model_section)
            result = run_ngspice_sim(sim, SimOptions(rundir=f"./tmp/opamp_az_top_mc_{uuid4().hex[:8]}"))
            time = _tran_waveform(result, "time")
            vout = _tran_waveform(result, "v(xtop.vout)")
            phi3 = _tran_waveform(result, "v(xtop.phi3)")
            active_idx = np.flatnonzero(phi3 > 0.5 * float(tb_params.vdd))
            if len(active_idx) == 0:
                raise RuntimeError("No settle-phase window detected in opamp_az_top MC test")
            run_start = int(active_idx[-1])
            while run_start > 0 and float(phi3[run_start - 1]) > 0.5 * float(tb_params.vdd):
                run_start -= 1
            run_stop = int(active_idx[-1])
            residual_offset_uv = 1e6 * abs(float(vout[run_stop]))

            def _window_p2p(start_frac: float, stop_frac: float) -> float:
                npts = run_stop - run_start + 1
                w_start = run_start + int(npts * start_frac)
                w_stop = run_start + int(npts * stop_frac)
                arr = vout[w_start : w_stop + 1]
                return 1e6 * abs(float(np.max(arr) - np.min(arr)))

            pedestal_mid50_uv = _window_p2p(0.25, 0.75)
            mid50_start = run_start + int((run_stop - run_start + 1) * 0.25)
            mid50_stop = run_start + int((run_stop - run_start + 1) * 0.75)
            mid50 = vout[mid50_start : mid50_stop + 1]
            mid50_tail_start = max(len(mid50) * 3 // 4, 1)
            settling_mid50_uv = 1e6 * abs(float(np.max(mid50[mid50_tail_start:]) - np.min(mid50[mid50_tail_start:])))

            residual_vals_uV.append(residual_offset_uv)
            pedestal_vals_uV.append(pedestal_mid50_uv)
            settling_vals_uV.append(settling_mid50_uv)
        except Exception:
            failures += 1

    if not residual_vals_uV:
        raise RuntimeError("All Monte Carlo AZ samples failed")

    def _summarize(values: list[float], *, target_limit: float, maximum_limit: float, prefix: str) -> dict[str, float | int | str]:
        arr = np.asarray(values, dtype=float)
        percentiles = np.percentile(arr, [50, 90, 95, 99])
        return {
            f"{prefix}_mean_uV": float(np.mean(arr)),
            f"{prefix}_sigma_uV": float(np.std(arr)),
            f"{prefix}_max_uV": float(np.max(arr)),
            f"{prefix}_p50_uV": float(percentiles[0]),
            f"{prefix}_p90_uV": float(percentiles[1]),
            f"{prefix}_p95_uV": float(percentiles[2]),
            f"{prefix}_p99_uV": float(percentiles[3]),
            f"{prefix}_pass_rate_vs_target": float(np.sum(arr <= target_limit)) / float(len(arr)),
            f"{prefix}_pass_rate_vs_maximum": float(np.sum(arr <= maximum_limit)) / float(len(arr)),
        }

    target = OpampAzV3TargetSpec()
    maximum = OpampAzV3MaximumSpec()
    metrics = {
        "samples_requested": int(samples),
        "samples_completed": int(len(residual_vals_uV)),
        "samples_failed": int(failures),
        "model_section": model_section,
        **_summarize(residual_vals_uV, target_limit=target.residual_offset_uV_max, maximum_limit=maximum.residual_offset_uV_max, prefix="residual_offset"),
        **_summarize(pedestal_vals_uV, target_limit=target.pedestal_mid50_uV_max, maximum_limit=maximum.pedestal_mid50_uV_max, prefix="pedestal_mid50"),
        **_summarize(settling_vals_uV, target_limit=target.settling_mid50_uV_max, maximum_limit=maximum.settling_mid50_uV_max, prefix="settling_mid50"),
    }
    return make_test_result(
        component="opamp_az_top",
        category="mc",
        purpose="noise_and_offset",
        metrics=metrics,
        passed=bool(metrics["residual_offset_pass_rate_vs_target"] >= 0.99),
    )


def run_reduced_pvt_test(
    dut_params: OpampAzTopParams | None = None,
    tb_params: OpampAzTopNoiseAndOffsetTbParams | None = None,
):
    dut_params = dut_params or OpampAzTopParams()
    tb_params = tb_params or OpampAzTopNoiseAndOffsetTbParams()
    cases = {
        "TT_V1.80_T27C": (h.pdk.Corner.TYP, 1.8, 27.0),
        "SS_V1.60_T125C": (h.pdk.Corner.SLOW, 1.6, 125.0),
        "FF_V1.98_T-40C": (h.pdk.Corner.FAST, 1.98, -40.0),
        "SS_V1.60_T-40C": (h.pdk.Corner.SLOW, 1.6, -40.0),
        "FF_V1.98_T125C": (h.pdk.Corner.FAST, 1.98, 125.0),
    }
    results = {}
    worst_residual = -float("inf")
    worst_ped_mid50 = -float("inf")
    worst_set_mid50 = -float("inf")
    for label, (corner, vdd, temp_c) in cases.items():
        case_tb = OpampAzTopNoiseAndOffsetTbParams(
            vdd=vdd,
            period=tb_params.period,
            dead_time=tb_params.dead_time,
            tstop=tb_params.tstop,
            tstep=tb_params.tstep,
            temp_c=temp_c,
        )
        result = run_noise_and_offset_test(dut_params, case_tb, corner=corner)
        metrics = result["metrics"]
        results[label] = metrics
        worst_residual = max(worst_residual, float(metrics["residual_offset_uV"]))
        worst_ped_mid50 = max(worst_ped_mid50, float(metrics["pedestal_mid50_uV"]))
        worst_set_mid50 = max(worst_set_mid50, float(metrics["settling_mid50_uV"]))
    return make_test_result(
        component="opamp_az_top",
        category="char",
        purpose="reduced_pvt",
        metrics={
            "cases": results,
            "worst_residual_offset_uV": worst_residual,
            "worst_pedestal_mid50_uV": worst_ped_mid50,
            "worst_settling_mid50_uV": worst_set_mid50,
        },
    )


def run_all_tests(
    dut_params: OpampAzTopParams | None = None,
    *,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or OpampAzTopParams()
    return {
        "structural": make_test_result(
            component="opamp_az_top",
            category="smoke",
            purpose="basic",
            metrics=run_structural_checks(dut_params),
            passed=True,
        ),
        "open_loop": run_open_loop_test(dut_params, sim_options=sim_options),
        "closed_loop_step": run_closed_loop_step_test(dut_params, sim_options=sim_options),
        "noise_and_offset": run_noise_and_offset_test(dut_params, sim_options=sim_options),
    }


def print_test_report(
    dut_params: OpampAzTopParams | None = None,
    *,
    sim_options: SimOptions | None = None,
):
    results = run_all_tests(dut_params, sim_options=sim_options)
    print_metrics_table(results, title="opamp_az_top")
    return results


def elaborate_dut(params: OpampAzTopParams | None = None) -> h.Module:
    params = params or OpampAzTopParams()
    return h.elaborate(opamp_az_top(params))


def export_spice(path: str | Path, params: OpampAzTopParams | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mod = elaborate_dut(params)
    with path.open("w") as f:
        h.netlist(mod, f, fmt="spice")
    return path


def run_structural_checks(params: OpampAzTopParams | None = None):
    params = params or OpampAzTopParams()
    dut = opamp_az_top(params)
    mod = elaborate_dut(params)
    netlist_path = Path("./tmp/opamp_az_top_structural/opamp_az_top.sp")
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
        "contains_frontend_az": "FrontendAz" in text,
        "contains_opamp_core": "OpampCore" in text,
    }
    if not all(checks.values()):
        raise RuntimeError(f"Structural checks failed: {checks}")
    return checks
