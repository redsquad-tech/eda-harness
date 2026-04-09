from dataclasses import dataclass

import hdl21 as h
import sky130_hdl21

from components.diffpair_p import DiffpairPParams, diffpair_p
from .pdk_passives import pdk_mim_capacitor, pdk_resistor


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
            "uses_pdk_output_resistors",
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
    purpose: str = "Compose the first real clean-sheet static amplifier loop for the v3 architecture."
    component_class: str = "architecture branch"
    pins: tuple[str, ...] = ("VINP", "VINN", "VOUT", "EN", "VDD", "VSS")
    measurable_behaviors: tuple[str, ...] = ("structural",)
    numeric_pass_fail_criteria: tuple[str, ...] = ("real transistor-level scaffold only; no numeric closure targets yet",)
    required_corners: tuple[str, ...] = ()
    statistical_verification_required: bool = False


def _mos_params(w: h.Scalar, l: h.Scalar, nf: int = 1, mult: int = 1):
    return sky130_hdl21.Sky130MosParams(w=w, l=l, nf=nf, mult=mult)


@h.paramclass
class OpampCoreParams:
    architecture_name = h.Param(dtype=str, desc="Human-readable architecture label", default="v3_clean_loop")
    w_in = h.Param(dtype=h.Scalar, desc="PMOS input-pair width in um", default=10.0)
    l_in = h.Param(dtype=h.Scalar, desc="PMOS input-pair length in um", default=3.0)
    w_load = h.Param(dtype=h.Scalar, desc="NMOS mirror-load width in um", default=4.0)
    l_load = h.Param(dtype=h.Scalar, desc="NMOS mirror-load length in um", default=8.0)
    w_tail_ref = h.Param(dtype=h.Scalar, desc="PMOS first-stage bias reference width in um", default=3.0)
    l_tail_ref = h.Param(dtype=h.Scalar, desc="PMOS first-stage bias reference length in um", default=4.0)
    w_tail = h.Param(dtype=h.Scalar, desc="PMOS first-stage bias device width in um", default=4.0)
    l_tail = h.Param(dtype=h.Scalar, desc="PMOS first-stage bias device length in um", default=4.0)
    r_stage1_bias = h.Param(dtype=h.Scalar, desc="First-stage PMOS bias reference resistor in ohm", default=2.5e6)
    w_tail_sw = h.Param(dtype=h.Scalar, desc="PMOS tail enable-switch width in um", default=12.0)
    l_tail_sw = h.Param(dtype=h.Scalar, desc="PMOS tail enable-switch length in um", default=0.15)
    tail_switch_stack = h.Param(dtype=int, desc="Number of stacked PMOS devices in the tail enable path", default=1)
    w_stage2_n = h.Param(dtype=h.Scalar, desc="Second-stage NMOS width in um", default=20.0)
    l_stage2_n = h.Param(dtype=h.Scalar, desc="Second-stage NMOS length in um", default=6.0)
    w_stage2_p = h.Param(dtype=h.Scalar, desc="Second-stage PMOS load width in um", default=12.0)
    l_stage2_p = h.Param(dtype=h.Scalar, desc="Second-stage PMOS load length in um", default=10.0)
    w_stage2_bias_ref = h.Param(dtype=h.Scalar, desc="Second-stage PMOS bias reference width in um", default=3.0)
    l_stage2_bias_ref = h.Param(dtype=h.Scalar, desc="Second-stage PMOS bias reference length in um", default=4.0)
    r_stage2_bias = h.Param(dtype=h.Scalar, desc="Second-stage PMOS bias reference resistor in ohm", default=300e3)
    w_out_n = h.Param(dtype=h.Scalar, desc="Output helper PMOS width in um", default=1.2)
    l_out_n = h.Param(dtype=h.Scalar, desc="Output follower NMOS length in um", default=0.5)
    w_out_boost = h.Param(dtype=h.Scalar, desc="Optional secondary PMOS assist width in um; <= 0 disables it", default=0.0)
    l_out_boost = h.Param(dtype=h.Scalar, desc="Optional secondary PMOS assist length in um", default=0.5)
    w_out_pd = h.Param(dtype=h.Scalar, desc="Optional low-side NMOS assist width in um; <= 0 disables it", default=0.0)
    l_out_pd = h.Param(dtype=h.Scalar, desc="Optional low-side NMOS assist length in um", default=0.5)
    r_vdrv_out = h.Param(dtype=h.Scalar, desc="Direct output-link resistance in ohm", default=1.0)
    r_gp = h.Param(dtype=h.Scalar, desc="PMOS helper gate coupling resistance in ohm", default=1e6)
    r_gp_pullup = h.Param(dtype=h.Scalar, desc="Optional weak pull-up from helper gate to VDD in ohm; <= 0 disables it", default=0.0)
    r_gp_boost = h.Param(dtype=h.Scalar, desc="Optional secondary helper gate coupling resistance in ohm", default=1e6)
    r_gp_boost_pullup = h.Param(dtype=h.Scalar, desc="Optional weak pull-up from secondary helper gate to VDD in ohm; <= 0 disables it", default=0.0)
    isolate_gp_link_in_shutdown = h.Param(dtype=bool, desc="Insert an EN-controlled transmission gate in series with the helper gate-link", default=True)
    w_gp_sw = h.Param(dtype=h.Scalar, desc="Helper gate-link switch width in um", default=1.0)
    l_gp_sw = h.Param(dtype=h.Scalar, desc="Helper gate-link switch length in um", default=0.15)
    c_comp = h.Param(dtype=h.Scalar, desc="Miller compensation capacitor in F", default=220e-15)
    debug_current_probes = h.Param(dtype=bool, desc="Insert internal 0 V current probes for debug-only diagnostics", default=False)


