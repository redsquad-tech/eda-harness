from dataclasses import dataclass
from pathlib import Path

import hdl21 as h
import sky130_hdl21
from hdl21.sim import Op, Save, SaveMode, Sim, Tran
from vlsirtools.spice import SimOptions, SupportedSimulators

from components import require_sky130_install, run_ngspice_sim
from components.diffpair_p import DiffpairPParams, diffpair_p
from components.tg_switch import TgSwitchParams, tg_switch
from .opamp_core import (
    OpampCoreParams,
)
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
            "contains_input_mux",
            "contains_trim_pair",
            "contains_trim_input_bias",
            "contains_hold_caps",
            "contains_output_isolation",
            "contains_direct_output_link",
            "contains_legacy_output_path",
        ],
        "pass_fail_rule": "all structural checks pass",
        "required_corners": [],
        "required_operating_conditions": [],
        "monte_carlo_required": False,
    },
}


@dataclass(frozen=True)
class OpampAzTopSpec:
    name: str = "opamp_az_top_v3"
    purpose: str = "Foreground auto-zero wrapper around the v3 core using input muxing, stored differential correction, and input-bias trim injection outside the high-gain node."
    component_class: str = "integrated auto-zero top"
    pins: tuple[str, ...] = ("VINP", "VINN", "VOUT", "D_EN_OA", "D_AZ_OA", "D_INF_OA", "VDD", "VSS")


def _mos_params(w: h.Scalar, l: h.Scalar, nf: int = 1, mult: int = 1):
    return sky130_hdl21.Sky130MosParams(w=w, l=l, nf=nf, mult=mult)


def _default_ngspice_options(test_name: str) -> SimOptions:
    return SimOptions(simulator=SupportedSimulators.NGSPICE, rundir=f"./tmp/{test_name}")


@h.paramclass
class OpampAzTopParams:
    opamp_core_params = h.Param(dtype=OpampCoreParams, desc="Core-derived sizing baseline", default=OpampCoreParams())
    c_az = h.Param(dtype=h.Scalar, desc="Held correction capacitance per side in F", default=4e-12)
    vcm_az = h.Param(dtype=h.Scalar, desc="Internal auto-zero common-mode reference in V", default=0.9)
    r_vdrv_ref_top = h.Param(dtype=h.Scalar, desc="Top resistor for internal VDRV_Q replica in ohm", default=2.4e6)
    r_vdrv_ref_bot = h.Param(dtype=h.Scalar, desc="Bottom resistor for internal VDRV_Q replica in ohm", default=1.0e6)
    w_trim_in = h.Param(dtype=h.Scalar, desc="Weak trim-pair PMOS width in um", default=4.0)
    l_trim_in = h.Param(dtype=h.Scalar, desc="Weak trim-pair PMOS length in um", default=12.0)
    w_trim_ref = h.Param(dtype=h.Scalar, desc="Trim-tail PMOS reference width in um", default=4.0)
    l_trim_ref = h.Param(dtype=h.Scalar, desc="Trim-tail PMOS reference length in um", default=12.0)
    w_trim_tail = h.Param(dtype=h.Scalar, desc="Trim-tail PMOS mirror width in um", default=4.0)
    l_trim_tail = h.Param(dtype=h.Scalar, desc="Trim-tail PMOS mirror length in um", default=12.0)
    r_trim_bias = h.Param(dtype=h.Scalar, desc="Trim-tail PMOS reference resistor in ohm", default=1e8)
    r_trim_inj = h.Param(dtype=h.Scalar, desc="Held-trim input-bias injection resistance in ohm", default=200e6)
    w_sw_n = h.Param(dtype=h.Scalar, desc="MUX/hold NMOS switch width in um", default=1.0)
    w_sw_p = h.Param(dtype=h.Scalar, desc="MUX/hold PMOS switch width in um", default=1.6)
    l_sw = h.Param(dtype=h.Scalar, desc="MUX/hold switch length in um", default=0.15)
    w_out_sw_n = h.Param(dtype=h.Scalar, desc="Output-isolation NMOS switch width in um", default=8.0)
    w_out_sw_p = h.Param(dtype=h.Scalar, desc="Output-isolation PMOS switch width in um", default=12.0)
    l_out_sw = h.Param(dtype=h.Scalar, desc="Output-isolation switch length in um", default=0.15)
    g_az_servo = h.Param(dtype=h.Scalar, desc="AZ servo transconductance in A/V", default=5e-6)
    r_az_reset_delay = h.Param(dtype=h.Scalar, desc="AZ reset pulse RC delay resistor in ohm", default=1e6)
    c_az_reset_delay = h.Param(dtype=h.Scalar, desc="AZ reset pulse RC delay capacitor in F", default=5e-13)


