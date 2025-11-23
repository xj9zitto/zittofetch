#!/usr/bin/env python3
"""
gif2ascii_clean.py

Generates cleaned bounded ASCII frames from a GIF. Supports --invert and --color.

Usage:
  python gif2ascii_clean.py --input input.gif --out /path/to/frames --width 40 --height 20 --color --invert
"""

from PIL import Image, ImageSequence
import argparse
import os

CHARS = "@%#*+=-:. "  # darkest -> lightest

def pixel_to_ansi(r, g, b, char):
    return f"\033[38;2;{r};{g};{b}m{char}\033[0m"

def frame_to_ascii_bounded(frame, box_w, box_h, use_color=False, invert=False):
    """
    Resize a PIL Image `frame` into a box exactly box_w x box_h and
    convert to a list of strings (each string is one row).
    If use_color is True, each character is wrapped with 24-bit ANSI color.
    """
    # Use a good resample filter for better downscaling
    frame = frame.convert("RGB").resize((box_w, box_h), Image.LANCZOS)
    gray = frame.convert("L")
    rgb = frame

    rows = []
    for y in range(box_h):
        line = []
        for x in range(box_w):
            p = gray.getpixel((x, y))
            if invert:
                p = 255 - p
            idx = int((p / 255) * (len(CHARS) - 1))
            ch = CHARS[idx]
            if use_color:
                r, g, b = rgb.getpixel((x, y))
                ch = pixel_to_ansi(r, g, b, ch)
            line.append(ch)
        rows.append("".join(line))
    return rows

def save_frame_rows(rows, path):
    # Save rows (list of strings) as UTF-8 text file
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(rows))

def main():
    p = argparse.ArgumentParser(description="gif2ascii_clean - generate clean bounded ASCII frames")
    p.add_argument("--input", "-i", required=True, help="Input animated GIF path")
    p.add_argument("--out", "-o", required=True, help="Output folder for frames (frame_0.txt, ...)")
    p.add_argument("--width", type=int, default=40, help="Frame width (columns)")
    p.add_argument("--height", type=int, default=20, help="Frame height (lines)")
    p.add_argument("--color", action="store_true", help="Generate colored ASCII (24-bit ANSI)")
    p.add_argument("--invert", action="store_true", help="Invert brightness when mapping characters")
    args = p.parse_args()

    if not os.path.isfile(args.input):
        print(f"Input file not found: {args.input}")
        return

    os.makedirs(args.out, exist_ok=True)

    try:
        img = Image.open(args.input)
    except Exception as e:
        print(f"Failed to open image: {e}")
        return

    count = 0
    for i, frame in enumerate(ImageSequence.Iterator(img)):
        rows = frame_to_ascii_bounded(frame.copy(), args.width, args.height, use_color=args.color, invert=args.invert)
        out_path = os.path.join(args.out, f"frame_{i}.txt")
        save_frame_rows(rows, out_path)
        print(f"Saved frame {i} -> {out_path}")
        count += 1

    print(f"Done. Generated {count} frames into {os.path.abspath(args.out)}")

if __name__ == "__main__":
    main()
