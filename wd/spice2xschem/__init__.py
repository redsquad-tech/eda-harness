#!/usr/bin/env python3
"""
SPICE to xschem (.sch/.sym) generator for Sky130.

The generator parses .subckt blocks from a SPICE netlist and creates:
  - one <subckt>.sch per local subcircuit
  - one <subckt>.sym per local subcircuit
  - fallback <cell>.sym files for unresolved external cells

Generated xschem files use the real file format primitives:
  - symbols / component instances: C
  - wires: N
  - rectangles: B
  - lines: L
  - text: T
  - global properties: K/G/V/S/E
"""

from __future__ import annotations

import argparse
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from statistics import median
from typing import Optional


VERSION_LINE = "v {xschem version=3.4.7 file_version=1.2}"
XSCHEM_PROPS = ["G {}", "K {}", "V {}", "S {}", "E {}"]
GRID = 20

PIN_ATTR_RE = re.compile(r"(\w+)=((?:\"[^\"]*\")|(?:\S+))")
PIN_ORDER_HINTS = {
    "m": 4,
    "q": 4,
    "d": 3,
    "j": 3,
    "r": 3,
    "c": 3,
    "l": 3,
    "v": 3,
    "i": 3,
}
NUMERIC_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?[a-zA-Z]*$")


def snap(value: float, grid: int = GRID) -> int:
    return int(round(value / grid) * grid)


def xescape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def quote_attr(value: str) -> str:
    if value == "":
        return '""'
    if any(ch.isspace() for ch in value) or '"' in value:
        return '"' + value.replace('"', '\\"') + '"'
    return value


def sanitize_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.+-]+", "_", name)


def relsym(path: str, base_dir: str) -> str:
    rel = os.path.relpath(path, base_dir)
    return rel.replace(os.sep, "/")


def direction_to_xschem(direction: str) -> str:
    direction = (direction or "inout").lower()
    if direction in {"input", "in"}:
        return "in"
    if direction in {"output", "out"}:
        return "out"
    return "inout"


def port_kind(name: str, direction: str) -> str:
    upper = name.upper()
    dir_norm = direction_to_xschem(direction)
    if any(token in upper for token in ("VDD", "VPWR", "AVDD", "DVDD", "VCC")):
        return "power"
    if any(token in upper for token in ("VSS", "VGND", "AVSS", "DVSS", "GND")):
        return "ground"
    if dir_norm == "in":
        return "input"
    if dir_norm == "out":
        return "output"
    return "inout"


@dataclass
class Port:
    name: str
    direction: str = "inout"


@dataclass
class Instance:
    name: str
    cell: str
    pins: list[str]
    prefix: str
    params: list[str] = field(default_factory=list)


@dataclass
class Subckt:
    name: str
    ports: list[Port]
    instances: list[Instance] = field(default_factory=list)


@dataclass
class PinDef:
    name: str
    x: int
    y: int
    direction: str = "inout"
    order: int = 0


@dataclass
class SymbolSpec:
    kind: str
    ref: str
    path: Optional[str]
    pins: list[PinDef]
    width: int
    height: int