@h.generator
def opamp_az_top(params: OpampAzTopParams) -> h.Module:
    pmos = sky130_hdl21.primitives.PMOS_1p8V_STD
    nmos = sky130_hdl21.primitives.NMOS_1p8V_STD

    core_params = params.opamp_core_params
    diffpair_main = diffpair_p(DiffpairPParams(w_in=core_params.w_in, l_in=core_params.l_in, nf_in=1, m_in=1))
    tg_small = tg_switch(
        TgSwitchParams(
            w_n=params.w_sw_n,
            l_n=params.l_sw,
            nf_n=1,
            m_n=1,
            w_p=params.w_sw_p,
            l_p=params.l_sw,
            nf_p=1,
            m_p=1,
            use_dummy_switch=False,
        )
    )
    tg_out = tg_switch(
        TgSwitchParams(
            w_n=params.w_out_sw_n,
            l_n=params.l_out_sw,
            nf_n=1,
            m_n=1,
            w_p=params.w_out_sw_p,
            l_p=params.l_out_sw,
            nf_p=1,
            m_p=1,
            use_dummy_switch=False,
        )
    )
    mod = h.Module(name="OpampAzTopV3")
    mod.VINP, mod.VINN, mod.VOUT, mod.D_EN_OA, mod.D_AZ_OA, mod.D_INF_OA, mod.VDD, mod.VSS = h.Ports(8)

    # Mode-control complements.
    mod.enb, mod.azb, mod.infb = h.Signals(3)
    mod.az_reset_raw, mod.az_reset_rawb, mod.az_reset, mod.az_reset_b, mod.az_null, mod.az_null_b = h.Signals(6)
    mod.az_rc, mod.az_nand_reset_b, mod.az_nand_null_b = h.Signals(3)
    inv_npar = _mos_params(1.0, 0.15)
    inv_ppar = _mos_params(2.0, 0.15)
    mod.m_enb_p = pmos(inv_ppar)(d=mod.enb, g=mod.D_EN_OA, s=mod.VDD, b=mod.VDD)
    mod.m_enb_n = nmos(inv_npar)(d=mod.enb, g=mod.D_EN_OA, s=mod.VSS, b=mod.VSS)
    mod.m_azb_p = pmos(inv_ppar)(d=mod.azb, g=mod.D_AZ_OA, s=mod.VDD, b=mod.VDD)
    mod.m_azb_n = nmos(inv_npar)(d=mod.azb, g=mod.D_AZ_OA, s=mod.VSS, b=mod.VSS)
    mod.m_infb_p = pmos(inv_ppar)(d=mod.infb, g=mod.D_INF_OA, s=mod.VDD, b=mod.VDD)
    mod.m_infb_n = nmos(inv_npar)(d=mod.infb, g=mod.D_INF_OA, s=mod.VSS, b=mod.VSS)

    # Internal AZ sequencing:
    # D_AZ rising edge generates a short AZ_RESET pulse, then transitions into AZ_NULL.
    mod.r_az_reset_delay = pdk_precision_resistor(params.r_az_reset_delay, p=mod.D_AZ_OA, n=mod.az_rc, bulk=mod.VSS)
    mod.c_az_reset_delay = pdk_mim_capacitor(params.c_az_reset_delay, p=mod.az_rc, n=mod.VSS)
    mod.m_az_reset_raw_p = pmos(inv_ppar)(d=mod.az_reset_raw, g=mod.az_rc, s=mod.VDD, b=mod.VDD)
    mod.m_az_reset_raw_n = nmos(inv_npar)(d=mod.az_reset_raw, g=mod.az_rc, s=mod.VSS, b=mod.VSS)
    mod.m_az_reset_rawb_p = pmos(inv_ppar)(d=mod.az_reset_rawb, g=mod.az_reset_raw, s=mod.VDD, b=mod.VDD)
    mod.m_az_reset_rawb_n = nmos(inv_npar)(d=mod.az_reset_rawb, g=mod.az_reset_raw, s=mod.VSS, b=mod.VSS)

    # az_reset = D_AZ & az_reset_raw
    mod.m_az_nand_reset_p0 = pmos(inv_ppar)(d=mod.az_nand_reset_b, g=mod.D_AZ_OA, s=mod.VDD, b=mod.VDD)
    mod.m_az_nand_reset_p1 = pmos(inv_ppar)(d=mod.az_nand_reset_b, g=mod.az_reset_raw, s=mod.VDD, b=mod.VDD)
    mod.az_nand_reset_mid = h.Signal(name="az_nand_reset_mid")
    mod.m_az_nand_reset_n0 = nmos(inv_npar)(d=mod.az_nand_reset_b, g=mod.D_AZ_OA, s=mod.az_nand_reset_mid, b=mod.VSS)
    mod.m_az_nand_reset_n1 = nmos(inv_npar)(d=mod.az_nand_reset_mid, g=mod.az_reset_raw, s=mod.VSS, b=mod.VSS)
    mod.m_az_reset_p = pmos(inv_ppar)(d=mod.az_reset, g=mod.az_nand_reset_b, s=mod.VDD, b=mod.VDD)
    mod.m_az_reset_n = nmos(inv_npar)(d=mod.az_reset, g=mod.az_nand_reset_b, s=mod.VSS, b=mod.VSS)
    mod.m_az_reset_b_p = pmos(inv_ppar)(d=mod.az_reset_b, g=mod.az_reset, s=mod.VDD, b=mod.VDD)
    mod.m_az_reset_b_n = nmos(inv_npar)(d=mod.az_reset_b, g=mod.az_reset, s=mod.VSS, b=mod.VSS)

    # az_null = D_AZ & az_reset_rawb
    mod.m_az_nand_null_p0 = pmos(inv_ppar)(d=mod.az_nand_null_b, g=mod.D_AZ_OA, s=mod.VDD, b=mod.VDD)
    mod.m_az_nand_null_p1 = pmos(inv_ppar)(d=mod.az_nand_null_b, g=mod.az_reset_rawb, s=mod.VDD, b=mod.VDD)
    mod.az_nand_null_mid = h.Signal(name="az_nand_null_mid")
    mod.m_az_nand_null_n0 = nmos(inv_npar)(d=mod.az_nand_null_b, g=mod.D_AZ_OA, s=mod.az_nand_null_mid, b=mod.VSS)
    mod.m_az_nand_null_n1 = nmos(inv_npar)(d=mod.az_nand_null_mid, g=mod.az_reset_rawb, s=mod.VSS, b=mod.VSS)
    mod.m_az_null_p = pmos(inv_ppar)(d=mod.az_null, g=mod.az_nand_null_b, s=mod.VDD, b=mod.VDD)
    mod.m_az_null_n = nmos(inv_npar)(d=mod.az_null, g=mod.az_nand_null_b, s=mod.VSS, b=mod.VSS)
    mod.m_az_null_b_p = pmos(inv_ppar)(d=mod.az_null_b, g=mod.az_null, s=mod.VDD, b=mod.VDD)
    mod.m_az_null_b_n = nmos(inv_npar)(d=mod.az_null_b, g=mod.az_null, s=mod.VSS, b=mod.VSS)

    # Internal references and held trim nodes.
    mod.vcm_az = h.Signal(name="vcm_az")
    mod.vdrv_qref = h.Signal(name="vdrv_qref")
    mod.vtrp = h.Signal(name="vtrp")
    mod.vtrn = h.Signal(name="vtrn")
    mod.vsense_az = h.Signal(name="vsense_az")
    mod.vtarget_az = h.Signal(name="vtarget_az")
    mod.vservo_p = h.Signal(name="vservo_p")
    mod.vservo_n = h.Signal(name="vservo_n")
    mod.vinp_core = h.Signal(name="vinp_core")
    mod.vinn_core = h.Signal(name="vinn_core")
    mod.vx, mod.vref, mod.vdrv = h.Signals(3)
    mod.ibias1, mod.ibias2 = h.Signals(2)
    mod.tail1 = h.Signal()
    mod.vbp1 = h.Signal()
    mod.vss_bias1, mod.vss_bias2 = h.Signals(2)
    mod.vvcm_az = h.Vdc(dc=params.vcm_az)(p=mod.vcm_az, n=mod.VSS)
    mod.r_vdrv_ref_top = pdk_precision_resistor(params.r_vdrv_ref_top, p=mod.VDD, n=mod.vdrv_qref, bulk=mod.VSS)
    mod.r_vdrv_ref_bot = pdk_precision_resistor(params.r_vdrv_ref_bot, p=mod.vdrv_qref, n=mod.VSS, bulk=mod.VSS)

    # Input mux: AZ mode forces both internal inputs to VCM_AZ, inference reconnects external pins.
    mod.xsw_inp_ext = tg_small(A=mod.VINP, B=mod.vinp_core, PHI=mod.D_INF_OA, PHIB=mod.infb, VDD=mod.VDD, VSS=mod.VSS)
    mod.xsw_inn_ext = tg_small(A=mod.VINN, B=mod.vinn_core, PHI=mod.D_INF_OA, PHIB=mod.infb, VDD=mod.VDD, VSS=mod.VSS)
    mod.xsw_inp_az = tg_small(A=mod.vcm_az, B=mod.vinp_core, PHI=mod.D_AZ_OA, PHIB=mod.azb, VDD=mod.VDD, VSS=mod.VSS)
    mod.xsw_inn_az = tg_small(A=mod.vcm_az, B=mod.vinn_core, PHI=mod.D_AZ_OA, PHIB=mod.azb, VDD=mod.VDD, VSS=mod.VSS)
    mod.r_vinp_bleed = pdk_precision_resistor(500e6, p=mod.vinp_core, n=mod.vcm_az, bulk=mod.VSS)
    mod.r_vinn_bleed = pdk_precision_resistor(500e6, p=mod.vinn_core, n=mod.vcm_az, bulk=mod.VSS)

    # AZ servo:
    # - store differential trim around fixed common-mode VTR_CM = VCM_AZ
    # - in AZ mode, compare VDRV against VDRV_QREF
    # - inject opposite currents into the held trim nodes
    # The servo outputs are physically disconnected outside AZ_NULL so the
    # latched correction is held only on CazP/ CazN during latch/ inference.
    mod.xsw_trim_reset_p = tg_small(A=mod.vcm_az, B=mod.vtrp, PHI=mod.az_reset, PHIB=mod.az_reset_b, VDD=mod.VDD, VSS=mod.VSS)
    mod.xsw_trim_reset_n = tg_small(A=mod.vcm_az, B=mod.vtrn, PHI=mod.az_reset, PHIB=mod.az_reset_b, VDD=mod.VDD, VSS=mod.VSS)
    mod.xsw_servo_sense = tg_small(A=mod.vdrv, B=mod.vsense_az, PHI=mod.az_null, PHIB=mod.az_null_b, VDD=mod.VDD, VSS=mod.VSS)
    mod.xsw_servo_target = tg_small(A=mod.vdrv_qref, B=mod.vtarget_az, PHI=mod.az_null, PHIB=mod.az_null_b, VDD=mod.VDD, VSS=mod.VSS)
    mod.xsw_servo_drive_p = tg_small(A=mod.vservo_p, B=mod.vtrp, PHI=mod.az_null, PHIB=mod.az_null_b, VDD=mod.VDD, VSS=mod.VSS)
    mod.xsw_servo_drive_n = tg_small(A=mod.vservo_n, B=mod.vtrn, PHI=mod.az_null, PHIB=mod.az_null_b, VDD=mod.VDD, VSS=mod.VSS)
    mod.r_vsense_bleed = pdk_precision_resistor(1e9, p=mod.vsense_az, n=mod.vcm_az, bulk=mod.VSS)
    mod.r_vtarget_bleed = pdk_precision_resistor(1e9, p=mod.vtarget_az, n=mod.vcm_az, bulk=mod.VSS)
    mod.r_vservo_p_bleed = pdk_precision_resistor(100e9, p=mod.vservo_p, n=mod.vcm_az, bulk=mod.VSS)
    mod.r_vservo_n_bleed = pdk_precision_resistor(100e9, p=mod.vservo_n, n=mod.vcm_az, bulk=mod.VSS)
    mod.gm_servo_p = h.Vccs(h.ControlledSourceParams(gain=params.g_az_servo))(p=mod.vservo_p, n=mod.vcm_az, cp=mod.vsense_az, cn=mod.vtarget_az)
    mod.gm_servo_n = h.Vccs(h.ControlledSourceParams(gain=params.g_az_servo))(p=mod.vcm_az, n=mod.vservo_n, cp=mod.vsense_az, cn=mod.vtarget_az)
    mod.caz_n = pdk_mim_capacitor(params.c_az, p=mod.vtrn, n=mod.vcm_az)
    mod.caz_p = pdk_mim_capacitor(params.c_az, p=mod.vtrp, n=mod.vcm_az)
    mod.r_vtrn_bleed = pdk_precision_resistor(100e9, p=mod.vtrn, n=mod.vcm_az, bulk=mod.VSS)
    mod.r_vtrp_bleed = pdk_precision_resistor(100e9, p=mod.vtrp, n=mod.vcm_az, bulk=mod.VSS)

    # Main stage1 bias.
    tail_ref_par = _mos_params(core_params.w_tail_ref, core_params.l_tail_ref)
    tail_par = _mos_params(core_params.w_tail, core_params.l_tail)
    mod.m_ibias1_ref = pmos(tail_ref_par)(d=mod.vbp1, g=mod.vbp1, s=mod.VDD, b=mod.VDD)
    mod.r_ibias1_ref = pdk_precision_resistor(core_params.r_stage1_bias, p=mod.vbp1, n=mod.vss_bias1, bulk=mod.VSS)
    mod.m_bias1_en = nmos(_mos_params(4.0, 0.15))(d=mod.vss_bias1, g=mod.D_EN_OA, s=mod.VSS, b=mod.VSS)
    mod.m_ibias1 = pmos(tail_par)(d=mod.ibias1, g=mod.vbp1, s=mod.VDD, b=mod.VDD)
    mod.m_tail1_sw = pmos(_mos_params(core_params.w_tail_sw, core_params.l_tail_sw))(d=mod.tail1, g=mod.enb, s=mod.ibias1, b=mod.VDD)
    mod.m_ibias1_off = pmos(inv_ppar)(d=mod.vbp1, g=mod.D_EN_OA, s=mod.VDD, b=mod.VDD)
    mod.m_ibias1_tail_off = pmos(inv_ppar)(d=mod.ibias1, g=mod.D_EN_OA, s=mod.VDD, b=mod.VDD)

    # Stage1: keep the high-gain drains clean in normal mode.
    # Stored trim is applied as a weak input-bias perturbation instead of a
    # current source directly on vx/ vref.
    mod.xin_main = diffpair_main(INP=mod.vinp_core, INN=mod.vinn_core, OUTP=mod.vx, OUTN=mod.vref, TAIL=mod.tail1, VDD=mod.VDD, VSS=mod.VSS)
    mod.r_trim_inp = pdk_precision_resistor(params.r_trim_inj, p=mod.vtrp, n=mod.vinp_core, bulk=mod.VSS)
    mod.r_trim_inn = pdk_precision_resistor(params.r_trim_inj, p=mod.vtrn, n=mod.vinn_core, bulk=mod.VSS)

    load_par = _mos_params(core_params.w_load, core_params.l_load)
    mod.m_load_ref = nmos(load_par)(d=mod.vref, g=mod.vref, s=mod.VSS, b=mod.VSS)
    mod.m_load_out = nmos(load_par)(d=mod.vx, g=mod.vref, s=mod.VSS, b=mod.VSS)

    # Stage2 copied from the debugged direct-output core baseline.
    stage2_bias_ref_par = _mos_params(core_params.w_stage2_bias_ref, core_params.l_stage2_bias_ref)
    mod.m_ibias2_ref = pmos(stage2_bias_ref_par)(d=mod.ibias2, g=mod.ibias2, s=mod.VDD, b=mod.VDD)
    mod.r_ibias2_ref = pdk_precision_resistor(core_params.r_stage2_bias, p=mod.ibias2, n=mod.vss_bias2, bulk=mod.VSS)
    mod.m_bias2_en = nmos(_mos_params(4.0, 0.15))(d=mod.vss_bias2, g=mod.D_EN_OA, s=mod.VSS, b=mod.VSS)
    mod.m_ibias2_off = pmos(inv_ppar)(d=mod.ibias2, g=mod.D_EN_OA, s=mod.VDD, b=mod.VDD)
    mod.m_stage2_p = pmos(_mos_params(core_params.w_stage2_p, core_params.l_stage2_p))(d=mod.vdrv, g=mod.ibias2, s=mod.VDD, b=mod.VDD)
    mod.m_stage2_n = nmos(_mos_params(core_params.w_stage2_n, core_params.l_stage2_n))(d=mod.vdrv, g=mod.vx, s=mod.VSS, b=mod.VSS)
    mod.m_stage2_off = nmos(inv_npar)(d=mod.vdrv, g=mod.enb, s=mod.VSS, b=mod.VSS)
    # External pin is isolated in calibration and latching, enabled only in inference.
    mod.xsw_vout = tg_out(A=mod.vdrv, B=mod.VOUT, PHI=mod.D_INF_OA, PHIB=mod.infb, VDD=mod.VDD, VSS=mod.VSS)

    mod.cc = pdk_mim_capacitor(core_params.c_comp, p=mod.vx, n=mod.vdrv)
    return mod


