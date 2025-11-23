#!/usr/bin/env python3
"""
gifzittofetch.py

Animated ASCII (left) + Fastfetch-style specs (right) with a vertical separator.

Features:
 - Auto-detects many system modules (OS, host, kernel, uptime, cpu, gpu, memory, swap, disk, packages, shell, display, de, wm, wmtheme, theme, icons, font, cursor, terminal, terminalfont, localip, battery, poweradapter, locale, colors)
 - Skips modules not available on the system
 - Safe ANSI handling & wide-char-aware width measurement (uses wcwidth if available)
 - Loads ASCII frames from directory (frame_0.txt ...), ensures a locked bounding box
 - Optionally generate frames from GIF using Pillow (--gen-frames)
 - Prints a vertical separator between ASCII animation and specs
"""

from pathlib import Path
import argparse
import os
import re
import shutil
import subprocess
import sys
import time

# Optional imports
try:
    from PIL import Image, ImageSequence
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

try:
    from wcwidth import wcswidth
except Exception:
    wcswidth = None

# ---------------- constants ----------------
DEFAULT_ANIM_DIR = os.path.expanduser("~/.local/share/gifzitto/anim")
ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')
CHARS = "@%#*+=-:. "  # used if generating frames inline
DEFAULT_WIDTH = 40
DEFAULT_HEIGHT = 20
DEFAULT_FPS = 12.0
SEPARATOR_CHAR = " │ "  # vertical separator (with spacing)

# ---------------- utilities ----------------
def run(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return None

def visible_width(s: str) -> int:
    """Return visible width ignoring ANSI codes and counting wide chars properly."""
    clean = ANSI_RE.sub('', s)
    if wcswidth:
        w = wcswidth(clean)
        if w >= 0:
            return w
    # fallback heuristic: treat many CJK/emoji ranges as width 2
    w = 0
    for ch in clean:
        o = ord(ch)
        if (0x1100 <= o <= 0x115F) or (0x2E80 <= o <= 0xA4CF) or (0xAC00 <= o <= 0xD7A3) \
           or (0xF900 <= o <= 0xFAFF) or (0xFE10 <= o <= 0xFE19) or (0xFE30 <= o <= 0xFE6F) \
           or (0xFF00 <= o <= 0xFF60) or (0x1F300 <= o <= 0x1F64F):
            w += 2
        else:
            w += 1
    return w

def truncate_ansi(s: str, target: int) -> str:
    """Truncate an ANSI string to visible width target, preserving ANSI sequences."""
    if visible_width(s) <= target:
        return s
    out = []
    vis = 0
    i = 0
    while i < len(s) and vis < target:
        if s[i] == '\x1b':
            m = ANSI_RE.match(s, i)
            if m:
                out.append(m.group(0))
                i = m.end(0)
                continue
            else:
                i += 1
                continue
        ch = s[i]
        ch_w = 1
        if wcswidth:
            w = wcswidth(ch)
            ch_w = w if (w and w > 0) else 1
        else:
            o = ord(ch)
            ch_w = 2 if (0x1F300 <= o <= 0x1F64F or 0x1100 <= o <= 0x115F) else 1
        if vis + ch_w > target:
            break
        out.append(ch)
        vis += ch_w
        i += 1
    out.append("\033[0m")
    return "".join(out)

def pad_ansi(s: str, target: int, align="left") -> str:
    """Pad ANSI string s to visible width target (left or center)."""
    cur = visible_width(s)
    if cur >= target:
        return truncate_ansi(s, target)
    pad = target - cur
    if align == "center":
        left = pad // 2
        right = pad - left
        return (" " * left) + s + (" " * right)
    else:
        return s + (" " * pad)

# ---------------- frame loading / generation ----------------
def load_frames_from_dir(anim_dir: str):
    p = Path(anim_dir).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"Animation directory not found: {p}")
    files = sorted([f for f in p.iterdir() if f.is_file() and f.name.startswith("frame_") and f.suffix == ".txt"])
    frames = []
    for f in files:
        with f.open("r", encoding="utf-8", errors="ignore") as fh:
            frames.append(fh.read().splitlines())
    if not frames:
        raise FileNotFoundError(f"No frames found in {p}")
    return frames

