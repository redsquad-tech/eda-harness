from pathlib import Path
import re
from dataclasses import dataclass
import math

import hdl21 as h
import numpy as np
import sky130_hdl21
from hdl21.sim import Ac, LogSweep, Op, Save, SaveMode, Sim, Tran
from vlsirtools.spice import ResultFormat, SimOptions, SupportedSimulators

from components import extract_subckt_name, make_test_result, print_metrics_table, require_sky130_install, run_ngspice_sim
from components.bias_gen import BiasGenParams, bias_gen, run_current_accuracy_test
from components.freq_comp import FreqCompParams, freq_comp
from components.gain_stage import GainStageParams, gain_stage
from components.output_stage import OutputStageParams, output_stage
from components.second_stage import SecondStageParams, second_stage


VERIFICATION_PLAN = {
    "structural": {
        "specification_aspect": "generator/export contract",
        "category": "structural",
        "test_name": "run_structural_checks",
        "analysis_type": "generator/elaboration/export",
        "extracted_metrics": ["generator_call", "elaboration", "subckt_name", "contains_bias_gen", "contains_gain_stage", "contains_second_stage", "contains_output_stage", "contains_freq_comp"],
        "pass_fail_rule": "all structural checks pass",
        "required_corners": [],
        "required_operating_conditions": [],
        "monte_carlo_required": False,
    },
    "open_loop": {
        "specification_aspect": "generic loop-break AC characterization",
        "category": "char",
        "test_name": "run_open_loop_test",
        "analysis_type": "Ac/Op",
        "extracted_metrics": [
            "aol_db",
            "direct_dc_gain_db",
            "loop_gain_dc_db",
            "gbw_hz",
            "phase_margin_deg",
            "gain_margin_db",
            "phase_at_unity_deg_raw",
            "low_freq_phase_deg_raw",
            "sign_offset_detected",
            "iq_uA",
            "ac_fixture_ok",
        ],
        "pass_fail_rule": "component exposes measurable loop-break AC and quiescent-current behavior under the nominal fixture",
        "required_corners": ["TT"],
        "required_operating_conditions": ["nominal_load"],
        "monte_carlo_required": False,
    },
    "direct_dc_gain": {
        "specification_aspect": "direct differential DC gain characterization",
        "category": "char",
        "test_name": "run_direct_dc_gain_test",
        "analysis_type": "Ac/Op",
        "extracted_metrics": ["vout_dc", "low_freq_vout_mag", "direct_gain_vv", "direct_gain_db", "iq_uA"],
        "pass_fail_rule": "component exposes measurable small-signal differential gain around the nominal operating point",
        "required_corners": ["TT"],
        "required_operating_conditions": ["nominal_load"],
        "monte_carlo_required": False,
    },
    "internal_direct_gain": {
        "specification_aspect": "direct internal-node DC gain characterization",
        "category": "char",
        "test_name": "run_internal_direct_gain_test",
        "analysis_type": "Ac/Op",
        "extracted_metrics": ["vdrv_dc", "low_freq_vdrv_mag", "direct_gain_vv", "direct_gain_db"],
        "pass_fail_rule": "component exposes measurable small-signal differential gain on the internal drive node around the nominal operating point",
        "required_corners": ["TT"],
        "required_operating_conditions": ["nominal_load"],
        "monte_carlo_required": False,
    },
    "direct_dc_gain_sweep": {
        "specification_aspect": "direct differential DC gain vs input amplitude characterization",
        "category": "char",
        "test_name": "run_direct_dc_gain_sweep_test",
        "analysis_type": "Op sweep",
        "extracted_metrics": ["cases", "best_direct_gain_db", "worst_direct_gain_db"],
        "pass_fail_rule": "component exposes measurable small-signal differential gain across a representative differential-input sweep",
        "required_corners": ["TT"],
        "required_operating_conditions": ["nominal_load", "vdiff sweep"],
        "monte_carlo_required": False,
    },
    "closed_loop_step": {
        "specification_aspect": "closed-loop step response",
        "category": "contract",
        "test_name": "run_closed_loop_step_test",
        "analysis_type": "Tran",
        "extracted_metrics": ["vout_final", "vout_peak", "overshoot", "target_step"],
        "pass_fail_rule": "response is measurable and convergent under the generic unity_feedback fixture",
        "required_corners": ["TT"],
        "required_operating_conditions": ["unity_feedback", "nominal_load"],
        "monte_carlo_required": False,
    },
    "internal_nodes": {
        "specification_aspect": "internal operating-point characterization",
        "category": "char",
        "test_name": "run_internal_nodes_test",
        "analysis_type": "Op",
        "extracted_metrics": ["vx_dc", "vref_dc", "vbias2_dc", "vout_dc", "iq_uA"],
        "pass_fail_rule": "characterize nominal internal bias points under the loop-broken DC fixture",
        "required_corners": ["TT"],
        "required_operating_conditions": ["nominal_load"],
        "monte_carlo_required": False,
    },
    "bias_characterization": {
        "specification_aspect": "bias distribution characterization",
        "category": "char",
        "test_name": "run_bias_characterization_test",
        "analysis_type": "Op",
        "extracted_metrics": ["bias_ratio_est", "bias_i1_est", "bias_i2_est"],
        "pass_fail_rule": "characterize nominal mirrored-bias behavior through the dedicated bias-generator fixture",
        "required_corners": ["TT"],
        "required_operating_conditions": ["nominal_bias"],
        "monte_carlo_required": False,
    },
    "output_swing": {
        "specification_aspect": "closed-loop compliant output swing characterization",
        "category": "char",
        "test_name": "run_output_swing_test",
        "analysis_type": "Op",
        "extracted_metrics": ["vout_low_target", "vout_low_actual", "vout_high_target", "vout_high_actual"],
        "pass_fail_rule": "characterize the follower-mode low and high output operating points under the nominal load fixture",
        "required_corners": ["TT"],
        "required_operating_conditions": ["unity_feedback", "nominal_load"],
        "monte_carlo_required": False,
    },
    "output_drive": {
        "specification_aspect": "closed-loop output-drive characterization",
        "category": "char",
        "test_name": "run_output_drive_test",
        "analysis_type": "Op",
        "extracted_metrics": ["vout_source", "vout_sink", "requested_source_load_uA", "requested_sink_load_uA"],
        "pass_fail_rule": "characterize follower-mode output compliance under nominal forced source and sink current loads",
        "required_corners": ["TT"],
        "required_operating_conditions": ["unity_feedback", "current_load"],
        "monte_carlo_required": False,
    },
    "output_current_limit": {
        "specification_aspect": "closed-loop maximum compliant output current characterization",
        "category": "char",
        "test_name": "run_output_current_limit_test",
        "analysis_type": "Op sweep",
        "extracted_metrics": ["max_source_current_uA", "max_sink_current_uA", "compliant_low_v", "compliant_high_v"],
        "pass_fail_rule": "characterize the maximum forced source and sink current that keeps the output inside the compliant swing window",
        "required_corners": ["TT"],
        "required_operating_conditions": ["unity_feedback", "current_load sweep"],
        "monte_carlo_required": False,
    },
    "disabled_leakage": {
        "specification_aspect": "disabled supply leakage characterization",
        "category": "char",
        "test_name": "run_disabled_leakage_test",
        "analysis_type": "Op",
        "extracted_metrics": ["disabled_leakage_nA", "vout_disabled_dc"],
        "pass_fail_rule": "characterize supply current with EN held low under the nominal disabled fixture",
        "required_corners": ["TT"],
        "required_operating_conditions": ["disabled"],
        "monte_carlo_required": False,
    },
    "load_sweep": {
        "specification_aspect": "load-capacitance sweep characterization",
        "category": "char",
        "test_name": "run_load_sweep_test",
        "analysis_type": "Ac/Op",
        "extracted_metrics": ["cases", "worst_aol_db", "worst_phase_margin_deg", "worst_iq_uA"],
        "pass_fail_rule": "characterize nominal AC behavior across the generic capacitive-load sweep",
        "required_corners": ["TT"],
        "required_operating_conditions": ["c_load sweep"],
        "monte_carlo_required": False,
    },
    "pvt": {
        "specification_aspect": "PVT sweep characterization",
        "category": "char",
        "test_name": "run_pvt_test",
        "analysis_type": "Ac/Op",
        "extracted_metrics": ["cases", "worst_aol_db", "worst_gbw_hz", "worst_phase_margin_deg", "worst_iq_uA"],
        "pass_fail_rule": "characterize open-loop behavior across the supported process, voltage, and temperature matrix",
        "required_corners": ["TT", "FF", "SS"],
        "required_operating_conditions": ["vdd sweep", "temp sweep"],
        "monte_carlo_required": False,
    },
    "area_estimate": {
        "specification_aspect": "rough device-area estimate",
        "category": "char",
        "test_name": "run_area_estimate",
        "analysis_type": "calculation",
        "extracted_metrics": ["transistor_area_um2", "comp_cap_fF", "total_device_count"],
        "pass_fail_rule": "characterize a rough parameter-derived device footprint; product floorplan budgets belong in external tests",
        "required_corners": [],
        "required_operating_conditions": [],
        "monte_carlo_required": False,
    },
}