def run_structural_checks(params: OpampAzTopParams | None = None):
    params = params or OpampAzTopParams()
    dut = opamp_az_top(params)
    mod = h.elaborate(dut)
    return {
        "generator_call": dut is not None,
        "elaboration": mod is not None,
        "subckt_name": mod.name.startswith("OpampAzTopV3"),
        "contains_input_mux": hasattr(mod, "xsw_inp_ext") and hasattr(mod, "xsw_inp_az"),
        "contains_trim_pair": hasattr(mod, "xin_trim") and hasattr(mod, "m_ibias_trim"),
        "contains_trim_input_bias": hasattr(mod, "r_trim_inp") and hasattr(mod, "r_trim_inn"),
        "contains_hold_caps": hasattr(mod, "caz_p") and hasattr(mod, "caz_n"),
        "contains_output_isolation": hasattr(mod, "xsw_vout"),
        "contains_direct_output_link": hasattr(mod, "xsw_vout") and not hasattr(mod, "vout_core"),
        "contains_legacy_output_path": any(
            hasattr(mod, name)
            for name in ("xout_driver", "xout_stage", "vout_drive_p", "vout_drive_n")
        ),
    }


def elaborate_dut(params: OpampAzTopParams | None = None) -> h.Module:
    return h.elaborate(opamp_az_top(params or OpampAzTopParams()))


