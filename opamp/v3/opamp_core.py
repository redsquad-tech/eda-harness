from dataclasses import dataclass

import hdl21 as h
import sky130_hdl21

from components.diffpair_p import DiffpairPParams, diffpair_p
from .pdk_passives import pdk_mim_capacitor, pdk_precision_resistor


VERIFICATION_PLAN = {
    "structural": {
        "specification_aspect": "generator/export contract",
        "category": "structural",
        "test_name": "run_structural_checks",
        "analysis_type": "generator/elaboration/export",
        "extracted_metrics": [
            "generator_call",
            "elaboration",
            "subckt_name",
            "contains_first_stage",
            "contains_second_stage",
            "contains_output_path",
            "contains_compensation",
            "contains_disable_hooks",
            "uses_pdk_bias_resistors",
            "uses_pdk_output_devices",
            "uses_pdk_comp_cap",
        ],
        "pass_fail_rule": "all structural checks pass",
        "required_corners": [],
        "required_operating_conditions": [],
        "monte_carlo_required": False,
    },
}


@dataclass(frozen=True)
class OpampCoreSpec:
    name: str = "opamp_core_v3"
    purpose: str = "Compose the current v3 static amplifier loop with a direct VDRV output and an explicitly cascoded second stage."
    component_class: str = "release candidate"
    pins: tuple[str, ...] = ("VINP", "VINN", "VOUT", "EN", "VDD", "VSS")
    measurable_behaviors: tuple[str, ...] = ("structural",)
    numeric_pass_fail_criteria: tuple[str, ...] = ("real transistor-level scaffold only; no numeric closure targets yet",)
    required_corners: tuple[str, ...] = ()
    statistical_verification_required: bool = False


def _mos_params(w: h.Scalar, l: h.Scalar, nf: int = 1, mult: int = 1):
    return sky130_hdl21.Sky130MosParams(w=w, l=l, nf=nf, mult=mult)


@h.paramclass
class SharedOutputDriverParams:
    r_q_spread = h.Param(dtype=h.Scalar, desc="Class-AB bias-spread resistor between VGP_Q and VGN_Q in ohm", default=120e3)
    w_q_n = h.Param(dtype=h.Scalar, desc="NMOS diode width for VGN_Q bias in um", default=0.5)
    l_q_n = h.Param(dtype=h.Scalar, desc="NMOS diode length for VGN_Q bias in um", default=1.0)
    w_q_p = h.Param(dtype=h.Scalar, desc="PMOS diode width for VGP_Q bias in um", default=2.4)
    l_q_p = h.Param(dtype=h.Scalar, desc="PMOS diode length for VGP_Q bias in um", default=1.0)
    r_vgn_from_q = h.Param(dtype=h.Scalar, desc="Strong VGN quiescent-bias to gate resistor in ohm", default=4e6)
    r_vgp_from_q = h.Param(dtype=h.Scalar, desc="Strong VGP quiescent-bias to gate resistor in ohm", default=40e3)
    r_vgn_from_vdrv = h.Param(dtype=h.Scalar, desc="Weak VDRV-to-VGN modulation resistor in ohm", default=6e9)
    r_vgp_from_vdrv = h.Param(dtype=h.Scalar, desc="Weak same-polarity VDRV-to-VGP modulation resistor in ohm", default=1e9)
    r_vgn_safety_pulldown = h.Param(dtype=h.Scalar, desc="Very-weak VGN safety pull-down in ohm", default=1e9)
    r_vgp_safety_pullup = h.Param(dtype=h.Scalar, desc="Very-weak VGP safety pull-up in ohm", default=1e9)


def default_output_driver_params(**overrides) -> SharedOutputDriverParams:
    params = dict(
        r_q_spread=120e3,
        w_q_n=0.5,
        l_q_n=1.0,
        w_q_p=2.4,
        l_q_p=1.0,
        r_vgn_from_q=4e6,
        r_vgp_from_q=40e3,
        r_vgn_from_vdrv=6e9,
        r_vgp_from_vdrv=1e9,
        r_vgn_safety_pulldown=1e9,
        r_vgp_safety_pullup=1e9,
    )
    params.update(overrides)
    return SharedOutputDriverParams(**params)


