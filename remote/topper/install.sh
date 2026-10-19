#!/usr/bin/env bash
# Install the remote topper on a Raspberry Pi (Raspberry Pi OS Lite, Bookworm): mpv, the agent, and a service
# that starts it at boot. Run it as the Pi's normal user (it uses sudo), from a clone of the repository:
#
#     bash remote/topper/install.sh
#
# or straight from GitHub, without a clone:
#
#     curl -fsSL https://raw.githubusercontent.com/Ashram56/Tron-Legacy-MPF/main/remote/topper/install.sh | bash
#
# Again to update; `bash install.sh --uninstall` removes it (the videos stay in ~/tron-topper/media).
# Then, on the game computer: python scripts/pup/topper_media.py --push <user>@<this Pi's name>.local
# (docs/pup/remote_topper.md).
set -euo pipefail

REF="${TRON_REF:-main}"
RAW="https://raw.githubusercontent.com/Ashram56/Tron-Legacy-MPF/$REF"
APP=/opt/tron-topper
CFG=/etc/tron-topper.cfg
UNIT=/etc/systemd/system/tron-topper.service
USER_NAME="$(id -un)"
MEDIA="$HOME/tron-topper/media"

if [ "$(id -u)" = 0 ]; then
    echo "Run this as the Pi's normal user, not root: it runs the topper as that user (and asks for sudo)." >&2
    exit 1
fi

if [ "${1:-}" = "--uninstall" ]; then
    sudo systemctl disable --now tron-topper 2>/dev/null || true
    sudo rm -rf "$APP" "$UNIT"
    sudo systemctl daemon-reload
    echo "Removed the topper service and $APP; kept $CFG and $MEDIA."
    exit 0
fi

echo "== mpv"
sudo apt-get update -qq
sudo apt-get install -y -qq mpv python3

echo "== the agent in $APP"
sudo mkdir -p "$APP"
HERE=""
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "$(dirname "${BASH_SOURCE[0]}")/tron_topper.py" ]; then
    HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi
if [ -n "$HERE" ]; then
    # from a clone: the agent, and the PuP rules it shares with the game
    sudo cp "$HERE/tron_topper.py" "$HERE/tron-topper.cfg" "$APP/"
    sudo cp "$HERE/../../game/tron_pup/screen_rules.py" "$APP/"
else
    for f in remote/topper/tron_topper.py remote/topper/tron-topper.cfg game/tron_pup/screen_rules.py; do
        sudo curl -fsSL "$RAW/$f" -o "$APP/$(basename "$f")"
    done
fi

echo "== settings in $CFG"
if [ ! -f "$CFG" ]; then
    sed "s#^media=.*#media=$MEDIA#" "$APP/tron-topper.cfg" | sudo tee "$CFG" > /dev/null
else
    echo "kept the existing $CFG"
fi
mkdir -p "$MEDIA"

echo "== the service (user $USER_NAME)"
# video and render: the screen and the hardware decoder without a desktop
sudo usermod -a -G video,render "$USER_NAME"
sudo tee "$UNIT" > /dev/null <<EOF
[Unit]
Description=Tron topper (PuP screens 13 and 14 from the game)
After=network-online.target
Wants=network-online.target

[Service]
User=$USER_NAME
SupplementaryGroups=video render
ExecStart=/usr/bin/python3 $APP/tron_topper.py --config $CFG
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable tron-topper
sudo systemctl restart tron-topper

echo
echo "Done. The topper starts at boot and finds the game on the network."
echo "Next, on the game computer:"
echo "  1. [remote] enabled=true in game/pup.local.cfg"
echo "  2. python scripts/pup/topper_media.py --push $USER_NAME@$(hostname).local"
echo "Its log: journalctl -u tron-topper -f    Settings: sudo nano $CFG, then sudo systemctl restart tron-topper"
