from pathlib import Path

import hdl21 as h
import sky130_hdl21

from components.diffpair_p import DiffpairPParams, diffpair_p
from .opamp_core import OpampCoreParams, _mos_params
from .pdk_passives import pdk_mim_capacitor, pdk_precision_resistor


@h.paramclass
class OpampOtaParams:
    architecture_name = h.Param(dtype=str, desc="Human-readable architecture label", default="v3_normal_mode_ota")
    w_in = h.Param(dtype=h.Scalar, desc="PMOS input-pair width in um", default=14.0)
    l_in = h.Param(dtype=h.Scalar, desc="PMOS input-pair length in um", default=3.0)
    w_load = h.Param(dtype=h.Scalar, desc="NMOS mirror-load width in um", default=4.0)
    l_load = h.Param(dtype=h.Scalar, desc="NMOS mirror-load length in um", default=8.0)
    w_tail_ref = h.Param(dtype=h.Scalar, desc="PMOS first-stage bias reference width in um", default=3.0)
    l_tail_ref = h.Param(dtype=h.Scalar, desc="PMOS first-stage bias reference length in um", default=4.0)
    w_tail = h.Param(dtype=h.Scalar, desc="PMOS first-stage bias device width in um", default=4.0)
    l_tail = h.Param(dtype=h.Scalar, desc="PMOS first-stage bias device length in um", default=4.0)
    r_stage1_bias = h.Param(dtype=h.Scalar, desc="First-stage PMOS bias reference resistor in ohm", default=2.5e6)
    w_stage2_n = h.Param(dtype=h.Scalar, desc="Second-stage NMOS width in um", default=24.0)
    l_stage2_n = h.Param(dtype=h.Scalar, desc="Second-stage NMOS length in um", default=6.0)
    w_stage2_p = h.Param(dtype=h.Scalar, desc="Second-stage PMOS load width in um", default=12.0)
    l_stage2_p = h.Param(dtype=h.Scalar, desc="Second-stage PMOS load length in um", default=12.0)
    w_stage2_bias_ref = h.Param(dtype=h.Scalar, desc="Second-stage PMOS bias reference width in um", default=3.0)
    l_stage2_bias_ref = h.Param(dtype=h.Scalar, desc="Second-stage PMOS bias reference length in um", default=4.0)
    r_stage2_bias = h.Param(dtype=h.Scalar, desc="Second-stage PMOS bias reference resistor in ohm", default=5.5e6)
    v_stage2_gate_shift = h.Param(dtype=h.Scalar, desc="Diagnostic DC level shift from VX to second-stage NMOS gate in V", default=0.18)
    c_comp = h.Param(dtype=h.Scalar, desc="Miller compensation capacitor in F", default=2.7e-12)
    r_comp_z = h.Param(dtype=h.Scalar, desc="Series resistor for Miller compensation capacitor in ohm", default=0.0)


def ota_params_from_core(core_params: OpampCoreParams) -> OpampOtaParams:
    return OpampOtaParams(
        architecture_name="v3_normal_mode_ota",
        w_in=core_params.w_in,
        l_in=core_params.l_in,
        w_load=core_params.w_load,
        l_load=core_params.l_load,
        w_tail_ref=core_params.w_tail_ref,
        l_tail_ref=core_params.l_tail_ref,
        w_tail=core_params.w_tail,
        l_tail=core_params.l_tail,
        r_stage1_bias=core_params.r_stage1_bias,
        w_stage2_n=core_params.w_stage2_n,
        l_stage2_n=core_params.l_stage2_n,
        w_stage2_p=core_params.w_stage2_p,
        l_stage2_p=core_params.l_stage2_p,
        w_stage2_bias_ref=core_params.w_stage2_bias_ref,
        l_stage2_bias_ref=core_params.l_stage2_bias_ref,
        r_stage2_bias=core_params.r_stage2_bias,
        v_stage2_gate_shift=0.18,
        c_comp=core_params.c_comp,
        r_comp_z=core_params.r_comp_z,
    )