@h.generator
def shared_output_driver(params: SharedOutputDriverParams) -> h.Module:
    pmos = sky130_hdl21.primitives.PMOS_1p8V_STD
    nmos = sky130_hdl21.primitives.NMOS_1p8V_STD

    mod = h.Module(name="SharedOutputDriver")
    mod.VDRV, mod.VGN, mod.VGP, mod.VDD, mod.VSS = h.Ports(5)
    mod.vgn_q, mod.vgp_q = h.Signals(2)
    mod.vdd_bias_p, mod.vss_bias_n = h.Signals(2)
    # Standalone-derived output law:
    # a linked PMOS/NMOS replica bias string sets the quiescent window,
    # a strong keep path pins both gates to that window,
    # and both signal branches use the same polarity from VDRV.
    mod.vprobe_bias_p = h.Vdc(dc=0)(p=mod.VDD, n=mod.vdd_bias_p)
    mod.m_vgp_q_diode = pmos(_mos_params(params.w_q_p, params.l_q_p))(d=mod.vgp_q, g=mod.vgp_q, s=mod.vdd_bias_p, b=mod.VDD)
    mod.r_q_spread = pdk_precision_resistor(params.r_q_spread, p=mod.vgp_q, n=mod.vgn_q, bulk=mod.VSS)
    mod.vprobe_bias_n = h.Vdc(dc=0)(p=mod.vss_bias_n, n=mod.VSS)
    mod.m_vgn_q_diode = nmos(_mos_params(params.w_q_n, params.l_q_n))(d=mod.vgn_q, g=mod.vgn_q, s=mod.vss_bias_n, b=mod.VSS)
    mod.r_vgn_from_q = pdk_precision_resistor(params.r_vgn_from_q, p=mod.vgn_q, n=mod.VGN, bulk=mod.VSS)
    mod.r_vgp_from_q = pdk_precision_resistor(params.r_vgp_from_q, p=mod.vgp_q, n=mod.VGP, bulk=mod.VSS)
    mod.r_vgn_from_vdrv = pdk_precision_resistor(params.r_vgn_from_vdrv, p=mod.VDRV, n=mod.VGN, bulk=mod.VSS)
    mod.r_vgp_from_vdrv = pdk_precision_resistor(params.r_vgp_from_vdrv, p=mod.VDRV, n=mod.VGP, bulk=mod.VSS)
    mod.r_vgn_safety_pulldown = pdk_precision_resistor(params.r_vgn_safety_pulldown, p=mod.VGN, n=mod.VSS, bulk=mod.VSS)
    mod.r_vgp_safety_pullup = pdk_precision_resistor(params.r_vgp_safety_pullup, p=mod.VDD, n=mod.VGP, bulk=mod.VSS)
    return mod


@h.paramclass
class SharedGateOutputStageParams:
    w_n = h.Param(dtype=h.Scalar, desc="Output NMOS width in um", default=1.2)
    l_n = h.Param(dtype=h.Scalar, desc="Output NMOS length in um", default=0.5)
    w_p = h.Param(dtype=h.Scalar, desc="Output PMOS width in um", default=2.4)
    l_p = h.Param(dtype=h.Scalar, desc="Output PMOS length in um", default=0.5)


@h.generator
def shared_gate_output_stage(params: SharedGateOutputStageParams) -> h.Module:
    pmos = sky130_hdl21.primitives.PMOS_1p8V_STD
    nmos = sky130_hdl21.primitives.NMOS_1p8V_STD

    mod = h.Module(name="SharedGateOutputStage")
    mod.VGN, mod.VGP, mod.VOUTP, mod.VOUTN, mod.VDD, mod.VSS = h.Ports(6)
    mod.m_out_n = nmos(_mos_params(params.w_n, params.l_n))(d=mod.VOUTN, g=mod.VGN, s=mod.VSS, b=mod.VSS)
    mod.m_out_p = pmos(_mos_params(params.w_p, params.l_p))(d=mod.VOUTP, g=mod.VGP, s=mod.VDD, b=mod.VDD)
    return mod


