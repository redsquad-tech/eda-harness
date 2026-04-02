#!/usr/bin/env python3
"""
Convert SVG schematic to Unicode ASCII art.
Supports: wires, arcs, circles, rectangles, arrows, diagonals.

Usage: python3 svg2unicode.py <file.svg> [width]
"""
import re
import sys
import math
import argparse

# ─────────────────────────────────────────────────────────────────────────────
# Unicode symbols
# ─────────────────────────────────────────────────────────────────────────────

# Wires
H = '─'      # horizontal
V = '│'      # vertical
CROSS = '┼'  # cross junction
T_UP = '┴'   # T up
T_DOWN = '┬' # T down
T_LEFT = '┤' # T left
T_RIGHT = '├'# T right

# Diagonals
DL = '╱'     # diagonal / (bottom-left to top-right)
DR = '╲'     # diagonal \ (top-left to bottom-right)

# Arcs/corners
ARC_TL = '╭'  # top-left
ARC_TR = '╮'  # top-right
ARC_BL = '╰'  # bottom-left
ARC_BR = '╯'  # bottom-right

# Shapes
CIRCLE_O = '○'   # open circle
CIRCLE_F = '●'   # filled circle
CIRCLE_D = '◍'   # dotted circle
SQUARE = '□'     # open square
SQUARE_F = '■'   # filled square

# Arrows
ARROW_U = '▲'    # up
ARROW_D = '▼'    # down
ARROW_L = '◀'    # left
ARROW_R = '▶'    # right
ARROW_UR = '↗'   # up-right
ARROW_DR = '↘'   # down-right
ARROW_DL = '↙'   # down-left
ARROW_UL = '↖'   # up-left

# Electronics (Unicode standard)
GROUND = '⏚'     # earth ground
FUSE = '⏛'       # fuse
OHM = 'Ω'        # ohm
MHO = '℧'        # mho (inverted ohm)
AC = '~'         # AC source
HIGH_VOLT = '⚡'  # high voltage

# Electronics (composite symbols - drawn as combinations)
# These are rendered by drawing multiple characters
DIODE = '▶│'     # diode
ZENER = '▶╲'     # zener diode  
LED = '▶│↑'      # LED
RESISTOR = '▭'   # resistor (IEC)
RESISTOR_US = '╱╲' # resistor (US zigzag segment)
CAPACITOR = '││'  # capacitor
INDUCTOR = '∿'   # inductor loop
TRANSISTOR_NPN = '├▷┤'  # NPN transistor
TRANSISTOR_PNP = '├◁┤'  # PNP transistor
OPAMP = '▷├'     # op-amp triangle

# Connection dots
DOT = '•'
DOT_BIG = '⦿'    # dot with circle


# ─────────────────────────────────────────────────────────────────────────────
# Main converter class
# ─────────────────────────────────────────────────────────────────────────────

