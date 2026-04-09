from __future__ import annotations

from dataclasses import asdict, dataclass, fields

from opamp.v3.frontend_az import FrontendAzParams
from opamp.v3.opamp_core import OpampCoreParams


CURRENT_CORE_RC_CASE = "K1_stage2p10"
CURRENT_AZ_RC_CASE = "m4r1_cap300_wswn1p1_wswp1p6_nf2"


@dataclass(frozen=True)
class RcPromotionRecord:
    core_case: str
    az_case: str
    rationale: str


CURRENT_RC_PROMOTION = RcPromotionRecord(
    core_case=CURRENT_CORE_RC_CASE,
    az_case=CURRENT_AZ_RC_CASE,
    rationale=(
        "Current production RC combines the best completed stable core branch "
        "with the best completed mismatch-hardening AZ branch."
    ),
)


def current_core_params() -> OpampCoreParams:
    return OpampCoreParams(
        l_stage2_p=10.0,
    )


def current_frontend_params() -> FrontendAzParams:
    return FrontendAzParams(
        c_az=300e-15,
        r_vcm_top=600.0,
        r_vcm_bot=5.0,
        c_out_p=10e-15,
        c_out_n=0.0,
        w_sw_n=1.1,
        w_sw_p=1.6,
        nf_sw=2,
    )


def current_noise_offset_timing() -> dict[str, float]:
    return {
        "period": 5e-6,
        "dead_time": 0.5e-6,
        "phi1_share": 0.4,
        "phi2_share": 0.2,
        "phi3_share": 0.4,
        "tstop": 60e-6,
        "tstep": 100e-9,
    }


def _serialize_paramclass(obj) -> dict[str, object]:
    serialized: dict[str, object] = {}
    for field in fields(obj):
        value = getattr(obj, field.name)
        if isinstance(value, (str, int, float, bool)) or value is None:
            serialized[field.name] = value
            continue
        try:
            serialized[field.name] = float(value)
        except (TypeError, ValueError):
            serialized[field.name] = str(value)
    return serialized


def current_rc_summary() -> dict[str, object]:
    return {
        "promotion": asdict(CURRENT_RC_PROMOTION),
        "core_params": _serialize_paramclass(current_core_params()),
        "frontend_params": _serialize_paramclass(current_frontend_params()),
        "timing": current_noise_offset_timing(),
    }