@h.paramclass
class OpampCoreParams:
    architecture_name = h.Param(dtype=str, desc="Human-readable architecture label", default="ref_sp_core_noaz")
    w_in = h.Param(dtype=h.Scalar, desc="PMOS input-pair width in um", default=14.0)
    l_in = h.Param(dtype=h.Scalar, desc="PMOS input-pair length in um", default=3.0)
    w_load = h.Param(dtype=h.Scalar, desc="NMOS mirror-load width in um", default=4.0)
    l_load = h.Param(dtype=h.Scalar, desc="NMOS mirror-load length in um", default=8.0)
    w_load_casc = h.Param(dtype=h.Scalar, desc="NMOS cascode-load width in um", default=2.0)
    l_load_casc = h.Param(dtype=h.Scalar, desc="NMOS cascode-load length in um", default=4.0)
    w_tail_ref = h.Param(dtype=h.Scalar, desc="Compatibility field; unused in ref core", default=2.0)
    l_tail_ref = h.Param(dtype=h.Scalar, desc="Compatibility field; unused in ref core", default=2.0)
    w_tail = h.Param(dtype=h.Scalar, desc="PMOS first-stage tail-source width in um", default=5.0)
    l_tail = h.Param(dtype=h.Scalar, desc="PMOS first-stage tail-source length in um", default=6.0)
    l_bias_tail_ref = h.Param(dtype=h.Scalar, desc="Tail PMOS-bias resistor length in um", default=60.0)
    r_stage1_bias = h.Param(dtype=h.Scalar, desc="Compatibility field; unused in exact-geometry ref core", default=4.8e6)
    w_tail_sw = h.Param(dtype=h.Scalar, desc="Compatibility field; unused in ref core", default=12.0)
    l_tail_sw = h.Param(dtype=h.Scalar, desc="Compatibility field; unused in ref core", default=0.15)
    tail_switch_stack = h.Param(dtype=int, desc="Compatibility field; unused in ref core", default=1)
    w_stage2_n = h.Param(dtype=h.Scalar, desc="Second-stage NMOS width in um", default=8.0)
    l_stage2_n = h.Param(dtype=h.Scalar, desc="Second-stage NMOS length in um", default=6.0)
    w_stage2_casc_n = h.Param(dtype=h.Scalar, desc="Compatibility field; unused in ref core", default=12.0)
    l_stage2_casc_n = h.Param(dtype=h.Scalar, desc="Compatibility field; unused in ref core", default=1.0)
    w_stage2_p = h.Param(dtype=h.Scalar, desc="Second-stage PMOS load width in um", default=8.0)
    l_stage2_p = h.Param(dtype=h.Scalar, desc="Second-stage PMOS load length in um", default=12.0)
    w_stage2_bias_ref = h.Param(dtype=h.Scalar, desc="Compatibility field; unused in exact-geometry ref core", default=2.0)
    l_stage2_bias_ref = h.Param(dtype=h.Scalar, desc="Compatibility field; unused in exact-geometry ref core", default=2.0)
    l_bias_stage2_ref = h.Param(dtype=h.Scalar, desc="Stage2 PMOS-bias resistor length in um", default=380.0)
    r_stage2_bias = h.Param(dtype=h.Scalar, desc="Compatibility field; unused in exact-geometry ref core", default=7.7e6)
    w_stage2_casc_bias = h.Param(dtype=h.Scalar, desc="NMOS cascode-bias diode width in um", default=1.0)
    l_stage2_casc_bias = h.Param(dtype=h.Scalar, desc="NMOS cascode-bias diode length in um", default=1.0)
    r_stage2_casc_bias = h.Param(dtype=h.Scalar, desc="Compatibility field; unused in exact-geometry ref core", default=3.5e6)
    w_out_n = h.Param(dtype=h.Scalar, desc="Output NMOS width in um", default=1.2)
    l_out_n = h.Param(dtype=h.Scalar, desc="Output device length in um", default=0.5)
    r_outdrv_vgn_from_vdrv = h.Param(dtype=h.Scalar, desc="Output-driver VDRV to VGN signal resistor in ohm", default=60e6)
    r_outdrv_vgp_from_vdrv = h.Param(dtype=h.Scalar, desc="Output-driver VDRV to VGP signal resistor in ohm", default=1e9)
    c_comp = h.Param(dtype=h.Scalar, desc="Compensation capacitor in F", default=0.4e-12)
    r_comp_z = h.Param(dtype=h.Scalar, desc="Compensation zero resistor in ohm", default=120e3)
    debug_current_probes = h.Param(dtype=bool, desc="Compatibility field; unused in ref core", default=False)


def _prec_res_params(length_um: float):
    return sky130_hdl21.Sky130PrecResParams(l=length_um, mult=1, m=1)


def _xhigh_res(length_um: float, *, p, n, bulk):
    return sky130_hdl21.ress["PM_PREC_0p35"](_prec_res_params(length_um))(p=p, n=n, b=bulk)


def _mim_m3(target_side_um: float, *, p, n):
    return sky130_hdl21.primitives.MIM_M3(sky130_hdl21.Sky130MimParams(w=target_side_um, l=target_side_um, mf=1))(p=p, n=n)