class SpiceParser:
    def __init__(self) -> None:
        self.subckts: dict[str, Subckt] = {}
        self.includes: list[str] = []
        self.input_dir: str = "."

    def parse_file(self, filepath: str) -> dict[str, Subckt]:
        self.subckts = {}
        self.includes = []
        self.input_dir = os.path.dirname(os.path.abspath(filepath)) or "."
        with open(filepath, "r", encoding="utf-8") as fh:
            logical_lines = self._logical_lines(fh.readlines())

        i = 0
        while i < len(logical_lines):
            raw = logical_lines[i]
            line = raw.strip()
            lower = line.lower()

            if lower.startswith(".include"):
                inc = self._parse_include(line)
                if inc:
                    self.includes.append(inc)
            elif lower.startswith(".subckt"):
                subckt, end_idx = self._parse_subckt(logical_lines, i)
                if subckt:
                    self.subckts[subckt.name] = subckt
                    i = end_idx
            i += 1
        return self.subckts

    def _logical_lines(self, raw_lines: list[str]) -> list[str]:
        out: list[str] = []
        current = ""
        for raw in raw_lines:
            line = raw.rstrip("\n")
            stripped = line.strip()
            if not stripped:
                if current:
                    out.append(current)
                    current = ""
                out.append("")
                continue
            if stripped.startswith("+"):
                current = (current + " " + stripped[1:].strip()).strip()
            else:
                if current:
                    out.append(current)
                current = stripped
        if current:
            out.append(current)
        return out

    def _parse_include(self, line: str) -> Optional[str]:
        parts = line.split(maxsplit=1)
        if len(parts) < 2:
            return None
        target = parts[1].strip().strip('"').strip("'")
        if not os.path.isabs(target):
            target = os.path.normpath(os.path.join(self.input_dir, target))
        return target

    def _parse_subckt(self, lines: list[str], start: int) -> tuple[Optional[Subckt], int]:
        header = lines[start].strip()
        parts = header.split()
        if len(parts) < 2:
            return None, start

        name = parts[1]
        ports = [Port(name=p) for p in self._subckt_ports(parts[2:])]
        subckt = Subckt(name=name, ports=ports)

        pininfo = ""
        i = start + 1
        while i < len(lines):
            line = lines[i].strip()
            lower = line.lower()

            if lower.startswith(".ends"):
                break
            if not line:
                i += 1
                continue
            if line.startswith("*"):
                if line.upper().startswith("*.PININFO"):
                    pininfo = line[len("*.PININFO"):].strip()
                i += 1
                continue
            if lower.startswith(".include"):
                inc = self._parse_include(line)
                if inc:
                    self.includes.append(inc)
                i += 1
                continue
            if lower.startswith("."):
                i += 1
                continue

            inst = self._parse_instance(line)
            if inst:
                subckt.instances.append(inst)
            i += 1

        if pininfo:
            pin_dirs = self._parse_pininfo(pininfo)
            for port in subckt.ports:
                if port.name in pin_dirs:
                    port.direction = pin_dirs[port.name]

        return subckt, i

    def _subckt_ports(self, tokens: list[str]) -> list[str]:
        ports: list[str] = []
        for token in tokens:
            if "=" in token:
                break
            ports.append(token)
        return ports

    def _parse_pininfo(self, pininfo: str) -> dict[str, str]:
        out: dict[str, str] = {}
        for item in pininfo.split():
            if ":" not in item:
                continue
            name, kind = item.rsplit(":", 1)
            kind = kind.upper()
            if kind == "I":
                out[name] = "input"
            elif kind == "O":
                out[name] = "output"
            else:
                out[name] = "inout"
        return out

    def _parse_instance(self, line: str) -> Optional[Instance]:
        parts = line.split()
        if len(parts) < 2:
            return None

        name = parts[0]
        prefix = name[0].lower()

        if prefix == "x":
            return self._parse_x_instance(parts)
        if prefix == "m":
            return self._fixed_model_instance(parts, prefix, 4)
        if prefix in {"d"}:
            return self._fixed_model_instance(parts, prefix, 2)
        if prefix in {"q"}:
            return self._fixed_model_instance(parts, prefix, 3)
        if prefix in {"r", "c", "l", "v", "i"}:
            return self._two_pin_instance(parts, prefix)
        return self._generic_instance(parts, prefix)

    def _parse_x_instance(self, parts: list[str]) -> Optional[Instance]:
        if len(parts) < 3:
            return None
        end = self._first_param_index(parts, 1)
        if end - 1 < 2:
            return None
        cell = parts[end - 1]
        pins = parts[1:end - 1]
        params = parts[end:]
        return Instance(name=parts[0], cell=cell, pins=pins, prefix="x", params=params)

    def _fixed_model_instance(self, parts: list[str], prefix: str, pin_count: int) -> Optional[Instance]:
        if len(parts) < 2 + pin_count:
            return None
        pins = parts[1 : 1 + pin_count]
        model_idx = 1 + pin_count
        cell = parts[model_idx] if len(parts) > model_idx else f"spice_{prefix}"
        params = parts[model_idx + 1 :] if len(parts) > model_idx + 1 else []
        return Instance(name=parts[0], cell=cell, pins=pins, prefix=prefix, params=params)

    def _two_pin_instance(self, parts: list[str], prefix: str) -> Optional[Instance]:
        if len(parts) < 3:
            return None
        pins = parts[1:3]
        cell = f"spice_{prefix}"
        params: list[str] = []
        if len(parts) >= 4:
            token = parts[3]
            if not NUMERIC_RE.match(token):
                cell = token
                params = parts[4:]
            else:
                params = parts[3:]
        return Instance(name=parts[0], cell=cell, pins=pins, prefix=prefix, params=params)

    def _generic_instance(self, parts: list[str], prefix: str) -> Optional[Instance]:
        end = self._first_param_index(parts, 1)
        positional = parts[1:end]
        if len(positional) < 2:
            return None
        pin_count = max(1, min(len(positional) - 1, PIN_ORDER_HINTS.get(prefix, len(positional) - 1)))
        pins = positional[:pin_count]
        cell = positional[pin_count] if pin_count < len(positional) else f"spice_{prefix}"
        params = parts[end:]
        return Instance(name=parts[0], cell=cell, pins=pins, prefix=prefix, params=params)

    def _first_param_index(self, parts: list[str], start: int) -> int:
        idx = len(parts)
        for i in range(start, len(parts)):
            if "=" in parts[i]:
                idx = i
                break
        return idx


