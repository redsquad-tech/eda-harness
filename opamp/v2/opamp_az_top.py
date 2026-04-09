from dataclasses import dataclass

import hdl21 as h
from .frontend_az import FrontendAzParams, frontend_az
from .opamp_core import OpampCoreParams, opamp_core


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
        default=FrontendAzParams(c_az=7e-14, r_vcm_top=8e2, r_vcm_bot=5),
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
    period = h.Param(dtype=h.Scalar, desc="AZ clock period in s", default=20e-6)
    dead_time = h.Param(dtype=h.Scalar, desc="Clock dead time between PHI1 and PHI2 in s", default=2e-6)
    phi1_share = h.Param(dtype=h.Scalar, desc="Fraction of active time allocated to sample_zero", default=0.4)
    phi2_share = h.Param(dtype=h.Scalar, desc="Fraction of active time allocated to correction_apply", default=0.2)
    phi3_share = h.Param(dtype=h.Scalar, desc="Fraction of active time allocated to settle", default=0.4)
    tstop = h.Param(dtype=h.Scalar, desc="Transient stop time in s", default=200e-6)
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

from .measure_top import (
    build_closed_loop_step_test,
    build_noise_and_offset_test,
    build_open_loop_test,
    elaborate_dut,
    export_spice,
    print_test_report,
    run_all_tests,
    run_closed_loop_step_test,
    run_noise_and_offset_test,
    run_open_loop_test,
    run_reduced_pvt_test,
    run_structural_checks,
)
