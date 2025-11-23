#!/usr/bin/env bash

set -e

echo "==> Installing gifzittofetch..."

# -------------------------------
# Paths
# -------------------------------
INSTALL_BIN="/usr/local/bin"
INSTALL_SHARE="/usr/local/share/gifzittofetch"
ANIM_DIR="$HOME/.local/share/gifzitto/anim"

# -------------------------------
# Create required dirs
# -------------------------------
echo "==> Creating dirs..."
sudo mkdir -p "$INSTALL_SHARE"
mkdir -p "$ANIM_DIR"

# -------------------------------
# Install main binaries
# -------------------------------
echo "==> Installing scripts..."

# Install gifzittofetch
if [[ -f "gifzittofetch.py" ]]; then
    sudo cp gifzittofetch.py "$INSTALL_BIN/gifzittofetch"
    sudo chmod +x "$INSTALL_BIN/gifzittofetch"
    echo "✓ Installed gifzittofetch"
else
    echo "⚠ gifzittofetch.py not found!"
fi

# Install gifzitto-frames tool
if [[ -f "gifzitto-frames.py" ]]; then
    sudo cp gifzitto-frames.py "$INSTALL_BIN/gifzitto-frames"
    sudo chmod +x "$INSTALL_BIN/gifzitto-frames"
    echo "✓ Installed gifzitto-frames"
else
    echo "⚠ gifzitto-frames.py not found (optional)"
fi

# -------------------------------
# Install theme_detect.py
# -------------------------------
if [[ -f "theme_detect.py" ]]; then
    sudo cp theme_detect.py "$INSTALL_SHARE/theme_detect.py"
    echo "✓ Installed theme_detect.py"
else
    echo "⚠ theme_detect.py not found!"
fi


# -------------------------------
# Patch PYTHONPATH automatically
# -------------------------------
echo "==> Updating PYTHONPATH..."

PROFILE_FILE="$HOME/.bashrc"

if ! grep -Fxq 'export PYTHONPATH="/usr/local/share/gifzittofetch:$PYTHONPATH"' "$PROFILE_FILE"; then
    echo 'export PYTHONPATH="/usr/local/share/gifzittofetch:$PYTHONPATH"' >> "$PROFILE_FILE"
    echo "✓ PYTHONPATH updated in ~/.bashrc"
else
    echo "✓ PYTHONPATH already configured"
fi

# ZSH users
if [[ -f "$HOME/.zshrc" ]]; then
    if ! grep -Fxq 'export PYTHONPATH="/usr/local/share/gifzittofetch:$PYTHONPATH"' "$HOME/.zshrc"; then
        echo 'export PYTHONPATH="/usr/local/share/gifzittofetch:$PYTHONPATH"' >> "$HOME/.zshrc"
        echo "✓ PYTHONPATH updated in ~/.zshrc"
    fi
fi

echo "==> Installation complete!"
echo ""
echo "You may need to restart your terminal or run: source ~/.bashrc"
echo ""
echo "Try running:  gifzittofetch"