class SVGSchematic:
    def __init__(self, svg_file, out_width=100):
        self.svg_file = svg_file
        self.out_width = out_width
        
        # Parse SVG dimensions
        self.svg_w, self.svg_h = self._get_svg_dims()
        
        # Calculate output height (terminal chars ~2x taller than wide)
        char_aspect = 2.0
        self.out_height = int(out_width * (self.svg_h / self.svg_w) / char_aspect)
        self.out_height = max(20, min(self.out_height, 60))
        
        # Scale factors
        self.scale_x = self.out_width / self.svg_w
        self.scale_y = self.out_height / self.svg_h
        
        # Grid
        self.grid = [[' ' for _ in range(self.out_width)] for _ in range(self.out_height)]
        
        # Statistics
        self.stats = {
            'lines': 0, 'polylines': 0, 'paths': 0,
            'circles': 0, 'rects': 0, 'polygons': 0,
            'arcs': 0, 'arrows': 0
        }
        
    def _get_svg_dims(self):
        """Extract SVG viewBox or width/height"""
        with open(self.svg_file, 'r') as f:
            content = f.read(2000)
        
        m = re.search(r'viewBox="[\d.]+\s+[\d.]+\s+([\d.]+)\s+([\d.]+)"', content)
        if m:
            return float(m.group(1)), float(m.group(2))
        
        w = re.search(r'width="([\d.]+)"', content)
        h = re.search(r'height="([\d.]+)"', content)
        if w and h:
            return float(w.group(1)), float(h.group(1))
        
        return 459, 339
    
    def to_grid(self, x, y):
        """Convert SVG coordinates to grid coordinates"""
        gx = int(x * self.scale_x)
        gy = int(y * self.scale_y)
        return (max(0, min(gx, self.out_width - 1)),
                max(0, min(gy, self.out_height - 1)))
    
    def set_char(self, x, y, char):
        """Set character with smart merging"""
        if 0 <= x < self.out_width and 0 <= y < self.out_height:
            old = self.grid[y][x]
            
            if old == ' ':
                self.grid[y][x] = char
                return
            
            # Merge logic
            if char in [H, V, CROSS, T_UP, T_DOWN, T_LEFT, T_RIGHT]:
                if old == ' ':
                    self.grid[y][x] = char
                elif old == H and char == V:
                    self.grid[y][x] = CROSS
                elif old == V and char == H:
                    self.grid[y][x] = CROSS
                elif old in [H, CROSS]:
                    self.grid[y][x] = H
                elif old in [V, CROSS]:
                    self.grid[y][x] = V
            elif char in [DL, DR]:
                if old == ' ':
                    self.grid[y][x] = char
            elif char in [CIRCLE_O, CIRCLE_F, CIRCLE_D]:
                if old == ' ':
                    self.grid[y][x] = char
            elif char in [SQUARE, SQUARE_F]:
                if old == ' ':
                    self.grid[y][x] = char
            elif char in [ARROW_U, ARROW_D, ARROW_L, ARROW_R]:
                if old == ' ':
                    self.grid[y][x] = char
    
    # ─────────────────────────────────────────────────────────────────────────
    # Drawing primitives
    # ─────────────────────────────────────────────────────────────────────────
    
    def draw_h_line(self, x1, x2, y):
        """Draw horizontal line"""
        for x in range(min(x1, x2), max(x1, x2) + 1):
            self.set_char(x, y, H)
    
    def draw_v_line(self, y1, y2, x):
        """Draw vertical line"""
        for y in range(min(y1, y2), max(y1, y2) + 1):
            self.set_char(x, y, V)
    
    def draw_line(self, x1, y1, x2, y2):
        """Draw line between two points"""
        gx1, gy1 = self.to_grid(x1, y1)
        gx2, gy2 = self.to_grid(x2, y2)
        
        if gx1 == gx2 and gy1 == gy2:
            self.set_char(gx1, gy1, DOT)
            return
        
        # Exact horizontal
        if gy1 == gy2:
            self.draw_h_line(gx1, gx2, gy1)
            return
        
        # Exact vertical
        if gx1 == gx2:
            self.draw_v_line(gy1, gy2, gx1)
            return
        
        # Diagonal - Bresenham
        dx = abs(gx2 - gx1)
        dy = abs(gy2 - gy1)
        x, y = gx1, gy1
        sx = 1 if gx2 > gx1 else -1
        sy = 1 if gy2 > gy1 else -1
        err = dx - dy
        
        while True:
            # Choose diagonal character based on direction
            if sy > 0:  # Going down
                char = DR if sx > 0 else DL  # \ or /
            else:  # Going up
                char = DL if sx > 0 else DR  # / or \
            
            self.set_char(x, y, char)
            
            if x == gx2 and y == gy2:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy
    
    def draw_polyline(self, points_str):
        """Draw polyline from SVG points"""
        nums = [float(n) for n in re.findall(r'[\d.]+', points_str)]
        points = [(nums[i], nums[i+1]) for i in range(0, len(nums)-1, 2)]
        
        for i in range(len(points) - 1):
            self.draw_line(points[i][0], points[i][1], 
                          points[i+1][0], points[i+1][1])
    
    def draw_rect(self, x, y, w, h, filled=False):
        """Draw rectangle"""
        gx, gy = self.to_grid(x, y)
        gw = max(1, int(w * self.scale_x))
        gh = max(1, int(h * self.scale_y))
        
        char_outline = SQUARE_F if filled else SQUARE
        
        # For small rects, use single char
        if gw <= 2 and gh <= 2:
            self.set_char(gx, gy, char_outline)
            return
        
        # Top and bottom
        for dx in range(gw):
            self.set_char(gx + dx, gy, H)
            self.set_char(gx + dx, gy + gh - 1, H)
        
        # Sides
        for dy in range(gh):
            self.set_char(gx, gy + dy, V)
            self.set_char(gx + gw - 1, gy + dy, V)
        
        # Corners
        self.set_char(gx, gy, '┌')
        self.set_char(gx + gw - 1, gy, '┐')
        self.set_char(gx, gy + gh - 1, '└')
        self.set_char(gx + gw - 1, gy + gh - 1, '┘')
    
    def draw_circle(self, cx, cy, r, filled=False):
        """Draw circle"""
        gcx, gcy = self.to_grid(cx, cy)
        gr = max(1, int(r * self.scale_x))
        
        # For small circles, use single symbol
        if gr <= 1:
            self.set_char(gcx, gcy, CIRCLE_F if filled else CIRCLE_O)
            return
        
        # Draw circle using parametric equation
        for angle in range(0, 360, 5):
            rad = math.radians(angle)
            # Adjust for character aspect ratio
            ox = int(gr * math.cos(rad))
            oy = int(gr * 0.5 * math.sin(rad))  # Compress Y for char aspect
            
            self.set_char(gcx + ox, gcy + oy, CIRCLE_F if filled else CIRCLE_O)
    
    def draw_arrow(self, points, direction='auto'):
        """Draw arrow from polygon points"""
        coords = [float(x) for x in points.split()]
        
        if len(coords) < 6:
            return
        
        # Calculate centroid
        cx = sum(coords[::2]) / len(coords[::2])
        cy = sum(coords[1::2]) / len(coords[1::2])
        
        # Find the point furthest from centroid (arrow tip)
        max_dist = 0
        tip_x, tip_y = cx, cy
        
        for i in range(0, len(coords), 2):
            dx = coords[i] - cx
            dy = coords[i+1] - cy
            dist = dx*dx + dy*dy
            if dist > max_dist:
                max_dist = dist
                tip_x, tip_y = coords[i], coords[i+1]
        
        # Determine direction
        gx, gy = self.to_grid(tip_x, tip_y)
        
        # Find direction from centroid to tip
        if abs(tip_x - cx) > abs(tip_y - cy):
            arrow = ARROW_R if tip_x > cx else ARROW_L
        else:
            arrow = ARROW_D if tip_y > cy else ARROW_U
        
        self.set_char(gx, gy, arrow)
        self.stats['arrows'] += 1
    
    def draw_arc(self, x, y, rx, ry, start_angle, end_angle, large_arc=False, sweep=False):
        """Draw arc (simplified - uses corner chars)"""
        gx, gy = self.to_grid(x, y)
        
        # Determine which corner based on angles
        # This is simplified - real SVG arcs are more complex
        dx = rx * self.scale_x
        dy = ry * self.scale_y * 0.5
        
        if start_angle == 0 and end_angle == 90:
            char = ARC_BR
        elif start_angle == 90 and end_angle == 180:
            char = ARC_BL
        elif start_angle == 180 and end_angle == 270:
            char = ARC_TR
        elif start_angle == 270 and end_angle == 360:
            char = ARC_TL
        else:
            # Generic - use diagonal
            char = DR if sweep else DL
        
        self.set_char(gx, gy, char)
        self.stats['arcs'] += 1
    
    # ─────────────────────────────────────────────────────────────────────────
    # Path parsing
    # ─────────────────────────────────────────────────────────────────────────
    
    def _draw_path(self, d):
        """Parse SVG path commands"""
        x, y = 0.0, 0.0
        start_x, start_y = 0.0, 0.0
        
        # Better number parsing - handles cases like "1.87.4"
        def parse_nums(s):
            # Replace . followed by digit (not at end) with space
            s = re.sub(r'\.(?=\d)', ' .', s)
            return [float(n) for n in re.findall(r'-?[\d.]+', s) if n and n != '.']
        
        # Parse all commands
        cmds = re.findall(r'([MLHVCSQTAZ])([\d.,\-\s]+)|([a-z])([\d.,\-\s]+)', d)
        
        for m in cmds:
            if m[0]:  # Absolute command
                cmd, params = m[0], m[1]
                relative = False
            else:  # Relative command
                cmd, params = m[2], m[3]
                relative = True
            
            nums = parse_nums(params)
            
            if not nums and cmd.upper() in ['Z', 'S']:
                # Command without params
                if cmd.upper() == 'Z':
                    x, y = start_x, start_y
                continue
            
            try:
                if cmd.upper() == 'M':  # Move to
                    if relative:
                        x += nums[0]
                        y += nums[1]
                    else:
                        x, y = nums[0], nums[1]
                    start_x, start_y = x, y
                
                elif cmd.upper() == 'L':  # Line to
                    nx, ny = nums[0], nums[1]
                    if relative:
                        nx += x
                        ny += y
                    self.draw_line(x, y, nx, ny)
                    x, y = nx, ny
                
                elif cmd.upper() == 'H':  # Horizontal line
                    nx = nums[0]
                    if relative:
                        nx += x
                    self.draw_line(x, y, nx, y)
                    x = nx
                
                elif cmd.upper() == 'V':  # Vertical line
                    ny = nums[0]
                    if relative:
                        ny += y
                    self.draw_line(x, y, x, ny)
                    y = ny
                
                elif cmd.upper() == 'A':  # Arc
                    rx, ry, rot, large, sweep, nx, ny = nums[0], nums[1], nums[2], nums[3], nums[4], nums[5], nums[6]
                    if relative:
                        nx += x
                        ny += y
                    
                    # Draw arc as series of points
                    self._draw_arc_points(x, y, nx, ny, rx, ry, large, sweep)
                    x, y = nx, ny
                
                elif cmd.upper() == 'C':  # Cubic bezier
                    # Simplify to line
                    nx, ny = nums[-2], nums[-1]
                    if relative:
                        nx += x
                        ny += y
                    self.draw_line(x, y, nx, ny)
                    x, y = nx, ny
                
                elif cmd.upper() == 'Z':  # Close path
                    x, y = start_x, start_y
                    
            except (IndexError, ValueError) as e:
                pass
    
    def _draw_arc_points(self, x1, y1, x2, y2, rx, ry, large_arc, sweep):
        """Draw arc as series of points"""
        # Simplified arc drawing
        steps = 10
        for i in range(steps + 1):
            t = i / steps
            # Linear interpolation with arc approximation
            x = x1 + (x2 - x1) * t
            y = y1 + (y2 - y1) * t
            
            # Add arc bulge
            bulge = math.sin(math.pi * t) * max(rx, ry) * 0.3
            if not sweep:
                bulge = -bulge
            
            gx, gy = self.to_grid(x, y + bulge)
            self.set_char(gx, gy, H)
        
        self.stats['arcs'] += 1
    
    # ─────────────────────────────────────────────────────────────────────────
    # Main render
    # ─────────────────────────────────────────────────────────────────────────
    
    def render(self, shapes=True, arrows=True):
        """Parse SVG and render
        
        Args:
            shapes: Render circles and rectangles
            arrows: Render arrow symbols
        """
        with open(self.svg_file, 'r') as f:
            content = f.read()
        
        # Polylines (wires)
        for pts in re.findall(r'<polyline[^>]*points="([^"]*)"', content):
            self.draw_polyline(pts)
            self.stats['polylines'] += 1
        
        # Lines
        for m in re.finditer(
            r'<line[^>]*x1="([\d.]+)"[^>]*y1="([\d.]+)"[^>]*x2="([\d.]+)"[^>]*y2="([\d.]+)"',
            content
        ):
            self.draw_line(
                float(m.group(1)), float(m.group(2)),
                float(m.group(3)), float(m.group(4))
            )
            self.stats['lines'] += 1
        
        # Rectangles
        if shapes:
            for m in re.finditer(
                r'<rect[^>]*x="([\d.]+)"[^>]*y="([\d.]+)"[^>]*width="([\d.]+)"[^>]*height="([\d.]+)"',
                content
            ):
                x, y, w, h = float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4))
                filled = 'filled' in m.group(0) or 'solid' in m.group(0)
                self.draw_rect(x, y, w, h, filled)
                self.stats['rects'] += 1
            
            # Circles
            for m in re.finditer(
                r'<circle[^>]*cx="([\d.]+)"[^>]*cy="([\d.]+)"[^>]*r="([\d.]+)"',
                content
            ):
                cx, cy, r = float(m.group(1)), float(m.group(2)), float(m.group(3))
                filled = 'filled' in m.group(0)
                self.draw_circle(cx, cy, r, filled)
                self.stats['circles'] += 1
        
        # Polygons (arrows)
        if arrows:
            for pts in re.findall(r'<polygon[^>]*points="([^"]*)"', content):
                self.draw_arrow(pts)
                self.stats['polygons'] += 1
        
        # Paths
        for d in re.findall(r'<path[^>]*d="([^"]*)"[^>]*>', content):
            self._draw_path(d)
            self.stats['paths'] += 1
    
    def output(self, show_info=False, show_legend=False):
        """Print rendered schematic"""
        border = '+' + '-' * self.out_width + '+'
        
        print(border)
        for row in self.grid:
            print('|' + ''.join(row) + '|')
        print(border)
        
        if show_info:
            print(f"\nSVG: {self.svg_w:.0f}x{self.svg_h:.0f} → Grid: {self.out_width}x{self.out_height}", 
                  file=sys.stderr)
            print(f"Scale: {self.scale_x:.3f} x {self.scale_y:.3f}", file=sys.stderr)
            print(f"Elements: {sum(self.stats.values())} total", file=sys.stderr)
            for k, v in self.stats.items():
                if v > 0:
                    print(f"  {k}: {v}", file=sys.stderr)
        
        if show_legend:
            print("\nSymbols:", file=sys.stderr)
            print("  Wires:      ─  │  ┼  ┬  ┴  ├  ┤", file=sys.stderr)
            print("  Diagonals:  ╱  ╲", file=sys.stderr)
            print("  Arcs:       ╭  ╮  ╯  ╰", file=sys.stderr)
            print("  Circles:    ○  ●  ◍", file=sys.stderr)
            print("  Squares:    □  ■", file=sys.stderr)
            print("  Arrows:     ▲  ▼  ◀  ▶", file=sys.stderr)
            print("  Dots:       •  ⦿", file=sys.stderr)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Convert SVG schematic to Unicode ASCII art',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s schematic.svg           # Default width (100 chars)
  %(prog)s schematic.svg 80        # Standard terminal
  %(prog)s schematic.svg 120 -i    # High detail with info
  %(prog)s schematic.svg 100 -e    # With electronics symbols

