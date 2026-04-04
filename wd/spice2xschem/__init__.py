#!/usr/bin/env python3
"""
SPICE to xschem (.sch/.sym) generator for Sky130
Parses SPICE netlist and generates xschem schematic and symbol files.
"""

import re
import os
import sys
import argparse
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict


@dataclass
class Port:
    name: str
    direction: str = "inout"


@dataclass
class Instance:
    name: str
    cell: str
    pins: list[str]
    x: float = 0.0
    y: float = 0.0


@dataclass
class Subckt:
    name: str
    ports: list[Port]
    instances: list[Instance] = field(default_factory=list)
    nets: dict[str, list[tuple]] = field(default_factory=dict)


@dataclass
class SymbolPin:
    name: str
    x: float
    y: float
    direction: str = "inout"


@dataclass
class Symbol:
    name: str
    pins: list[SymbolPin]
    width: float = 140
    height: float = 100
    is_hierarchical: bool = False


class SpiceParser:
    def __init__(self):
        self.subckts: dict[str, Subckt] = {}
        self.includes: list[str] = []
        self.current_subckt: Optional[Subckt] = None

    def parse_file(self, filepath: str) -> dict[str, Subckt]:
        with open(filepath, 'r') as f:
            content = f.read()
        
        lines = content.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if line.startswith('.include'):
                parts = line.split()
                if len(parts) >= 2:
                    self.includes.append(parts[1])
            
            elif line.startswith('.subckt'):
                subckt = self._parse_subckt(line, lines, i + 1)
                if subckt:
                    self.subckts[subckt.name] = subckt
                    i = self._find_ends(lines, i) + 1
                    continue
            i += 1
        
        return self.subckts
    
    def _get_pin_direction_from_pininfo(self, pininfo: str, pin_name: str) -> str:
        if not pininfo:
            return "inout"
        
        pininfo = pininfo.upper()
        pin_name_upper = pin_name.upper()
        
        for part in pininfo.split():
            if ':' in part:
                parts = part.split(':')
                name = parts[0]
                direction = parts[-1]
                if name.upper() == pin_name_upper:
                    if direction.upper() == 'I':
                        return "input"
                    elif direction.upper() == 'O':
                        return "output"
                    elif direction.upper() == 'B':
                        return "inout"
        return "inout"

    def _parse_subckt(self, header_line: str, lines: list[str], start: int) -> Optional[Subckt]:
        parts = header_line.split()
        if len(parts) < 2:
            return None
        
        name = parts[1]
        
        ports = []
        port_idx = 2
        for part in parts[2:]:
            if '=' in part:
                break
            direction = "inout"
            if ':' in part:
                clean_part, direction = part.split(':')
                ports.append(Port(clean_part, direction))
            else:
                ports.append(Port(part, direction))
        
        subckt = Subckt(name=name, ports=ports)
        
        i = start
        pininfo = ""
        while i < len(lines):
            line = lines[i].strip()
            if not line or line.startswith('*'):
                if line.startswith('*.PININFO'):
                    pininfo = line.replace('*.PININFO', '').strip()
                i += 1
                continue
            
            if line.startswith('.ends'):
                break
            
            if line.startswith('.save') or line.startswith('.'):
                i += 1
                continue
            
            inst = self._parse_instance(line)
            if inst:
                subckt.instances.append(inst)
            
            i += 1
        
        if pininfo:
            for port in subckt.ports:
                port.direction = self._get_pin_direction_from_pininfo(pininfo, port.name)
        
        return subckt

    def _parse_instance(self, line: str) -> Optional[Instance]:
        parts = line.split()
        if len(parts) < 3:
            return None
        
        inst_type = parts[0]
        
        if inst_type.startswith('x'):
            name = parts[0]
            cell = parts[-1]
            pins = parts[1:-1]
            return Instance(name=name, cell=cell, pins=pins)
        
        return None

    def _find_ends(self, lines: list[str], start: int) -> int:
        for i in range(start, len(lines)):
            if lines[i].strip().startswith('.ends'):
                return i
        return len(lines) - 1


