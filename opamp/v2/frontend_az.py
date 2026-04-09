from dataclasses import dataclass

import hdl21 as h
from components.sample_hold_cap import SampleHoldCapParams, sample_hold_cap
from components.tg_switch import TgSwitchParams, tg_switch

from .pdk_resistor import pdk_resistor


VERIFICATION_PLAN = {
    "structural": {
        "specification_aspect": "generator/export contract",
        "category": "structural",
        "test_name": "run_structural_checks",
        "analysis_type": "generator/elaboration/export",
        "extracted_metrics": ["generator_call", "elaboration", "subckt_name", "contains_tg_switch", "contains_sample_hold_cap"],
        "pass_fail_rule": "all structural checks pass",
        "required_corners": [],
        "required_operating_conditions": [],
        "monte_carlo_required": False,
    },
    "pedestal_zero_input": {
        "specification_aspect": "zero-input switched-cap pedestal behavior",
        "category": "contract",
        "test_name": "run_pedestal_zero_input_test",
        "analysis_type": "Tran",
        "extracted_metrics": ["pedestal_uV"],
        "pass_fail_rule": "zero-input switching sequence produces a finite and measurable pedestal result",
        "required_corners": ["TT"],
        "required_operating_conditions": ["hold_cap"],
        "monte_carlo_required": False,
    },
    "settling_in_phase_window": {
        "specification_aspect": "settling during amplify phase",
        "category": "contract",
        "test_name": "run_settling_in_phase_window_test",
        "analysis_type": "Tran",
        "extracted_metrics": ["settling_residue_uV", "phase_window_utilization"],
        "pass_fail_rule": "frontend exposes measurable settling behavior during the amplify phase window",
        "required_corners": ["TT"],
        "required_operating_conditions": ["sc_loop"],
        "monte_carlo_required": False,
    },
}


@dataclass(frozen=True)
class FrontendAzSpec:
    name: str = "frontend_az"
    purpose: str = "Sample and apply an offset-correction term to the non-inverting input during auto-zero operation."
    component_class: str = "reusable block"
    pins: tuple[str, ...] = ("VINP", "VINN", "VOFF", "VXP", "VXN", "PHI1", "PHI1B", "PHI2", "PHI2B", "PHI3", "PHI3B", "VDD", "VSS")
    measurable_behaviors: tuple[str, ...] = ("pedestal_zero_input", "settling_in_phase_window")
    numeric_pass_fail_criteria: tuple[str, ...] = ("generic transient contract only; product budgets belong in external budget tests",)
    required_corners: tuple[str, ...] = ("TT",)
    statistical_verification_required: bool = False


@h.paramclass
class FrontendAzParams:
    c_az = h.Param(dtype=h.Scalar, desc="Per-side AZ capacitor in F", default=1e-12)
    w_sw_n = h.Param(dtype=h.Scalar, desc="NMOS switch width in um", default=0.65)
    w_sw_p = h.Param(dtype=h.Scalar, desc="PMOS switch width in um", default=1.0)
    l_sw = h.Param(dtype=h.Scalar, desc="Switch length in um", default=0.15)
    nf_sw = h.Param(dtype=int, desc="Switch fingers", default=1)
    m_sw = h.Param(dtype=int, desc="Switch multiplier", default=1)
    use_dummy_switch = h.Param(dtype=bool, desc="Add dummy TG devices", default=False)
    r_vcm_top = h.Param(dtype=h.Scalar, desc="Top resistor for sampled output-error attenuator in ohm", default=1e3)
    r_vcm_bot = h.Param(dtype=h.Scalar, desc="Bottom resistor for sampled output-error attenuator in ohm", default=1e6)
    r_out_p = h.Param(dtype=h.Scalar, desc="Series resistor from SC non-inverting node to core input in ohm", default=1.0)
    r_out_n = h.Param(dtype=h.Scalar, desc="Series resistor from SC inverting node to core input in ohm", default=1.0)
    c_out_p = h.Param(dtype=h.Scalar, desc="Optional shunt capacitor on core-facing non-inverting input in F", default=0.0)
    c_out_n = h.Param(dtype=h.Scalar, desc="Optional shunt capacitor on core-facing inverting input in F", default=0.0)
    c_corr_n_scale = h.Param(dtype=h.Scalar, desc="Fractional mirrored correction capacitor on the inverting path", default=0.0)


