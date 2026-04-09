from dataclasses import dataclass

import hdl21 as h


VERIFICATION_PLAN = {
    "structural": {
        "specification_aspect": "generator/export contract",
        "category": "structural",
        "test_name": "run_structural_checks",
        "analysis_type": "generator/elaboration/export",
        "extracted_metrics": ["generator_call", "elaboration", "subckt_name"],
        "pass_fail_rule": "all structural checks pass",
        "required_corners": [],
        "required_operating_conditions": [],
        "monte_carlo_required": False,
    },
}


@dataclass(frozen=True)
class FrontendAzSpec:
    name: str = "frontend_az_v3"
    purpose: str = "Provide the isolated AZ interface for the v3 branch."
    component_class: str = "architecture branch"
    pins: tuple[str, ...] = ("VINP", "VINN", "VOUTP", "VOUTN", "PHI1", "PHI2", "VDD", "VSS")


@h.paramclass
class FrontendAzParams:
    interface_style = h.Param(dtype=str, desc="Top-level AZ interface metadata", default="two_phase_external")


@h.generator
def frontend_az(params: FrontendAzParams) -> h.Module:
    mod = h.Module(name="FrontendAzV3")
    mod.VINP, mod.VINN, mod.VOUTP, mod.VOUTN, mod.PHI1, mod.PHI2, mod.VDD, mod.VSS = h.Ports(8)
    mod.rp = h.Res(r=1e-3)(p=mod.VINP, n=mod.VOUTP)
    mod.rn = h.Res(r=1e-3)(p=mod.VINN, n=mod.VOUTN)
    return mod


def run_structural_checks(params: FrontendAzParams | None = None):
    params = params or FrontendAzParams()
    dut = frontend_az(params)
    mod = h.elaborate(dut)
    return {
        "generator_call": dut is not None,
        "elaboration": mod is not None,
        "subckt_name": mod.name.startswith("FrontendAzV3"),
    }
