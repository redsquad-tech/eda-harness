from pathlib import Path
from typing import Optional

from hdl21.sim.proto import to_proto
from hdl21.sim.data import Sim as Hdl21Sim
import vlsir.spice_pb2 as vsp
from vlsirtools.netlist.spice import NgspiceNetlister
from vlsirtools.spice.ngspice import NGSpiceSim
from vlsirtools.spice.base import SimResultUnion
from vlsirtools.spice.spice import SimOptions


class CompatibleNgspiceNetlister(NgspiceNetlister):
    """Repository-local ngspice netlister with Save support."""

    @staticmethod
    def _is_zero(value: str) -> bool:
        try:
            return float(value) == 0.0
        except ValueError:
            return value.strip() in {"0", "'0'", "0.0", "'0.0'"}

    def write_save(self, save: vsp.Save) -> None:
        if save.HasField("signal") and save.signal:
            names = [name.strip() for name in save.signal.split(",") if name.strip()]
            if not names:
                raise ValueError(f"Invalid ngspice save target: {save.signal!r}")
            return self.writeln(".save " + " ".join(names))

        if save.mode == vsp.Save.SaveMode.ALL:
            return self.writeln(".save all")

        if save.mode == vsp.Save.SaveMode.NONE:
            return self.writeln(".save none")

        raise NotImplementedError(f"Unsupported ngspice save control: {save}")

    def write_voltage_source_instance(self, pinst, ref) -> None:
        resolved_param_values = self.get_instance_params(pinst, ref.module)

        self.write_instance_name(pinst, ref.spice_type)
        self.write_instance_conns(pinst, ref.module)

        name = ref.module.name.name
        if name == "vdc":
            dc = resolved_param_values.pop("dc")
            self.write(f"+ DC {dc}\n")

            ac = resolved_param_values.pop("ac") if "ac" in resolved_param_values else None
            if ac is not None and not self._is_zero(ac):
                self.write(f"+ AC {ac}\n")
        elif name == "vpulse":
            ordered = []
            aliases = {
                "v1": ("v1",),
                "v2": ("v2",),
                "td": ("td", "delay"),
                "tr": ("tr", "rise"),
                "tf": ("tf", "fall"),
                "tpw": ("tpw", "pw", "width"),
                "tper": ("tper", "per", "period"),
            }
            for label in ("v1", "v2", "td", "tr", "tf", "tpw", "tper"):
                value = None
                for src in aliases[label]:
                    if src in resolved_param_values:
                        value = resolved_param_values.pop(src)
                        break
                if value is None:
                    raise RuntimeError(f"Required parameter `{label}` not specified for {name}")
                ordered.append(value)
            self.write("+ PULSE (" + " ".join(ordered) + ")\n")
        else:
            return super().write_voltage_source_instance(pinst, ref)

        self.write_instance_params(resolved_param_values)
        self.write("\n")


class CompatibleNGSpiceSim(NGSpiceSim):
    """NGSpice simulator state using the repository-local compatible netlister."""

    def write_netlist(self) -> None:
        netlist_file = self.open("netlist.sp", "w")
        netlister = CompatibleNgspiceNetlister(dest=netlist_file)
        netlister.write_sim_input(self.inp)
        netlist_file.flush()
        netlist_file.close()

    @classmethod
    def sim(cls, inp: vsp.SimInput, opts: Optional[SimOptions] = None) -> SimResultUnion:
        return super().sim(inp=inp, opts=opts)


def write_compatible_netlist(inp: vsp.SimInput, path: str | Path) -> Path:
    """Write a ngspice netlist using the repository-local compatible netlister."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        CompatibleNgspiceNetlister(dest=f).write_sim_input(inp)
    return path


def run_compatible_sim(sim: Hdl21Sim, opts: Optional[SimOptions] = None) -> SimResultUnion:
    """Run an HDL21 Sim through the repository-local compatible ngspice path."""
    return CompatibleNGSpiceSim.sim(inp=to_proto(sim), opts=opts)


__all__ = [
    "CompatibleNGSpiceSim",
    "CompatibleNgspiceNetlister",
    "run_compatible_sim",
    "write_compatible_netlist",
]