@h.paramclass
class FrontendAzPedestalZeroInputTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    period = h.Param(dtype=h.Scalar, desc="Clock period in s", default=20e-6)
    dead_time = h.Param(dtype=h.Scalar, desc="Clock dead time between PHI1 and PHI2 in s", default=2e-6)
    phi1_share = h.Param(dtype=h.Scalar, desc="Fraction of active time allocated to sample_zero", default=0.4)
    phi2_share = h.Param(dtype=h.Scalar, desc="Fraction of active time allocated to correction_apply", default=0.2)
    phi3_share = h.Param(dtype=h.Scalar, desc="Fraction of active time allocated to settle", default=0.4)
    tstop = h.Param(dtype=h.Scalar, desc="Transient stop time in s", default=120e-6)
    tstep = h.Param(dtype=h.Scalar, desc="Transient step in s", default=100e-9)


@h.paramclass
class FrontendAzSettlingInPhaseWindowTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    c_load = h.Param(dtype=h.Scalar, desc="Observation capacitance in F", default=100e-15)
    period = h.Param(dtype=h.Scalar, desc="Clock period in s", default=20e-6)
    dead_time = h.Param(dtype=h.Scalar, desc="Clock dead time between PHI1 and PHI2 in s", default=2e-6)
    phi1_share = h.Param(dtype=h.Scalar, desc="Fraction of active time allocated to sample_zero", default=0.4)
    phi2_share = h.Param(dtype=h.Scalar, desc="Fraction of active time allocated to correction_apply", default=0.2)
    phi3_share = h.Param(dtype=h.Scalar, desc="Fraction of active time allocated to settle", default=0.4)
    tstop = h.Param(dtype=h.Scalar, desc="Transient stop time in s", default=120e-6)
    tstep = h.Param(dtype=h.Scalar, desc="Transient step in s", default=100e-9)