@dataclass(frozen=True)
class OpampCoreSpec:
    name: str = "opamp_core"
    purpose: str = "Compose the bias generator, gain stage, second stage, and compensation network."
    component_class: str = "reusable block"
    pins: tuple[str, ...] = ("VINP", "VINN", "VOUT", "EN", "VDD", "VSS")
    measurable_behaviors: tuple[str, ...] = (
        "open_loop",
        "direct_dc_gain",
        "internal_direct_gain",
        "direct_dc_gain_sweep",
        "closed_loop_step",
        "internal_nodes",
        "bias_characterization",
        "output_swing",
        "output_drive",
        "output_current_limit",
        "disabled_leakage",
        "load_sweep",
        "pvt",
        "area_estimate",
    )
    numeric_pass_fail_criteria: tuple[str, ...] = ("generic AC and transient contracts only; product budgets belong in external budget tests",)
    required_corners: tuple[str, ...] = ("TT",)
    statistical_verification_required: bool = False


@h.paramclass
class OpampCoreParams:
    gain_stage_params = h.Param(dtype=GainStageParams, desc="First-stage parameters", default=GainStageParams())
    second_stage_params = h.Param(dtype=SecondStageParams, desc="Second-stage parameters", default=SecondStageParams(device_type="p", w_amp=2.0, l_amp=2.0, w_load_scale=2.0, l_load=4.0))
    output_stage_params = h.Param(
        dtype=OutputStageParams,
        desc="Output-stage parameters",
        default=OutputStageParams(style="push_pull", w_amp=4.0, l_amp=1.0, w_load_scale=2.0, l_load=1.0, r_gate_bias=100e3),
    )
    freq_comp_params = h.Param(
        dtype=FreqCompParams,
        desc="Compensation parameters",
        default=FreqCompParams(c_comp=400e-15),
    )
    bias_gen_params = h.Param(
        dtype=BiasGenParams,
        desc="Bias generator parameters",
        default=BiasGenParams(device_type="p", dev_ref="PMOS_1p8V_STD", dev_out="PMOS_1p8V_STD"),
    )


