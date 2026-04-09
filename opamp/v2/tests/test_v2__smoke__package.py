from __future__ import annotations

import hdl21 as h

from opamp.v2 import (
    BiasGenV2Params,
    FrontendAzV2Params,
    OpampAzTopV2Params,
    OpampCoreV2Params,
    bias_gen_v2,
    frontend_az_v2,
    opamp_az_top_v2,
    opamp_core_v2,
)
from opamp.v2.tests._helpers import BaseV2Test


class TestV2SmokePackage(BaseV2Test):
    def test_v2_blocks_import_and_elaborate(self) -> None:
        bias = h.elaborate(bias_gen_v2(BiasGenV2Params()))
        frontend = h.elaborate(frontend_az_v2(FrontendAzV2Params()))
        core = h.elaborate(opamp_core_v2(OpampCoreV2Params()))
        top = h.elaborate(opamp_az_top_v2(OpampAzTopV2Params()))

        self.assertIsNotNone(bias)
        self.assertIsNotNone(frontend)
        self.assertIsNotNone(core)
        self.assertIsNotNone(top)


if __name__ == "__main__":
    unittest.main()
