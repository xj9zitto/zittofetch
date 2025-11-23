#!/usr/bin/env python3
"""
gif2ascii_clean.py

Generates clean bounded ASCII frames from a GIF.
Supports:
  --invert
  --color
  Automatic cleanup of old frame_*.txt files before generating new ones.
"""

from PIL import Image, ImageSequence
import argparse
import os
from pathlib import Path

CHARS = "@%#*+=-:. "  # darkest -> lightest


def pixel_to_ansi(r, g, b, char):
    return f"\033[38;2;{r};{g};{b}m{char}\033[0m"


def frame_to_ascii_bounded(frame, box_w, box_h, use_color=False, invert=False):
    """Convert image frame into bounded ASCII (color optional)."""
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
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(rows))


def clean_old_frames(out_dir: Path):
    """Remove all old frame_*.txt files before generating new ones."""
    removed = 0
    for f in out_dir.glob("frame_*.txt"):
        try:
            f.unlink()
            removed += 1
        except Exception:
            pass
    return removed


def main():
    p = argparse.ArgumentParser(description="gif2ascii_clean - generate clean bounded ASCII frames")
    p.add_argument("--input", "-i", required=True, help="Input animated GIF file")
    p.add_argument("--out", "-o", required=True, help="Folder for frame_*.txt output")
    p.add_argument("--width", type=int, default=40)
    p.add_argument("--height", type=int, default=20)
    p.add_argument("--color", action="store_true")
    p.add_argument("--invert", action="store_true")
    args = p.parse_args()

    input_path = Path(args.input).expanduser()
    out_dir = Path(args.out).expanduser()

    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        return

    out_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------
    # CLEANUP OLD FRAMES
    # ------------------------------------------------------
    removed = clean_old_frames(out_dir)
    if removed > 0:
        print(f"🔥 Removed {removed} old frame files.")
    else:
        print("No old frames found — clean start.")

    # ------------------------------------------------------
    # GENERATE NEW FRAMES
    # ------------------------------------------------------
    try:
        img = Image.open(input_path)
    except Exception as e:
        print(f"Error loading image: {e}")
        return

    count = 0
    for i, frame in enumerate(ImageSequence.Iterator(img)):
        rows = frame_to_ascii_bounded(
            frame.copy(),
            args.width,
            args.height,
            use_color=args.color,
            invert=args.invert
        )

        out_path = out_dir / f"frame_{i}.txt"
        save_frame_rows(rows, out_path)
        print(f"Saved frame {i} → {out_path}")
        count += 1

    print(f"\n✅ DONE — Generated {count} frames into {out_dir}")


if __name__ == "__main__":
    main()
