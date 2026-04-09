"""V2 opamp development workspace.

This package is intentionally isolated from the baseline `components/` tree.
Higher-level opamp blocks live here and may depend only on low-level reusable
generators from `components/` such as primitive switch or diffpair cells.
"""

from .architecture import ARCHITECTURE_EXPERIMENT, BLOCK_ROLES, TEST_MATRIX
from .bias_gen import BiasGenParams as BiasGenV2Params, BiasGenSpec as BiasGenV2Spec, bias_gen as bias_gen_v2
from .frontend_az import FrontendAzParams as FrontendAzV2Params, FrontendAzSpec as FrontendAzV2Spec, frontend_az as frontend_az_v2
from .freq_comp import FreqCompParams as FreqCompV2Params, FreqCompSpec as FreqCompV2Spec, freq_comp as freq_comp_v2
from .gm_stage import SecondStageParams as GmStageV2Params, SecondStageSpec as GmStageV2Spec, second_stage as gm_stage_v2
from .input_stage import GainStageParams as InputStageV2Params, GainStageSpec as InputStageV2Spec, gain_stage as input_stage_v2
from .opamp_az_top import OpampAzTopParams as OpampAzTopV2Params, OpampAzTopSpec as OpampAzTopV2Spec, opamp_az_top as opamp_az_top_v2
from .opamp_core import OpampCoreParams as OpampCoreV2Params, OpampCoreSpec as OpampCoreV2Spec, opamp_core as opamp_core_v2
from .specs import OpampAzV2TargetSpec

__all__ = [
    "ARCHITECTURE_EXPERIMENT",
    "BLOCK_ROLES",
    "TEST_MATRIX",
    "BiasGenV2Params",
    "BiasGenV2Spec",
    "FrontendAzV2Params",
    "FrontendAzV2Spec",
    "FreqCompV2Params",
    "FreqCompV2Spec",
    "GmStageV2Params",
    "GmStageV2Spec",
    "InputStageV2Params",
    "InputStageV2Spec",
    "OpampAzTopV2Params",
    "OpampAzTopV2Spec",
    "OpampAzV2TargetSpec",
    "OpampCoreV2Params",
    "OpampCoreV2Spec",
    "bias_gen_v2",
    "frontend_az_v2",
    "freq_comp_v2",
    "gm_stage_v2",
    "input_stage_v2",
    "opamp_az_top_v2",
    "opamp_core_v2",
]