class SymFileParser:
    def parse(self, path: str) -> tuple[list[PinDef], int, int]:
        pins: list[PinDef] = []
        min_x = min_y = 0
        max_x = max_y = 0
        with open(path, "r", encoding="utf-8") as fh:
            for line_no, line in enumerate(fh):
                raw = line.strip()
                if not raw:
                    continue
                if raw.startswith(("B ", "L ", "P ", "A ", "T ")):
                    fields = raw.split("{", 1)[0].strip().split()
                    nums = [self._safe_int(tok) for tok in fields[2:] if self._looks_num(tok)]
                    if len(nums) >= 4:
                        for x, y in zip(nums[::2], nums[1::2]):
                            min_x = min(min_x, x)
                            min_y = min(min_y, y)
                            max_x = max(max_x, x)
                            max_y = max(max_y, y)
                if not raw.startswith("B 5 "):
                    continue
                attrs = self._attrs(raw)
                x1, y1, x2, y2 = [self._safe_int(v) for v in raw.split("{", 1)[0].split()[2:6]]
                name = attrs.get("name", f"p{line_no}")
                direction = attrs.get("dir", "inout")
                order = int(attrs.get("sim_pinnumber", str(len(pins))))
                pins.append(PinDef(name=name, x=(x1 + x2) // 2, y=(y1 + y2) // 2, direction=direction, order=order))
        pins.sort(key=lambda pin: (pin.order, pin.name))
        width = max(GRID * 4, max_x - min_x)
        height = max(GRID * 4, max_y - min_y)
        return pins, width, height

    def _attrs(self, raw: str) -> dict[str, str]:
        if "{" not in raw or "}" not in raw:
            return {}
        attr_text = raw.split("{", 1)[1].rsplit("}", 1)[0]
        out: dict[str, str] = {}
        for key, value in PIN_ATTR_RE.findall(attr_text):
            out[key] = value.strip('"')
        return out

    def _looks_num(self, token: str) -> bool:
        try:
            float(token)
            return True
        except ValueError:
            return False

    def _safe_int(self, token: str) -> int:
        return int(round(float(token)))


class SymbolResolver:
    def __init__(self, output_dir: str, local_dir: str, pdk_path: Optional[str] = None) -> None:
        self.output_dir = os.path.abspath(output_dir)
        self.local_dir = os.path.abspath(local_dir)
        self.include_dirs: list[str] = []
        self.sym_parser = SymFileParser()
        self._resolved: dict[str, SymbolSpec] = {}
        self._pdk_index: Optional[dict[str, str]] = None
        pdk_base = pdk_path or os.environ.get("SKY130_PDK_PATH") or "/usr/local/share/pdk/sky130A"
        self.pdk_xschem_root = os.path.join(os.path.abspath(pdk_base), "libs.tech", "xschem")

    def add_include_dir(self, include_path: str) -> None:
        if not include_path:
            return
        inc_dir = os.path.dirname(os.path.abspath(include_path))
        if inc_dir not in self.include_dirs:
            self.include_dirs.append(inc_dir)

    def resolve(self, cell_name: str, local_subckts: dict[str, Subckt], fallback_pin_count: int) -> SymbolSpec:
        if cell_name in self._resolved:
            return self._resolved[cell_name]

        if cell_name in local_subckts:
            subckt = local_subckts[cell_name]
            pins, width, height = build_symbol_geometry(subckt.ports)
            spec = SymbolSpec(
                kind="local",
                ref=f"{sanitize_filename(cell_name)}.sym",
                path=os.path.join(self.output_dir, f"{sanitize_filename(cell_name)}.sym"),
                pins=pins,
                width=width,
                height=height,
            )
            self._resolved[cell_name] = spec
            return spec

        pdk = self._find_pdk_symbol(cell_name)
        if pdk:
            self._resolved[cell_name] = pdk
            return pdk

        project = self._find_project_symbol(cell_name)
        if project:
            self._resolved[cell_name] = project
            return project

        include = self._find_include_symbol(cell_name)
        if include:
            self._resolved[cell_name] = include
            return include

        pins, width, height = build_fallback_geometry(fallback_pin_count)
        spec = SymbolSpec(
            kind="fallback",
            ref=f"{sanitize_filename(cell_name)}.sym",
            path=os.path.join(self.output_dir, f"{sanitize_filename(cell_name)}.sym"),
            pins=pins,
            width=width,
            height=height,
        )
        self._resolved[cell_name] = spec
        return spec

    def _find_pdk_symbol(self, cell_name: str) -> Optional[SymbolSpec]:
        if not os.path.isdir(self.pdk_xschem_root):
            return None
        if self._pdk_index is None:
            self._pdk_index = {}
            for root, _, files in os.walk(self.pdk_xschem_root):
                for fname in files:
                    if fname.endswith(".sym"):
                        self._pdk_index.setdefault(fname[:-4], os.path.join(root, fname))
        path = self._pdk_index.get(cell_name)
        if not path:
            return None
        pins, width, height = self.sym_parser.parse(path)
        return SymbolSpec(kind="pdk", ref=relsym(path, self.pdk_xschem_root), path=path, pins=pins, width=width, height=height)

    def _find_project_symbol(self, cell_name: str) -> Optional[SymbolSpec]:
        for base_dir in [self.local_dir, self.output_dir]:
            path = self._find_named_file(base_dir, f"{cell_name}.sym")
            if path:
                pins, width, height = self.sym_parser.parse(path)
                return SymbolSpec(kind="project", ref=relsym(path, self.output_dir), path=path, pins=pins, width=width, height=height)
        return None

    def _find_include_symbol(self, cell_name: str) -> Optional[SymbolSpec]:
        for inc_dir in self.include_dirs:
            sym_path = os.path.join(inc_dir, f"{cell_name}.sym")
            sch_path = os.path.join(inc_dir, f"{cell_name}.sch")
            if os.path.isfile(sym_path) and os.path.isfile(sch_path):
                pins, width, height = self.sym_parser.parse(sym_path)
                return SymbolSpec(kind="include", ref=relsym(sym_path, self.output_dir), path=sym_path, pins=pins, width=width, height=height)
        return None

    def _find_named_file(self, base_dir: str, target: str) -> Optional[str]:
        direct = os.path.join(base_dir, target)
        if os.path.isfile(direct):
            return direct
        for root, _, files in os.walk(base_dir):
            if target in files:
                return os.path.join(root, target)
        return None


def build_symbol_geometry(ports: list[Port]) -> tuple[list[PinDef], int, int]:
    groups: dict[str, list[Port]] = {"power": [], "ground": [], "input": [], "output": [], "inout": []}
    for port in ports:
        groups[port_kind(port.name, port.direction)].append(port)

    side_counts = {
        "left": max(1, len(groups["input"])),
        "right": max(1, len(groups["output"]) + len(groups["inout"])),
        "top": max(1, len(groups["power"])),
        "bottom": max(1, len(groups["ground"])),
    }
    width = snap(max(8 * GRID, (max(side_counts["top"], side_counts["bottom"]) + 1) * 2 * GRID))
    height = snap(max(6 * GRID, (max(side_counts["left"], side_counts["right"]) + 1) * 2 * GRID))

    body_w = width
    body_h = height
    x0 = 0
    y0 = 0

    pins: list[PinDef] = []
    order = 1

    def spaced(count: int, span: int) -> list[int]:
        if count <= 0:
            return []
        if count == 1:
            return [0]
        step = span / (count + 1)
        return [snap(-span / 2 + step * (i + 1)) for i in range(count)]

    for port, y in zip(groups["input"], spaced(len(groups["input"]), body_h)):
        pins.append(PinDef(port.name, x0 - GRID, y, direction_to_xschem(port.direction), order))
        order += 1

    right_ports = groups["inout"] + groups["output"]
    for port, y in zip(right_ports, spaced(len(right_ports), body_h)):
        pins.append(PinDef(port.name, x0 + body_w + GRID, y, direction_to_xschem(port.direction), order))
        order += 1

    for port, x in zip(groups["power"], spaced(len(groups["power"]), body_w)):
        pins.append(PinDef(port.name, x, y0 - GRID, direction_to_xschem(port.direction), order))
        order += 1

    for port, x in zip(groups["ground"], spaced(len(groups["ground"]), body_w)):
        pins.append(PinDef(port.name, x, y0 + body_h + GRID, direction_to_xschem(port.direction), order))
        order += 1

    pin_map = {pin.name: pin for pin in pins}
    ordered_pins = [pin_map[port.name] for port in ports if port.name in pin_map]
    return ordered_pins, body_w, body_h


def build_fallback_geometry(pin_count: int) -> tuple[list[PinDef], int, int]:
    ports = [Port(name=f"p{i + 1}") for i in range(max(1, pin_count))]
    return build_symbol_geometry(ports)


class SymbolGenerator:
    def generate_local_symbol(self, subckt: Subckt) -> str:
        pins, width, height = build_symbol_geometry(subckt.ports)
        return self._render_symbol(
            cell_name=subckt.name,
            pins=pins,
            width=width,
            height=height,
            symbol_type="subcircuit",
            fmt='@name @pinlist @symname',
            template="name=x1",
        )

    def generate_fallback_symbol(self, cell_name: str, pin_count: int) -> str:
        pins, width, height = build_fallback_geometry(pin_count)
        return self._render_symbol(
            cell_name=cell_name,
            pins=pins,
            width=width,
            height=height,
            symbol_type="primitive",
            fmt=f'@name @pinlist {cell_name}',
            template="name=x1",
        )

    def _render_symbol(
        self,
        cell_name: str,
        pins: list[PinDef],
        width: int,
        height: int,
        symbol_type: str,
        fmt: str,
        template: str,
    ) -> str:
        symbol_props = f'type={symbol_type} format="{fmt}" template="{template}"'
        lines = [
            VERSION_LINE,
            f"G {{{symbol_props}}}",
            f"K {{{symbol_props}}}",
            "V {}",
            "S {}",
            "E {}",
            f"B 4 0 0 {width} {height} {{fill=false}}",
            f'T {{{xescape(cell_name)}}} {width // 2} {height // 2} 0 0 0.35 0.35 {{hcenter=true vcenter=true}}',
        ]
        for pin in pins:
            x1 = pin.x - GRID // 4
            y1 = pin.y - GRID // 4
            x2 = pin.x + GRID // 4
            y2 = pin.y + GRID // 4
            lines.append(
                f'B 5 {x1} {y1} {x2} {y2} '
                f'{{name={pin.name} dir={direction_to_xschem(pin.direction)} sim_pinnumber={pin.order}}}'
            )
            tx = pin.x - GRID if pin.x <= 0 else pin.x + GRID
            lines.append(
                f'T {{{xescape(pin.name)}}} {tx} {pin.y} 0 0 0.25 0.25 '
                f'{{{"hcenter=false"}}}'
            )
        return "\n".join(lines) + "\n"


class LayoutEngine:
    def __init__(self, grid: int = GRID) -> None:
        self.grid = grid

    def layout_subckt(self, subckt: Subckt, symbol_specs: dict[str, SymbolSpec]) -> dict[str, tuple[int, int]]:
        if not subckt.instances:
            return {}

        layers = self._assign_layers(subckt, symbol_specs)
        by_layer: dict[int, list[Instance]] = defaultdict(list)
        for inst in subckt.instances:
            by_layer[layers[inst.name]].append(inst)

        layer_ids = sorted(by_layer)
        max_rows = max(len(by_layer[layer]) for layer in layer_ids)
        col_pitch = 12 * self.grid
        row_pitch = 10 * self.grid
        positions: dict[str, tuple[int, int]] = {}

        for layer in layer_ids:
            column = by_layer[layer]
            column.sort(key=lambda inst: self._instance_sort_key(inst, subckt, symbol_specs))
            x = snap(10 * self.grid + layer * col_pitch, self.grid)
            total_h = (len(column) - 1) * row_pitch
            y0 = snap((max_rows * row_pitch - total_h) / 2 + 8 * self.grid, self.grid)
            for idx, inst in enumerate(column):
                positions[inst.name] = (x, snap(y0 + idx * row_pitch, self.grid))
        return positions

    def place_ports(
        self,
        subckt: Subckt,
        positions: dict[str, tuple[int, int]],
        symbol_specs: dict[str, SymbolSpec],
    ) -> dict[str, tuple[int, int, str]]:
        if positions:
            max_inst_x = max(x + symbol_specs[self._cell_for_name(subckt, name)].width for name, (x, _) in positions.items())
            max_inst_y = max(y + symbol_specs[self._cell_for_name(subckt, name)].height for name, (_, y) in positions.items())
        else:
            max_inst_x = 20 * self.grid
            max_inst_y = 14 * self.grid

        left_x = 2 * self.grid
        right_x = snap(max_inst_x + 10 * self.grid, self.grid)
        top_y = 2 * self.grid
        bottom_y = snap(max_inst_y + 8 * self.grid, self.grid)

        groups: dict[str, list[Port]] = {"power": [], "ground": [], "input": [], "output": [], "inout": []}
        for port in subckt.ports:
            groups[port_kind(port.name, port.direction)].append(port)

        placed: dict[str, tuple[int, int, str]] = {}

        def stack(items: list[Port], axis: str, fixed: int, start: int, step: int, role: str) -> None:
            for idx, port in enumerate(items):
                pos = snap(start + idx * step, self.grid)
                if axis == "x":
                    placed[port.name] = (pos, fixed, role)
                else:
                    placed[port.name] = (fixed, pos, role)

        stack(groups["input"], "y", left_x, 4 * self.grid, 2 * self.grid, "input")
        stack(groups["output"], "y", right_x, max(4 * self.grid, bottom_y - (len(groups["output"]) + 2) * 2 * self.grid), 2 * self.grid, "output")
        stack(groups["power"], "x", top_y, 6 * self.grid, 3 * self.grid, "power")
        stack(groups["ground"], "x", bottom_y, 6 * self.grid, 3 * self.grid, "ground")
        stack(groups["inout"], "y", right_x, max(8 * self.grid, bottom_y // 2 - len(groups["inout"]) * self.grid), 2 * self.grid, "inout")
        return placed

    def _assign_layers(self, subckt: Subckt, symbol_specs: dict[str, SymbolSpec]) -> dict[str, int]:
        net_ports = {port.name: port_kind(port.name, port.direction) for port in subckt.ports}
        inst_by_name = {inst.name: inst for inst in subckt.instances}
        net_users: dict[str, list[tuple[str, PinDef]]] = defaultdict(list)
        for inst in subckt.instances:
            spec = symbol_specs[inst.cell]
            pin_defs = self._ordered_pin_defs(spec, len(inst.pins))
            for net, pin_def in zip(inst.pins, pin_defs):
                net_users[net].append((inst.name, pin_def))

        graph: dict[str, set[str]] = defaultdict(set)
        indeg: dict[str, int] = {inst.name: 0 for inst in subckt.instances}
        layers: dict[str, int] = {inst.name: 0 for inst in subckt.instances}

        for net, users in net_users.items():
            srcs: list[str] = []
            dsts: list[str] = []
            if net_ports.get(net) in {"input", "power"}:
                srcs.append(f"PORT:{net}")
            if net_ports.get(net) in {"output", "ground"}:
                dsts.append(f"PORT:{net}")
            for inst_name, pin in users:
                direction = direction_to_xschem(pin.direction)
                if direction == "out":
                    srcs.append(inst_name)
                elif direction == "in":
                    dsts.append(inst_name)
                else:
                    srcs.append(inst_name)
                    dsts.append(inst_name)
            for src in srcs:
                for dst in dsts:
                    if src == dst or dst.startswith("PORT:"):
                        continue
                    if src.startswith("PORT:"):
                        layers[dst] = max(layers[dst], 1)
                        continue
                    if dst not in graph[src]:
                        graph[src].add(dst)
                        indeg[dst] += 1

        queue = sorted([name for name, degree in indeg.items() if degree == 0])
        while queue:
            current = queue.pop(0)
            for nxt in sorted(graph[current]):
                layers[nxt] = max(layers[nxt], layers[current] + 1)
                indeg[nxt] -= 1
                if indeg[nxt] == 0:
                    queue.append(nxt)
                    queue.sort()
        return layers

    def _ordered_pin_defs(self, spec: SymbolSpec, count: int) -> list[PinDef]:
        if not spec.pins:
            return [PinDef(name=f"p{i + 1}", x=0, y=0, order=i + 1) for i in range(count)]
        if len(spec.pins) >= count:
            return spec.pins[:count]
        extra = [PinDef(name=f"p{i + 1}", x=spec.width + GRID, y=i * GRID, order=len(spec.pins) + i + 1) for i in range(count - len(spec.pins))]
        return spec.pins + extra

    def _instance_sort_key(self, inst: Instance, subckt: Subckt, symbol_specs: dict[str, SymbolSpec]) -> tuple[int, str]:
        top_level_nets = {port.name for port in subckt.ports}
        top_hits = sum(1 for net in inst.pins if net in top_level_nets)
        return (-top_hits, symbol_specs[inst.cell].height, inst.name)

    def _cell_for_name(self, subckt: Subckt, inst_name: str) -> str:
        for inst in subckt.instances:
            if inst.name == inst_name:
                return inst.cell
        raise KeyError(inst_name)


class SchematicGenerator:
    PORT_SYMS = {
        "input": "devices/ipin.sym",
        "output": "devices/opin.sym",
        "inout": "devices/iopin.sym",
        "power": "devices/iopin.sym",
        "ground": "devices/iopin.sym",
    }

    def generate_schematic(
        self,
        subckt: Subckt,
        symbol_specs: dict[str, SymbolSpec],
        inst_positions: dict[str, tuple[int, int]],
        port_positions: dict[str, tuple[int, int, str]],
    ) -> str:
        lines = [VERSION_LINE, *XSCHEM_PROPS]

        name_seq = 1
        for port in subckt.ports:
            x, y, role = port_positions[port.name]
            sym = self.PORT_SYMS[role]
            rot = 0
            if role == "output":
                rot = 2
            elif role == "power":
                rot = 1
            elif role == "ground":
                rot = 3
            lines.append(f'C {{{sym}}} {x} {y} {rot} 0 {{name=p{name_seq} lab={port.name}}}')
            name_seq += 1

        for inst in subckt.instances:
            x, y = inst_positions.get(inst.name, (10 * GRID, 10 * GRID))
            spec = symbol_specs[inst.cell]
            inst_attrs = self._instance_attrs(inst)
            lines.append(f'C {{{spec.ref}}} {x} {y} 0 0 ' + "{" + " ".join(inst_attrs) + "}")

        for x1, y1, x2, y2, attrs in self._route_nets(subckt, symbol_specs, inst_positions, port_positions):
            lines.append(f"N {x1} {y1} {x2} {y2} {attrs}")

        return "\n".join(lines) + "\n"

    def _ordered_pin_defs(self, spec: SymbolSpec, count: int) -> list[PinDef]:
        if len(spec.pins) >= count:
            return spec.pins[:count]
        fallback = [PinDef(name=f"p{i + 1}", x=spec.width + GRID, y=(i + 1) * GRID) for i in range(count - len(spec.pins))]
        return spec.pins + fallback

    def _label_rotation(self, pin: PinDef) -> int:
        if pin.x <= 0:
            return 0
        return 2

    def _route_nets(
        self,
        subckt: Subckt,
        symbol_specs: dict[str, SymbolSpec],
        inst_positions: dict[str, tuple[int, int]],
        port_positions: dict[str, tuple[int, int, str]],
    ) -> list[tuple[int, int, int, int, str]]:
        endpoints: dict[str, list[tuple[int, int]]] = defaultdict(list)
        port_nets = {port.name for port in subckt.ports}

        for port in subckt.ports:
            x, y, _ = port_positions[port.name]
            endpoints[port.name].append((snap(x), snap(y)))

        for inst in subckt.instances:
            spec = symbol_specs[inst.cell]
            pin_defs = self._ordered_pin_defs(spec, len(inst.pins))
            x0, y0 = inst_positions.get(inst.name, (10 * GRID, 10 * GRID))
            for pin_def, net in zip(pin_defs, inst.pins):
                endpoints[net].append((snap(x0 + pin_def.x), snap(y0 + pin_def.y)))

        segments: list[tuple[int, int, int, int, str]] = []
        seen: set[tuple[int, int, int, int, str]] = set()

        def add_seg(x1: int, y1: int, x2: int, y2: int, lab: Optional[str] = None) -> None:
            x1 = snap(x1)
            y1 = snap(y1)
            x2 = snap(x2)
            y2 = snap(y2)
            if x1 == x2 and y1 == y2:
                return
            attrs = "{}" if lab is None else "{lab=" + quote_attr(lab) + "}"
            key = (x1, y1, x2, y2, attrs)
            rev = (x2, y2, x1, y1, attrs)
            if key in seen or rev in seen:
                return
            seen.add(key)
            segments.append((x1, y1, x2, y2, attrs))

        for net, pts in sorted(endpoints.items()):
            uniq = sorted(set((snap(x), snap(y)) for x, y in pts))
            if len(uniq) < 2:
                continue
            if len(uniq) == 2:
                (x1, y1), (x2, y2) = uniq
                if x1 == x2 or y1 == y2:
                    add_seg(x1, y1, x2, y2, net)
                else:
                    mid_x = snap((x1 + x2) / 2)
                    add_seg(x1, y1, mid_x, y1, net)
                    add_seg(mid_x, y1, mid_x, y2, None)
                    add_seg(mid_x, y2, x2, y2, None)
                continue

            xs = [x for x, _ in uniq]
            ys = [y for _, y in uniq]
            trunk_x = snap(median(xs))
            min_y = min(ys)
            max_y = max(ys)
            add_seg(trunk_x, min_y, trunk_x, max_y, net)
            for x, y in uniq:
                add_seg(x, y, trunk_x, y, None)

        return segments

    def _instance_attrs(self, inst: Instance) -> list[str]:
        attrs = [f"name={inst.name}"]
        bare_idx = 1
        for param in inst.params:
            if "=" in param:
                attrs.append(param)
                continue
            key = "value" if bare_idx == 1 else f"value{bare_idx}"
            attrs.append(f"{key}={quote_attr(param)}")
            bare_idx += 1
        return attrs


class SpiceToXschem:
    def __init__(self, output_dir: str, local_dir: str, pdk_path: Optional[str] = None) -> None:
        self.output_dir = os.path.abspath(output_dir)
        self.local_dir = os.path.abspath(local_dir)
        self.parser = SpiceParser()
        self.symbol_resolver = SymbolResolver(self.output_dir, self.local_dir, pdk_path=pdk_path)
        self.symbol_gen = SymbolGenerator()
        self.layout_engine = LayoutEngine()
        self.schem_gen = SchematicGenerator()

    def process(self, input_file: str) -> dict[str, str]:
        os.makedirs(self.output_dir, exist_ok=True)
        subckts = self.parser.parse_file(input_file)
        for inc in self.parser.includes:
            self.symbol_resolver.add_include_dir(inc)

        fallback_pin_counts = self._fallback_pin_counts(subckts)
        symbol_specs: dict[str, SymbolSpec] = {}
        for subckt in subckts.values():
            for inst in subckt.instances:
                symbol_specs[inst.cell] = self.symbol_resolver.resolve(inst.cell, subckts, fallback_pin_counts.get(inst.cell, len(inst.pins)))

        generated_files: dict[str, str] = {}

        for name, subckt in sorted(subckts.items()):
            sym_path = os.path.join(self.output_dir, f"{sanitize_filename(name)}.sym")
            with open(sym_path, "w", encoding="utf-8") as fh:
                fh.write(self.symbol_gen.generate_local_symbol(subckt))
            generated_files[os.path.basename(sym_path)] = sym_path

            inst_positions = self.layout_engine.layout_subckt(subckt, symbol_specs)
            port_positions = self.layout_engine.place_ports(subckt, inst_positions, symbol_specs)
            sch_path = os.path.join(self.output_dir, f"{sanitize_filename(name)}.sch")
            with open(sch_path, "w", encoding="utf-8") as fh:
                fh.write(self.schem_gen.generate_schematic(subckt, symbol_specs, inst_positions, port_positions))
            generated_files[os.path.basename(sch_path)] = sch_path

        for cell, pin_count in sorted(fallback_pin_counts.items()):
            spec = symbol_specs.get(cell)
            if spec and spec.kind == "fallback":
                sym_path = os.path.join(self.output_dir, f"{sanitize_filename(cell)}.sym")
                with open(sym_path, "w", encoding="utf-8") as fh:
                    fh.write(self.symbol_gen.generate_fallback_symbol(cell, pin_count))
                generated_files[os.path.basename(sym_path)] = sym_path

        xschemrc_path = os.path.join(self.output_dir, "xschemrc")
        with open(xschemrc_path, "w", encoding="utf-8") as fh:
            fh.write(self._generate_xschemrc())
        generated_files[os.path.basename(xschemrc_path)] = xschemrc_path

        return generated_files

    def _fallback_pin_counts(self, subckts: dict[str, Subckt]) -> dict[str, int]:
        counts: dict[str, int] = {}
        local_names = set(subckts)
        for subckt in subckts.values():
            for inst in subckt.instances:
                if inst.cell not in local_names:
                    counts[inst.cell] = max(counts.get(inst.cell, 0), len(inst.pins))
        return counts

    def _generate_xschemrc(self) -> str:
        design_paths: list[str] = [self.output_dir]
        if self.local_dir not in design_paths:
            design_paths.append(self.local_dir)
        for inc_dir in self.symbol_resolver.include_dirs:
            if inc_dir not in design_paths:
                design_paths.append(inc_dir)
        pdk_root = self.symbol_resolver.pdk_xschem_root
        if os.path.isdir(pdk_root) and pdk_root not in design_paths:
            design_paths.append(pdk_root)
        path_expr = ":".join(design_paths)
        return (
            "if {![info exists XSCHEM_LIBRARY_PATH]} {\n"
            "  set XSCHEM_LIBRARY_PATH \"\"\n"
            "}\n"
            f"append XSCHEM_LIBRARY_PATH :{path_expr}\n"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="SPICE to xschem generator")
    parser.add_argument("input", help="Input SPICE file")
    parser.add_argument("-o", "--output", default=".", help="Output directory")
    parser.add_argument("-l", "--local", default=".", help="Local symbol directory")
    parser.add_argument("-p", "--pdk", default=None, help="Sky130 PDK root")
    args = parser.parse_args()

    converter = SpiceToXschem(args.output, args.local, pdk_path=args.pdk)
    files = converter.process(args.input)
    print(f"Generated {len(files)} files:")
    for fname in sorted(files):
        print(f"  {fname}")


if __name__ == "__main__":
    main()