@h.paramclass
class OpampCoreOpenLoopTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    c_load = h.Param(dtype=h.Scalar, desc="Load capacitance in F", default=1e-12)
    r_probe = h.Param(dtype=h.Scalar, desc="Weak output probe resistance in ohm", default=1e12)
    v_cm = h.Param(dtype=h.Scalar, desc="Input common-mode voltage in V", default=0.4)
    v_diff = h.Param(dtype=h.Scalar, desc="Differential AC excitation in V", default=1.0)
    dc_v_diff = h.Param(dtype=h.Scalar, desc="Differential DC excitation in V for direct-gain characterization", default=100e-6)
    f_start = h.Param(dtype=h.Scalar, desc="AC sweep start frequency in Hz", default=1.0)
    f_stop = h.Param(dtype=h.Scalar, desc="AC sweep stop frequency in Hz", default=1e9)
    npts = h.Param(dtype=int, desc="AC sweep points per decade", default=40)
    temp_c = h.Param(dtype=h.Scalar, desc="Simulation temperature in degC", default=27.0)


@h.paramclass
class OpampCoreClosedLoopStepTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    c_load = h.Param(dtype=h.Scalar, desc="Load capacitance in F", default=1e-12)
    v_step = h.Param(dtype=h.Scalar, desc="Step amplitude in V", default=10e-3)
    tstop = h.Param(dtype=h.Scalar, desc="Transient stop time in s", default=10e-6)
    tstep = h.Param(dtype=h.Scalar, desc="Transient step in s", default=100e-9)
    temp_c = h.Param(dtype=h.Scalar, desc="Simulation temperature in degC", default=27.0)


@h.paramclass
class OpampCoreFollowerTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    c_load = h.Param(dtype=h.Scalar, desc="Load capacitance in F", default=1e-12)
    r_probe = h.Param(dtype=h.Scalar, desc="Weak probe resistance in ohm", default=1e12)
    vout_low_target = h.Param(dtype=h.Scalar, desc="Low compliant swing target in V", default=0.1)
    vout_high_target = h.Param(dtype=h.Scalar, desc="High compliant swing target in V", default=1.7)
    vout_mid_target = h.Param(dtype=h.Scalar, desc="Mid-swing target used for current drive in V", default=0.9)
    drive_current_uA = h.Param(dtype=h.Scalar, desc="Source/sink current target in uA", default=25.0)
    drive_sweep_stop_uA = h.Param(dtype=h.Scalar, desc="Maximum forced current in uA for output-current characterization", default=40.0)
    drive_sweep_step_uA = h.Param(dtype=h.Scalar, desc="Forced-current step in uA for output-current characterization", default=2.5)
    temp_c = h.Param(dtype=h.Scalar, desc="Simulation temperature in degC", default=27.0)


