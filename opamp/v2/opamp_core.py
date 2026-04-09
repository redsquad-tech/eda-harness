from dataclasses import dataclass

import hdl21 as h
import sky130_hdl21
from .bias_gen import BiasGenParams, bias_gen
from .freq_comp import FreqCompParams, freq_comp
from .output_buffer import OutputStageParams, output_stage
from .pdk_resistor import pdk_resistor
from components.diffpair_n import DiffpairNParams, diffpair_n
from components.diffpair_p import DiffpairPParams, diffpair_p


VERIFICATION_PLAN = {
    "structural": {
        "specification_aspect": "generator/export contract",
        "category": "structural",
        "test_name": "run_structural_checks",
        "analysis_type": "generator/elaboration/export",
        "extracted_metrics": ["generator_call", "elaboration", "subckt_name", "contains_bias_gen", "contains_input_stage", "contains_gm_stage", "contains_freq_comp"],
        "pass_fail_rule": "all structural checks pass",
        "required_corners": [],
        "required_operating_conditions": [],
        "monte_carlo_required": False,
    },
    "open_loop": {
        "specification_aspect": "direct open-loop gain plus closed-loop stability characterization",
        "category": "char",
        "test_name": "run_open_loop_test",
        "analysis_type": "Ac/Op",
        "extracted_metrics": [
            "aol_db",
            "direct_dc_gain_db",
            "gbw_hz",
            "phase_margin_deg",
            "gain_margin_db",
            "phase_at_unity_deg_raw",
            "low_freq_phase_deg_raw",
            "iq_uA",
            "ac_fixture_ok",
        ],
        "pass_fail_rule": "component exposes measurable direct open-loop gain and unity-follower stability behavior under the nominal fixture",
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
        "extracted_metrics": ["vx_dc", "vref_dc", "ibias1_dc", "ibias2_dc", "vout_dc", "iq_uA"],
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
    "disable_nodes": {
        "specification_aspect": "disabled internal-node characterization",
        "category": "char",
        "test_name": "run_disable_nodes_test",
        "analysis_type": "Op",
        "extracted_metrics": ["vx_dc", "vref_dc", "ibias1_dc", "ibias2_dc", "vbp_dc", "vout_dc", "iq_uA"],
        "pass_fail_rule": "characterize internal node voltages with EN held low under the nominal disabled fixture",
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
    "output_source_sweep": {
        "specification_aspect": "closed-loop source-drive sweep characterization",
        "category": "char",
        "test_name": "run_output_source_sweep_test",
        "analysis_type": "Op sweep",
        "extracted_metrics": ["cases", "worst_vout_source", "worst_current_uA"],
        "pass_fail_rule": "characterize follower-mode source-drive degradation across a forced-current sweep",
        "required_corners": ["TT"],
        "required_operating_conditions": ["unity_feedback", "source current sweep"],
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
    purpose: str = "Compose the bias generator, input stage, gm stage, and compensation network."
    component_class: str = "reusable block"
    pins: tuple[str, ...] = ("VINP", "VINN", "VOUT", "EN", "VDD", "VSS")
    measurable_behaviors: tuple[str, ...] = (
        "open_loop",
        "direct_dc_gain",
        "internal_nodes",
        "area_estimate",
    )
    numeric_pass_fail_criteria: tuple[str, ...] = ("generic AC and transient contracts only; product budgets belong in external budget tests",)
    required_corners: tuple[str, ...] = ("TT",)
    statistical_verification_required: bool = False


@h.paramclass
class GainStageParams:
    in_type = h.Param(dtype=str, desc="Input pair polarity", default="p")
    load_style = h.Param(dtype=str, desc="Active-load topology", default="mirror")
    tail_style = h.Param(dtype=str, desc="Tail-source style metadata", default="ideal")
    w_in = h.Param(dtype=h.Scalar, desc="Input width in um", default=10.0)
    l_in = h.Param(dtype=h.Scalar, desc="Input length in um", default=8.0)
    nf_in = h.Param(dtype=int, desc="Input fingers", default=1)
    m_in = h.Param(dtype=int, desc="Input multiplier", default=1)
    w_load = h.Param(dtype=h.Scalar, desc="Load width in um", default=4.0)
    l_load = h.Param(dtype=h.Scalar, desc="Load length in um", default=16.0)
    nf_load = h.Param(dtype=int, desc="Load fingers", default=1)
    m_load = h.Param(dtype=int, desc="Load multiplier", default=1)
    i_tail = h.Param(dtype=h.Scalar, desc="Tail current in A", default=2.2e-6)
    use_degeneration = h.Param(dtype=bool, desc="Insert input degeneration", default=False)
    r_deg = h.Param(dtype=h.Scalar, desc="Degeneration resistor in ohm", default=100.0)


@h.paramclass
class SecondStageParams:
    style = h.Param(dtype=str, desc="Second-stage topology", default="common_source")
    device_type = h.Param(dtype=str, desc="Amplifying device polarity", default="n")
    w_amp = h.Param(dtype=h.Scalar, desc="Amplifier width in um", default=10.0)
    l_amp = h.Param(dtype=h.Scalar, desc="Amplifier length in um", default=6.0)
    nf_amp = h.Param(dtype=int, desc="Amplifier fingers", default=1)
    m_amp = h.Param(dtype=int, desc="Amplifier multiplier", default=1)
    w_load_scale = h.Param(dtype=h.Scalar, desc="Load width scale relative to amplifier", default=5.5)
    l_load = h.Param(dtype=h.Scalar, desc="Load length in um", default=10.0)
    i_bias = h.Param(dtype=h.Scalar, desc="Bias current metadata in A", default=2.6e-6)
    r_out_target = h.Param(dtype=h.Scalar, desc="Nominal output load in ohm", default=200e3)
    r_gate_bias = h.Param(dtype=h.Scalar, desc="PMOS gate-bias mixing resistance in ohm", default=200e3)
    use_pullup_assist = h.Param(dtype=bool, desc="Add a weak droop-sensing PMOS pull-up assist to the common-source stage", default=True)
    assist_w_scale = h.Param(dtype=h.Scalar, desc="PMOS pull-up assist width scale relative to amplifier", default=0.05)
    assist_l = h.Param(dtype=h.Scalar, desc="PMOS pull-up assist length in um", default=1.0)
    assist_r_series = h.Param(dtype=h.Scalar, desc="Series isolation resistance in ohm between the pull-up assist and VOUT", default=5e3)


@h.paramclass
class OutputHelperParams:
    style = h.Param(dtype=str, desc="Output-helper topology", default="source_follower")
    w_n = h.Param(dtype=h.Scalar, desc="NMOS helper width in um", default=4.0)
    l_n = h.Param(dtype=h.Scalar, desc="NMOS helper length in um", default=0.5)
    w_p = h.Param(dtype=h.Scalar, desc="PMOS helper width in um", default=8.0)
    l_p = h.Param(dtype=h.Scalar, desc="PMOS helper length in um", default=0.5)
    nf = h.Param(dtype=int, desc="Helper fingers", default=1)
    m = h.Param(dtype=int, desc="Helper multiplier", default=1)


def _mos_primitive(name: str):
    try:
        return getattr(sky130_hdl21.primitives, name)
    except AttributeError as err:
        raise ValueError(f"Unsupported SKY130 primitive: {name}") from err


def _mos_params(w: h.Scalar, l: h.Scalar, nf: int, mult: int):
    return sky130_hdl21.Sky130MosParams(w=w, l=l, nf=nf, mult=mult)


@h.generator
def gain_stage(params: GainStageParams) -> h.Module:
    if params.in_type not in ("p", "n"):
        raise ValueError(f"Unsupported in_type: {params.in_type}")
    if params.load_style not in ("mirror", "diode", "cascoded", "wilson"):
        raise ValueError(f"Unsupported load_style: {params.load_style}")
    if params.tail_style != "ideal":
        raise ValueError(f"Unsupported tail_style: {params.tail_style}")
    if params.i_tail <= 0:
        raise ValueError("i_tail must be positive")

    mod = h.Module(name="GainStage")
    mod.VINP, mod.VINN, mod.VX, mod.VREF, mod.IBIAS, mod.VDD, mod.VSS = h.Ports(7)
    if params.in_type == "p":
        diffpair_params = DiffpairPParams(
            w_in=params.w_in,
            l_in=params.l_in,
            nf_in=params.nf_in,
            m_in=params.m_in,
            use_degeneration=params.use_degeneration,
            r_deg=params.r_deg,
        )
        diffpair = diffpair_p(diffpair_params)
        nmos = sky130_hdl21.primitives.NMOS_1p8V_STD
        npar = sky130_hdl21.Sky130MosParams(w=params.w_load, l=params.l_load, nf=params.nf_load, mult=params.m_load)

        mod.xin = diffpair(INP=mod.VINP, INN=mod.VINN, OUTP=mod.VX, OUTN=mod.VREF, TAIL=mod.IBIAS, VDD=mod.VDD, VSS=mod.VSS)
        if params.load_style == "diode":
            mod.m_load_ref = nmos(npar)(d=mod.VREF, g=mod.VREF, s=mod.VSS, b=mod.VSS)
            mod.m_load_out = nmos(npar)(d=mod.VX, g=mod.VX, s=mod.VSS, b=mod.VSS)
        elif params.load_style == "mirror":
            mod.m_load_ref = nmos(npar)(d=mod.VREF, g=mod.VREF, s=mod.VSS, b=mod.VSS)
            mod.m_load_out = nmos(npar)(d=mod.VX, g=mod.VREF, s=mod.VSS, b=mod.VSS)
        elif params.load_style == "wilson":
            mod.m_load_ref = nmos(npar)(d=mod.VREF, g=mod.VREF, s=mod.VSS, b=mod.VSS)
            mod.m_load_out = nmos(npar)(d=mod.VX, g=mod.VREF, s=mod.VSS, b=mod.VSS)
            mod.m_load_fb = nmos(npar)(d=mod.VREF, g=mod.VX, s=mod.VSS, b=mod.VSS)
        else:
            mod.ref_mid = h.Signal(name="ref_mid")
            mod.out_mid = h.Signal(name="out_mid")
            mod.m_ref_cas = nmos(npar)(d=mod.VREF, g=mod.VREF, s=mod.ref_mid, b=mod.VSS)
            mod.m_ref_bot = nmos(npar)(d=mod.ref_mid, g=mod.ref_mid, s=mod.VSS, b=mod.VSS)
            mod.m_out_cas = nmos(npar)(d=mod.VX, g=mod.VREF, s=mod.out_mid, b=mod.VSS)
            mod.m_out_bot = nmos(npar)(d=mod.out_mid, g=mod.ref_mid, s=mod.VSS, b=mod.VSS)
    else:
        if params.load_style == "cascoded":
            raise ValueError("cascoded load is not supported for n-input gain_stage")
        diffpair_params = DiffpairNParams(
            w_in=params.w_in,
            l_in=params.l_in,
            nf_in=params.nf_in,
            m_in=params.m_in,
            use_degeneration=params.use_degeneration,
            r_deg=params.r_deg,
        )
        diffpair = diffpair_n(diffpair_params)
        pmos = sky130_hdl21.primitives.PMOS_1p8V_STD
        nmos = sky130_hdl21.primitives.NMOS_1p8V_STD
        ppar = sky130_hdl21.Sky130MosParams(w=params.w_load, l=params.l_load, nf=params.nf_load, mult=params.m_load)
        tail_par = sky130_hdl21.Sky130MosParams(
            w=max(params.w_load, 2.0),
            l=max(params.l_load, 1.0),
            nf=params.nf_load,
            mult=params.m_load,
        )

        mod.tail = h.Signal(name="tail")
        # Local current-to-voltage conversion for the NMOS tail sink lets the
        # stage reuse the global PMOS current-bias generator without adding a
        # new top-level bias contract.
        mod.m_tail_ref = nmos(tail_par)(d=mod.IBIAS, g=mod.IBIAS, s=mod.VSS, b=mod.VSS)
        mod.m_tail = nmos(tail_par)(d=mod.tail, g=mod.IBIAS, s=mod.VSS, b=mod.VSS)
        # Cross-couple the differential inputs so the total core polarity
        # remains positive through the inverting NMOS second stage.
        mod.xin = diffpair(INP=mod.VINN, INN=mod.VINP, OUTP=mod.VREF, OUTN=mod.VX, TAIL=mod.tail, VDD=mod.VDD, VSS=mod.VSS)
        if params.load_style == "diode":
            mod.m_load_ref = pmos(ppar)(d=mod.VREF, g=mod.VREF, s=mod.VDD, b=mod.VDD)
            mod.m_load_out = pmos(ppar)(d=mod.VX, g=mod.VX, s=mod.VDD, b=mod.VDD)
        else:
            mod.m_load_ref = pmos(ppar)(d=mod.VREF, g=mod.VREF, s=mod.VDD, b=mod.VDD)
            mod.m_load_out = pmos(ppar)(d=mod.VX, g=mod.VREF, s=mod.VDD, b=mod.VDD)
    return mod


@h.generator
def second_stage(params: SecondStageParams) -> h.Module:
    if params.style not in ("common_source", "push_pull", "cmos_inverter", "pmos_common_source", "diffpair_n"):
        raise ValueError(f"Unsupported style: {params.style}")
    if params.device_type not in ("n", "p"):
        raise ValueError(f"Unsupported device_type: {params.device_type}")
    if params.w_amp <= 0 or params.l_amp <= 0 or params.w_load_scale <= 0 or params.l_load <= 0:
        raise ValueError("w_amp, l_amp, w_load_scale, and l_load must be positive")
    if params.assist_w_scale <= 0 or params.assist_l <= 0 or params.assist_r_series <= 0:
        raise ValueError("assist_w_scale, assist_l, and assist_r_series must be positive")
    if params.nf_amp < 1 or params.m_amp < 1:
        raise ValueError("nf_amp and m_amp must be >= 1")
    if params.i_bias <= 0 or params.r_out_target <= 0 or params.r_gate_bias <= 0:
        raise ValueError("i_bias, r_out_target, and r_gate_bias must be positive")

    mod = h.Module(name="SecondStage")
    mod.VIN, mod.VOUT, mod.VBIAS, mod.EN, mod.VDD, mod.VSS = h.Ports(6)
    mod.enb = h.Signal(name="enb")
    inv_npar = _mos_params(1.0, 0.15, 1, 1)
    inv_ppar = _mos_params(2.0, 0.15, 1, 1)
    mod.m_enb_p = sky130_hdl21.primitives.PMOS_1p8V_STD(inv_ppar)(d=mod.enb, g=mod.EN, s=mod.VDD, b=mod.VDD)
    mod.m_enb_n = sky130_hdl21.primitives.NMOS_1p8V_STD(inv_npar)(d=mod.enb, g=mod.EN, s=mod.VSS, b=mod.VSS)

    if params.style == "diffpair_n":
        raise ValueError("diffpair_n second stage uses differential_second_stage() and is not available through second_stage()")
    if params.style == "push_pull":
        npar = _mos_params(params.w_amp, params.l_amp, params.nf_amp, params.m_amp)
        ppar = _mos_params(params.w_amp * params.w_load_scale, params.l_load, params.nf_amp, params.m_amp)
        nmos = sky130_hdl21.primitives.NMOS_1p8V_STD
        pmos = sky130_hdl21.primitives.PMOS_1p8V_STD
        mod.gp = h.Signal(name="gp")
        mod.gn = h.Signal(name="gn")
        mod.rgp_sig = pdk_resistor(params.r_gate_bias, p=mod.VIN, n=mod.gp, bulk=mod.VSS)
        mod.rgp_bias = pdk_resistor(params.r_gate_bias, p=mod.VBIAS, n=mod.gp, bulk=mod.VSS)
        mod.rgn_sig = h.Res(r=1e-3)(p=mod.gn, n=mod.VIN)
        mod.m_gp_off = pmos(inv_ppar)(d=mod.gp, g=mod.EN, s=mod.VDD, b=mod.VDD)
        mod.m_gn_off = nmos(inv_npar)(d=mod.gn, g=mod.enb, s=mod.VSS, b=mod.VSS)
        mod.m_p = pmos(ppar)(d=mod.VOUT, g=mod.gp, s=mod.VDD, b=mod.VDD)
        mod.m_n = nmos(npar)(d=mod.VOUT, g=mod.gn, s=mod.VSS, b=mod.VSS)
    elif params.style == "cmos_inverter":
        npar = _mos_params(params.w_amp, params.l_amp, params.nf_amp, params.m_amp)
        ppar = _mos_params(params.w_amp * params.w_load_scale, params.l_load, params.nf_amp, params.m_amp)
        nmos = sky130_hdl21.primitives.NMOS_1p8V_STD
        pmos = sky130_hdl21.primitives.PMOS_1p8V_STD
        mod.ginv = h.Signal(name="ginv")
        mod.rginv = h.Res(r=1e-3)(p=mod.ginv, n=mod.VIN)
        mod.m_ginv_p = pmos(inv_ppar)(d=mod.ginv, g=mod.EN, s=mod.VDD, b=mod.VDD)
        mod.m_ginv_n = nmos(inv_npar)(d=mod.ginv, g=mod.enb, s=mod.VSS, b=mod.VSS)
        mod.m_p = pmos(ppar)(d=mod.VOUT, g=mod.ginv, s=mod.VDD, b=mod.VDD)
        mod.m_n = nmos(npar)(d=mod.VOUT, g=mod.ginv, s=mod.VSS, b=mod.VSS)
    elif params.style == "pmos_common_source":
        amp_par = _mos_params(params.w_amp, params.l_amp, params.nf_amp, params.m_amp)
        load_par = _mos_params(params.w_amp * params.w_load_scale, params.l_load, params.nf_amp, params.m_amp)
        mod.gamp = h.Signal(name="gamp")
        mod.rgamp = h.Res(r=1e-3)(p=mod.gamp, n=mod.VIN)
        mod.m_amp_off = sky130_hdl21.primitives.PMOS_1p8V_STD(inv_ppar)(d=mod.gamp, g=mod.EN, s=mod.VDD, b=mod.VDD)
        # Cleaner current-bias contract:
        # - VBIAS is a current-bias node sourced by bias_gen
        # - a local diode-connected NMOS reference converts it into the gate
        #   voltage for the actual NMOS current-sink load
        mod.m_load_ref = sky130_hdl21.primitives.NMOS_1p8V_STD(load_par)(d=mod.VBIAS, g=mod.VBIAS, s=mod.VSS, b=mod.VSS)
        mod.m_load = sky130_hdl21.primitives.NMOS_1p8V_STD(load_par)(d=mod.VOUT, g=mod.VBIAS, s=mod.VSS, b=mod.VSS)
        mod.m_amp = sky130_hdl21.primitives.PMOS_1p8V_STD(amp_par)(d=mod.VOUT, g=mod.gamp, s=mod.VDD, b=mod.VDD)
    else:
        amp_name = "NMOS_1p8V_STD" if params.device_type == "n" else "PMOS_1p8V_STD"
        load_name = "PMOS_1p8V_STD" if params.device_type == "n" else "NMOS_1p8V_STD"
        amp_prim = _mos_primitive(amp_name)
        load_prim = _mos_primitive(load_name)
        amp_par = _mos_params(params.w_amp, params.l_amp, params.nf_amp, params.m_amp)
        load_par = _mos_params(params.w_amp * params.w_load_scale, params.l_load, params.nf_amp, params.m_amp)
        if params.device_type == "n":
            mod.gload = h.Signal(name="gload")
            mod.gamp = h.Signal(name="gamp")
            mod.rgload = h.Res(r=1e-3)(p=mod.gload, n=mod.VBIAS)
            mod.rgamp = h.Res(r=1e-3)(p=mod.gamp, n=mod.VIN)
            mod.m_load_off = sky130_hdl21.primitives.PMOS_1p8V_STD(inv_ppar)(d=mod.gload, g=mod.EN, s=mod.VDD, b=mod.VDD)
            mod.m_amp_off = sky130_hdl21.primitives.NMOS_1p8V_STD(inv_npar)(d=mod.gamp, g=mod.enb, s=mod.VSS, b=mod.VSS)
            mod.m_load = load_prim(load_par)(d=mod.VOUT, g=mod.gload, s=mod.VDD, b=mod.VDD)
            mod.m_amp = amp_prim(amp_par)(d=mod.VOUT, g=mod.gamp, s=mod.VSS, b=mod.VSS)
            if params.use_pullup_assist:
                assist_par = _mos_params(
                    params.w_amp * params.assist_w_scale,
                    params.assist_l,
                    params.nf_amp,
                    params.m_amp,
                )
                mod.gassist = h.Signal(name="gassist")
                mod.vassist = h.Signal(name="vassist")
                # Self-limiting source assist:
                # - gate tracks the output node, so the PMOS only turns on when
                #   VOUT droops and naturally turns back off near the top rail
                # - a small series resistor decouples the helper from the DC
                #   low-swing operating point while still allowing source assist
                # - a hard disable clamp still forces the gate to VDD when EN=0
                mod.rassist = h.Res(r=1e-3)(p=mod.gassist, n=mod.VOUT)
                mod.rassist_series = pdk_resistor(params.assist_r_series, p=mod.vassist, n=mod.VOUT)
                mod.m_assist_off = sky130_hdl21.primitives.PMOS_1p8V_STD(inv_ppar)(
                    d=mod.gassist,
                    g=mod.EN,
                    s=mod.VDD,
                    b=mod.VDD,
                )
                mod.m_assist = sky130_hdl21.primitives.PMOS_1p8V_STD(assist_par)(
                    d=mod.vassist,
                    g=mod.gassist,
                    s=mod.VDD,
                    b=mod.VDD,
                )
        else:
            mod.gload = h.Signal(name="gload")
            mod.gamp = h.Signal(name="gamp")
            mod.rgload = h.Res(r=1e-3)(p=mod.gload, n=mod.VBIAS)
            mod.rgamp = h.Res(r=1e-3)(p=mod.gamp, n=mod.VIN)
            mod.m_load_off = sky130_hdl21.primitives.NMOS_1p8V_STD(inv_npar)(d=mod.gload, g=mod.enb, s=mod.VSS, b=mod.VSS)
            mod.m_amp_off = sky130_hdl21.primitives.PMOS_1p8V_STD(inv_ppar)(d=mod.gamp, g=mod.EN, s=mod.VDD, b=mod.VDD)
            mod.m_load = load_prim(load_par)(d=mod.VOUT, g=mod.gload, s=mod.VSS, b=mod.VSS)
            mod.m_amp = amp_prim(amp_par)(d=mod.VOUT, g=mod.gamp, s=mod.VDD, b=mod.VDD)

    return mod


@h.generator
def differential_second_stage(params: SecondStageParams) -> h.Module:
    if params.style != "diffpair_n":
        raise ValueError(f"differential_second_stage requires style='diffpair_n', got {params.style!r}")
    if params.w_amp <= 0 or params.l_amp <= 0 or params.w_load_scale <= 0 or params.l_load <= 0:
        raise ValueError("w_amp, l_amp, w_load_scale, and l_load must be positive")
    if params.nf_amp < 1 or params.m_amp < 1:
        raise ValueError("nf_amp and m_amp must be >= 1")

    mod = h.Module(name="DifferentialSecondStage")
    mod.VINP, mod.VINN, mod.VOUT, mod.VBIAS, mod.EN, mod.VDD, mod.VSS = h.Ports(7)
    mod.vref2 = h.Signal(name="vref2")
    mod.tail = h.Signal(name="tail")
    mod.enb = h.Signal(name="enb")

    inv_npar = _mos_params(1.0, 0.15, 1, 1)
    inv_ppar = _mos_params(2.0, 0.15, 1, 1)
    mod.m_enb_p = sky130_hdl21.primitives.PMOS_1p8V_STD(inv_ppar)(d=mod.enb, g=mod.EN, s=mod.VDD, b=mod.VDD)
    mod.m_enb_n = sky130_hdl21.primitives.NMOS_1p8V_STD(inv_npar)(d=mod.enb, g=mod.EN, s=mod.VSS, b=mod.VSS)

    # Convert the current-bias node into an NMOS tail-sink gate locally.
    tail_par = _mos_params(params.w_amp, max(params.l_amp, 1.0), params.nf_amp, params.m_amp)
    mod.m_tail_ref = sky130_hdl21.primitives.NMOS_1p8V_STD(tail_par)(d=mod.VBIAS, g=mod.VBIAS, s=mod.VSS, b=mod.VSS)
    mod.m_tail = sky130_hdl21.primitives.NMOS_1p8V_STD(tail_par)(d=mod.tail, g=mod.VBIAS, s=mod.VSS, b=mod.VSS)
    mod.m_tail_off = sky130_hdl21.primitives.NMOS_1p8V_STD(inv_npar)(d=mod.tail, g=mod.enb, s=mod.VSS, b=mod.VSS)

    diffpair_params = DiffpairNParams(
        w_in=params.w_amp,
        l_in=params.l_amp,
        nf_in=params.nf_amp,
        m_in=params.m_amp,
    )
    mod.xin = diffpair_n(diffpair_params)(INP=mod.VINP, INN=mod.VINN, OUTP=mod.VOUT, OUTN=mod.vref2, TAIL=mod.tail, VDD=mod.VDD, VSS=mod.VSS)

    ppar = _mos_params(params.w_amp * params.w_load_scale, params.l_load, params.nf_amp, params.m_amp)
    mod.m_load_ref = sky130_hdl21.primitives.PMOS_1p8V_STD(ppar)(d=mod.vref2, g=mod.vref2, s=mod.VDD, b=mod.VDD)
    mod.m_load_out = sky130_hdl21.primitives.PMOS_1p8V_STD(ppar)(d=mod.VOUT, g=mod.vref2, s=mod.VDD, b=mod.VDD)
    mod.m_load_off = sky130_hdl21.primitives.PMOS_1p8V_STD(inv_ppar)(d=mod.vref2, g=mod.EN, s=mod.VDD, b=mod.VDD)
    return mod


@h.generator
def output_helper(params: OutputHelperParams) -> h.Module:
    if params.style not in ("source_follower", "pmos_follower", "pmos_assist", "class_ab_follower"):
        raise ValueError(f"Unsupported output-helper style: {params.style}")
    if params.w_n <= 0 or params.l_n <= 0 or params.w_p <= 0 or params.l_p <= 0:
        raise ValueError("output-helper dimensions must be positive")
    if params.nf < 1 or params.m < 1:
        raise ValueError("output-helper nf and m must be >= 1")

    mod = h.Module(name="OutputHelper")
    mod.VIN, mod.VOUT, mod.EN, mod.VDD, mod.VSS = h.Ports(5)
    mod.enb = h.Signal(name="enb")
    mod.gbuf = h.Signal(name="gbuf")

    inv_npar = _mos_params(1.0, 0.15, 1, 1)
    inv_ppar = _mos_params(2.0, 0.15, 1, 1)
    mod.m_enb_p = sky130_hdl21.primitives.PMOS_1p8V_STD(inv_ppar)(d=mod.enb, g=mod.EN, s=mod.VDD, b=mod.VDD)
    mod.m_enb_n = sky130_hdl21.primitives.NMOS_1p8V_STD(inv_npar)(d=mod.enb, g=mod.EN, s=mod.VSS, b=mod.VSS)

    mod.rg = h.Res(r=1e-3)(p=mod.gbuf, n=mod.VIN)
    mod.m_gbuf_p = sky130_hdl21.primitives.PMOS_1p8V_STD(inv_ppar)(d=mod.gbuf, g=mod.EN, s=mod.VDD, b=mod.VDD)
    mod.m_gbuf_n = sky130_hdl21.primitives.NMOS_1p8V_STD(inv_npar)(d=mod.gbuf, g=mod.enb, s=mod.VSS, b=mod.VSS)

    npar = _mos_params(params.w_n, params.l_n, params.nf, params.m)
    ppar = _mos_params(params.w_p, params.l_p, params.nf, params.m)
    if params.style == "class_ab_follower":
        # Purpose-built non-inverting final buffer:
        # - complementary source followers provide output drive
        # - local diode-connected bias-spread devices generate separate gate
        #   drives around VIN instead of forcing both followers to share one
        #   raw gate voltage
        # - hard disable clamps shut both followers off explicitly
        shift_npar = _mos_params(max(params.w_n * 0.5, 1.0), params.l_n, params.nf, params.m)
        shift_ppar = _mos_params(max(params.w_p * 0.5, 1.0), params.l_p, params.nf, params.m)
        mod.gn = h.Signal(name="gn")
        mod.gp = h.Signal(name="gp")
        mod.m_gn_pull = sky130_hdl21.primitives.PMOS_1p8V_STD(shift_ppar)(d=mod.gn, g=mod.gn, s=mod.VDD, b=mod.VDD)
        mod.m_gn_shift = sky130_hdl21.primitives.NMOS_1p8V_STD(shift_npar)(d=mod.gn, g=mod.gn, s=mod.gbuf, b=mod.VSS)
        mod.m_gp_shift = sky130_hdl21.primitives.PMOS_1p8V_STD(shift_ppar)(d=mod.gp, g=mod.gp, s=mod.gbuf, b=mod.VDD)
        mod.m_gp_pull = sky130_hdl21.primitives.NMOS_1p8V_STD(shift_npar)(d=mod.gp, g=mod.gp, s=mod.VSS, b=mod.VSS)
        mod.m_gn_off = sky130_hdl21.primitives.NMOS_1p8V_STD(inv_npar)(d=mod.gn, g=mod.enb, s=mod.VSS, b=mod.VSS)
        mod.m_gp_off = sky130_hdl21.primitives.PMOS_1p8V_STD(inv_ppar)(d=mod.gp, g=mod.EN, s=mod.VDD, b=mod.VDD)
        mod.m_n = sky130_hdl21.primitives.NMOS_1p8V_STD(npar)(d=mod.VDD, g=mod.gn, s=mod.VOUT, b=mod.VSS)
        mod.m_p = sky130_hdl21.primitives.PMOS_1p8V_STD(ppar)(d=mod.VSS, g=mod.gp, s=mod.VOUT, b=mod.VDD)
    elif params.style == "source_follower":
        mod.m_n = sky130_hdl21.primitives.NMOS_1p8V_STD(npar)(d=mod.VDD, g=mod.gbuf, s=mod.VOUT, b=mod.VSS)
        mod.m_p = sky130_hdl21.primitives.PMOS_1p8V_STD(ppar)(d=mod.VSS, g=mod.gbuf, s=mod.VOUT, b=mod.VDD)
    elif params.style == "pmos_follower":
        # Light non-inverting pull-up helper:
        # PMOS source follower only, with gate hard-clamped high in disable.
        mod.m_p = sky130_hdl21.primitives.PMOS_1p8V_STD(ppar)(d=mod.VDD, g=mod.gbuf, s=mod.VOUT, b=mod.VDD)
    else:
        # Light source-assist stage behind the gain path:
        # PMOS from VDD to VOUT, signal-driven from VIN and hard-clamped off in disable.
        mod.m_p = sky130_hdl21.primitives.PMOS_1p8V_STD(ppar)(d=mod.VOUT, g=mod.gbuf, s=mod.VDD, b=mod.VDD)
    return mod


@h.paramclass
class OpampCoreParams:
    gain_stage_params = h.Param(
        dtype=GainStageParams,
        desc="First-stage parameters",
        default=GainStageParams(),
    )
    second_stage_params = h.Param(
        dtype=SecondStageParams,
        desc="Second-stage parameters",
        default=SecondStageParams(device_type="n"),
    )
    freq_comp_params = h.Param(
        dtype=FreqCompParams,
        desc="Compensation parameters",
        default=FreqCompParams(c_comp=200e-15),
    )
    output_stage_params = h.Param(
        dtype=OutputStageParams,
        desc="Output-stage parameters",
        default=OutputStageParams(
            style="push_pull",
            device_type="p",
            w_amp=4.0,
            l_amp=1.0,
            w_load_scale=2.0,
            l_load=1.0,
            i_bias=2e-6,
            r_out_target=100e3,
            r_gate_bias=200e3,
        ),
    )
    use_output_stage = h.Param(
        dtype=bool,
        desc="Insert a dedicated output stage after the second stage",
        default=False,
    )
    output_helper_params = h.Param(
        dtype=OutputHelperParams,
        desc="Dedicated non-invasive output-helper parameters",
        default=OutputHelperParams(),
    )
    use_output_helper = h.Param(
        dtype=bool,
        desc="Insert a dedicated output helper behind the gain-oriented second stage",
        default=False,
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
    f_start = h.Param(dtype=h.Scalar, desc="AC sweep start frequency in Hz for follower stability characterization", default=1.0)
    f_stop = h.Param(dtype=h.Scalar, desc="AC sweep stop frequency in Hz for follower stability characterization", default=1e9)
    npts = h.Param(dtype=int, desc="AC sweep points per decade for follower stability characterization", default=40)
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
    second_stage_inst = None if params.second_stage_params.style == "diffpair_n" else second_stage(params.second_stage_params)
    diff_second_stage_inst = differential_second_stage(params.second_stage_params) if params.second_stage_params.style == "diffpair_n" else None
    freq_comp_inst = freq_comp(params.freq_comp_params)
    output_stage_inst = output_stage(params.output_stage_params) if params.use_output_stage else None
    output_helper_inst = output_helper(params.output_helper_params) if params.use_output_helper else None
    bias_inst = bias_gen(params.bias_gen_params)

    mod = h.Module(name="OpampCore")
    mod.VINP, mod.VINN, mod.VOUT, mod.EN, mod.VDD, mod.VSS = h.Ports(6)
    mod.vx, mod.vref, mod.vdrv = h.Signals(3)
    mod.ibias1, mod.ibias2, mod.vbp = h.Signals(3)

    mod.xbias = bias_inst(VDD=mod.VDD, VSS=mod.VSS, EN=mod.EN, IBIAS1=mod.ibias1, IBIAS2=mod.ibias2, VBP=mod.vbp)
    off_clamp = sky130_hdl21.primitives.PMOS_1p8V_STD(_mos_params(4.0, 0.5, 1, 1))
    # Clamp bias nodes high in disable mode so PMOS-biased stages turn off hard.
    mod.m_ibias1_off = off_clamp(d=mod.ibias1, g=mod.EN, s=mod.VDD, b=mod.VDD)
    mod.m_ibias2_off = off_clamp(d=mod.ibias2, g=mod.EN, s=mod.VDD, b=mod.VDD)
    mod.xgain = gain_stage_inst(VINP=mod.VINP, VINN=mod.VINN, VX=mod.vx, VREF=mod.vref, IBIAS=mod.ibias1, VDD=mod.VDD, VSS=mod.VSS)
    second_stage_bias = mod.ibias2 if params.second_stage_params.style in ("pmos_common_source", "diffpair_n") else mod.vbp
    if params.use_output_stage:
        if diff_second_stage_inst is not None:
            mod.xgm = diff_second_stage_inst(VINP=mod.vx, VINN=mod.vref, VOUT=mod.vdrv, VBIAS=second_stage_bias, EN=mod.EN, VDD=mod.VDD, VSS=mod.VSS)
        else:
            mod.xgm = second_stage_inst(VIN=mod.vx, VOUT=mod.vdrv, VBIAS=second_stage_bias, EN=mod.EN, VDD=mod.VDD, VSS=mod.VSS)
        mod.xout = output_stage_inst(VIN=mod.vdrv, VOUT=mod.VOUT, IBIAS=mod.vbp, VDD=mod.VDD, VSS=mod.VSS)
        mod.xcomp = freq_comp_inst(V1=mod.vx, VOUT=mod.vdrv)
    elif params.use_output_helper:
        if diff_second_stage_inst is not None:
            mod.xgm = diff_second_stage_inst(VINP=mod.vx, VINN=mod.vref, VOUT=mod.vdrv, VBIAS=second_stage_bias, EN=mod.EN, VDD=mod.VDD, VSS=mod.VSS)
        else:
            mod.xgm = second_stage_inst(VIN=mod.vx, VOUT=mod.vdrv, VBIAS=second_stage_bias, EN=mod.EN, VDD=mod.VDD, VSS=mod.VSS)
        mod.xhelper = output_helper_inst(VIN=mod.vdrv, VOUT=mod.VOUT, EN=mod.EN, VDD=mod.VDD, VSS=mod.VSS)
        mod.xcomp = freq_comp_inst(V1=mod.vx, VOUT=mod.vdrv)
    else:
        if diff_second_stage_inst is not None:
            mod.xgm = diff_second_stage_inst(VINP=mod.vx, VINN=mod.vref, VOUT=mod.VOUT, VBIAS=second_stage_bias, EN=mod.EN, VDD=mod.VDD, VSS=mod.VSS)
        else:
            mod.xgm = second_stage_inst(VIN=mod.vx, VOUT=mod.VOUT, VBIAS=second_stage_bias, EN=mod.EN, VDD=mod.VDD, VSS=mod.VSS)
        mod.xcomp = freq_comp_inst(V1=mod.vx, VOUT=mod.VOUT)
    # Keep only the high-gain nodes weakly anchored for numerical robustness.
    return mod

from .measure_core import (
    build_closed_loop_step_test,
    build_open_loop_test,
    elaborate_dut,
    export_spice,
    print_test_report,
    run_all_tests,
    run_area_estimate,
    run_bias_characterization_test,
    run_closed_loop_step_test,
    run_direct_dc_gain_sweep_test,
    run_direct_dc_gain_test,
    run_disabled_leakage_test,
    run_disable_nodes_test,
    run_fast_checks,
    run_internal_direct_gain_test,
    run_internal_nodes_test,
    run_load_sweep_test,
    run_open_loop_test,
    run_open_loop_fast_test,
    run_output_current_limit_test,
    run_output_drive_test,
    run_output_source_sweep_test,
    run_output_swing_test,
    run_pvt_test,
    run_structural_checks,
)