@h.generator
def frontend_az(params: FrontendAzParams) -> h.Module:
    c_az = float(params.c_az)
    w_sw_n = float(params.w_sw_n)
    w_sw_p = float(params.w_sw_p)
    l_sw = float(params.l_sw)
    r_vcm_top = float(params.r_vcm_top)
    r_vcm_bot = float(params.r_vcm_bot)
    r_out_p = float(params.r_out_p)
    r_out_n = float(params.r_out_n)
    c_out_p = float(params.c_out_p)
    c_out_n = float(params.c_out_n)
    c_corr_n_scale = float(params.c_corr_n_scale)

    if c_az <= 0:
        raise ValueError("c_az must be positive")
    if w_sw_n <= 0 or w_sw_p <= 0 or l_sw <= 0:
        raise ValueError("w_sw_n, w_sw_p, and l_sw must be positive")
    if params.nf_sw < 1 or params.m_sw < 1:
        raise ValueError("nf_sw and m_sw must be >= 1")
    if r_vcm_top <= 0 or r_vcm_bot <= 0:
        raise ValueError("r_vcm_top and r_vcm_bot must be positive")
    if r_out_p <= 0 or r_out_n <= 0:
        raise ValueError("r_out_p and r_out_n must be positive")
    if c_out_p < 0 or c_out_n < 0:
        raise ValueError("c_out_p and c_out_n must be >= 0")
    if c_corr_n_scale < 0:
        raise ValueError("c_corr_n_scale must be >= 0")

    tg_params = TgSwitchParams(
        w_n=params.w_sw_n,
        l_n=params.l_sw,
        nf_n=params.nf_sw,
        m_n=params.m_sw,
        w_p=params.w_sw_p,
        l_p=params.l_sw,
        nf_p=params.nf_sw,
        m_p=params.m_sw,
        use_dummy_switch=params.use_dummy_switch,
    )
    cap_params = SampleHoldCapParams(c_target=params.c_az)

    tg = tg_switch(tg_params)
    cap = sample_hold_cap(cap_params)

    mod = h.Module(name="FrontendAz")
    mod.VINP, mod.VINN, mod.VOFF, mod.VXP, mod.VXN, mod.PHI1, mod.PHI1B, mod.PHI2, mod.PHI2B, mod.PHI3, mod.PHI3B, mod.VDD, mod.VSS = h.Ports(13)
    mod.samp_p, mod.samp_n, mod.voff_sense, mod.vxp_sc, mod.vxn_sc = h.Signals(5)

    mod.rvoff_top = pdk_resistor(params.r_vcm_top, p=mod.VOFF, n=mod.voff_sense, bulk=mod.VSS)
    mod.rvoff_bot = pdk_resistor(params.r_vcm_bot, p=mod.voff_sense, n=mod.VSS, bulk=mod.VSS)

    # During sample_zero, store the present output error on the left plate while
    # the core-facing non-inverting node is reset near ground. During settle,
    # reconnect the left plate to VINP so the core sees VINP - VOFF(sampled)
    # on a live signal path instead of on a floating held node.
    mod.xsw_err_sample = tg(A=mod.voff_sense, B=mod.samp_p, PHI=mod.PHI1, PHIB=mod.PHI1B, VDD=mod.VDD, VSS=mod.VSS)
    mod.xsw_vxp_reset = tg(A=mod.VSS, B=mod.vxp_sc, PHI=mod.PHI1, PHIB=mod.PHI1B, VDD=mod.VDD, VSS=mod.VSS)
    mod.xsw_vxp_apply = tg(A=mod.VINP, B=mod.samp_p, PHI=mod.PHI3, PHIB=mod.PHI3B, VDD=mod.VDD, VSS=mod.VSS)
    mod.xcap_p_phys = cap(P=mod.samp_p, N=mod.vxp_sc)
    mod.xcap_p = h.Cap(c=params.c_az)(p=mod.samp_p, n=mod.vxp_sc)
    mod.rout_p = pdk_resistor(params.r_out_p, p=mod.vxp_sc, n=mod.VXP, bulk=mod.VSS)
    if c_out_p > 0:
        mod.cout_p = h.Cap(c=params.c_out_p)(p=mod.VXP, n=mod.VSS)

    # Keep the inverting path simple and predictable: reset during sample_zero,
    # then transparently pass the external VINN signal during settle.
    mod.xsw_vxn_reset = tg(A=mod.VSS, B=mod.vxn_sc, PHI=mod.PHI1, PHIB=mod.PHI1B, VDD=mod.VDD, VSS=mod.VSS)
    mod.xsw_vxn_track = tg(A=mod.VINN, B=mod.vxn_sc, PHI=mod.PHI3, PHIB=mod.PHI3B, VDD=mod.VDD, VSS=mod.VSS)
    mod.xcap_n_phys = cap(P=mod.vxn_sc, N=mod.VSS)
    mod.xcap_n = h.Cap(c=max(0.5 * params.c_az, 1e-15))(p=mod.vxn_sc, n=mod.VSS)
    if c_corr_n_scale > 0:
        mod.xsw_err_sample_n = tg(A=mod.voff_sense, B=mod.samp_n, PHI=mod.PHI1, PHIB=mod.PHI1B, VDD=mod.VDD, VSS=mod.VSS)
        mod.xsw_vxn_apply_corr = tg(A=mod.VINN, B=mod.samp_n, PHI=mod.PHI3, PHIB=mod.PHI3B, VDD=mod.VDD, VSS=mod.VSS)
        mod.xcap_corr_n_phys = cap(P=mod.samp_n, N=mod.vxn_sc)
        mod.xcap_corr_n = h.Cap(c=max(c_corr_n_scale * params.c_az, 1e-15))(p=mod.samp_n, n=mod.vxn_sc)
    mod.rout_n = pdk_resistor(params.r_out_n, p=mod.vxn_sc, n=mod.VXN, bulk=mod.VSS)
    if c_out_n > 0:
        mod.cout_n = h.Cap(c=params.c_out_n)(p=mod.VXN, n=mod.VSS)

    return mod

from .measure_az import (
    build_pedestal_zero_input_test,
    build_settling_in_phase_window_test,
    elaborate_dut,
    export_spice,
    print_test_report,
    run_all_tests,
    run_pedestal_zero_input_test,
    run_settling_in_phase_window_test,
    run_structural_checks,
)
