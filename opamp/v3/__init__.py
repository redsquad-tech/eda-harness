"""V3 opamp development workspace."""

import warnings

from pydantic.warnings import PydanticDeprecatedSince20

warnings.filterwarnings(
    "ignore",
    category=PydanticDeprecatedSince20,
)

from .frontend_az import FrontendAzSpec as FrontendAzV3Spec, frontend_az as frontend_az_v3
from .opamp_az_top import OpampAzTopParams as OpampAzTopV3Params, OpampAzTopSpec as OpampAzTopV3Spec, opamp_az_top as opamp_az_top_v3
from .opamp_core import OpampCoreParams as OpampCoreV3Params, OpampCoreSpec as OpampCoreV3Spec, opamp_core as opamp_core_v3
from .opamp_ota import opamp_ota as opamp_ota_v3
from .specs import OpampAzV3TargetSpec

__all__ = [
    "FrontendAzV3Spec",
    "OpampAzTopV3Params",
    "OpampAzTopV3Spec",
    "OpampAzV3TargetSpec",
    "OpampCoreV3Params",
    "OpampCoreV3Spec",
    "frontend_az_v3",
    "opamp_az_top_v3",
    "opamp_core_v3",
    "opamp_ota_v3",
]