Recommended widths:
  80   - Standard terminal
  100  - Good balance (default)
  120  - High detail
  150  - Maximum detail

Electronics symbols (-e, --electronics):
  Uses special Unicode characters for electronic components:
  ⏚ Ground  ⏛ Fuse  Ω Ohm  ~ AC
  ▭ Resistor  ││ Capacitor  ∿ Inductor
'''
    )
    parser.add_argument('svg_file', help='Input SVG file')
    parser.add_argument('width', nargs='?', type=int, default=100,
                       help='Output width (default: 100, range: 60-150)')
    parser.add_argument('-i', '--info', action='store_true',
                       help='Show conversion info')
    parser.add_argument('-l', '--legend', action='store_true',
                       help='Show symbol legend')
    parser.add_argument('--no-shapes', action='store_true',
                       help='Disable circles/rectangles (wires only)')
    parser.add_argument('--no-arrows', action='store_true',
                       help='Disable arrow symbols')
    parser.add_argument('-e', '--electronics', action='store_true',
                       help='Use electronics symbols')
    
    args = parser.parse_args()
    width = max(60, min(args.width, 150))
    
    schematic = SVGSchematic(args.svg_file, width)
    schematic.render(
        shapes=not args.no_shapes,
        arrows=not args.no_arrows
    )
    schematic.output(show_info=args.info, show_legend=args.legend)


if __name__ == '__main__':
    main()
