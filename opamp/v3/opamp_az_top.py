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
    SharedGateOutputStageParams,
    default_output_driver_params,
    shared_gate_output_stage,
    shared_output_driver,
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
            "contains_hold_caps",
            "contains_output_isolation",
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
    purpose: str = "Foreground auto-zero wrapper around the v3 core using input muxing, weak trim injection in stage1, and held correction in inference."
    component_class: str = "integrated auto-zero top"
    pins: tuple[str, ...] = ("VINP", "VINN", "VOUT", "D_EN_OA", "D_AZ_OA", "D_INF_OA", "VDD", "VSS")


def _mos_params(w: h.Scalar, l: h.Scalar, nf: int = 1, mult: int = 1):
    return sky130_hdl21.Sky130MosParams(w=w, l=l, nf=nf, mult=mult)


def _default_ngspice_options(test_name: str) -> SimOptions:
    return SimOptions(simulator=SupportedSimulators.NGSPICE, rundir=f"./tmp/{test_name}")


@h.paramclass
class OpampAzTopParams:
    opamp_core_params = h.Param(dtype=OpampCoreParams, desc="Core-derived sizing baseline", default=OpampCoreParams())
    c_az = h.Param(dtype=h.Scalar, desc="Held correction capacitance per side in F", default=1e-12)
    vcm_az = h.Param(dtype=h.Scalar, desc="Internal auto-zero common-mode reference in V", default=0.45)
    r_vdrv_ref_top = h.Param(dtype=h.Scalar, desc="Top resistor for internal VDRV_Q replica in ohm", default=2.4e6)
    r_vdrv_ref_bot = h.Param(dtype=h.Scalar, desc="Bottom resistor for internal VDRV_Q replica in ohm", default=1.0e6)
    w_trim_in = h.Param(dtype=h.Scalar, desc="Weak trim-pair PMOS width in um", default=0.5)
    l_trim_in = h.Param(dtype=h.Scalar, desc="Weak trim-pair PMOS length in um", default=12.0)
    w_trim_ref = h.Param(dtype=h.Scalar, desc="Trim-tail PMOS reference width in um", default=0.5)
    l_trim_ref = h.Param(dtype=h.Scalar, desc="Trim-tail PMOS reference length in um", default=12.0)
    w_trim_tail = h.Param(dtype=h.Scalar, desc="Trim-tail PMOS mirror width in um", default=0.5)
    l_trim_tail = h.Param(dtype=h.Scalar, desc="Trim-tail PMOS mirror length in um", default=12.0)
    r_trim_bias = h.Param(dtype=h.Scalar, desc="Trim-tail PMOS reference resistor in ohm", default=2e9)
    w_sw_n = h.Param(dtype=h.Scalar, desc="MUX/hold NMOS switch width in um", default=1.0)
    w_sw_p = h.Param(dtype=h.Scalar, desc="MUX/hold PMOS switch width in um", default=1.6)
    l_sw = h.Param(dtype=h.Scalar, desc="MUX/hold switch length in um", default=0.15)
    w_out_sw_n = h.Param(dtype=h.Scalar, desc="Output-isolation NMOS switch width in um", default=8.0)
    w_out_sw_p = h.Param(dtype=h.Scalar, desc="Output-isolation PMOS switch width in um", default=12.0)
    l_out_sw = h.Param(dtype=h.Scalar, desc="Output-isolation switch length in um", default=0.15)