def gen_frames_from_gif(gif_path: str, out_dir: str, width: int, height: int, color: bool=False, invert: bool=False):
    if not PIL_AVAILABLE:
        raise RuntimeError("Pillow is required for --gen-frames (pip install pillow)")
    gif_path = Path(gif_path).expanduser()
    if not gif_path.exists():
        raise FileNotFoundError(f"{gif_path} not found")
    out_dir = Path(out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    img = Image.open(str(gif_path))
    count = 0
    for i, frame in enumerate(ImageSequence.Iterator(img)):
        # resize and convert to ascii rows
        frame = frame.convert("RGB").resize((width, height), Image.LANCZOS)
        gray = frame.convert("L")
        rgb = frame
        rows = []
        for y in range(height):
            row_chars = []
            for x in range(width):
                p = gray.getpixel((x, y))
                if invert:
                    p = 255 - p
                idx = int((p / 255) * (len(CHARS) - 1))
                ch = CHARS[idx]
                if color:
                    r,g,b = rgb.getpixel((x,y))
                    row_chars.append(f"\033[38;2;{r};{g};{b}m{ch}\033[0m")
                else:
                    row_chars.append(ch)
            rows.append("".join(row_chars))
        with (out_dir / f"frame_{i}.txt").open("w", encoding="utf-8") as fh:
            fh.write("\n".join(rows))
        count += 1
    return count

# ---------------- module detection functions ----------------
# each returns string or None if unavailable

def mod_title():
    user = os.environ.get("USER") or run("whoami") or "user"
    host = run("hostname") or "host"
    return f"{user}@{host}"

def mod_separator():
    return "─" * 28

def mod_os():
    # /etc/os-release preferred
    try:
        with open("/etc/os-release") as fh:
            data = fh.read()
            m = re.search(r'^PRETTY_NAME="?([^\"\\n]+)"?', data, re.MULTILINE)
            if m:
                return m.group(1)
    except Exception:
        pass
    return run("lsb_release -ds") or run("uname -o") or None

def mod_host(): return run("hostnamectl --static") or run("hostname") or None
def mod_kernel(): return run("uname -r")
def mod_uptime():
    s = run("uptime -p")
    if s:
        return s.replace("up ", "")
    # fallback proc
    try:
        with open("/proc/uptime") as fh:
            secs = float(fh.read().split()[0])
            m, _ = divmod(int(secs), 60)
            h, m = divmod(m, 60)
            d, h = divmod(h, 24)
            if d:
                return f"{d}d {h}h {m}m"
            if h:
                return f"{h}h {m}m"
            return f"{m}m"
    except Exception:
        return None

def mod_packages():
    counts = []
    if shutil.which("pacman"):
        n = run("pacman -Qq | wc -l")
        if n: counts.append(f"pacman:{n}")
    if shutil.which("dpkg-query"):
        n = run("dpkg-query -f '${binary:Package}\\n' -W | wc -l")
        if n: counts.append(f"dpkg:{n}")
    if shutil.which("rpm"):
        n = run("rpm -qa | wc -l")
        if n: counts.append(f"rpm:{n}")
    if shutil.which("flatpak"):
        n = run("flatpak list --app | wc -l")
        if n: counts.append(f"flatpak:{n}")
    if shutil.which("snap"):
        n = run("snap list | wc -l")
        if n: counts.append(f"snap:{n}")
    return ", ".join(counts) if counts else None

def mod_shell():
    sh = os.environ.get("SHELL")
    if sh:
        return sh
    return run("ps -o comm= -p $$")

def mod_display():
    # try Xrandr
    x = run("xrandr --current | awk '/\\*/ {print $1; exit}'")
    if x: return x
    # wayland: try qwern? session?
    return run("swaymsg -t get_outputs 2>/dev/null | jq -r '.[0].current_mode'") or None

def mod_de():
    return os.environ.get("XDG_CURRENT_DESKTOP") or os.environ.get("DESKTOP_SESSION") or None

def mod_wm():
    # prefer wmctrl
    if shutil.which("wmctrl"):
        s = run("wmctrl -m | awk -F': ' '/Name/ {print $2; exit}'")
        if s: return s
    # try process scan
    wm_procs = ["hyprland", "sway", "i3", "i3-wm", "bspwm", "openbox", "kwin_x11", "kwin_wayland", "mutter", "kwin"]
    ps = run("ps -e -o comm=") or ""
    for w in wm_procs:
        if w in ps:
            return w
    return None

def mod_wmtheme():
    # best-effort lookups
    # gsettings (GNOME)
    if shutil.which("gsettings"):
        s = run("gsettings get org.gnome.desktop.interface gtk-theme 2>/dev/null")
        if s: return s.strip(\"'\\\" \")
    # xfconf
    p = Path.home() / ".config/gtk-3.0/settings.ini"
    if p.exists():
        for line in p.read_text().splitlines():
            if "gtk-theme-name" in line:
                return line.split("=")[1].strip()
    return None

def mod_theme(): return mod_wmtheme()

def mod_icons():
    p = Path.home() / ".config/gtk-3.0/settings.ini"
    if p.exists():
        for line in p.read_text().splitlines():
            if "gtk-icon-theme-name" in line:
                return line.split("=")[1].strip()
    s = run("gsettings get org.gnome.desktop.interface icon-theme 2>/dev/null")
    if s: return s.strip("'\" ")
    return None

def mod_font():
    # GNOME
    s = run("gsettings get org.gnome.desktop.interface font-name 2>/dev/null")
    if s: return s.strip("'\" ")
    # Kitty
    k = Path.home() / ".config/kitty/kitty.conf"
    if k.exists():
        for line in k.read_text().splitlines():
            if line.strip().startswith("font "):
                return line.split(" ",1)[1].strip()
    return None

def mod_cursor():
    s = run("gsettings get org.gnome.desktop.interface cursor-theme 2>/dev/null")
    if s: return s.strip("'\" ")
    return None

def mod_terminal():
    # try parent process
    p = run("ps -o comm= -p $(ps -o ppid= -p $$)")
    return p or os.environ.get("TERM")

def mod_terminalfont():
    # try gnome-terminal (profile detection is complex); fallback to kitty/alacritty conf
    k = Path.home() / ".config/kitty/kitty.conf"
    if k.exists():
        for line in k.read_text().splitlines():
            if line.strip().startswith("font "):
                return line.split(" ",1)[1].strip()
    a = Path.home() / ".config/alacritty/alacritty.yml"
    if a.exists():
        for line in a.read_text().splitlines():
            if "family:" in line:
                return line.split(":",1)[1].strip()
    return None

def mod_cpu():
    s = run("awk -F: '/model name/ {print $2; exit}' /proc/cpuinfo")
    if s: return s.strip()
    return None

def mod_gpu():
    s = run("lspci | grep -i 'vga\\|3d\\|display' | sed -E 's/.*: //' | head -n1")
    return s

def mod_memory():
    return run("free -h | awk '/Mem:/ {print $3\"/\"$2}'")

def mod_swap():
    return run("free -h | awk '/Swap:/ {print $3\"/\"$2}'")

def mod_disk():
    out = run("df -h --output=source,size,used,avail,pcent / | tail -n1")
    return out

def mod_localip():
    return run("hostname -I | awk '{print $1}'")

def mod_battery():
    # upower
    if shutil.which("upower"):
        out = run("upower -i $(upower -e | grep battery | head -n1) 2>/dev/null | awk -F: '/percentage/ {print $2; exit}'")
        if out: return out.strip()
    # fallback /sys
    try:
        p = Path("/sys/class/power_supply")
        for d in p.iterdir():
            if d.is_dir() and "BAT" in d.name.upper():
                pct = (d / "capacity").read_text().strip()
                state = (d / "status").read_text().strip()
                return f"{pct}% ({state})"
    except Exception:
        pass
    return None

def mod_poweradapter():
    # check AC status
    try:
        p = Path("/sys/class/power_supply")
        for d in p.iterdir():
            if d.is_dir() and d.name.lower().startswith("ac"):
                return "AC"
    except Exception:
        pass
    return None

def mod_locale():
    return os.environ.get("LANG") or run("locale | awk -F= '/^LANG=/ {print $2}'")

def mod_break():
    return ""

def mod_colors():
    # print 16 color blocks
    blocks = []
    for i in range(0,8):
        blocks.append(f"\033[3{i}m██\033[0m")
    for i in range(0,8):
        blocks.append(f"\033[9{i-8}m██\033[0m") if False else None
    return " ".join(blocks[:8])

# ---------------- aggregate modules ----------------
MODULE_FUNCS = [
    ("title", mod_title),
    ("separator", mod_separator),
    ("os", mod_os),
    ("host", mod_host),
    ("kernel", mod_kernel),
    ("uptime", mod_uptime),
    ("packages", mod_packages),
    ("shell", mod_shell),
    ("display", mod_display),
    ("de", mod_de),
    ("wm", mod_wm),
    ("wmtheme", mod_wmtheme),
    ("theme", mod_theme),
    ("icons", mod_icons),
    ("font", mod_font),
    ("cursor", mod_cursor),
    ("terminal", mod_terminal),
    ("terminalfont", mod_terminalfont),
    ("cpu", mod_cpu),
    ("gpu", mod_gpu),
    ("memory", mod_memory),
    ("swap", mod_swap),
    ("disk", mod_disk),
    ("localip", mod_localip),
    ("battery", mod_battery),
    ("poweradapter", mod_poweradapter),
    ("locale", mod_locale),
    ("break", mod_break),
    ("colors", mod_colors),
]

def gather_all_modules():
    out = []
    for name, func in MODULE_FUNCS:
        try:
            val = func()
        except Exception:
            val = None
        out.append((name, val))
    return out

# ---------------- display/rendering ----------------
def build_spec_lines(mods):
    lines = []
    for (name, val) in mods:
        if val is None:
            continue
        if name == "separator":
            lines.append(val)
            continue
        if name == "colors":
            lines.append(val)
            continue
        if name == "title":
            lines.append(val)
            continue
        # pretty label
        label = name.capitalize()
        lines.append(f"\033[1m{label}:\033[0m {val}")
    return lines

def render_loop(frames, box_w, box_h, fps, align="left"):
    # gather modules once per loop iteration (can be optimized to refresh every N seconds)
    mods = gather_all_modules()
    spec_lines = build_spec_lines(mods)
    # ensure spec_lines length is at least 1
    if not spec_lines:
        spec_lines = ["No info"]

    pad_between = SEPARATOR_CHAR
    term_w = shutil.get_terminal_size().columns

    total_frames = len(frames)
    idx = 0
    delay = 1.0 / fps

    try:
        while True:
            mods = gather_all_modules()  # refresh each frame so uptime etc updates
            spec_lines = build_spec_lines(mods)

            frame = frames[idx]
            # constrain frame to box_h lines & box_w width (pad/truncate)
            frame = frame[:box_h] + [""] * max(0, box_h - len(frame))
            padded_left = [pad_ansi(line, box_w, align=align) for line in frame]

            # compute right width available
            avail_right = term_w - visible_width(pad_ansi(" " * box_w, box_w)) - visible_width(pad_between) - 1
            # but we will compute per-line truncation

            max_lines = max(box_h, len(spec_lines))
            for i in range(max_lines):
                left = padded_left[i] if i < len(padded_left) else " " * box_w
                right = spec_lines[i] if i < len(spec_lines) else ""
                # compute allowed for right
                allowed = max(0, term_w - visible_width(left) - visible_width(pad_between))
                right_trunc = truncate_ansi(right, allowed)
                print(left + pad_between + right_trunc)
            idx = (idx + 1) % total_frames
            time.sleep(delay)
    except KeyboardInterrupt:
        print("\nExiting gifzittofetch.")

# ---------------- CLI ----------------
def parse_args():
    p = argparse.ArgumentParser(description="gifzittofetch - animated ASCII left + Fastfetch-like specs right")
    p.add_argument("--anim-dir", default=DEFAULT_ANIM_DIR, help="Directory with frame_*.txt files")
    p.add_argument("--width", type=int, default=DEFAULT_WIDTH, help="ASCII box width (columns)")
    p.add_argument("--height", type=int, default=DEFAULT_HEIGHT, help="ASCII box height (lines)")
    p.add_argument("--fps", type=float, default=DEFAULT_FPS, help="Frames per second")
    p.add_argument("--align", choices=["left", "center"], default="left", help="Alignment of ASCII art in box")
    p.add_argument("--gen-frames", action="store_true", help="Generate frames from GIF (requires Pillow)")
    p.add_argument("--input", "-i", help="Input GIF path for --gen-frames")
    p.add_argument("--out", "-o", default=DEFAULT_ANIM_DIR, help="Output directory for generated frames")
    p.add_argument("--color", action="store_true", help="Generate colored frames when using --gen-frames")
    p.add_argument("--invert", action="store_true", help="Invert brightness during generation")
    return p.parse_args()

def main():
    args = parse_args()

    if args.gen_frames:
        if not args.input:
            print("Error: specify --input path to GIF when using --gen-frames")
            return
        try:
            n = gen_frames_from_gif(args.input, args.out, args.width, args.height, color=args.color, invert=args.invert)
            print(f"Generated {n} frames into {args.out}")
        except Exception as e:
            print("Failed to generate frames:", e)
        return

    try:
        frames = load_frames_from_dir(args.anim_dir)
    except Exception as e:
        print("Error loading frames:", e)
        print(f"Generate frames with: gifzittofetch --gen-frames -i input.gif --out {args.anim_dir}")
        return

    render_loop(frames, args.width, args.height, args.fps, align=args.align)

if __name__ == "__main__":
    main()
