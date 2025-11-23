#!/usr/bin/env python3
"""
theme_detect.py

Standalone terminal + theme detection for gifzittofetch.

Provides:
    detect_terminal_theme()  -> dict of {
        'terminal': str,
        'foreground': (r,g,b) or None,
        'background': (r,g,b) or None,
        'accent': (r,g,b) or None,
        'palette': dict[str,(r,g,b)]
    }

Supported terminals:
    - Kitty
    - Alacritty
    - Konsole
    - GNOME Terminal (via dconf)
    - Xresources / Xdefaults
"""

import os
import re
import subprocess
from pathlib import Path


# ---------------- Utilities ----------------

def run(cmd):
    try:
        return subprocess.check_output(
            cmd,
            shell=True,
            stderr=subprocess.DEVNULL,
            text=True
        ).strip()
    except:
        return None

def hex_to_rgb(h):
    if not h:
        return None
    s = h.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c*2 for c in s)
    if len(s) != 6:
        return None
    try:
        return tuple(int(s[i:i+2], 16) for i in (0,2,4))
    except:
        return None

def rgb_to_ansi(rgb):
    if not rgb:
        return ""
    r,g,b = rgb
    return f"\033[38;2;{r};{g};{b}m"

def parse_ini_colors(lines):
    out = {}
    for line in lines:
        if "=" not in line:
            continue
        k,v = [x.strip() for x in line.split("=",1)]
        if "," in v:
            parts = v.split(",")
            if len(parts) >= 3:
                try:
                    out[k.lower()] = (int(parts[0]), int(parts[1]), int(parts[2]))
                except:
                    pass
        elif v.startswith("#"):
            out[k.lower()] = hex_to_rgb(v)
    return out


# ---------------- Terminal Detection ----------------

def detect_terminal():
    """
    Detect actual terminal emulator.
    """
    # Mac standard
    if "TERM_PROGRAM" in os.environ:
        return os.environ["TERM_PROGRAM"]

    known = [
        "kitty", "alacritty", "wezterm", "konsole",
        "gnome-terminal", "xfce4-terminal", "xterm",
        "st", "tilix", "urxvt", "rxvt",
    ]

    pid = os.getppid()
    while pid > 1:
        comm = run(f"ps -o comm= -p {pid}")
        if comm:
            low = comm.lower()
            for t in known:
                if t in low:
                    return low
        ppid = run(f"ps -o ppid= -p {pid}")
        if not ppid:
            break
        pid = int(ppid)
    return os.environ.get("TERM", "unknown")


# ---------------- Theme Parsers ----------------

def parse_kitty():
    home = Path.home()
    paths = [
        home/".config/kitty/kitty.conf",
        home/".config/kitty/theme.conf",
        home/".config/kitty/themes/kitty.conf",
    ]

    out = {"palette": {}}
    for p in paths:
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                k = parts[0].lower()
                v = hex_to_rgb(parts[1])
                if k == "foreground":
                    out["foreground"] = v
                elif k == "background":
                    out["background"] = v
                elif k.startswith("color"):
                    out["palette"][k] = v
    if "foreground" in out:
        out["accent"] = (
            out["palette"].get("color4")
            or out["palette"].get("color2")
            or out["foreground"]
        )
    return out if out.get("foreground") or out["palette"] else None


def parse_alacritty():
    yml = Path.home()/".config/alacritty/alacritty.yml"
    if not yml.exists():
        return None

    txt = yml.read_text()
    out = {"palette": {}}

    # foreground/background
    for k in ("foreground", "background"):
        m = re.search(rf"{k}:\s*['\"]?(#?[0-9A-Fa-f]{{6}})", txt)
        if m:
            out[k] = hex_to_rgb(m.group(1))

    # palette
    for name in ("black","red","green","yellow","blue","magenta","cyan","white"):
        m = re.search(rf"{name}:\s*['\"]?(#?[0-9A-Fa-f]{{6}})", txt)
        if m:
            out["palette"][f"color_{name}"] = hex_to_rgb(m.group(1))

    out["accent"] = out["palette"].get("color_blue") or out.get("foreground")
    return out


def parse_konsole():
    d = Path.home()/".local/share/konsole"
    if not d.exists():
        return None

    for f in d.iterdir():
        if f.suffix != ".colorscheme":
            continue
        return parse_ini_colors(f.read_text().splitlines())
    return None


def parse_gnome_terminal(term):
    if "gnome" not in term:
        return None

    profiles = run("gsettings get org.gnome.Terminal.ProfilesList list | tr -d \"[]'\"")
    if not profiles:
        return None
    pid = profiles.split(",")[0].strip()
    if not pid:
        return None

    out = {"palette": {}}

    # Palette
    raw = run(f"dconf read /org/gnome/terminal/legacy/profiles:/:{pid}/palette")
    if raw:
        hexes = re.findall(r"'(#(?:[0-9A-Fa-f]{6}))'", raw)
        for i,h in enumerate(hexes):
            out["palette"][f"color{i}"] = hex_to_rgb(h)

    # fg/bg
    for k in ("foreground", "background"):
        raw = run(f"dconf read /org/gnome/terminal/legacy/profiles:/:{pid}/{k}")
        if raw:
            m = re.search(r"'(#(?:[0-9A-Fa-f]{6}))'", raw)
            if m:
                out[k] = hex_to_rgb(m.group(1))

    if "foreground" in out:
        out["accent"] = out["palette"].get("color4") or out["foreground"]

    return out if out.get("foreground") or out["palette"] else None


def parse_xresources():
    xr = Path.home()/".Xresources"
    if not xr.exists():
        xr = Path.home()/".Xdefaults"
        if not xr.exists():
            return None

    out = {"palette": {}}

    for line in xr.read_text().splitlines():
        line = line.strip()
        m = re.match(r'^(\*\w+|[A-Za-z0-9.*-]+):\s*(#?[0-9A-Fa-f]{6})', line)
        if m:
            k,v = m.group(1), m.group(2)
            if "foreground" in k.lower():
                out["foreground"] = hex_to_rgb(v)
            elif "background" in k.lower():
                out["background"] = hex_to_rgb(v)
            elif "color" in k.lower():
                num = re.findall(r"color(\d+)", k.lower())
                if num:
                    out["palette"][f"color{num[0]}"] = hex_to_rgb(v)

    if out:
        out["accent"] = (
            out["palette"].get("color4")
            or out.get("foreground")
        )
    return out if out else None


# ---------------- Public API ----------------

def detect_terminal_theme():
    term = detect_terminal()

    theme = (
        parse_kitty()
        or parse_alacritty()
        or parse_konsole()
        or parse_gnome_terminal(term)
        or parse_xresources()
        or {}
    )

    theme.setdefault("terminal", term)
    theme.setdefault("foreground", None)
    theme.setdefault("background", None)
    theme.setdefault("accent", None)
    theme.setdefault("palette", {})

    return theme