@h.generator
def _p_tail_source(params: OpampCoreParams) -> h.Module:
    pmos = sky130_hdl21.primitives.PMOS_1p8V_STD

    mod = h.Module(name="PTailSource")
    mod.OUT, mod.VBP, mod.VDD, mod.VSS = h.Ports(4)
    mod.xtail = pmos(_mos_params(params.w_tail, params.l_tail))(d=mod.OUT, g=mod.VBP, s=mod.VDD, b=mod.VDD)
    return mod


@h.generator
def _n_mirror_load_cascode(params: OpampCoreParams) -> h.Module:
    nmos = sky130_hdl21.primitives.NMOS_1p8V_STD

    mod = h.Module(name="NMirrorLoadCascode")
    mod.REFH, mod.OUTH, mod.VBN, mod.VDD, mod.VSS = h.Ports(5)
    mod.nrefb, mod.noutb = h.Signals(2)
    mod.xmn_ref = nmos(_mos_params(params.w_load, params.l_load))(d=mod.nrefb, g=mod.nrefb, s=mod.VSS, b=mod.VSS)
    mod.xmn_out = nmos(_mos_params(params.w_load, params.l_load))(d=mod.noutb, g=mod.nrefb, s=mod.VSS, b=mod.VSS)
    mod.xmc_ref = nmos(_mos_params(params.w_load_casc, params.l_load_casc))(d=mod.REFH, g=mod.VBN, s=mod.nrefb, b=mod.VSS)
    mod.xmc_out = nmos(_mos_params(params.w_load_casc, params.l_load_casc))(d=mod.OUTH, g=mod.VBN, s=mod.noutb, b=mod.VSS)
    return mod


@h.generator
def _stage1_pinput_casc_load(params: OpampCoreParams) -> h.Module:
    diffpair = diffpair_p(DiffpairPParams(w_in=params.w_in, l_in=params.l_in, nf_in=1, m_in=1))
    load = _n_mirror_load_cascode(params)

    mod = h.Module(name="Stage1PInputCascLoad")
    mod.VINP, mod.VINN, mod.VX, mod.VTAIL, mod.VBN1, mod.VDD, mod.VSS = h.Ports(7)
    mod.vref1 = h.Signal(name="vref1")
    mod.xdp = diffpair(INP=mod.VINP, INN=mod.VINN, OUTP=mod.vref1, OUTN=mod.VX, TAIL=mod.VTAIL, VDD=mod.VDD, VSS=mod.VSS)
    mod.xload = load(REFH=mod.vref1, OUTH=mod.VX, VBN=mod.VBN1, VDD=mod.VDD, VSS=mod.VSS)
    return mod


@h.generator
def _stage2_n_common_source(params: OpampCoreParams) -> h.Module:
    pmos = sky130_hdl21.primitives.PMOS_1p8V_STD
    nmos = sky130_hdl21.primitives.NMOS_1p8V_STD

    mod = h.Module(name="Stage2NCommonSource")
    mod.VX, mod.VOUT, mod.VBP2, mod.VDD, mod.VSS = h.Ports(5)
    mod.xmp2 = pmos(_mos_params(params.w_stage2_p, params.l_stage2_p))(d=mod.VOUT, g=mod.VBP2, s=mod.VDD, b=mod.VDD)
    mod.xmn2 = nmos(_mos_params(params.w_stage2_n, params.l_stage2_n))(d=mod.VOUT, g=mod.VX, s=mod.VSS, b=mod.VSS)
    return mod


@h.generator
def _miller_rz_cc(params: OpampCoreParams) -> h.Module:
    mod = h.Module(name="MillerRzCc")
    mod.N1, mod.N2, mod.VSS = h.Ports(3)
    if float(params.r_comp_z) > 0.0:
        mod.ncc = h.Signal(name="ncc")
        mod.xrz = pdk_precision_resistor(float(params.r_comp_z), p=mod.N1, n=mod.ncc, bulk=mod.VSS)
        mod.xcc = pdk_mim_capacitor(float(params.c_comp), p=mod.ncc, n=mod.N2)
    else:
        mod.xcc = pdk_mim_capacitor(float(params.c_comp), p=mod.N1, n=mod.N2)
    return mod


@h.generator
def _p_bias_tail_ref(_: OpampCoreParams) -> h.Module:
    pmos = sky130_hdl21.primitives.PMOS_1p8V_STD

    mod = h.Module(name="PBiasTailRef")
    mod.VBP, mod.VDD, mod.VSS = h.Ports(3)
    mod.xpd = pmos(_mos_params(2.0, 2.0))(d=mod.VBP, g=mod.VBP, s=mod.VDD, b=mod.VDD)
    mod.xrb = _xhigh_res(float(_.l_bias_tail_ref), p=mod.VBP, n=mod.VSS, bulk=mod.VSS)
    return mod


