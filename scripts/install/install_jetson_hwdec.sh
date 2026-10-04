#!/usr/bin/env bash
# NVIDIA Jetson (JetPack 5 or 6): installs libnvmpi, which GDE GoZen's FFmpeg loads to decode the PuP videos on
# the hardware decoder (pup_addons/gde_gozen/README.md). Safe to re-run. install_prereqs_linux.sh runs it by
# itself on a Jetson (TRON_HWDEC=0 skips it); on its own:
#
#   bash <(curl -fsSL https://raw.githubusercontent.com/Ashram56/Tron-Legacy-MPF-PuP/main/scripts/install/install_jetson_hwdec.sh)
#
#   ... --test      also build a small ffmpeg (no system install) and decode a pack video with h264_nvmpi
#   ... --dry-run   print the plan, change nothing
#
# Steps: the build packages and the Jetson Multimedia API (apt), jetson-ffmpeg at the revision GoZen was built
# with (scripts/build_gozen.sh) in ~/.cache/tron-legacy-mpf/, its libnvmpi built and installed in /usr/local/lib.
set -euo pipefail

JETSON_FFMPEG_URL=https://github.com/gjrtimmer/jetson-ffmpeg
JETSON_FFMPEG_REV=8d70c17efeee57f4d956df500fec78a73f8c27d4      # same as scripts/build_gozen.sh
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/tron-legacy-mpf"
SRC="$CACHE/jetson-ffmpeg"
TEST_VIDEO="${TRON_DIR:-$HOME/Tron-Legacy-MPF-PuP}/pup_pack/trn_174h/Drain/Drain1.mp4"
MMAPI=/usr/src/jetson_multimedia_api

DRY=0 TEST=0
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY=1 ;;
        --test) TEST=1 ;;
        -h|--help) sed -n '2,13p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown option: $arg (see --help)" >&2; exit 2 ;;
    esac
done

say() { printf '\n== %s\n' "$*"; }
note() { printf '   %s\n' "$*"; }
run() { printf '   $ %s\n' "$*"; [ "$DRY" = 1 ] || "$@"; }
root() { if [ "$(id -u)" = 0 ]; then run "$@"; else run sudo "$@"; fi; }

# ------------------------------------------------------------------ is this a Jetson with JetPack 5+?

if [ "${TRON_HWDEC:-1}" = 0 ]; then
    echo "TRON_HWDEC=0: skipping the Jetson hardware decoder (GoZen decodes in software)"
    exit 0
fi

say "Jetson"
if [ "$(uname -m)" != aarch64 ] || [ ! -f /etc/nv_tegra_release ]; then
    echo "   not an NVIDIA Jetson (no /etc/nv_tegra_release): nothing to do, GoZen decodes in software here"
    exit 0
fi
L4T="$(sed -n 's/^# R\([0-9]*\) (release), REVISION: \([0-9.]*\).*/\1.\2/p' /etc/nv_tegra_release)"
note "L4T R${L4T:-?} ($( (tr -d '\0' < /proc/device-tree/model) 2>/dev/null || echo unknown model))"
case "${L4T%%.*}" in
    35|36|3[7-9]) ;;
    *) echo "   L4T R${L4T:-?} is JetPack 4 or older: Godot 4.6 needs JetPack 5 or newer (glibc 2.28+)" >&2; exit 1 ;;
esac

# ------------------------------------------------------------------ packages

say "Build packages and the Jetson Multimedia API"
PKGS=(git cmake build-essential pkg-config)
[ -d "$MMAPI/include" ] || PKGS+=(nvidia-l4t-jetson-multimedia-api)
MISSING=()
for p in "${PKGS[@]}"; do
    dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q "install ok installed" || MISSING+=("$p")
done
if [ ${#MISSING[@]} -eq 0 ]; then
    note "in place"
else
    root apt-get update
    root apt-get install -y --no-install-recommends "${MISSING[@]}"
fi
if [ "$DRY" = 0 ] && [ ! -d "$MMAPI/include" ]; then
    echo "   $MMAPI is still missing: check that the NVIDIA apt sources are enabled (JetPack)" >&2
    exit 1
fi

# ------------------------------------------------------------------ libnvmpi

say "libnvmpi (jetson-ffmpeg ${JETSON_FFMPEG_REV:0:7})"
if [ -d "$SRC/.git" ]; then
    run git -C "$SRC" fetch --quiet origin
else
    run mkdir -p "$CACHE"
    run git clone --quiet "$JETSON_FFMPEG_URL" "$SRC"
fi
run git -C "$SRC" checkout --quiet --force "$JETSON_FFMPEG_REV"
# --no-stubs: fail rather than build the non-working stub library when the Multimedia API is missing
run "$SRC/scripts/build.sh" --no-stubs --install
if [ "$DRY" = 0 ]; then
    if ldconfig -p | grep -q 'libnvmpi\.so '; then
        note "installed: $(ldconfig -p | grep 'libnvmpi\.so ' | sed 's/.*=> //')"
    else
        echo "   libnvmpi.so is not in the loader cache (ldconfig -p): GoZen would decode in software" >&2
        exit 1
    fi
fi

# ------------------------------------------------------------------ optional decode test

if [ "$TEST" = 1 ]; then
    FFMPEG="$CACHE/ffmpeg-src/ffmpeg7.1/ffmpeg"
    say "Decode test: an ffmpeg with nvmpi at $FFMPEG (not installed system-wide; takes a while)"
    run "$SRC/scripts/build.sh" --no-stubs --ffmpeg 7.1 --ffmpeg-dir "$CACHE/ffmpeg-src" --no-libx264 --no-libx265
    if [ -f "$TEST_VIDEO" ]; then
        run "$FFMPEG" -hide_banner -benchmark -c:v h264_nvmpi -i "$TEST_VIDEO" -f null -
        note "a 'speed=' well above 1x and no error above: the hardware decoder works"
    else
        note "no pack video at $TEST_VIDEO (set TRON_DIR); try:"
        note "$FFMPEG -benchmark -c:v h264_nvmpi -i <some H.264 .mp4> -f null -"
    fi
fi

say "Done$([ "$DRY" = 1 ] && echo ' (dry run: nothing was changed)')"
note "Start the game (python scripts/run.py): Godot's log says 'GoZen: hardware decoder h264_nvmpi' per video,"
note "and 'sudo tegrastats' shows NVDEC busy while they play."