@h.generator
def opamp_core(params: OpampCoreParams) -> h.Module:
    pmos = sky130_hdl21.primitives.PMOS_1p8V_STD
    nmos = sky130_hdl21.primitives.NMOS_1p8V_STD

    diffpair = diffpair_p(
        DiffpairPParams(
            w_in=params.w_in,
            l_in=params.l_in,
            nf_in=1,
            m_in=1,
        )
    )

    mod = h.Module(name="OpampCoreV3")
    mod.VINP, mod.VINN, mod.VOUT, mod.EN, mod.VDD, mod.VSS = h.Ports(6)
    mod.vx, mod.vref, mod.vdrv = h.Signals(3)
    mod.ibias1, mod.ibias2 = h.Signals(2)
    mod.tail1 = h.Signal(name="tail1")
    mod.vbp1 = h.Signal(name="vbp1")
    mod.vinp_int = h.Signal(name="vinp_int")
    mod.vinn_int = h.Signal(name="vinn_int")
    mod.gp = h.Signal(name="gp")
    mod.vss_bias1 = h.Signal(name="vss_bias1")
    mod.vss_bias2 = h.Signal(name="vss_bias2")
    mod.enb = h.Signal(name="enb")

    inv_npar = _mos_params(1.0, 0.15)
    inv_ppar = _mos_params(2.0, 0.15)
    mod.m_enb_p = pmos(inv_ppar)(d=mod.enb, g=mod.EN, s=mod.VDD, b=mod.VDD)
    mod.m_enb_n = nmos(inv_npar)(d=mod.enb, g=mod.EN, s=mod.VSS, b=mod.VSS)

    # First-stage PMOS current-bias generation and hard disable.
    tail_ref_par = _mos_params(params.w_tail_ref, params.l_tail_ref)
    tail_par = _mos_params(params.w_tail, params.l_tail)
    tail_sw_stack = max(int(params.tail_switch_stack), 1)
    mod.m_ibias1_ref = pmos(tail_ref_par)(d=mod.vbp1, g=mod.vbp1, s=mod.VDD, b=mod.VDD)
    mod.r_ibias1_ref = pdk_resistor(params.r_stage1_bias, p=mod.vbp1, n=mod.vss_bias1, bulk=mod.VSS)
    mod.m_bias1_en = nmos(_mos_params(4.0, 0.15))(d=mod.vss_bias1, g=mod.EN, s=mod.VSS, b=mod.VSS)
    mod.m_ibias1 = pmos(tail_par)(d=mod.ibias1, g=mod.vbp1, s=mod.VDD, b=mod.VDD)
    tail_sw_par = _mos_params(params.w_tail_sw, params.l_tail_sw)
    if tail_sw_stack == 1:
        mod.m_tail1_sw = pmos(tail_sw_par)(d=mod.tail1, g=mod.enb, s=mod.ibias1, b=mod.VDD)
        tail1_clamp_node = mod.tail1
    else:
        prev_node = mod.ibias1
        for idx in range(tail_sw_stack - 1):
            mid = h.Signal(name=f"tail1_sw_mid{idx + 1}")
            setattr(mod, f"tail1_sw_mid{idx + 1}", mid)
            setattr(mod, f"m_tail1_sw_{idx + 1}", pmos(tail_sw_par)(d=mid, g=mod.enb, s=prev_node, b=mod.VDD))
            prev_node = mid
        mod.m_tail1_sw = pmos(tail_sw_par)(d=mod.tail1, g=mod.enb, s=prev_node, b=mod.VDD)
        tail1_clamp_node = prev_node
    mod.m_ibias1_off = pmos(inv_ppar)(d=mod.vbp1, g=mod.EN, s=mod.VDD, b=mod.VDD)
    mod.m_ibias1_tail_off = pmos(inv_ppar)(d=mod.ibias1, g=mod.EN, s=mod.VDD, b=mod.VDD)
    mod.m_tail1_off = pmos(inv_ppar)(d=tail1_clamp_node, g=mod.EN, s=mod.VDD, b=mod.VDD)
    tg_npar = _mos_params(4.0, 0.15)
    tg_ppar = _mos_params(4.0, 0.15)
    mod.m_vinp_tg_n = nmos(tg_npar)(d=mod.vinp_int, g=mod.EN, s=mod.VINP, b=mod.VSS)
    mod.m_vinp_tg_p = pmos(tg_ppar)(d=mod.vinp_int, g=mod.enb, s=mod.VINP, b=mod.VDD)
    mod.m_vinn_tg_n = nmos(tg_npar)(d=mod.vinn_int, g=mod.EN, s=mod.VINN, b=mod.VSS)
    mod.m_vinn_tg_p = pmos(tg_ppar)(d=mod.vinn_int, g=mod.enb, s=mod.VINN, b=mod.VDD)
    mod.m_vinp_off = pmos(inv_ppar)(d=mod.vinp_int, g=mod.EN, s=mod.VDD, b=mod.VDD)
    mod.m_vinn_off = pmos(inv_ppar)(d=mod.vinn_int, g=mod.EN, s=mod.VDD, b=mod.VDD)

    if params.debug_current_probes:
        mod.tail1_core = h.Signal(name="tail1_core")
        mod.vx_core = h.Signal(name="vx_core")
        mod.vref_core = h.Signal(name="vref_core")
        mod.vdrv_core = h.Signal(name="vdrv_core")
        mod.vdrv_stage2_p = h.Signal(name="vdrv_stage2_p")
        mod.vdrv_stage2_n = h.Signal(name="vdrv_stage2_n")
        mod.vdrv_stage2_off = h.Signal(name="vdrv_stage2_off")
        mod.vdrv_out_link = h.Signal(name="vdrv_out_link")
        mod.vdrv_gp_link = h.Signal(name="vdrv_gp_link")
        tail1_core = mod.tail1_core
        vx_core = mod.vx_core
        vref_core = mod.vref_core
        vdrv_core = mod.vdrv_core
        vdrv_stage2_p = mod.vdrv_stage2_p
        vdrv_stage2_n = mod.vdrv_stage2_n
        vdrv_stage2_off = mod.vdrv_stage2_off
        vdrv_out_link = mod.vdrv_out_link
        vdrv_gp_link = mod.vdrv_gp_link
        mod.vprobe_tail1 = h.Vdc(dc=0)(p=mod.tail1, n=tail1_core)
        mod.vprobe_vx = h.Vdc(dc=0)(p=vx_core, n=mod.vx)
        mod.vprobe_vref = h.Vdc(dc=0)(p=vref_core, n=mod.vref)
        mod.vprobe_vdrv = h.Vdc(dc=0)(p=vdrv_core, n=mod.vdrv)
        mod.vprobe_stage2_p = h.Vdc(dc=0)(p=vdrv_stage2_p, n=vdrv_core)
        mod.vprobe_stage2_n = h.Vdc(dc=0)(p=vdrv_stage2_n, n=vdrv_core)
        mod.vprobe_stage2_off = h.Vdc(dc=0)(p=vdrv_stage2_off, n=vdrv_core)
        mod.vprobe_vdrv_out = h.Vdc(dc=0)(p=mod.vdrv, n=vdrv_out_link)
        mod.vprobe_vdrv_gp = h.Vdc(dc=0)(p=mod.vdrv, n=vdrv_gp_link)
    else:
        tail1_core = mod.tail1
        vx_core = mod.vx
        vref_core = mod.vref
        vdrv_core = mod.vdrv
        vdrv_stage2_p = vdrv_core
        vdrv_stage2_n = vdrv_core
        vdrv_stage2_off = vdrv_core
        vdrv_out_link = mod.vdrv
        vdrv_gp_link = mod.vdrv

    # First stage: PMOS differential pair + NMOS mirror load.
    mod.xin = diffpair(INP=mod.vinp_int, INN=mod.vinn_int, OUTP=vx_core, OUTN=vref_core, TAIL=tail1_core, VDD=mod.VDD, VSS=mod.VSS)
    load_par = _mos_params(params.w_load, params.l_load)
    mod.m_load_ref = nmos(load_par)(d=mod.vref, g=mod.vref, s=mod.VSS, b=mod.VSS)
    mod.m_load_out = nmos(load_par)(d=mod.vx, g=mod.vref, s=mod.VSS, b=mod.VSS)

    # Second-stage PMOS load-bias generation and hard disable.
    stage2_bias_ref_par = _mos_params(params.w_stage2_bias_ref, params.l_stage2_bias_ref)
    stage2_p_par = _mos_params(params.w_stage2_p, params.l_stage2_p)
    stage2_n_par = _mos_params(params.w_stage2_n, params.l_stage2_n)
    mod.m_ibias2_ref = pmos(stage2_bias_ref_par)(d=mod.ibias2, g=mod.ibias2, s=mod.VDD, b=mod.VDD)
    mod.r_ibias2_ref = pdk_resistor(params.r_stage2_bias, p=mod.ibias2, n=mod.vss_bias2, bulk=mod.VSS)
    mod.m_bias2_en = nmos(_mos_params(4.0, 0.15))(d=mod.vss_bias2, g=mod.EN, s=mod.VSS, b=mod.VSS)
    mod.m_ibias2_off = pmos(inv_ppar)(d=mod.ibias2, g=mod.EN, s=mod.VDD, b=mod.VDD)

    # Explicit second gain node.
    # Use a PMOS current-source load referenced from the dedicated stage-2 bias node.
    mod.m_stage2_p = pmos(stage2_p_par)(d=vdrv_stage2_p, g=mod.ibias2, s=mod.VDD, b=mod.VDD)
    mod.m_stage2_n = nmos(stage2_n_par)(d=vdrv_stage2_n, g=mod.vx, s=mod.VSS, b=mod.VSS)
    mod.m_stage2_off = nmos(inv_npar)(d=vdrv_stage2_off, g=mod.enb, s=mod.VSS, b=mod.VSS)

    # Explicit non-inverting final output path:
    # direct VDRV drive plus high-side PMOS helper.
    out_p_par = _mos_params(params.w_out_n, params.l_out_n)
    mod.r_vdrv_out = pdk_resistor(params.r_vdrv_out, p=vdrv_out_link, n=mod.VOUT)
    if params.isolate_gp_link_in_shutdown:
        mod.gp_link_src = h.Signal(name="gp_link_src")
        gp_sw_npar = _mos_params(params.w_gp_sw, params.l_gp_sw)
        gp_sw_ppar = _mos_params(params.w_gp_sw, params.l_gp_sw)
        mod.m_gp_sw_n = nmos(gp_sw_npar)(d=mod.gp_link_src, g=mod.EN, s=vdrv_gp_link, b=mod.VSS)
        mod.m_gp_sw_p = pmos(gp_sw_ppar)(d=mod.gp_link_src, g=mod.enb, s=vdrv_gp_link, b=mod.VDD)
        gp_link_node = mod.gp_link_src
    else:
        gp_link_node = vdrv_gp_link
    mod.r_gp = pdk_resistor(params.r_gp, p=gp_link_node, n=mod.gp, bulk=mod.VSS)
    if float(params.r_gp_pullup) > 0.0:
        mod.r_gp_pullup = pdk_resistor(params.r_gp_pullup, p=mod.VDD, n=mod.gp, bulk=mod.VSS)
    mod.m_gp_off = pmos(inv_ppar)(d=mod.gp, g=mod.EN, s=mod.VDD, b=mod.VDD)
    mod.m_out_p = pmos(out_p_par)(d=mod.VOUT, g=mod.gp, s=mod.VDD, b=mod.VDD)
    if float(params.w_out_boost) > 0.0:
        out_boost_par = _mos_params(params.w_out_boost, params.l_out_boost)
        mod.gp_boost = h.Signal(name="gp_boost")
        mod.r_gp_boost = pdk_resistor(params.r_gp_boost, p=gp_link_node, n=mod.gp_boost, bulk=mod.VSS)
        if float(params.r_gp_boost_pullup) > 0.0:
            mod.r_gp_boost_pullup = pdk_resistor(params.r_gp_boost_pullup, p=mod.VDD, n=mod.gp_boost, bulk=mod.VSS)
        mod.m_gp_boost_off = pmos(inv_ppar)(d=mod.gp_boost, g=mod.EN, s=mod.VDD, b=mod.VDD)
        mod.m_out_p_boost = pmos(out_boost_par)(d=mod.VOUT, g=mod.gp_boost, s=mod.VDD, b=mod.VDD)
    if float(params.w_out_pd) > 0.0:
        out_pd_par = _mos_params(params.w_out_pd, params.l_out_pd)
        mod.gn = h.Signal(name="gn")
        mod.m_gn_p = pmos(inv_ppar)(d=mod.gn, g=mod.vdrv, s=mod.VDD, b=mod.VDD)
        mod.m_gn_n = nmos(inv_npar)(d=mod.gn, g=mod.vdrv, s=mod.VSS, b=mod.VSS)
        mod.m_out_n_assist = nmos(out_pd_par)(d=mod.VOUT, g=mod.gn, s=mod.VSS, b=mod.VSS)

    # Compensation between the two explicit gain nodes.
    mod.cc = pdk_mim_capacitor(params.c_comp, p=mod.vx, n=mod.vdrv)
    return mod


