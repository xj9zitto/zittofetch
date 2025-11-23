#!/bin/bash

echo "==== gifzittofetch Uninstaller ===="

BIN1="/usr/local/bin/gifzittofetch"
BIN2="/usr/local/bin/gifzitto-frames"
DATA="$HOME/.local/share/gifzitto"

echo "This will remove:"
echo "  $BIN1"
echo "  $BIN2"
echo "  $DATA"
echo
read -rp "Are you sure you want to uninstall gifzittofetch? (y/N): " CONFIRM

if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
    echo "Uninstall cancelled."
    exit 0
fi

echo "Removing binaries (requires sudo)..."
if [[ -f "$BIN1" ]]; then
    sudo rm "$BIN1"
    echo "Removed $BIN1"
else
    echo "Skipping: $BIN1 not found"
fi

if [[ -f "$BIN2" ]]; then
    sudo rm "$BIN2"
    echo "Removed $BIN2"
else
    echo "Skipping: $BIN2 not found"
fi

echo "Removing data directory..."
if [[ -d "$DATA" ]]; then
    rm -rf "$DATA"
    echo "Removed $DATA"
else
    echo "Skipping: $DATA not found"
fi

echo "gifzittofetch successfully uninstalled."
exit 0
