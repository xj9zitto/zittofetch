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
import termios
import tty
import select


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
CHARS = "@%#*+=-:. "
DEFAULT_WIDTH = 40
DEFAULT_HEIGHT = 20
DEFAULT_FPS = 12.0
SEPARATOR_CHAR = " │ "

# ---------------- utilities ----------------
def run(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return None

def visible_width(s: str) -> int:
    clean = ANSI_RE.sub("", s)
    if wcswidth:
        w = wcswidth(clean)
        if w >= 0:
            return w
    w = 0
    for ch in clean:
        if ord(ch) >= 0x1100:
            w += 2
        else:
            w += 1
    return w

def truncate_ansi(s: str, target: int) -> str:
    if visible_width(s) <= target:
        return s
    out = []
    vis = 0
    i = 0
    while i < len(s) and vis < target:
        if s[i] == "\x1b":
            m = ANSI_RE.match(s, i)
            if m:
                out.append(m.group(0))
                i = m.end(0)
                continue
        ch = s[i]
        ch_w = 2 if ord(ch) >= 0x1100 else 1
        if vis + ch_w > target:
            break
        out.append(ch)
        vis += ch_w
        i += 1
    out.append("\033[0m")
    return "".join(out)

def pad_ansi(s: str, target: int, align="left") -> str:
    cur = visible_width(s)
    if cur >= target:
        return truncate_ansi(s, target)
    pad = target - cur
    if align == "center":
        left = pad // 2
        right = pad - left
        return (" " * left) + s + (" " * right)
    return s + (" " * pad)

# ---------------- frame loading ----------------
def load_frames_from_dir(anim_dir: str):
    p = Path(anim_dir).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"Animation directory not found: {p}")
    files = sorted(f for f in p.iterdir() if f.name.startswith("frame_") and f.suffix == ".txt")
    frames = []
    for f in files:
        frames.append(f.read_text(encoding="utf-8", errors="ignore").splitlines())
    if not frames:
        raise FileNotFoundError("No frame_*.txt found.")
    return frames

