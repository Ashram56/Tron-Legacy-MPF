# Tron Legacy MPF in a container, for Linux hosts (docker/README.md). The image holds the toolchain only:
# Python 3.11 with the pinned MPF + MPF Monitor in /opt/venv, Godot in /opt/godot, and the libraries Godot and
# Qt need for windows (X11), OpenGL/Vulkan (Mesa) and sound (PulseAudio/PipeWire). The repository, with the
# asset submodule, is bind-mounted at /workspace at run time; the generated config, media and the Godot
# import land there (git-ignored, the same files a native setup makes).
#
#   docker compose -f docker/docker-compose.yml build                         # from the repository root
#   docker compose -f docker/docker-compose.yml build --build-arg WITH_PROC=1 # + libpinproc/pypinproc (P-ROC)
#
# Versions come from scripts/toolchain.py, the same file the native setup reads.
ARG BASE_IMAGE=python:3.11-slim-bookworm
FROM ${BASE_IMAGE}

ARG WITH_PROC=0
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1

# Godot (X11/Wayland, GL/Vulkan through Mesa, ALSA/PulseAudio), Qt 6 for MPF Monitor (xcb), Xvfb for the
# headless render check, git for the GMC fallback download, and the P-ROC's USB libraries. (Ubuntu 24.04
# renamed two of them with a t64 suffix: picked automatically, should BASE_IMAGE be such an image.)
RUN apt-get update \
 && t64() { if apt-cache show "${1}t64" >/dev/null 2>&1; then echo "${1}t64"; else echo "$1"; fi; } \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl unzip git procps \
      libgl1 libegl1 libgl1-mesa-dri libglx-mesa0 libvulkan1 mesa-vulkan-drivers \
      libx11-6 libxcursor1 libxinerama1 libxrandr2 libxi6 libxext6 libxrender1 libxkbcommon0 \
      libwayland-client0 libwayland-cursor0 libwayland-egl1 libdecor-0-0 \
      libfontconfig1 fonts-dejavu-core "$(t64 libasound2)" libpulse0 libdbus-1-3 libudev1 \
      "$(t64 libglib2.0-0)" libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
      libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 libxcb-xkb1 \
      xvfb xauth \
      libusb-1.0-0 libftdi1-2 \
 && rm -rf /var/lib/apt/lists/* \
 && git config --system --add safe.directory '*'

# The pinned Python packages (MPF, pillow, pytest, MPF Monitor) in /opt/venv, plus MPF Monitor's window
# layouts that its PyPI release lacks (scripts/toolchain.py)
COPY scripts/toolchain.py scripts/setup.py /opt/tron/
RUN python -m venv /opt/venv \
 && /opt/venv/bin/python -m pip install --quiet --upgrade pip \
 && python -c "import sys; sys.path.insert(0, '/opt/tron'); import toolchain as t; \
print('\n'.join(t.REQUIREMENTS + t.MONITOR_REQUIREMENTS))" > /opt/tron/requirements.txt \
 && /opt/venv/bin/python -m pip install --quiet -r /opt/tron/requirements.txt \
 && python -c "import sys; sys.path.insert(0, '/opt/tron'); import setup; setup.install_monitor_ui('/opt/venv/bin/python')" \
 && /opt/venv/bin/mpf --version

# Godot, the official Linux build for this CPU (x86_64 or arm64)
RUN url="$(python -c "import sys; sys.path.insert(0, '/opt/tron'); import toolchain as t; print(t.godot_url('linux'))")" \
 && echo "Godot: $url" \
 && curl -fsSL -o /tmp/godot.zip "$url" \
 && mkdir -p /opt/godot \
 && unzip -q /tmp/godot.zip -d /opt/godot \
 && rm /tmp/godot.zip \
 && ln -s "$(ls /opt/godot/Godot_v*)" /opt/godot/godot \
 && chmod +x /opt/godot/Godot_v* \
 && /opt/godot/godot --headless --version

# Optional: libpinproc + pypinproc for the real machine (docker compose build --build-arg WITH_PROC=1)
COPY scripts/install/build_pinproc.sh /opt/tron/build_pinproc.sh
RUN if [ "$WITH_PROC" = 1 ]; then \
      apt-get update \
   && apt-get install -y --no-install-recommends build-essential cmake pkg-config \
        libusb-1.0-0-dev libusb-dev libftdi1-dev \
   && /opt/tron/build_pinproc.sh --python /opt/venv/bin/python --prefix /usr/local --src /tmp/pinproc \
   && rm -rf /tmp/pinproc /var/lib/apt/lists/*; \
    fi

# Any user id can run the image (compose passes the host user's, so files in the repository stay yours).
# HOME is a volume in compose: Godot's user data (user://) survives restarts.
RUN mkdir -p /home/tron && chmod 1777 /home/tron
COPY docker/entrypoint.py /opt/tron/entrypoint.py
ENV TRON_VENV=/opt/venv \
    GODOT=/opt/godot/godot \
    PATH=/opt/venv/bin:/opt/godot:$PATH \
    HOME=/home/tron \
    XDG_RUNTIME_DIR=/tmp \
    QT_QPA_PLATFORM=xcb
WORKDIR /workspace
ENTRYPOINT ["python", "/opt/tron/entrypoint.py"]
CMD ["shell"]