@h.generator
def opamp_ota(params: OpampOtaParams) -> h.Module:
    pmos = sky130_hdl21.primitives.PMOS_1p8V_STD
    nmos = sky130_hdl21.primitives.NMOS_1p8V_STD

    diffpair = diffpair_p(DiffpairPParams(w_in=params.w_in, l_in=params.l_in, nf_in=1, m_in=1))
    mod = h.Module(name="OpampOtaV3")
    mod.VINP, mod.VINN, mod.VOUT, mod.VDD, mod.VSS = h.Ports(5)
    mod.vx, mod.vref, mod.vdrv = h.Signals(3)
    mod.ibias1, mod.ibias2 = h.Signals(2)
    mod.vg_stage2 = h.Signal(name="vg_stage2")
    mod.tail1 = h.Signal(name="tail1")
    mod.vbp1 = h.Signal(name="vbp1")
    mod.vss_bias1 = h.Signal(name="vss_bias1")
    mod.vss_bias2 = h.Signal(name="vss_bias2")

    tail_ref_par = _mos_params(params.w_tail_ref, params.l_tail_ref)
    tail_par = _mos_params(params.w_tail, params.l_tail)
    load_par = _mos_params(params.w_load, params.l_load)
    stage2_bias_ref_par = _mos_params(params.w_stage2_bias_ref, params.l_stage2_bias_ref)

    mod.m_ibias1_ref = pmos(tail_ref_par)(d=mod.vbp1, g=mod.vbp1, s=mod.VDD, b=mod.VDD)
    mod.r_ibias1_ref = pdk_precision_resistor(params.r_stage1_bias, p=mod.vbp1, n=mod.vss_bias1, bulk=mod.VSS)
    mod.m_bias1_on = nmos(_mos_params(4.0, 0.15))(d=mod.vss_bias1, g=mod.VDD, s=mod.VSS, b=mod.VSS)
    mod.m_ibias1 = pmos(tail_par)(d=mod.ibias1, g=mod.vbp1, s=mod.VDD, b=mod.VDD)
    mod.vlink_tail1 = h.Vdc(dc=0)(p=mod.ibias1, n=mod.tail1)

    mod.xin = diffpair(INP=mod.VINP, INN=mod.VINN, OUTP=mod.vx, OUTN=mod.vref, TAIL=mod.tail1, VDD=mod.VDD, VSS=mod.VSS)
    mod.m_load_ref = nmos(load_par)(d=mod.vref, g=mod.vref, s=mod.VSS, b=mod.VSS)
    mod.m_load_out = nmos(load_par)(d=mod.vx, g=mod.vref, s=mod.VSS, b=mod.VSS)

    mod.m_ibias2_ref = pmos(stage2_bias_ref_par)(d=mod.ibias2, g=mod.ibias2, s=mod.VDD, b=mod.VDD)
    mod.r_ibias2_ref = pdk_precision_resistor(params.r_stage2_bias, p=mod.ibias2, n=mod.vss_bias2, bulk=mod.VSS)
    mod.m_bias2_on = nmos(_mos_params(4.0, 0.15))(d=mod.vss_bias2, g=mod.VDD, s=mod.VSS, b=mod.VSS)
    mod.vshift_stage2_gate = h.Vdc(dc=params.v_stage2_gate_shift)(p=mod.vg_stage2, n=mod.vx)
    mod.m_stage2_p = pmos(_mos_params(params.w_stage2_p, params.l_stage2_p))(d=mod.vdrv, g=mod.ibias2, s=mod.VDD, b=mod.VDD)
    mod.m_stage2_n = nmos(_mos_params(params.w_stage2_n, params.l_stage2_n))(d=mod.vdrv, g=mod.vg_stage2, s=mod.VSS, b=mod.VSS)
    mod.vlink_vout = h.Vdc(dc=0)(p=mod.vdrv, n=mod.VOUT)

    if float(params.r_comp_z) > 0:
        mod.vccomp = h.Signal(name="vccomp")
        mod.r_comp_z = pdk_precision_resistor(params.r_comp_z, p=mod.vx, n=mod.vccomp, bulk=mod.VSS)
        mod.cc = pdk_mim_capacitor(params.c_comp, p=mod.vccomp, n=mod.vdrv)
    else:
        mod.cc = pdk_mim_capacitor(params.c_comp, p=mod.vx, n=mod.vdrv)

    return mod


def elaborate_dut(params: OpampOtaParams | None = None) -> h.Module:
    return h.elaborate(opamp_ota(params or OpampOtaParams()))


def export_spice(path: str | Path, params: OpampOtaParams | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mod = elaborate_dut(params)
    with path.open("w") as f:
        h.netlist(mod, f, fmt="spice")
    return path