class SymbolResolver:
    SKY130_PDK_PATH = os.environ.get('SKY130_PDK_PATH', '/usr/local/share/pdk/sky130A')
    SKY130_SYMLIB = os.path.join(SKY130_PDK_PATH, 'libs.tech', 'xschem', 'sky130')
    
    def __init__(self, output_dir: str, local_dir: str):
        self.output_dir = output_dir
        self.local_dir = local_dir
        self.includes_dirs: list[str] = []
        self._symbol_map: dict[str, str] = {}
    
    def add_include_dir(self, include_path: str):
        if include_path:
            inc_dir = os.path.dirname(os.path.abspath(include_path))
            if inc_dir not in self.includes_dirs:
                self.includes_dirs.append(inc_dir)
    
    def resolve(self, cell_name: str, local_subckts: set[str]) -> str:
        if cell_name in local_subckts:
            return 'local'
        
        if cell_name in self._symbol_map:
            return self._symbol_map[cell_name]
        
        pdk_sym = self._find_pdk_symbol(cell_name)
        if pdk_sym:
            self._symbol_map[cell_name] = pdk_sym
            return pdk_sym
        
        local_sym = self._find_local_symbol(cell_name)
        if local_sym:
            self._symbol_map[cell_name] = local_sym
            return local_sym
        
        inc_sym = self._find_include_symbol(cell_name)
        if inc_sym:
            self._symbol_map[cell_name] = inc_sym
            return inc_sym
        
        return 'fallback'
    
    def _find_pdk_symbol(self, cell_name: str) -> Optional[str]:
        if not os.path.exists(self.SKY130_SYMLIB):
            return None
        
        possible_names = [
            cell_name,
            cell_name.replace('sky130_fd_pr__', ''),
            cell_name.replace('sky130_fd_sc_hvl__', ''),
            cell_name.replace('sky130_fd_sc_hd__', ''),
        ]
        
        for name in possible_names:
            for ext in ['', '.sym']:
                path = os.path.join(self.SKY130_SYMLIB, name + ext)
                if os.path.exists(path):
                    return f"sky130:{name}"
        
        return None
    
    def _find_local_symbol(self, cell_name: str) -> Optional[str]:
        for search_dir in [self.local_dir, self.output_dir]:
            for ext in ['', '.sym']:
                path = os.path.join(search_dir, cell_name + ext)
                if os.path.exists(path):
                    return f"local:{cell_name}"
        
        return None
    
    def _find_include_symbol(self, cell_name: str) -> Optional[str]:
        for inc_dir in self.includes_dirs:
            for ext in ['', '.sym']:
                path = os.path.join(inc_dir, cell_name + ext)
                if os.path.exists(path):
                    return f"include:{os.path.join(inc_dir, cell_name)}"
        
        return None


class SymbolGenerator:
    def __init__(self):
        self.grid = 10
    
    def generate_local_symbol(self, subckt: Subckt) -> str:
        lines = [
            "v {xschem version=3.4.4 file_version=1.2",
            "}",
            "G {}",
            "K {}",
            "V {}",
            "S {}",
            "E {}",
        ]
        
        num_pins = len(subckt.ports)
        if num_pins == 0:
            lines.append(f"T {{n {subckt.name} 50 55 0 0.3 0.3 0 {subckt.name}}}")
            return '\n'.join(lines)
        
        left_pins = num_pins // 2
        right_pins = num_pins - left_pins
        
        left_idx = 0
        right_idx = left_pins
        
        for i, port in enumerate(subckt.ports):
            direction = port.direction if port.direction else "inout"
            
            if i < left_pins:
                y_pos = 10 + int(80 * left_idx / max(1, left_pins - 1)) if left_pins > 1 else 50
                lines.append(f"P {{n {port.name} {direction} 0 {y_pos} 0 {y_pos} {port.name}}}")
                left_idx += 1
            else:
                y_pos = 10 + int(80 * right_idx / max(1, right_pins - 1)) if right_pins > 1 else 50
                lines.append(f"P {{n {port.name} {direction} 140 {y_pos} 140 {y_pos} {port.name}}}")
                right_idx += 1
        
        lines.append(f"T {{n {subckt.name} 70 55 0 0.3 0.3 0 {subckt.name}}}")
        
        return '\n'.join(lines)
    
    def generate_fallback_symbol(self, cell_name: str, num_pins: int = 4) -> str:
        lines = [
            "v {xschem version=3.4.4 file_version=1.2",
            "}",
            "G {}",
            "K {}",
            "V {}",
            "S {}",
            "E {}",
        ]
        
        for i in range(num_pins):
            y = 20 + int(60 * i / max(1, num_pins - 1)) if num_pins > 1 else 50
            if num_pins == 1:
                y = 50
            pin_name = f"p{i + 1}"
            line = f"P {{n {pin_name} inout 0 0 {y} 0 {y} {pin_name}}}"
            lines.append(line)
        
        lines.append(f"T {{n {cell_name} 50 55 0 0.3 0.3 0 {cell_name}}}")
        
        return '\n'.join(lines)