# ---------------- frame generation ----------------
def gen_frames_from_gif(gif_path, out_dir, width, height, color=False, invert=False):
    if not PIL_AVAILABLE:
        raise RuntimeError("Pillow required.")
    gif_path = Path(gif_path).expanduser()
    out_dir = Path(out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    img = Image.open(gif_path)
    count = 0

    for i, frame in enumerate(ImageSequence.Iterator(img)):
        frame = frame.convert("RGB").resize((width, height), Image.LANCZOS)
        gray = frame.convert("L")
        rows = []
        for y in range(height):
            line = []
            for x in range(width):
                p = gray.getpixel((x, y))
                if invert:
                    p = 255 - p
                idx = int((p / 255) * (len(CHARS) - 1))
                ch = CHARS[idx]
                if color:
                    r, g, b = frame.getpixel((x, y))
                    line.append(f"\033[38;2;{r};{g};{b}m{ch}\033[0m")
                else:
                    line.append(ch)
            rows.append("".join(line))
        (out_dir / f"frame_{i}.txt").write_text("\n".join(rows), encoding="utf-8")
        count += 1

    return count

# ---------------- module detection ----------------
def mod_title():
    user = os.environ.get("USER") or run("whoami")
    host = run("hostname")
    return f"{user}@{host}"

def mod_separator():
    return "────────────────────────"

def mod_os():
    try:
        txt = Path("/etc/os-release").read_text()
        m = re.search(r'PRETTY_NAME="([^"]+)"', txt)
        if m:
            return m.group(1)
    except:
        pass
    return run("uname -o")

def mod_host():
    return run("hostnamectl --static") or run("hostname")

def mod_kernel():
    return run("uname -r")

def mod_uptime():
    s = run("uptime -p")
    return s.replace("up ", "") if s else None

def mod_packages():
    pkg = []
    if shutil.which("pacman"):
        pkg.append(f"pacman:{run('pacman -Qq | wc -l')}")
    if shutil.which("dpkg-query"):
        pkg.append(f"dpkg:{run('dpkg-query -f \"${binary:Package}\\n\" -W | wc -l')}")
    if shutil.which("flatpak"):
        pkg.append(f"flatpak:{run('flatpak list --app | wc -l')}")
    if shutil.which("snap"):
        pkg.append(f"snap:{run('snap list | wc -l')}")
    return ", ".join(pkg) if pkg else None

def mod_shell():
    return os.environ.get("SHELL") or run("ps -o comm= -p $$")

def mod_display():
    return run("xrandr | grep '*' | awk '{print $1}'")

def mod_de():
    return os.environ.get("XDG_CURRENT_DESKTOP") or os.environ.get("DESKTOP_SESSION")

def mod_wm():
    if shutil.which("wmctrl"):
        return run("wmctrl -m | grep Name | awk -F': ' '{print $2}'")
    ps = run("ps -e -o comm=") or ""
    for w in ["hyprland", "sway", "i3", "bspwm", "openbox", "kwin", "mutter"]:
        if w in ps:
            return w
    return None

def mod_wmtheme():
    if shutil.which("gsettings"):
        s = run("gsettings get org.gnome.desktop.interface gtk-theme")
        if s:
            return s.strip("'\" ")
    ini = Path.home() / ".config/gtk-3.0/settings.ini"
    if ini.exists():
        for line in ini.read_text().splitlines():
            if "gtk-theme-name" in line:
                return line.split("=", 1)[1].strip()
    return None

def mod_theme():
    return mod_wmtheme()

def mod_icons():
    ini = Path.home() / ".config/gtk-3.0/settings.ini"
    if ini.exists():
        for line in ini.read_text().splitlines():
            if "gtk-icon-theme-name" in line:
                return line.split("=", 1)[1].strip()
    s = run("gsettings get org.gnome.desktop.interface icon-theme")
    return s.strip("'\" ") if s else None

def mod_font():
    s = run("gsettings get org.gnome.desktop.interface font-name")
    return s.strip("'\" ") if s else None

def mod_cursor():
    s = run("gsettings get org.gnome.desktop.interface cursor-theme")
    return s.strip("'\" ") if s else None

def mod_terminal():
    return run("ps -o comm= -p $(ps -o ppid= -p $$)") or os.environ.get("TERM")

def mod_terminalfont():
    kitty = Path.home() / ".config/kitty/kitty.conf"
    if kitty.exists():
        for line in kitty.read_text().splitlines():
            if line.startswith("font "):
                return line.split(" ", 1)[1]
    return None

def mod_cpu():
    return run("awk -F: '/model name/ {print $2; exit}' /proc/cpuinfo").strip()

def mod_gpu():
    return run("lspci | grep -i 'vga\\|3d\\|display' | sed 's/.*: //'")

def mod_memory():
    return run("free -h | awk '/Mem:/ {print $3\"/\"$2}'")

def mod_swap():
    return run("free -h | awk '/Swap:/ {print $3\"/\"$2}'")

def mod_disk():
    return run("df -h / | tail -1 | awk '{print $2\"/\"$3\" (\"$5\")\"}'")

def mod_localip():
    return run("hostname -I | awk '{print $1}'")

def mod_battery():
    ps = Path("/sys/class/power_supply")
    for d in ps.iterdir():
        if "BAT" in d.name.upper():
            pct = (d / "capacity").read_text().strip()
            state = (d / "status").read_text().strip()
            return f"{pct}% ({state})"
    return None

def mod_poweradapter():
    ps = Path("/sys/class/power_supply")
    for d in ps.iterdir():
        if d.name.lower().startswith("ac"):
            return "AC"
    return None

def mod_locale():
    return os.environ.get("LANG")

def mod_break():
    return ""

def mod_colors():
    return " ".join([f"\033[3{i}m██\033[0m" for i in range(8)])

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
        except:
            val = None
        if val:
            out.append((name, val))
    return out

def build_spec_lines(mods):
    out = []
    for name, val in mods:
        if name == "separator":
            out.append(val)
        elif name == "title":
            out.append(val)
        elif name == "colors":
            out.append(val)
        else:
            out.append(f"\033[1m{name.capitalize()}:\033[0m {val}")
    return out

def enable_raw_mode():
    fd = sys.stdin.fileno()
    global old_settings
    old_settings = termios.tcgetattr(fd)
    tty.setcbreak(fd)

def disable_raw_mode():
    try:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)
    except:
        pass

