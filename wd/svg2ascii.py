#!/usr/bin/env python3
"""Convert SVG to ASCII art - with inversion for line drawings"""
import sys
import re
from subprocess import run, PIPE, DEVNULL

SVG_FILE = sys.argv[1] if len(sys.argv) > 1 else "ts-25.svg"
WIDTH = int(sys.argv[2]) if len(sys.argv) > 2 else 80

def parse_rgb(line):
    match = re.search(r'rgba?\((\d+),(\d+),(\d+)', line, re.I)
    if match:
        return int(match.group(1)), int(match.group(2)), int(match.group(3))
    return 255, 255, 255

def render_ascii(chars, threshold_func, invert=False):
    convert = run([
        "convert", SVG_FILE, "-background", "white", "-alpha", "remove",
        "-resize", f"{WIDTH}x{WIDTH*3//4}",
        "-negate" if invert else "",
        "txt:"
    ], stdout=PIPE, stderr=DEVNULL, text=True)
    
    lines = convert.stdout.strip().split("\n")[1:]
    img = [parse_rgb(line) for line in lines]
    
    height = len(lines) // WIDTH if WIDTH else 0
    for y in range(height):
        start = y * WIDTH
        if start + WIDTH <= len(img):
            row = ""
            for x in range(start, start + WIDTH):
                r, g, b = img[x]
                row += chars[threshold_func(r, g, b)]
            print(row)

# Method 1: Simple grayscale (inverted for line drawings)
print("=== METHOD 1: Simple Grayscale (inverted) ===\n")
chars1 = " .:-=+*#%@"
render_ascii(chars1, lambda r,g,b: min(len(chars1)-1, (r+g+b)//3 // 28), invert=True)

# Method 2: High contrast  
print("\n=== METHOD 2: High Contrast (inverted) ===\n")
chars2 = " ░▒▓█"
render_ascii(chars2, lambda r,g,b: min(len(chars2)-1, int((r+g+b)/3 / 255 * len(chars2))), invert=True)

# Method 3: Binary - best for technical drawings
print("\n=== METHOD 3: Binary B/W (inverted) ===\n")
chars3 = " █"
render_ascii(chars3, lambda r,g,b: 1 if (r+g+b)//3 < 200 else 0, invert=True)

# Method 4: Detailed with more chars
print("\n=== METHOD 4: Detailed 64-level (inverted) ===\n")
chars4 = " .'`^\",:;Il!i~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"
render_ascii(chars4, lambda r,g,b: min(len(chars4)-1, (r+g+b)//3 // 4), invert=True)

# Method 5: Colored ANSI (no invert for colors)
print("\n=== METHOD 5: ANSI Color ===\n")
convert = run([
    "convert", SVG_FILE, "-background", "white", "-alpha", "remove",
    "-resize", f"{WIDTH//2}x{WIDTH*3//8}", "txt:"
], stdout=PIPE, stderr=DEVNULL, text=True)

lines = convert.stdout.strip().split("\n")[1:]
w = WIDTH // 2
height = len(lines) // w if w else 0

for y in range(height):
    start = y * w
    row = ""
    for x in range(start, min(start + w, len(lines))):
        r, g, b = parse_rgb(lines[x])
        if r > 240 and g > 240 and b > 240:
            row += " "
        else:
            color = 16 + (r//43)*36 + (g//43)*6 + (b//43)
            row += f"\033[38;5;{color}m▄\033[0m"
    print(row)

# Method 6: Braille (high res, inverted)
print("\n=== METHOD 6: Braille (high resolution) ===\n")
convert = run([
    "convert", SVG_FILE, "-background", "white", "-alpha", "remove",
    "-negate", "-resize", f"{WIDTH*2}x{WIDTH*3//4}", "txt:"
], stdout=PIPE, stderr=DEVNULL, text=True)

lines = convert.stdout.strip().split("\n")[1:]
w = WIDTH * 2
h = len(lines) // w if w else 0

braille = " ⠁⠂⠃⠄⠅⠆⠇⠈⠉⠊⠋⠌⠍⠎⠏⠐⠑⠒⠓⠔⠕⠖⠗⠘⠙⠚⠛⠜⠝⠞⠟⠠⠡⠢⠣⠤⠥⠦⠧⠨⠩⠪⠫⠬⠭⠮⠯⠰⠱⠲⠳⠴⠵⠶⠷⠸⠹⠺⠻⠼⠽⠾⠿"

img = []
for line in lines:
    r, g, b = parse_rgb(line)
    img.append(1 if (r+g+b)//3 < 180 else 0)

for y in range(h // 4):
    row = ""
    for x in range(w // 2):
        bits = 0
        for dy in range(4):
            for dx in range(2):
                py, px = y * 4 + dy, x * 2 + dx
                idx = py * w + px
                if idx < len(img) and img[idx]:
                    bits |= 1 << (dy * 2 + dx)
        row += braille[min(len(braille)-1, bits)]
    print(row)
