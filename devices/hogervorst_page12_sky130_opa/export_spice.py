from io import StringIO
from pathlib import Path

import hdl21 as h

from .common import init_sky130_install
from .opamp import NeuronOaParams, compile_for_sky130, neuron_core_oa_sky130


def export_spice(output_path: Path | None = None) -> Path:
    output_path = output_path or Path(__file__).resolve().with_name("neuron_core_oa_sky130.spice")
    init_sky130_install()
    dut = h.elaborate(neuron_core_oa_sky130(NeuronOaParams()))
    compile_for_sky130(dut)
    stream = StringIO()
    h.netlist(dut, stream, fmt="spice")
    output_path.write_text(stream.getvalue(), encoding="utf-8")
    return output_path


def main() -> int:
    path = export_spice()
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
