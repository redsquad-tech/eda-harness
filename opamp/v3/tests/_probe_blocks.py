from __future__ import annotations

import hdl21 as h

from opamp.v3.opamp_core import (
    OpampCoreParams,
    SharedGateOutputStageParams,
    default_output_driver_params,
    shared_gate_output_stage,
    shared_output_driver,
)
from opamp.v3.tests._helpers import build_debug_core_params


def debug_params(**updates) -> OpampCoreParams:
    return build_debug_core_params(**updates)


def output_driver_probe() -> h.Module:
    driver = shared_output_driver(default_output_driver_params())

    mod = h.Module(name="RcOutputDriverProbe")
    mod.VDRV, mod.VGN, mod.VGP, mod.VDD, mod.VSS = h.Ports(5)
    mod.vgn_int, mod.vgp_int = h.Signals(2)
    mod.vprobe_vgn = h.Vdc(dc=0)(p=mod.vgn_int, n=mod.VGN)
    mod.vprobe_vgp = h.Vdc(dc=0)(p=mod.vgp_int, n=mod.VGP)
    mod.xdrv = driver(VDRV=mod.VDRV, VGN=mod.vgn_int, VGP=mod.vgp_int, VDD=mod.VDD, VSS=mod.VSS)
    return mod


def output_stage_probe(params: OpampCoreParams) -> h.Module:
    stage = shared_gate_output_stage(
        SharedGateOutputStageParams(
            w_n=max(float(params.w_out_n), 1.0),
            l_n=float(params.l_out_n),
            w_p=max(float(params.w_out_n) * 2.0, 1.0),
            l_p=float(params.l_out_n),
        )
    )

    mod = h.Module(name="RcOutputStageProbe")
    mod.VGN, mod.VGP, mod.VOUT, mod.VDD, mod.VSS = h.Ports(5)
    mod.vout_op, mod.vout_on = h.Signals(2)
    mod.vprobe_outp = h.Vdc(dc=0)(p=mod.vout_op, n=mod.VOUT)
    mod.vprobe_outn = h.Vdc(dc=0)(p=mod.vout_on, n=mod.VOUT)
    mod.xstage = stage(VGN=mod.VGN, VGP=mod.VGP, VOUTP=mod.vout_op, VOUTN=mod.vout_on, VDD=mod.VDD, VSS=mod.VSS)
    return mod


def output_path_probe(params: OpampCoreParams) -> h.Module:
    driver = shared_output_driver(default_output_driver_params())
    stage = shared_gate_output_stage(
        SharedGateOutputStageParams(
            w_n=max(float(params.w_out_n), 1.0),
            l_n=float(params.l_out_n),
            w_p=max(float(params.w_out_n) * 2.0, 1.0),
            l_p=float(params.l_out_n),
        )
    )

    mod = h.Module(name="RcOutputPathProbe")
    mod.VDRV, mod.VOUT, mod.VDD, mod.VSS = h.Ports(4)
    mod.vgn, mod.vgp = h.Signals(2)
    mod.vgn_drv, mod.vgp_drv = h.Signals(2)
    mod.vout_op, mod.vout_on = h.Signals(2)
    mod.vprobe_vgn = h.Vdc(dc=0)(p=mod.vgn_drv, n=mod.vgn)
    mod.vprobe_vgp = h.Vdc(dc=0)(p=mod.vgp_drv, n=mod.vgp)
    mod.vprobe_outp = h.Vdc(dc=0)(p=mod.vout_op, n=mod.VOUT)
    mod.vprobe_outn = h.Vdc(dc=0)(p=mod.vout_on, n=mod.VOUT)
    mod.xdrv = driver(VDRV=mod.VDRV, VGN=mod.vgn_drv, VGP=mod.vgp_drv, VDD=mod.VDD, VSS=mod.VSS)
    mod.xstage = stage(VGN=mod.vgn, VGP=mod.vgp, VOUTP=mod.vout_op, VOUTN=mod.vout_on, VDD=mod.VDD, VSS=mod.VSS)
    return mod