def kbhit():
    dr, _, _ = select.select([sys.stdin], [], [], 0)
    return dr != []

def getch():
    return sys.stdin.read(1)




# ---------------- rendering ----------------
# ---------------- TERMINAL RAW MODE ----------------

def enable_raw_mode():
    """Enable raw keyboard input mode."""
    global old_settings
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    tty.setcbreak(fd)

def disable_raw_mode():
    """Restore terminal to normal mode."""
    try:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)
    except:
        pass


# ---------------- RENDERING LOOP ----------------

def render_loop(frames, box_w, box_h, fps, align="left"):
    """
    Smooth animation + specs + proper quit handling + partial redraw.
    """
    idx = 0
    delay = 1 / fps
    last_refresh = 0

    # Light modules (refresh every 1s)
    LIGHT_FIELDS = ["uptime", "localip"]

    # Pre-load heavy modules once
    mods = gather_all_modules()
    specs = build_spec_lines(mods)

    # ---------------- enable raw keyboard mode once ----------------
    enable_raw_mode()

    try:
        while True:

            # -------- Quit detection --------
            if kbhit():
                c = getch().lower()
                if c == "q":
                    print("\nExiting gifzittofetch…")
                    break

            now = time.time()

            # -------- Refresh lightweight modules every 1s --------
            if now - last_refresh >= 1:
                last_refresh = now
                for name, func in MODULE_FUNCS:
                    if name in LIGHT_FIELDS:
                        try:
                            val = func()
                        except:
                            val = None
                        for i, (n, _) in enumerate(mods):
                            if n == name:
                                mods[i] = (name, val)
                                break
                specs = build_spec_lines(mods)

            # -------- Prepare frame --------
            frame = frames[idx]
            frame = frame[:box_h] + [""] * max(0, box_h - len(frame))
            frame = [pad_ansi(x, box_w, align) for x in frame]

            max_rows = max(len(frame), len(specs))

            # -------- Fast partial clear (no input lag) --------
            print("\033[H\033[J", end="")   # home + clear below

            # -------- Draw combined output --------
            for i in range(max_rows):
                left = frame[i] if i < len(frame) else " " * box_w
                right = specs[i] if i < len(specs) else ""
                term_w = shutil.get_terminal_size().columns

                allowed = term_w - visible_width(left) - visible_width(SEPARATOR_CHAR)
                right = truncate_ansi(right, allowed)

                print(left + SEPARATOR_CHAR + right)

            # -------- Next frame --------
            idx = (idx + 1) % len(frames)
            time.sleep(delay)

    finally:
        disable_raw_mode()


# ---------------- CLI ----------------
def parse_args():
    p = argparse.ArgumentParser(description="gifzittofetch - animated ASCII fetch")
    p.add_argument("--anim-dir", default=DEFAULT_ANIM_DIR)
    p.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    p.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    p.add_argument("--fps", type=float, default=DEFAULT_FPS)
    p.add_argument("--align", choices=["left", "center"], default="left")
    p.add_argument("--gen-frames", action="store_true")
    p.add_argument("--input", "-i")
    p.add_argument("--out", "-o", default=DEFAULT_ANIM_DIR)
    p.add_argument("--color", action="store_true")
    p.add_argument("--invert", action="store_true")
    return p.parse_args()


def main():
    args = parse_args()

    if args.gen_frames:
        n = gen_frames_from_gif(args.input, args.out, args.width, args.height,
                                color=args.color, invert=args.invert)
        print(f"Generated {n} frames into {args.out}")
        return

    frames = load_frames_from_dir(args.anim_dir)
    render_loop(frames, args.width, args.height, args.fps, align=args.align)


if __name__ == "__main__":
    main()