@h.generator
def opamp_az_top(params: OpampAzTopParams) -> h.Module:
    pmos = sky130_hdl21.primitives.PMOS_1p8V_STD
    nmos = sky130_hdl21.primitives.NMOS_1p8V_STD

    core_params = params.opamp_core_params
    diffpair_main = diffpair_p(DiffpairPParams(w_in=core_params.w_in, l_in=core_params.l_in, nf_in=1, m_in=1))
    diffpair_trim = diffpair_p(DiffpairPParams(w_in=params.w_trim_in, l_in=params.l_trim_in, nf_in=1, m_in=1))
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
    out_driver = shared_output_driver(
        default_output_driver_params(
            r_vgn_from_vdrv=float(core_params.r_outdrv_vgn_from_vdrv),
            r_vgp_from_vdrv=float(core_params.r_outdrv_vgp_from_vdrv),
        )
    )
    out_stage = shared_gate_output_stage(
        SharedGateOutputStageParams(
            w_n=max(float(core_params.w_out_n), 1.0),
            l_n=float(core_params.l_out_n),
            w_p=max(float(core_params.w_out_n) * 2.0, 1.0),
            l_p=float(core_params.l_out_n),
        )
    )

    mod = h.Module(name="OpampAzTopV3")
    mod.VINP, mod.VINN, mod.VOUT, mod.D_EN_OA, mod.D_AZ_OA, mod.D_INF_OA, mod.VDD, mod.VSS = h.Ports(8)

    # Mode-control complements.
    mod.enb, mod.azb, mod.infb = h.Signals(3)
    inv_npar = _mos_params(1.0, 0.15)
    inv_ppar = _mos_params(2.0, 0.15)
    mod.m_enb_p = pmos(inv_ppar)(d=mod.enb, g=mod.D_EN_OA, s=mod.VDD, b=mod.VDD)
    mod.m_enb_n = nmos(inv_npar)(d=mod.enb, g=mod.D_EN_OA, s=mod.VSS, b=mod.VSS)
    mod.m_azb_p = pmos(inv_ppar)(d=mod.azb, g=mod.D_AZ_OA, s=mod.VDD, b=mod.VDD)
    mod.m_azb_n = nmos(inv_npar)(d=mod.azb, g=mod.D_AZ_OA, s=mod.VSS, b=mod.VSS)
    mod.m_infb_p = pmos(inv_ppar)(d=mod.infb, g=mod.D_INF_OA, s=mod.VDD, b=mod.VDD)
    mod.m_infb_n = nmos(inv_npar)(d=mod.infb, g=mod.D_INF_OA, s=mod.VSS, b=mod.VSS)

    # Internal references and held trim nodes.
    mod.vcm_az = h.Signal(name="vcm_az")
    mod.vdrv_qref = h.Signal(name="vdrv_qref")
    mod.vtrp = h.Signal(name="vtrp")
    mod.vtrn = h.Signal(name="vtrn")
    mod.vinp_core = h.Signal(name="vinp_core")
    mod.vinn_core = h.Signal(name="vinn_core")
    mod.vout_core = h.Signal(name="vout_core")
    mod.vout_drive_p = h.Signal(name="vout_drive_p")
    mod.vout_drive_n = h.Signal(name="vout_drive_n")
    mod.vx, mod.vref, mod.vdrv = h.Signals(3)
    mod.ibias1, mod.ibias2, mod.ibias_trim = h.Signals(3)
    mod.tail1, mod.tail_trim = h.Signals(2)
    mod.vbp1, mod.vbp_trim = h.Signals(2)
    mod.vss_bias1, mod.vss_bias2, mod.vss_bias_trim = h.Signals(3)
    mod.vgn, mod.vgp = h.Signals(2)

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

    # Held trim loop: in AZ mode, VTRP tracks VDRV while VTRN tracks VDRV_QREF.
    # In latch and inference these nodes float only on the AZ storage capacitors.
    mod.xsw_trim_track_p = tg_small(A=mod.vdrv, B=mod.vtrp, PHI=mod.D_AZ_OA, PHIB=mod.azb, VDD=mod.VDD, VSS=mod.VSS)
    mod.xsw_trim_track_n = tg_small(A=mod.vdrv_qref, B=mod.vtrn, PHI=mod.D_AZ_OA, PHIB=mod.azb, VDD=mod.VDD, VSS=mod.VSS)
    mod.caz_n = pdk_mim_capacitor(params.c_az, p=mod.vtrn, n=mod.VSS)
    mod.caz_p = pdk_mim_capacitor(params.c_az, p=mod.vtrp, n=mod.VSS)
    mod.r_vtrn_bleed = pdk_precision_resistor(1e9, p=mod.vtrn, n=mod.vdrv_qref, bulk=mod.VSS)
    mod.r_vtrp_bleed = pdk_precision_resistor(1e9, p=mod.vtrp, n=mod.vdrv_qref, bulk=mod.VSS)

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

    # Weak trim-tail bias. Separate from the main signal path, but left enabled in AZ and inference.
    trim_ref_par = _mos_params(params.w_trim_ref, params.l_trim_ref)
    trim_tail_par = _mos_params(params.w_trim_tail, params.l_trim_tail)
    mod.m_ibias_trim_ref = pmos(trim_ref_par)(d=mod.vbp_trim, g=mod.vbp_trim, s=mod.VDD, b=mod.VDD)
    mod.r_ibias_trim_ref = pdk_precision_resistor(params.r_trim_bias, p=mod.vbp_trim, n=mod.vss_bias_trim, bulk=mod.VSS)
    mod.m_bias_trim_en = nmos(_mos_params(2.0, 0.15))(d=mod.vss_bias_trim, g=mod.D_EN_OA, s=mod.VSS, b=mod.VSS)
    mod.m_ibias_trim = pmos(trim_tail_par)(d=mod.ibias_trim, g=mod.vbp_trim, s=mod.VDD, b=mod.VDD)
    mod.m_trim_tail_sw = pmos(_mos_params(2.0, 0.5))(d=mod.tail_trim, g=mod.enb, s=mod.ibias_trim, b=mod.VDD)
    mod.m_ibias_trim_off = pmos(inv_ppar)(d=mod.vbp_trim, g=mod.D_EN_OA, s=mod.VDD, b=mod.VDD)

    # Stage1: main pair plus weak trim pair injecting into the same drains.
    mod.xin_main = diffpair_main(INP=mod.vinp_core, INN=mod.vinn_core, OUTP=mod.vx, OUTN=mod.vref, TAIL=mod.tail1, VDD=mod.VDD, VSS=mod.VSS)
    mod.xin_trim = diffpair_trim(INP=mod.vtrp, INN=mod.vtrn, OUTP=mod.vx, OUTN=mod.vref, TAIL=mod.tail_trim, VDD=mod.VDD, VSS=mod.VSS)

    load_par = _mos_params(core_params.w_load, core_params.l_load)
    mod.m_load_ref = nmos(load_par)(d=mod.vref, g=mod.vref, s=mod.VSS, b=mod.VSS)
    mod.m_load_out = nmos(load_par)(d=mod.vx, g=mod.vref, s=mod.VSS, b=mod.VSS)

    # Stage2 and output path copied from the debugged core baseline.
    stage2_bias_ref_par = _mos_params(core_params.w_stage2_bias_ref, core_params.l_stage2_bias_ref)
    mod.m_ibias2_ref = pmos(stage2_bias_ref_par)(d=mod.ibias2, g=mod.ibias2, s=mod.VDD, b=mod.VDD)
    mod.r_ibias2_ref = pdk_precision_resistor(core_params.r_stage2_bias, p=mod.ibias2, n=mod.vss_bias2, bulk=mod.VSS)
    mod.m_bias2_en = nmos(_mos_params(4.0, 0.15))(d=mod.vss_bias2, g=mod.D_EN_OA, s=mod.VSS, b=mod.VSS)
    mod.m_ibias2_off = pmos(inv_ppar)(d=mod.ibias2, g=mod.D_EN_OA, s=mod.VDD, b=mod.VDD)
    mod.m_stage2_p = pmos(_mos_params(core_params.w_stage2_p, core_params.l_stage2_p))(d=mod.vdrv, g=mod.ibias2, s=mod.VDD, b=mod.VDD)
    mod.m_stage2_n = nmos(_mos_params(core_params.w_stage2_n, core_params.l_stage2_n))(d=mod.vdrv, g=mod.vx, s=mod.VSS, b=mod.VSS)
    mod.m_stage2_off = nmos(inv_npar)(d=mod.vdrv, g=mod.enb, s=mod.VSS, b=mod.VSS)

    mod.xout_driver = out_driver(VDRV=mod.vdrv, VGN=mod.vgn, VGP=mod.vgp, VDD=mod.VDD, VSS=mod.VSS)
    mod.xout_stage = out_stage(VGN=mod.vgn, VGP=mod.vgp, VOUTP=mod.vout_drive_p, VOUTN=mod.vout_drive_n, VDD=mod.VDD, VSS=mod.VSS)
    mod.r_vout_core_merge_p = h.Res(r=1e-3)(p=mod.vout_drive_p, n=mod.vout_core)
    mod.r_vout_core_merge_n = h.Res(r=1e-3)(p=mod.vout_drive_n, n=mod.vout_core)
    mod.r_vout_core_bleed = pdk_precision_resistor(1e9, p=mod.vout_core, n=mod.VSS, bulk=mod.VSS)

    # External pin is isolated in calibration and latching, enabled only in inference.
    mod.xsw_vout = tg_out(A=mod.vout_core, B=mod.VOUT, PHI=mod.D_INF_OA, PHIB=mod.infb, VDD=mod.VDD, VSS=mod.VSS)

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
        "contains_hold_caps": hasattr(mod, "caz_p") and hasattr(mod, "caz_n"),
        "contains_output_isolation": hasattr(mod, "xsw_vout"),
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

    return Sim(tb=Tb, attrs=[Op(), Save(SaveMode.ALL), install.include(corner)])


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
        # Negative-feedback hookup for the current core sign: VINN sees the target, VINP sees VOUT.
        vvin = h.Vdc(dc=tb_params.vin)(p=vinn, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinp)
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
