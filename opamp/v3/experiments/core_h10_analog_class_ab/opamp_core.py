import hdl21 as h
import sky130_hdl21

from components.diffpair_p import DiffpairPParams, diffpair_p
from opamp.v3.opamp_core import OpampCoreParams, _mos_params
from opamp.v3.pdk_passives import pdk_mim_capacitor, pdk_resistor


@h.generator
def opamp_core(params: OpampCoreParams) -> h.Module:
    pmos = sky130_hdl21.primitives.PMOS_1p8V_STD
    nmos = sky130_hdl21.primitives.NMOS_1p8V_STD

    diffpair = diffpair_p(DiffpairPParams(w_in=params.w_in, l_in=params.l_in, nf_in=1, m_in=1))

    mod = h.Module(name="OpampCoreV3AnalogClassAB")
    mod.VINP, mod.VINN, mod.VOUT, mod.EN, mod.VDD, mod.VSS = h.Ports(6)
    mod.vx, mod.vref, mod.vdrv = h.Signals(3)
    mod.ibias1, mod.ibias2 = h.Signals(2)
    mod.tail1 = h.Signal(name="tail1")
    mod.vbp1 = h.Signal(name="vbp1")
    mod.vinp_int = h.Signal(name="vinp_int")
    mod.vinn_int = h.Signal(name="vinn_int")
    mod.vss_bias1 = h.Signal(name="vss_bias1")
    mod.vss_bias2 = h.Signal(name="vss_bias2")
    mod.enb = h.Signal(name="enb")
    mod.vbuf = h.Signal(name="vbuf")
    mod.vgn = h.Signal(name="vgn")
    mod.vgp = h.Signal(name="vgp")

    inv_npar = _mos_params(1.0, 0.15)
    inv_ppar = _mos_params(2.0, 0.15)
    vgn_ppar = _mos_params(0.8, 0.15)
    vgp_npar = _mos_params(0.8, 0.15)

    mod.m_enb_p = pmos(inv_ppar)(d=mod.enb, g=mod.EN, s=mod.VDD, b=mod.VDD)
    mod.m_enb_n = nmos(inv_npar)(d=mod.enb, g=mod.EN, s=mod.VSS, b=mod.VSS)

    tail_ref_par = _mos_params(params.w_tail_ref, params.l_tail_ref)
    tail_par = _mos_params(params.w_tail, params.l_tail)
    mod.m_ibias1_ref = pmos(tail_ref_par)(d=mod.vbp1, g=mod.vbp1, s=mod.VDD, b=mod.VDD)
    mod.r_ibias1_ref = pdk_resistor(params.r_stage1_bias, p=mod.vbp1, n=mod.vss_bias1, bulk=mod.VSS)
    mod.m_bias1_en = nmos(_mos_params(4.0, 0.15))(d=mod.vss_bias1, g=mod.EN, s=mod.VSS, b=mod.VSS)
    mod.m_ibias1 = pmos(tail_par)(d=mod.ibias1, g=mod.vbp1, s=mod.VDD, b=mod.VDD)
    mod.m_tail1_sw = pmos(_mos_params(params.w_tail_sw, params.l_tail_sw))(d=mod.tail1, g=mod.enb, s=mod.ibias1, b=mod.VDD)
    mod.m_ibias1_off = pmos(inv_ppar)(d=mod.vbp1, g=mod.EN, s=mod.VDD, b=mod.VDD)
    mod.m_ibias1_tail_off = pmos(inv_ppar)(d=mod.ibias1, g=mod.EN, s=mod.VDD, b=mod.VDD)
    mod.m_tail1_off = pmos(inv_ppar)(d=mod.tail1, g=mod.EN, s=mod.VDD, b=mod.VDD)

    tg_npar = _mos_params(4.0, 0.15)
    tg_ppar = _mos_params(4.0, 0.15)
    mod.m_vinp_tg_n = nmos(tg_npar)(d=mod.vinp_int, g=mod.EN, s=mod.VINP, b=mod.VSS)
    mod.m_vinp_tg_p = pmos(tg_ppar)(d=mod.vinp_int, g=mod.enb, s=mod.VINP, b=mod.VDD)
    mod.m_vinn_tg_n = nmos(tg_npar)(d=mod.vinn_int, g=mod.EN, s=mod.VINN, b=mod.VSS)
    mod.m_vinn_tg_p = pmos(tg_ppar)(d=mod.vinn_int, g=mod.enb, s=mod.VINN, b=mod.VDD)
    mod.m_vinp_off = pmos(inv_ppar)(d=mod.vinp_int, g=mod.EN, s=mod.VDD, b=mod.VDD)
    mod.m_vinn_off = pmos(inv_ppar)(d=mod.vinn_int, g=mod.EN, s=mod.VDD, b=mod.VDD)

    if params.debug_current_probes:
        mod.vdrv_s2p = h.Signal(name="vdrv_s2p")
        mod.vdrv_s2n = h.Signal(name="vdrv_s2n")
        mod.vbuf_drv = h.Signal(name="vbuf_drv")
        mod.vgn_drv = h.Signal(name="vgn_drv")
        mod.vgp_drv = h.Signal(name="vgp_drv")
        mod.vout_op = h.Signal(name="vout_op")
        mod.vout_on = h.Signal(name="vout_on")
        mod.vprobe_s2p = h.Vdc(dc=0)(p=mod.vdrv_s2p, n=mod.vdrv)
        mod.vprobe_s2n = h.Vdc(dc=0)(p=mod.vdrv_s2n, n=mod.vdrv)
        mod.vprobe_vbuf = h.Vdc(dc=0)(p=mod.vbuf_drv, n=mod.vbuf)
        mod.vprobe_vgn = h.Vdc(dc=0)(p=mod.vgn_drv, n=mod.vgn)
        mod.vprobe_vgp = h.Vdc(dc=0)(p=mod.vgp_drv, n=mod.vgp)
        mod.vprobe_outp = h.Vdc(dc=0)(p=mod.vout_op, n=mod.VOUT)
        mod.vprobe_outn = h.Vdc(dc=0)(p=mod.vout_on, n=mod.VOUT)
        vdrv_s2p = mod.vdrv_s2p
        vdrv_s2n = mod.vdrv_s2n
        vbuf_drv = mod.vbuf_drv
        vgn_drv = mod.vgn_drv
        vgp_drv = mod.vgp_drv
        vout_op = mod.vout_op
        vout_on = mod.vout_on
    else:
        vdrv_s2p = mod.vdrv
        vdrv_s2n = mod.vdrv
        vbuf_drv = mod.vbuf
        vgn_drv = mod.vgn
        vgp_drv = mod.vgp
        vout_op = mod.VOUT
        vout_on = mod.VOUT

    mod.xin = diffpair(INP=mod.vinp_int, INN=mod.vinn_int, OUTP=mod.vx, OUTN=mod.vref, TAIL=mod.tail1, VDD=mod.VDD, VSS=mod.VSS)
    load_par = _mos_params(params.w_load, params.l_load)
    mod.m_load_ref = nmos(load_par)(d=mod.vref, g=mod.vref, s=mod.VSS, b=mod.VSS)
    mod.m_load_out = nmos(load_par)(d=mod.vx, g=mod.vref, s=mod.VSS, b=mod.VSS)

    stage2_bias_ref_par = _mos_params(params.w_stage2_bias_ref, params.l_stage2_bias_ref)
    mod.m_ibias2_ref = pmos(stage2_bias_ref_par)(d=mod.ibias2, g=mod.ibias2, s=mod.VDD, b=mod.VDD)
    mod.r_ibias2_ref = pdk_resistor(params.r_stage2_bias, p=mod.ibias2, n=mod.vss_bias2, bulk=mod.VSS)
    mod.m_bias2_en = nmos(_mos_params(4.0, 0.15))(d=mod.vss_bias2, g=mod.EN, s=mod.VSS, b=mod.VSS)
    mod.m_ibias2_off = pmos(inv_ppar)(d=mod.ibias2, g=mod.EN, s=mod.VDD, b=mod.VDD)

    mod.m_stage2_p = pmos(_mos_params(params.w_stage2_p, params.l_stage2_p))(d=vdrv_s2p, g=mod.ibias2, s=mod.VDD, b=mod.VDD)
    mod.m_stage2_n = nmos(_mos_params(params.w_stage2_n, params.l_stage2_n))(d=vdrv_s2n, g=mod.vx, s=mod.VSS, b=mod.VSS)
    mod.m_stage2_off = nmos(inv_npar)(d=mod.vdrv, g=mod.enb, s=mod.VSS, b=mod.VSS)

    # Internal inverter remains only as a sign-probe node for diagnostics.
    mod.m_buf_p = pmos(inv_ppar)(d=vbuf_drv, g=mod.vdrv, s=mod.VDD, b=mod.VDD)
    mod.m_buf_n = nmos(inv_npar)(d=vbuf_drv, g=mod.vdrv, s=mod.VSS, b=mod.VSS)

    # Analog class-AB gate drivers.
    # vgn is driven above vdrv through a PMOS source-follower-like branch.
    # vgp is driven below vdrv through an NMOS source-follower-like branch.
    mod.r_vgn_pulldown = pdk_resistor(150e3, p=mod.vgn, n=mod.VSS, bulk=mod.VSS)
    mod.r_vgp_pullup = pdk_resistor(150e3, p=mod.VDD, n=mod.vgp, bulk=mod.VSS)
    mod.m_vgn_p = pmos(vgn_ppar)(d=mod.VSS, g=mod.vdrv, s=vgn_drv, b=mod.VDD)
    mod.m_vgp_n = nmos(vgp_npar)(d=mod.VDD, g=mod.vdrv, s=vgp_drv, b=mod.VSS)

    mod.m_out_p = pmos(_mos_params(max(float(params.w_out_n) * 2.0, 1.0), float(params.l_out_n)))(d=vout_op, g=mod.vgp, s=mod.VDD, b=mod.VDD)
    mod.m_out_n = nmos(_mos_params(max(float(params.w_out_n), 1.0), float(params.l_out_n)))(d=vout_on, g=mod.vgn, s=mod.VSS, b=mod.VSS)

    mod.cc = pdk_mim_capacitor(params.c_comp, p=mod.vx, n=mod.vdrv)
    return mod