@h.paramclass
class OpampCoreDisabledTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    c_load = h.Param(dtype=h.Scalar, desc="Load capacitance in F", default=1e-12)
    r_probe = h.Param(dtype=h.Scalar, desc="Weak probe resistance in ohm", default=1e12)
    v_cm = h.Param(dtype=h.Scalar, desc="Common-mode anchor in V", default=0.4)
    temp_c = h.Param(dtype=h.Scalar, desc="Simulation temperature in degC", default=27.0)


@h.generator
def opamp_core(params: OpampCoreParams) -> h.Module:
    gain_stage_inst = gain_stage(params.gain_stage_params)
    second_stage_inst = second_stage(params.second_stage_params)
    output_stage_inst = output_stage(params.output_stage_params)
    freq_comp_inst = freq_comp(params.freq_comp_params)
    bias_inst = bias_gen(params.bias_gen_params)

    mod = h.Module(name="OpampCore")
    mod.VINP, mod.VINN, mod.VOUT, mod.EN, mod.VDD, mod.VSS = h.Ports(6)
    mod.vx, mod.vref = h.Signals(2)
    mod.ibias1, mod.ibias2 = h.Signals(2)
    mod.vbias2 = h.Signal(name="vbias2")
    mod.vcm = h.Signal(name="vcm")
    mod.vdrv = h.Signal(name="vdrv")

    mod.xbias = bias_inst(VDD=mod.VDD, VSS=mod.VSS, EN=mod.EN, IBIAS1=mod.ibias1, IBIAS2=mod.ibias2)
    # The push-pull output stage is inverting. Flip the first-stage differential
    # sense here so the top-level opamp polarity remains unchanged.
    mod.xgain = gain_stage_inst(VINP=mod.VINN, VINN=mod.VINP, VX=mod.vx, VREF=mod.vref, IBIAS=mod.ibias1, VDD=mod.VDD, VSS=mod.VSS)
    # Internal common-mode anchor keeps the inter-stage and output nodes out of hard rails.
    mod.rvcm_top = h.Res(r=10e6)(p=mod.VDD, n=mod.vcm)
    mod.rvcm_bot = h.Res(r=10e6)(p=mod.vcm, n=mod.VSS)

    # Convert the mirrored bias current into the gate-bias voltage required by the
    # selected second-stage load polarity.
    bias2_ref_par = sky130_hdl21.Sky130MosParams(
        w=params.second_stage_params.w_amp,
        l=params.second_stage_params.l_amp,
        nf=params.second_stage_params.nf_amp,
        mult=params.second_stage_params.m_amp,
    )
    if params.second_stage_params.device_type == "n":
        mod.bias2_ref = sky130_hdl21.primitives.PMOS_1p8V_STD(bias2_ref_par)(d=mod.vbias2, g=mod.vbias2, s=mod.VDD, b=mod.VDD)
    else:
        mod.bias2_ref = sky130_hdl21.primitives.NMOS_1p8V_STD(bias2_ref_par)(d=mod.vbias2, g=mod.vbias2, s=mod.VSS, b=mod.VSS)
    mod.bias2_short = h.Res(r=1e-3)(p=mod.ibias2, n=mod.vbias2)
    mod.xsecond = second_stage_inst(VIN=mod.vx, VOUT=mod.vdrv, IBIAS=mod.vbias2, VDD=mod.VDD, VSS=mod.VSS)
    mod.xout = output_stage_inst(VIN=mod.vdrv, VOUT=mod.VOUT, IBIAS=mod.vbias2, VDD=mod.VDD, VSS=mod.VSS)
    mod.xcomp = freq_comp_inst(V1=mod.vx, VOUT=mod.vdrv)
    mod.bleed_vdrv = h.Res(r=1e9)(p=mod.vdrv, n=mod.vcm)
    # Keep floating nodes numerically well-behaved without materially loading the
    # high-impedance gain nodes.
    mod.bleed_vx = h.Res(r=1e9)(p=mod.vx, n=mod.vcm)
    mod.bleed_vref = h.Res(r=1e9)(p=mod.vref, n=mod.vcm)
    mod.bleed_vout = h.Res(r=1e9)(p=mod.VOUT, n=mod.vcm)
    return mod


def _default_ngspice_options(test_name: str) -> SimOptions:
    return SimOptions(
        simulator=SupportedSimulators.NGSPICE,
        fmt=ResultFormat.SIM_DATA,
        rundir=f"./tmp/{test_name}",
    )


def _op_scalar(result, signal_name: str) -> float:
    op = getattr(result.an[0], "op", result.an[0])
    target = signal_name.lower()
    if isinstance(getattr(op, "data", None), dict):
        for name, value in op.data.items():
            if name.lower() == target:
                return float(value)
        raise RuntimeError(f"Signal {signal_name} not found in op result: {list(op.data.keys())}")
    for name, value in zip(op.signals, op.data):
        if name.lower() == target:
            return float(value)
    raise RuntimeError(f"Signal {signal_name} not found in op result")