class LayoutEngine:
    def __init__(self, grid: int = 10):
        self.grid = grid
    
    def layout_subckt(self, subckt: Subckt, symbol_sizes: dict[str, tuple[float, float]]) -> dict[tuple, tuple[float, float, float, float]]:
        positions = {}
        
        num_instances = len(subckt.instances)
        if num_instances == 0:
            return positions
        
        cols = max(1, int((num_instances ** 0.5)))
        rows = (num_instances + cols - 1) // cols
        
        block_w = 120
        block_h = 80
        spacing_x = 40
        spacing_y = 30
        
        for idx, inst in enumerate(subckt.instances):
            col = idx % cols
            row = idx // cols
            
            x = 180 + col * (block_w + spacing_x)
            y = 100 + row * (block_h + spacing_y)
            
            inst.x = x
            inst.y = y
            positions[(inst.name, inst.cell)] = (x, y, block_w, block_h)
        
        return positions
    
    def assign_port_positions(self, subckt: Subckt) -> dict[str, tuple[float, float, str]]:
        port_positions = {}
        
        num_ports = len(subckt.ports)
        
        power_ports = [p for p in subckt.ports if 'VDD' in p.name.upper() or 'AVDD' in p.name.upper() or 'DVDD' in p.name.upper()]
        gnd_ports = [p for p in subckt.ports if 'VSS' in p.name.upper() or 'AVSS' in p.name.upper() or 'DVSS' in p.name.upper()]
        input_ports = [p for p in subckt.ports if p not in power_ports and p not in gnd_ports and self._is_likely_input(p.name)]
        output_ports = [p for p in subckt.ports if p not in power_ports and p not in gnd_ports and self._is_likely_output(p.name)]
        other_ports = [p for p in subckt.ports if p not in power_ports and p not in gnd_ports and p not in input_ports and p not in output_ports]
        
        y = 30
        for port in input_ports:
            port_positions[port.name] = (30, y, 'input')
            y += 20
        
        y = 30
        for port in output_ports:
            port_positions[port.name] = (700, y, 'output')
            y += 20
        
        y = 30
        for port in power_ports:
            port_positions[port.name] = (y, 30, 'power')
            y += 20
        
        y = 30 + len(power_ports) * 20
        for port in gnd_ports:
            port_positions[port.name] = (y, 570, 'gnd')
            y += 20
        
        y = 30
        for port in other_ports:
            port_positions[port.name] = (670, y, 'other')
            y += 20
        
        return port_positions
    
    def _is_likely_input(self, name: str) -> bool:
        name_upper = name.upper()
        return 'IN' in name_upper and 'OUT' not in name_upper
    
    def _is_likely_output(self, name: str) -> bool:
        name_upper = name.upper()
        return 'OUT' in name_upper
    
    def calculate_wires(self, subckt: Subckt, inst_positions: dict[tuple, tuple[float, float, float, float]], port_positions: dict[str, tuple[float, float, str]]) -> list[tuple]:
        wires = []
        
        net_map: dict[str, list[tuple[str, str]]] = defaultdict(list)
        
        for inst in subckt.instances:
            inst_key = (inst.name, inst.cell)
            inst_bbox = inst_positions.get(inst_key)
            if not inst_bbox:
                continue
            
            ix, iy, iw, ih = inst_bbox
            
            for pin_idx, net in enumerate(inst.pins):
                side = self._get_pin_side(pin_idx, len(inst.pins))
                if side == 'left':
                    px = ix
                    py = iy + ih // 2 + (pin_idx - len(inst.pins) // 2) * 15
                elif side == 'right':
                    px = ix + iw
                    py = iy + ih // 2 + (pin_idx - len(inst.pins) // 2) * 15
                else:
                    px = ix + iw // 2
                    py = iy
                
                net_map[net].append(('inst', inst.name, px, py))
        
        for port in subckt.ports:
            if port.name in port_positions:
                px, py, _ = port_positions[port.name]
                net_map[port.name].append(('port', port.name, px, py))
        
        for net_name, connections in net_map.items():
            if len(connections) < 2:
                continue
            
            sorted_conns = sorted(connections, key=lambda c: c[2])
            prev = None
            for conn in sorted_conns:
                if prev:
                    wires.append((prev[2], prev[3], conn[2], conn[3]))
                prev = conn
        
        return wires
    
    def _get_pin_side(self, pin_idx: int, total_pins: int) -> str:
        return 'left' if pin_idx < total_pins // 2 else 'right'


