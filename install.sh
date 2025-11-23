#!/usr/bin/env bash

# ---------------------------------------------------------
#  gifzittofetch installer
# ---------------------------------------------------------

set -e

PREFIX="/usr/local/bin"
SHARE="$HOME/.local/share/gifzitto"

GREEN="\033[32m"
YELLOW="\033[33m"
RESET="\033[0m"

echo -e "${GREEN}Installing gifzittofetch...${RESET}"

# ---------------------------------------------------------
#  Create share directory
# ---------------------------------------------------------

mkdir -p "$SHARE/anim"

# ---------------------------------------------------------
#  Copy main scripts
# ---------------------------------------------------------

if [[ ! -f gifzittofetch.py ]]; then
    echo "Error: gifzittofetch.py not found in current directory."
    exit 1
fi

if [[ ! -f gif2ascii_clean.py ]]; then
    echo "Warning: gif2ascii_clean.py not found. Only main fetch tool will install."
fi

echo "Copying scripts to $PREFIX..."

sudo install -m 755 gifzittofetch.py "$PREFIX/gifzittofetch"
[[ -f gif2ascii_clean.py ]] && sudo install -m 755 gif2ascii_clean.py "$PREFIX/gifzitto-frames"


# ---------------------------------------------------------
#  Create default animation (optional placeholder)
# ---------------------------------------------------------

if [[ ! -f "$SHARE/anim/frame_0.txt" ]]; then
    echo -e "${YELLOW}No animation detected — creating placeholder.${RESET}"

    cat > "$SHARE/anim/frame_0.txt" << EOF
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@                                          @
@        gifzittofetch installed!          @
@                                          @
@    Run gifzitto-frames to add frames     @
@                                          @
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
EOF

fi


# ---------------------------------------------------------
#  Success
# ---------------------------------------------------------

echo -e "${GREEN}gifzittofetch installation complete!${RESET}"
echo ""
echo "Run it with:"
echo -e "  ${YELLOW}gifzittofetch${RESET}"
echo ""
echo "Generate frames from a GIF with:"
echo -e "  ${YELLOW}gifzitto-frames -i my.gif --out ~/.local/share/gifzitto/anim${RESET}"
echo ""
echo "Uninstall by running:"
echo -e "  ${YELLOW}sudo rm /usr/local/bin/gifzittofetch /usr/local/bin/gifzitto-frames${RESET}"