def _op_scalar_suffix(result, suffix: str) -> float:
    op = getattr(result.an[0], "op", result.an[0])
    target = suffix.lower()
    if isinstance(getattr(op, "data", None), dict):
        for name, value in op.data.items():
            if name.lower().endswith(target):
                return float(value)
        raise RuntimeError(f"Signal suffix {suffix} not found in op result: {list(op.data.keys())}")
    for name, value in zip(op.signals, op.data):
        if name.lower().endswith(target):
            return float(value)
    raise RuntimeError(f"Signal suffix {suffix} not found in op result")


def _tran_waveform(result, signal_name: str):
    tran = getattr(result.an[0], "tran", result.an[0])
    target = signal_name.lower()
    if hasattr(tran, "signals") and hasattr(tran, "data"):
        signals = list(tran.signals)
        if target not in [name.lower() for name in signals]:
            raise RuntimeError(f"Signal {signal_name} not found in tran result: {signals}")
        idx = next(idx for idx, name in enumerate(signals) if name.lower() == target)
        nsignals = len(signals)
        data = list(tran.data)
        npts = len(data) // nsignals
        start = idx * npts
        return data[start : start + npts]
    if isinstance(getattr(tran, "data", None), dict):
        for name, value in tran.data.items():
            if name.lower() == target:
                return value
        raise RuntimeError(f"Signal {signal_name} not found in tran result keys: {list(tran.data.keys())}")
    raise RuntimeError(f"Unsupported tran result shape for signal {signal_name}: {type(tran)}")


def _extract_ac_trace(result, signal_name: str):
    ac = result.an[0]
    target = signal_name.lower()
    for key, data in ac.data.items():
        if key.lower() == target:
            return ac.freq, data
    raise RuntimeError(f"AC trace {signal_name} not found in result keys: {list(ac.data.keys())}")


def _extract_ac_trace_suffix(result, suffix: str):
    ac = result.an[0]
    target = suffix.lower()
    for key, data in ac.data.items():
        if key.lower().endswith(target):
            return ac.freq, data
    raise RuntimeError(f"AC trace suffix {suffix} not found in result keys: {list(ac.data.keys())}")


def _interp_crossing(x_vals, y_vals, target: float):
    for idx in range(1, len(y_vals)):
        y0 = float(y_vals[idx - 1])
        y1 = float(y_vals[idx])
        if (y0 - target) == 0.0:
            return float(x_vals[idx - 1]), idx - 1
        if (y0 - target) * (y1 - target) <= 0.0 and y1 != y0:
            frac = (target - y0) / (y1 - y0)
            x = float(x_vals[idx - 1] + frac * (x_vals[idx] - x_vals[idx - 1]))
            return x, idx
    return float("nan"), None


def _interp_value(x_vals, y_vals, x_target: float):
    for idx in range(1, len(x_vals)):
        x0 = float(x_vals[idx - 1])
        x1 = float(x_vals[idx])
        if x0 <= x_target <= x1 and x1 != x0:
            frac = (x_target - x0) / (x1 - x0)
            return float(y_vals[idx - 1] + frac * (y_vals[idx] - y_vals[idx - 1]))
    return float("nan")


def _phase_margin_from_unity_phase(phase_deg_at_unity: float) -> float:
    """Map the loop-gain phase at unity into a physical phase-margin range.

    The current series-injection loop-break fixture can produce either the
    conventional negative-feedback phase near ``-180 deg`` or the same loop gain
    with a 180-degree sign offset. Normalize the result into the physical phase-
    margin interval ``[0, 180]`` without changing the underlying AOL/ GBW data.
    """
    if not math.isfinite(phase_deg_at_unity):
        return float("nan")
    phase = ((phase_deg_at_unity + 180.0) % 360.0) - 180.0
    pm = phase if phase >= 0.0 else 180.0 + phase
    return min(max(pm, 0.0), 180.0)


