from io import StringIO

import hdl21 as h

from opamp.v4.opamp import NeuronOaParams, compile_for_sky130, neuron_core_oa_sky130
from opamp.v4.tests._helpers import BaseV4Test


class TestV4SmokePackage(BaseV4Test):
    def test_v4_import_elaborate_and_compile(self) -> None:
        dut = neuron_core_oa_sky130(NeuronOaParams())
        elaborated = h.elaborate(dut)
        compile_for_sky130(elaborated)

        stream = StringIO()
        h.netlist(elaborated, stream, fmt="spice")
        text = stream.getvalue()

        self.assertIsNotNone(elaborated)
        self.assertIn(".SUBCKT NeuronCoreOaSky130", text)
        self.assertIn("sky130_fd_pr__nfet_01v8", text)
        self.assertIn("sky130_fd_pr__pfet_01v8", text)