def export_spice(path: str | Path, params: OpampAzTopParams | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mod = elaborate_dut(params)
    with path.open("w") as f:
        h.netlist(mod, f, fmt="spice")
    return path


@h.paramclass
class OpampAzHighZTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    i_probe = h.Param(dtype=h.Scalar, desc="External probe current into VOUT in A", default=1e-6)
    r_probe = h.Param(dtype=h.Scalar, desc="External probe resistor from VOUT to VSS in ohm", default=1e6)
    mode_inf = h.Param(dtype=h.Scalar, desc="Inference control voltage", default=0.0)
    mode_az = h.Param(dtype=h.Scalar, desc="Calibration control voltage", default=1.8)
    tstop = h.Param(dtype=h.Scalar, desc="Transient stop time in s", default=2e-6)
    tstep = h.Param(dtype=h.Scalar, desc="Transient step in s", default=20e-9)


def build_highz_test(
    dut_params: OpampAzTopParams,
    tb_params: OpampAzHighZTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
) -> Sim:
    tb_params = tb_params or OpampAzHighZTbParams()
    install = require_sky130_install()
    dut = opamp_az_top(dut_params)

    @h.module
    class Tb:
        VSS = h.Port()
        vinp, vinn, vout, den, daz, dinf, vdd = h.Signals(7)
        vvdd = h.Vdc(dc=tb_params.vdd)(p=vdd, n=VSS)
        vden = h.Vdc(dc=tb_params.vdd)(p=den, n=VSS)
        vdaz = h.Vdc(dc=tb_params.mode_az)(p=daz, n=VSS)
        vdinf = h.Vdc(dc=tb_params.mode_inf)(p=dinf, n=VSS)
        vvinp = h.Vdc(dc=0.0)(p=vinp, n=VSS)
        vvinn = h.Vdc(dc=0.0)(p=vinn, n=VSS)
        iprobe = h.Idc(dc=tb_params.i_probe)(p=vout, n=VSS)
        rprobe = h.Res(r=tb_params.r_probe)(p=vout, n=VSS)
        xdut = dut(VINP=vinp, VINN=vinn, VOUT=vout, D_EN_OA=den, D_AZ_OA=daz, D_INF_OA=dinf, VDD=vdd, VSS=VSS)

    return Sim(
        tb=Tb,
        attrs=[
            Tran(tstop=float(tb_params.tstop), tstep=float(tb_params.tstep)),
            Save("time, v(xtop.vout)"),
            install.include(corner),
        ],
    )


@h.paramclass
class OpampAzHoldTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    vin = h.Param(dtype=h.Scalar, desc="Nominal follower target in V", default=0.9)
    t_az = h.Param(dtype=h.Scalar, desc="Calibration duration in s", default=10e-6)
    t_lat = h.Param(dtype=h.Scalar, desc="Latching duration in s", default=2e-6)
    t_inf = h.Param(dtype=h.Scalar, desc="Inference hold duration in s", default=220e-6)
    tstep = h.Param(dtype=h.Scalar, desc="Transient step in s", default=200e-9)


def build_hold_test(
    dut_params: OpampAzTopParams,
    tb_params: OpampAzHoldTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
) -> Sim:
    tb_params = tb_params or OpampAzHoldTbParams()
    install = require_sky130_install()
    dut = opamp_az_top(dut_params)
    t_az = float(tb_params.t_az)
    t_lat = float(tb_params.t_lat)
    t_inf = float(tb_params.t_inf)
    tstop = t_az + t_lat + t_inf

    @h.module
    class Tb:
        VSS = h.Port()
        vinp, vinn, vout, den, daz, dinf, vdd = h.Signals(7)
        vvdd = h.Vdc(dc=tb_params.vdd)(p=vdd, n=VSS)
        vden = h.Vdc(dc=tb_params.vdd)(p=den, n=VSS)
        # Calibration high, then latching low, inference high.
        vdaz = h.Vpulse(v1=tb_params.vdd, v2=0.0, delay=t_az, rise=20e-9, fall=20e-9, width=tstop, period=2 * tstop)(p=daz, n=VSS)
        vdinf = h.Vpulse(v1=0.0, v2=tb_params.vdd, delay=t_az + t_lat, rise=20e-9, fall=20e-9, width=t_inf, period=2 * tstop)(p=dinf, n=VSS)
        # Direct-output core follower sign: VINP sees the target, VINN sees VOUT.
        vvin = h.Vdc(dc=tb_params.vin)(p=vinp, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinn)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        rload = h.Res(r=1e6)(p=vout, n=VSS)
        xdut = dut(VINP=vinp, VINN=vinn, VOUT=vout, D_EN_OA=den, D_AZ_OA=daz, D_INF_OA=dinf, VDD=vdd, VSS=VSS)

    return Sim(
        tb=Tb,
        attrs=[
            Tran(tstop=tstop, tstep=float(tb_params.tstep)),
            Save("time, v(xtop.vout), v(xtop.xdut.vtrp), v(xtop.xdut.vtrn), v(xtop.xdut.vdrv), v(xtop.daz), v(xtop.dinf)"),
            install.include(corner),
        ],
    )