def _negative_feedback_phase_trace(loop_gain: np.ndarray):
    """Return a loop-gain phase trace referenced to the negative-feedback branch.

    Series-injection benches often report the low-frequency loop phase on the
    `+180 deg` branch. For PM/ GM extraction we want the continuous branch around
    `-180 deg`, not a wrapped positive-angle representation.
    """
    if len(loop_gain) == 0:
        return np.asarray([], dtype=float), float("nan")
    phase_deg = np.unwrap(np.angle(loop_gain)) * 180.0 / math.pi
    if float(phase_deg[0]) > 90.0:
        phase_deg = phase_deg - 360.0
    return phase_deg, float(phase_deg[0])


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
            Save("i(v.xtop.vvvdd), v(xtop.vout), v(xtop.vinn_sig), v(xtop.xdut.vx), v(xtop.xdut.vref), v(xtop.xdut.vbias2)"),
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
        _default_ngspice_options("opamp_core_direct_dc_gain_ac"),
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
        _default_ngspice_options("opamp_core_direct_dc_gain_bias"),
    )
    _, vout_amp = _extract_ac_trace(ac_result, "v(xtop.vout)")
    low_freq_vout = complex(np.asarray(vout_amp)[0])
    direct_gain_vv = abs(low_freq_vout) / max(abs(float(tb_params.dc_v_diff)), 1e-18)
    direct_gain_db = 20.0 * math.log10(max(direct_gain_vv, 1e-30))
    iq_abs = abs(_op_scalar(op_result, "i(v.xtop.vvvdd)"))
    return make_test_result(
        component="opamp_core",
        category="char",
        purpose="direct_dc_gain",
        metrics={
            "vout_dc": _op_scalar(op_result, "v(xtop.vout)"),
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
        _default_ngspice_options("opamp_core_internal_direct_gain_ac"),
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
        _default_ngspice_options("opamp_core_internal_direct_gain_bias"),
    )
    _, vdrv_amp = _extract_ac_trace_suffix(ac_result, ".vdrv)")
    low_freq_vdrv = complex(np.asarray(vdrv_amp)[0])
    direct_gain_vv = abs(low_freq_vdrv) / max(abs(float(tb_params.dc_v_diff)), 1e-18)
    direct_gain_db = 20.0 * math.log10(max(direct_gain_vv, 1e-30))
    return make_test_result(
        component="opamp_core",
        category="char",
        purpose="internal_direct_gain",
        metrics={
            "vdrv_dc": _op_scalar_suffix(op_result, ".vdrv)"),
            "low_freq_vdrv_mag": abs(low_freq_vdrv),
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
    ac_failed = False
    phase_at_unity_deg_raw = float("nan")
    low_freq_phase_deg_raw = float("nan")
    try:
        ac_result = run_ngspice_sim(
            _build_open_loop_tb(
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
            ),
            sim_options if sim_options is not None else _default_ngspice_options("opamp_core_open_loop_pos"),
        )
    except Exception:
        ac_failed = True
        ac_result = None
    op_result = run_ngspice_sim(
        _build_open_loop_op_tb(
            dut_params,
            vdd=float(tb_params.vdd),
            c_load=float(tb_params.c_load),
            r_probe=float(tb_params.r_probe),
            v_cm=float(tb_params.v_cm),
            temp_c=float(tb_params.temp_c),
            corner=corner,
        ),
        _default_ngspice_options("opamp_core_open_loop_bias"),
    )
    direct_gain = run_direct_dc_gain_test(dut_params, tb_params, corner=corner)
    direct_gain_est = float(direct_gain["metrics"]["direct_gain_vv"])
    direct_dc_gain_db = float(direct_gain["metrics"]["direct_gain_db"])
    if not ac_failed:
        freq, vout_amp = _extract_ac_trace(ac_result, "v(xtop.vout)")
        _, vfb = _extract_ac_trace(ac_result, "v(xtop.vinn_sig)")
        freq = np.asarray(freq, dtype=float)
        vout_amp = np.asarray(vout_amp)
        vfb = np.asarray(vfb)
        vtest_amp = vout_amp - vfb
        # Series-injection return-ratio estimate:
        # T ~= -Vtest / Vreturn, where Vreturn is the signal on the feedback side
        # of the break and Vtest is the injected AC voltage across the break.
        loop_gain = -vtest_amp / np.where(np.abs(vfb) > 1e-30, vfb, 1e-30 + 0j)
        mag = np.abs(loop_gain)
        mag_db = 20.0 * np.log10(np.maximum(mag, 1e-30))
        phase_deg, low_freq_phase_deg_raw = _negative_feedback_phase_trace(loop_gain)
        loop_gain_dc_db = float(mag_db[0]) if len(mag_db) else float("nan")
        aol_db = direct_dc_gain_db
        gbw_hz, _ = _interp_crossing(freq, mag, 1.0)
        phase_margin_deg = float("nan")
        if math.isfinite(gbw_hz):
            phase_at_unity = _interp_value(freq, phase_deg, gbw_hz)
            if math.isfinite(phase_at_unity):
                phase_at_unity_deg_raw = phase_at_unity
                phase_margin_deg = 180.0 + phase_at_unity
        phase_cross_hz, _ = _interp_crossing(freq, phase_deg, -180.0)
        gain_margin_db = float("nan")
        if math.isfinite(phase_cross_hz):
            mag_db_at_phase_cross = _interp_value(freq, mag_db, phase_cross_hz)
            if math.isfinite(mag_db_at_phase_cross):
                gain_margin_db = -mag_db_at_phase_cross
        elif len(phase_deg) and float(np.min(phase_deg)) > -180.0:
            gain_margin_db = float("inf")
        gain_est = direct_gain_est
    else:
        gain_est = direct_gain_est
        aol_db = direct_dc_gain_db
        loop_gain_dc_db = float("nan")
        gbw_hz = float("nan")
        phase_margin_deg = float("nan")
        gain_margin_db = float("nan")
    iq_abs = abs(_op_scalar(op_result, "i(v.xtop.vvvdd)"))
    metrics = {
        "gain_est": gain_est,
        "aol_db": aol_db,
        "direct_dc_gain_db": direct_dc_gain_db,
        "loop_gain_dc_db": loop_gain_dc_db,
        "gbw_hz": gbw_hz,
        "phase_margin_deg": phase_margin_deg,
        "gain_margin_db": gain_margin_db,
        "phase_at_unity_deg_raw": phase_at_unity_deg_raw,
        "low_freq_phase_deg_raw": low_freq_phase_deg_raw,
        "sign_offset_detected": False,
        "iq_uA": 1e6 * iq_abs,
        "ac_fixture_ok": not ac_failed,
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
    return make_test_result(
        component="opamp_core",
        category="char",
        purpose="open_loop",
        metrics=metrics,
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
        sim_options if sim_options is not None else _default_ngspice_options("opamp_core_internal_nodes"),
    )
    iq_abs = abs(_op_scalar(result, "i(v.xtop.vvvdd)"))
    metrics = {
        "vx_dc": _op_scalar_suffix(result, ".vx)"),
        "vref_dc": _op_scalar_suffix(result, ".vref)"),
        "vbias2_dc": _op_scalar_suffix(result, ".vbias2)"),
        "vout_dc": _op_scalar(result, "v(xtop.vout)"),
        "iq_uA": 1e6 * iq_abs,
    }
    return make_test_result(
        component="opamp_core",
        category="char",
        purpose="internal_nodes",
        metrics=metrics,
    )


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
        vstep = h.Vpulse(
            v1=0.0,
            v2=tb_params.v_step,
            delay=1e-6,
            rise=100e-9,
            fall=100e-9,
            width=tb_params.tstop,
            period=2 * tb_params.tstop,
        )(p=vinp_sig, n=VSS)
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
        sim_options if sim_options is not None else _default_ngspice_options("opamp_core_closed_loop_step"),
    )
    vout = _tran_waveform(result, "v(xtop.vout)")
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
        margin={
            "overshoot_margin": metrics["target_step"] - metrics["overshoot"],
        },
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
        sim_options if sim_options is not None else _default_ngspice_options("opamp_core_output_swing_low"),
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
        _default_ngspice_options("opamp_core_output_swing_high"),
    )
    metrics = {
        "vout_low_target": float(tb_params.vout_low_target),
        "vout_low_actual": _op_scalar(low_result, "v(xtop.vout)"),
        "vout_high_target": float(tb_params.vout_high_target),
        "vout_high_actual": _op_scalar(high_result, "v(xtop.vout)"),
    }
    return make_test_result(
        component="opamp_core",
        category="char",
        purpose="output_swing",
        metrics=metrics,
    )


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
        sim_options if sim_options is not None else _default_ngspice_options("opamp_core_output_drive_source"),
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
        _default_ngspice_options("opamp_core_output_drive_sink"),
    )
    metrics = {
        "requested_source_load_uA": float(tb_params.drive_current_uA),
        "requested_sink_load_uA": float(tb_params.drive_current_uA),
        "vout_source": _op_scalar(source_result, "v(xtop.vout)"),
        "vout_sink": _op_scalar(sink_result, "v(xtop.vout)"),
        "target_vout": float(tb_params.vout_mid_target),
    }
    return make_test_result(
        component="opamp_core",
        category="char",
        purpose="output_drive",
        metrics=metrics,
    )


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
        sim_options if sim_options is not None else _default_ngspice_options("opamp_core_disabled_leakage"),
    )
    iq_abs = abs(_op_scalar(result, "i(v.xtop.vvvdd)"))
    metrics = {
        "disabled_leakage_nA": 1e9 * iq_abs,
        "vout_disabled_dc": _op_scalar(result, "v(xtop.vout)"),
    }
    return make_test_result(
        component="opamp_core",
        category="char",
        purpose="disabled_leakage",
        metrics=metrics,
    )


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
            _default_ngspice_options(f"opamp_core_output_current_source_{current_uA:g}uA"),
        )
        vout_source = _op_scalar(source_result, "v(xtop.vout)")
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
            _default_ngspice_options(f"opamp_core_output_current_sink_{current_uA:g}uA"),
        )
        vout_sink = _op_scalar(sink_result, "v(xtop.vout)")
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
        metrics={
            "cases": cases,
            "worst_aol_db": worst_aol_db,
            "worst_phase_margin_deg": worst_phase_margin_deg,
            "worst_iq_uA": worst_iq_uA,
        },
    )