class SchematicGenerator:
    def __init__(self, grid: int = 10):
        self.grid = grid
        self.layout_engine = LayoutEngine(grid)
    
    def generate_schematic(self, subckt: Subckt, symbol_refs: dict[str, str], inst_positions: dict[tuple, tuple[float, float, float, float]], port_positions: dict[str, tuple[float, float, str]], wires: list[tuple]) -> str:
        lines = [
            "v {xschem version=3.4.4 file_version=1.2",
            "}",
            "G {}",
            "K {}",
            "V {}",
        ]
        
        for port_name, (x, y, ptype) in port_positions.items():
            direction = "inout"
            line = f"P {{n {port_name} {direction} {x} {y} {x} {y} {port_name}}}"
            lines.append(line)

        for inst in subckt.instances:
            inst_key = (inst.name, inst.cell)
            inst_bbox = inst_positions.get(inst_key)
            if not inst_bbox:
                continue
            
            ix, iy, iw, ih = inst_bbox
            sym_ref = symbol_refs.get(inst.cell, 'local')
            
            if sym_ref == 'local':
                sym_path = inst.cell
            elif sym_ref.startswith('sky130:'):
                lib_name, cell_name = sym_ref.split(':')
                sym_path = f"sky130:{cell_name}"
            elif sym_ref.startswith('local:'):
                sym_path = sym_ref.replace('local:', '')
            elif sym_ref.startswith('include:'):
                sym_path = sym_ref.replace('include:', '')
            else:
                sym_path = inst.cell
            
            line = f"I {{n {inst.name} {ix + iw // 2} {iy + ih // 2} 0 0 {sym_path}}}"
            lines.append(line)
        
        for x1, y1, x2, y2 in wires:
            lines.append(f"W {{n __net0__ {x1} {y1} {x2} {y2}}}")
        
        lines.append("E {}")
        
        return '\n'.join(lines)


class SpiceToXschem:
    def __init__(self, output_dir: str, local_dir: str):
        self.output_dir = output_dir
        self.local_dir = local_dir
        self.parser = SpiceParser()
        self.symbol_resolver = SymbolResolver(output_dir, local_dir)
        self.symbol_gen = SymbolGenerator()
        self.schem_gen = SchematicGenerator()
        self.layout_engine = LayoutEngine()
    
    def process(self, input_file: str) -> dict[str, str]:
        subckts = self.parser.parse_file(input_file)
        
        for inc in self.parser.includes:
            self.symbol_resolver.add_include_dir(inc)
        
        local_subckts = set(subckts.keys())
        symbol_sizes = {}
        
        for name, subckt in subckts.items():
            for inst in subckt.instances:
                sym_type = self.symbol_resolver.resolve(inst.cell, local_subckts)
                if sym_type == 'local':
                    if inst.cell in subckts:
                        num_ports = len(subckts[inst.cell].ports)
                        symbol_sizes[inst.cell] = (140, 100)
        
        generated_files = {}
        
        for name, subckt in subckts.items():
            sym_content = self.symbol_gen.generate_local_symbol(subckt)
            sym_file = os.path.join(self.output_dir, f"{name}.sym")
            with open(sym_file, 'w') as f:
                f.write(sym_content)
            generated_files[f"{name}.sym"] = sym_file
            
            symbol_refs = {}
            for inst in subckt.instances:
                symbol_refs[inst.cell] = self.symbol_resolver.resolve(inst.cell, local_subckts)
            
            inst_positions = self.layout_engine.layout_subckt(subckt, symbol_sizes)
            port_positions = self.layout_engine.assign_port_positions(subckt)
            wires = self.layout_engine.calculate_wires(subckt, inst_positions, port_positions)
            
            sch_content = self.schem_gen.generate_schematic(subckt, symbol_refs, inst_positions, port_positions, wires)
            sch_file = os.path.join(self.output_dir, f"{name}.sch")
            with open(sch_file, 'w') as f:
                f.write(sch_content)
            generated_files[f"{name}.sch"] = sch_file
        
        external_cells = set()
        for subckt in subckts.values():
            for inst in subckt.instances:
                if inst.cell not in local_subckts:
                    external_cells.add(inst.cell)
        
        for cell in external_cells:
            sym_type = self.symbol_resolver.resolve(cell, local_subckts)
            
            if sym_type == 'fallback':
                sym_content = self.symbol_gen.generate_fallback_symbol(cell)
                sym_file = os.path.join(self.output_dir, f"{cell}.sym")
                with open(sym_file, 'w') as f:
                    f.write(sym_content)
                generated_files[f"{cell}.sym"] = sym_file
        
        return generated_files


def main():
    parser = argparse.ArgumentParser(description='SPICE to xschem generator')
    parser.add_argument('input', help='Input SPICE file')
    parser.add_argument('-o', '--output', default='.', help='Output directory')
    parser.add_argument('-l', '--local', default='.', help='Local symbol directory')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.output):
        os.makedirs(args.output)
    
    converter = SpiceToXschem(args.output, args.local)
    files = converter.process(args.input)
    
    print(f"Generated {len(files)} files:")
    for fname, fpath in sorted(files.items()):
        print(f"  {fname}")


if __name__ == '__main__':
    main()