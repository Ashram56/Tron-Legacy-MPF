#!/usr/bin/env bash
# docker compose for this repository with this host's settings (docker/README.md). Linux only.
#
#   docker/tron.sh                       # = up: setup, then Godot (DMD), MPF and MPF Monitor
#   docker/tron.sh up -d / down / logs -f mpf / build
#   docker/tron.sh run --rm render-check # headless DMD capture into captures/
#   docker/tron.sh run --rm test         # the unit tests
#
# It exports your user and group id (files in the repository stay yours, and the X and sound servers accept
# the container), allows your user on the X server (xhost +SI:localuser:...), and adds gpu.yml when /dev/dri
# exists, audio.yml when the PulseAudio/PipeWire socket exists and proc.yml when TRON_HW=proc. Settings come
# from the environment or docker/.env (tron.env.example). TRON_DRY=1 prints the compose command only.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

env_file_value() {      # a KEY=value from docker/.env, when the environment does not set it
    [ -f "$HERE/.env" ] || return 0
    sed -n "s/^[[:space:]]*$1=//p" "$HERE/.env" | tail -n 1 | tr -d '"'"'"
}
setting() { local v="${!1:-}"; [ -n "$v" ] || v="$(env_file_value "$1")"; printf '%s' "${v:-$2}"; }

export TRON_UID="${TRON_UID:-$(id -u)}"
export TRON_GID="${TRON_GID:-$(id -g)}"
export DISPLAY="${DISPLAY:-:0}"

FILES=(-f "$HERE/docker-compose.yml")
ADDED=()

if [ "$(setting TRON_GPU 1)" != 0 ] && [ -d /dev/dri ]; then
    FILES+=(-f "$HERE/gpu.yml")
    ADDED+=(gpu)
    card="$(find /dev/dri -maxdepth 1 -name 'card*' | head -n 1)"
    render="$(find /dev/dri -maxdepth 1 -name 'renderD*' | head -n 1)"
    [ -n "$card" ] && export TRON_VIDEO_GID="${TRON_VIDEO_GID:-$(stat -c %g "$card")}"
    [ -n "$render" ] && export TRON_RENDER_GID="${TRON_RENDER_GID:-$(stat -c %g "$render")}"
fi

PULSE="${TRON_PULSE_SOCKET:-${XDG_RUNTIME_DIR:-/run/user/$TRON_UID}/pulse/native}"
if [ "$(setting TRON_AUDIO 1)" != 0 ] && [ -S "$PULSE" ]; then
    export TRON_PULSE_SOCKET="$PULSE"
    FILES+=(-f "$HERE/audio.yml")
    ADDED+=(audio)
fi

if [ "$(setting TRON_HW virtual)" = proc ]; then
    export TRON_HW=proc
    FILES+=(-f "$HERE/proc.yml")
    ADDED+=(proc)
fi

[ $# -gt 0 ] || set -- up

CMD=(docker compose "${FILES[@]}" "$@")
echo "[tron.sh] uid $TRON_UID, DISPLAY $DISPLAY, extras: ${ADDED[*]:-none}" >&2
if [ "${TRON_DRY:-0}" = 1 ]; then
    echo "${CMD[*]}"
    exit 0
fi

case "$1" in
    up|run|start|create|restart)
        if command -v xhost >/dev/null; then
            xhost "+SI:localuser:$(id -un)" >/dev/null 2>&1 \
                || echo "[tron.sh] xhost could not allow $(id -un) on $DISPLAY: windows may not open (docker/README.md)" >&2
        else
            echo "[tron.sh] no xhost (package x11-xserver-utils or xorg-xhost): if no window opens, see docker/README.md" >&2
        fi
        ;;
esac
exec "${CMD[@]}"