def run_pvt_test(
    dut_params: OpampCoreParams | None = None,
    tb_params: OpampCoreOpenLoopTbParams | None = None,
):
    dut_params = dut_params or OpampCoreParams()
    tb_params = tb_params or OpampCoreOpenLoopTbParams()
    corners = {
        "TT": h.pdk.Corner.TYP,
        "FF": h.pdk.Corner.FAST,
        "SS": h.pdk.Corner.SLOW,
    }
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
        metrics={
            "cases": cases,
            "worst_aol_db": worst_aol_db,
            "worst_gbw_hz": worst_gbw_hz,
            "worst_phase_margin_deg": worst_phase_margin_deg,
            "worst_iq_uA": worst_iq_uA,
        },
    )


def run_area_estimate(dut_params: OpampCoreParams | None = None):
    dut_params = dut_params or OpampCoreParams()

    def mos_area(w: float, l: float, nf: int, mult: int, count: int = 1) -> float:
        return float(w) * float(l) * int(nf) * int(mult) * int(count)

    bias = dut_params.bias_gen_params
    gain = dut_params.gain_stage_params
    second = dut_params.second_stage_params
    output = dut_params.output_stage_params
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
    second_area = (
        mos_area(second.w_amp, second.l_amp, second.nf_amp, second.m_amp)
        + mos_area(second.w_amp * second.w_load_scale, second.l_load, second.nf_amp, second.m_amp)
    )
    output_area = (
        mos_area(output.w_amp, output.l_amp, output.nf_amp, output.m_amp)
        + mos_area(output.w_amp * output.w_load_scale, output.l_load, output.nf_amp, output.m_amp)
    )
    bias2_ref_area = mos_area(second.w_amp, second.l_amp, second.nf_amp, second.m_amp)
    total_device_count = 3 + 4 + 2 + 2 + 1
    if gain.load_style == "cascoded":
        total_device_count += 2
    transistor_area_um2 = bias_area + gain_area + second_area + output_area + bias2_ref_area
    return make_test_result(
        component="opamp_core",
        category="char",
        purpose="area_estimate",
        metrics={
            "transistor_area_um2": transistor_area_um2,
            "comp_cap_fF": 1e15 * float(comp.c_comp),
            "total_device_count": total_device_count,
        },
    )


