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
        "extracted_metrics": ["generator_call", "elaboration", "subckt_name", "contains_frontend", "contains_core"],
        "pass_fail_rule": "all structural checks pass",
        "required_corners": [],
        "required_operating_conditions": [],
        "monte_carlo_required": False,
    },
}


@dataclass(frozen=True)
class OpampAzTopSpec:
    name: str = "opamp_az_top_v3"
    purpose: str = "Compose the native v3 AZ front end and v3 static core."
    component_class: str = "main-branch integrated device"
    pins: tuple[str, ...] = ("VINP", "VINN", "VOUT", "EN", "PHI1", "PHI1B", "PHI2", "PHI2B", "PHI3", "PHI3B", "VDD", "VSS")


@h.paramclass
class OpampAzTopParams:
    frontend_az_params = h.Param(dtype=FrontendAzParams, desc="Frontend AZ parameters", default=FrontendAzParams())
    opamp_core_params = h.Param(dtype=OpampCoreParams, desc="Core parameters", default=OpampCoreParams())


@h.generator
def opamp_az_top(params: OpampAzTopParams) -> h.Module:
    front = frontend_az(params.frontend_az_params)
    core = opamp_core(params.opamp_core_params)

    mod = h.Module(name="OpampAzTopV3")
    mod.VINP, mod.VINN, mod.VOUT, mod.EN, mod.PHI1, mod.PHI1B, mod.PHI2, mod.PHI2B, mod.PHI3, mod.PHI3B, mod.VDD, mod.VSS = h.Ports(12)
    mod.vcorep, mod.vcoren = h.Signals(2)
    mod.xfront = front(
        VINP=mod.VINP,
        VINN=mod.VINN,
        VOFF=mod.VOUT,
        VXP=mod.vcorep,
        VXN=mod.vcoren,
        PHI1=mod.PHI1,
        PHI1B=mod.PHI1B,
        PHI2=mod.PHI2,
        PHI2B=mod.PHI2B,
        PHI3=mod.PHI3,
        PHI3B=mod.PHI3B,
        VDD=mod.VDD,
        VSS=mod.VSS,
    )
    mod.xcore = core(VINP=mod.vcorep, VINN=mod.vcoren, VOUT=mod.VOUT, EN=mod.EN, VDD=mod.VDD, VSS=mod.VSS)
    return mod


def run_structural_checks(params: OpampAzTopParams | None = None):
    params = params or OpampAzTopParams()
    dut = opamp_az_top(params)
    mod = h.elaborate(dut)
    return {
        "generator_call": dut is not None,
        "elaboration": mod is not None,
        "subckt_name": mod.name.startswith("OpampAzTopV3"),
        "contains_frontend": hasattr(mod, "xfront"),
        "contains_core": hasattr(mod, "xcore"),
    }
