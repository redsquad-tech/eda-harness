#!/usr/bin/env python3
"""Convert SVG to ASCII using vector paths directly"""
import re
import math
from collections import defaultdict

# SVG dimensions
SVG_W, SVG_H = 459, 339

# Output dimensions
OUT_W, OUT_H = 100, 40

# Scale factors
SCALE_X = OUT_W / SVG_W
SCALE_Y = OUT_H / SVG_H

# Grid to store characters
grid = [[' ' for _ in range(OUT_W)] for _ in range(OUT_H)]

# Unicode box drawing chars
H_LINE = '─'  # horizontal
V_LINE = '│'  # vertical
TL = '┌'      # top-left
TR = '┐'      # top-right
BL = '└'      # bottom-left
BR = '┘'      # bottom-right
CROSS = '┼'   # cross
T_RIGHT = '├' # T right
T_LEFT = '┤'  # T left
T_DOWN = '┬'  # T down
T_UP = '┴'    # T up
DIAG_L = '╱'  # diagonal /
DIAG_R = '╲'  # diagonal \
DOT = '•'     # connection dot
CIRCLE_O = '○' # open circle
FILLED = '●'  # filled circle

def svg_to_grid(x, y):
    """Convert SVG coords to grid coords"""
    gx = int(x * SCALE_X)
    gy = int(y * SCALE_Y)
    return max(0, min(gx, OUT_W-1)), max(0, min(gy, OUT_H-1))

def set_char(x, y, char):
    """Set character at grid position, handling overlaps"""
    if 0 <= x < OUT_W and 0 <= y < OUT_H:
        old = grid[y][x]
        if old == ' ':
            grid[y][x] = char
        elif old == H_LINE and char == V_LINE:
            grid[y][x] = CROSS
        elif old == V_LINE and char == H_LINE:
            grid[y][x] = CROSS
        elif old in [H_LINE, CROSS] and char in [H_LINE, CROSS]:
            grid[y][x] = H_LINE
        elif old in [V_LINE, CROSS] and char in [V_LINE, CROSS]:
            grid[y][x] = V_LINE

def draw_h_line(x1, x2, y):
    """Draw horizontal line"""
    for x in range(min(x1, x2), max(x1, x2) + 1):
        set_char(x, y, H_LINE)

def draw_v_line(y1, y2, x):
    """Draw vertical line"""
    for y in range(min(y1, y2), max(y1, y2) + 1):
        set_char(x, y, V_LINE)

def draw_line(x1, y1, x2, y2):
    """Draw line using Bresenham algorithm"""
    x1, y1 = svg_to_grid(x1, y1)
    x2, y2 = svg_to_grid(x2, y2)
    
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    
    if dx == 0 and dy == 0:
        set_char(x1, y1, DOT)
        return
    
    if dx > dy:
        # More horizontal
        if y1 == y2:
            draw_h_line(x1, x2, y1)
        else:
            x, y = x1, y1
            sx = 1 if x2 > x1 else -1
            sy = 1 if y2 > y1 else -1
            err = dx // 2
            while x != x2 + sx:
                set_char(x, y, H_LINE if abs(x2-x1) > abs(y2-y1) else DIAG_R if sy > 0 else DIAG_L)
                err -= dy
                if err < 0:
                    y += sy
                    err += dx
                x += sx
    else:
        # More vertical
        if x1 == x2:
            draw_v_line(y1, y2, x1)
        else:
            x, y = x1, y1
            sx = 1 if x2 > x1 else -1
            sy = 1 if y2 > y1 else -1
            err = dy // 2
            while y != y2 + sy:
                set_char(x, y, V_LINE)
                err -= dx
                if err < 0:
                    x += sx
                    err += dy
                y += sy

def draw_polyline(points_str):
    """Draw polyline from points string"""
    points = re.findall(r'[\d.]+', points_str)
    coords = [(float(points[i]), float(points[i+1])) for i in range(0, len(points), 2)]
    
    for i in range(len(coords) - 1):
        draw_line(coords[i][0], coords[i][1], coords[i+1][0], coords[i+1][1])

def draw_path(d):
    """Parse and draw SVG path - simplified"""
    try:
        # Extract just H (horizontal) commands which are simple
        for x in re.findall(r'H([\d.]+)', d):
            draw_line(0, 0, float(x), 0)  # Will be relative, need tracking
    except:
        pass

def add_dot(x, y):
    """Add connection dot"""
    gx, gy = svg_to_grid(x, y)
    set_char(gx, gy, DOT)

# Parse SVG
with open('ts-25.svg', 'r') as f:
    content = f.read()

# Draw polylines (wires)
for points in re.findall(r'<polyline[^>]*points="([^"]*)"', content):
    draw_polyline(points)

# Draw lines
for x1, y1, x2, y2 in re.findall(r'<line[^>]*x1="([^"]*)"[^>]*y1="([^"]*)"[^>]*x2="([^"]*)"[^>]*y2="([^"]*)"', content):
    draw_line(float(x1), float(y1), float(x2), float(y2))

# Skip complex paths for now - focus on lines and polylines
# Paths contain transistors/symbols that need special handling

# Output
print("╔" + "═" * OUT_W + "╗")
for row in grid:
    print("║" + "".join(row) + "║")
print("╚" + "═" * OUT_W + "╝")
print(f"\nSize: {OUT_W}x{OUT_H}, SVG: {SVG_W}x{SVG_H}")
