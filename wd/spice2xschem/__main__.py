#!/usr/bin/env python3
"""
SPICE to xschem converter CLI
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spice2xschem import SpiceToXschem
import argparse


def main():
    parser = argparse.ArgumentParser(
        description='Convert SPICE netlist to xschem (.sch/.sym) files'
    )
    parser.add_argument('input', help='Input SPICE netlist file')
    parser.add_argument('-o', '--output', default='.', help='Output directory')
    parser.add_argument('-l', '--local', default='.', help='Local symbol search directory')
    parser.add_argument('-p', '--pdk', default=None, help='Sky130 PDK path (default: SKY130_PDK_PATH env or /usr/local/share/pdk/sky130A)')
    
    args = parser.parse_args()
    
    if args.pdk:
        os.environ['SKY130_PDK_PATH'] = args.pdk
    
    if not os.path.exists(args.output):
        os.makedirs(args.output)
    
    converter = SpiceToXschem(args.output, args.local)
    files = converter.process(args.input)
    
    print(f"Generated {len(files)} files:")
    for fname in sorted(files.keys()):
        print(f"  {fname}")


if __name__ == '__main__':
    main()