@h.generator
def _p_bias_stage2_ref(_: OpampCoreParams) -> h.Module:
    pmos = sky130_hdl21.primitives.PMOS_1p8V_STD

    mod = h.Module(name="PBiasStage2Ref")
    mod.VBP, mod.VDD, mod.VSS = h.Ports(3)
    mod.xpd = pmos(_mos_params(2.0, 2.0))(d=mod.VBP, g=mod.VBP, s=mod.VDD, b=mod.VDD)
    mod.xrb = _xhigh_res(float(_.l_bias_stage2_ref), p=mod.VBP, n=mod.VSS, bulk=mod.VSS)
    return mod


@h.generator
def _n_bias_cascode_ref(params: OpampCoreParams) -> h.Module:
    nmos = sky130_hdl21.primitives.NMOS_1p8V_STD

    mod = h.Module(name="NBiasCascodeRef")
    mod.VBN, mod.VDD, mod.VSS = h.Ports(3)
    mod.nrefb = h.Signal(name="nrefb")
    mod.xrb = _xhigh_res(55.0, p=mod.VDD, n=mod.VBN, bulk=mod.VSS)
    mod.xmnr = nmos(_mos_params(params.w_load, params.l_load))(d=mod.nrefb, g=mod.nrefb, s=mod.VSS, b=mod.VSS)
    mod.xmcr = nmos(_mos_params(params.w_load_casc, params.l_load_casc))(d=mod.VBN, g=mod.VBN, s=mod.nrefb, b=mod.VSS)
    return mod


@h.generator
def opamp_core(params: OpampCoreParams) -> h.Module:
    mod = h.Module(name="OpampCoreV3")
    mod.VINP, mod.VINN, mod.VOUT, mod.EN, mod.VDD, mod.VSS = h.Ports(6)
    mod.vbp1, mod.vbn1, mod.vbp2 = h.Signals(3)
    mod.vtail, mod.vx, mod.vout_int = h.Signals(3)

    tail = _p_tail_source(params)
    stage1 = _stage1_pinput_casc_load(params)
    stage2 = _stage2_n_common_source(params)
    comp = _miller_rz_cc(params)

    mod.x_bp1 = _p_bias_tail_ref(params)(VBP=mod.vbp1, VDD=mod.VDD, VSS=mod.VSS)
    mod.x_bn1 = _n_bias_cascode_ref(params)(VBN=mod.vbn1, VDD=mod.VDD, VSS=mod.VSS)
    mod.x_bp2 = _p_bias_stage2_ref(params)(VBP=mod.vbp2, VDD=mod.VDD, VSS=mod.VSS)
    mod.x_tail = tail(OUT=mod.vtail, VBP=mod.vbp1, VDD=mod.VDD, VSS=mod.VSS)
    mod.x_stage1 = stage1(VINP=mod.VINP, VINN=mod.VINN, VX=mod.vx, VTAIL=mod.vtail, VBN1=mod.vbn1, VDD=mod.VDD, VSS=mod.VSS)
    mod.x_stage2 = stage2(VX=mod.vx, VOUT=mod.vout_int, VBP2=mod.vbp2, VDD=mod.VDD, VSS=mod.VSS)
    mod.x_comp = comp(N1=mod.vx, N2=mod.vout_int, VSS=mod.VSS)
    mod.vvout_link = h.Vdc(dc=0)(p=mod.vout_int, n=mod.VOUT)
    return mod


def run_structural_checks(params: OpampCoreParams | None = None):
    params = params or OpampCoreParams()
    try:
        h.generator.cache.reset()
    except Exception:
        pass
    dut = opamp_core(params)
    mod = h.elaborate(dut)
    return {
        "generator_call": dut is not None,
        "elaboration": mod is not None,
        "subckt_name": mod.name.startswith("OpampCoreV3"),
        "contains_first_stage": hasattr(mod, "x_stage1"),
        "contains_second_stage": hasattr(mod, "x_stage2"),
        "contains_output_path": False,
        "contains_compensation": hasattr(mod, "x_comp"),
        "contains_disable_hooks": False,
        "uses_pdk_bias_resistors": hasattr(mod, "x_bp1") and hasattr(mod, "x_bp2") and hasattr(mod, "x_bn1"),
        "uses_pdk_output_devices": False,
        "uses_pdk_comp_cap": hasattr(mod, "x_comp"),
    }