def run_all_tests(
    dut_params: OpampCoreParams | None = None,
    *,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or OpampCoreParams()
    return {
        "structural": make_test_result(
            component="opamp_core",
            category="smoke",
            purpose="basic",
            metrics=run_structural_checks(dut_params),
            passed=True,
        ),
        "direct_dc_gain": run_direct_dc_gain_test(dut_params),
        "open_loop": run_open_loop_test(dut_params, sim_options=sim_options),
        "bias_characterization": run_bias_characterization_test(dut_params),
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
    step_tb = OpampCoreClosedLoopStepTbParams(
        vdd=1.8,
        c_load=1e-12,
        v_step=10e-3,
        tstop=5e-6,
        tstep=100e-9,
        temp_c=27.0,
    )
    follower_tb = OpampCoreFollowerTbParams(
        vdd=1.8,
        c_load=1e-12,
        r_probe=1e12,
        vout_low_target=0.1,
        vout_high_target=1.7,
        vout_mid_target=0.9,
        drive_current_uA=25.0,
        drive_sweep_stop_uA=25.0,
        drive_sweep_step_uA=5.0,
        temp_c=27.0,
    )
    disabled_tb = OpampCoreDisabledTbParams(
        vdd=1.8,
        c_load=1e-12,
        r_probe=1e12,
        v_cm=0.4,
        temp_c=27.0,
    )
    return {
        "structural": make_test_result(
            component="opamp_core",
            category="smoke",
            purpose="fast_structural",
            metrics=run_structural_checks(dut_params),
            passed=True,
        ),
        "direct_dc_gain": run_direct_dc_gain_test(dut_params, open_loop_tb),
        "open_loop": run_open_loop_test(dut_params, open_loop_tb, sim_options=sim_options),
        "closed_loop_step": run_closed_loop_step_test(dut_params, step_tb, sim_options=sim_options),
        "output_drive": run_output_drive_test(dut_params, follower_tb),
        "disabled_leakage": run_disabled_leakage_test(dut_params, disabled_tb),
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
        "contains_gain_stage": "GainStage" in text,
        "contains_second_stage": "SecondStage" in text,
        "contains_output_stage": "OutputStage" in text,
        "contains_freq_comp": "FreqComp" in text,
    }
    if not all(checks.values()):
        raise RuntimeError(f"Structural checks failed: {checks}")
    return checks