def run_structural_checks(params: OpampCoreParams | None = None):
    params = params or OpampCoreParams()
    dut = opamp_core(params)
    mod = h.elaborate(dut)
    return {
        "generator_call": dut is not None,
        "elaboration": mod is not None,
        "subckt_name": mod.name.startswith("OpampCoreV3"),
        "contains_first_stage": hasattr(mod, "xin") and hasattr(mod, "m_load_out"),
        "contains_second_stage": hasattr(mod, "m_stage2_p") and hasattr(mod, "m_stage2_n"),
        "contains_output_path": hasattr(mod, "m_out_p") and hasattr(mod, "r_vdrv_out"),
        "contains_compensation": hasattr(mod, "cc"),
        "uses_pdk_bias_resistors": hasattr(mod, "r_ibias1_ref") and hasattr(mod, "r_ibias2_ref"),
        "uses_pdk_output_resistors": hasattr(mod, "r_vdrv_out") and hasattr(mod, "r_gp"),
        "uses_pdk_comp_cap": hasattr(mod, "cc"),
        "contains_disable_hooks": hasattr(mod, "m_ibias1_off") and hasattr(mod, "m_ibias1_tail_off") and hasattr(mod, "m_tail1_off") and hasattr(mod, "m_vinp_off") and hasattr(mod, "m_vinn_off") and hasattr(mod, "m_ibias2_off") and hasattr(mod, "m_gp_off") and hasattr(mod, "m_stage2_off") and hasattr(mod, "m_bias1_en") and hasattr(mod, "m_bias2_en"),
    }
