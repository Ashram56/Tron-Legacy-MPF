#!/usr/bin/env bash
# Builds dmd_serum: libserum (pinned; git, CMake >= 3.25, a C++17 compiler) linked into the game's colouriser (GPL v2). Build on a
# build box (the bundle's build, scripts/package/build_bundle.py), never on the Raspberry Pi. Another CPU:
# CC=... CXX=... (e.g. "zig cc -target aarch64-linux-gnu", "zig c++ -target aarch64-linux-gnu").
#   game/native/dmd_serum/build.sh OUT [WORKDIR]
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=$1
CC=${CC:-cc}; CXX=${CXX:-c++}
for t in git cmake; do command -v $t >/dev/null || { echo "build.sh needs $t on the build box (git, CMake >= 3.25, a C++17 compiler; zig for another CPU)" >&2; exit 1; }; done
W=${2:-$HERE/../serum_build}; mkdir -p "$W"; W=$(cd "$W" && pwd)
# CMake wants one executable, not "zig cc -target ...": a command with arguments goes through a small wrapper
wrap() { case "$1" in *" "*) printf '#!/bin/sh\nexec %s "$@"\n' "$1" > "$W/$2"; chmod +x "$W/$2"; echo "$W/$2";; *) echo "$1";; esac; }
case "$CC" in *aarch64*|*arm64*) TARGET_ARCH=arm64;; *x86_64*) TARGET_ARCH=x64;; *) TARGET_ARCH=;; esac
CC=$(wrap "$CC" cc-wrap); CXX=$(wrap "$CXX" cxx-wrap)
LIBSERUM_REF=v2.8.0
FRAMEUTIL_SHA=711ab21dcf9ad33d8db8339dfd3b1548bcc34cdb       # libserum's platforms/config.sh
[ -d "$W/libserum" ] || git clone -q --depth 1 --branch $LIBSERUM_REF https://github.com/PPUC/libserum.git "$W/libserum"
[ -d "$W/libframeutil" ] || { git clone -q https://github.com/PPUC/libframeutil.git "$W/libframeutil"; git -C "$W/libframeutil" checkout -q $FRAMEUTIL_SHA; }
cp "$W/libframeutil/include/FrameUtil.h" "$W/libserum/third-party/include/FrameUtil.h"
case "$(uname -s)" in Darwin) PLAT=macos;; *) PLAT=linux;; esac
case "$(uname -m)" in arm64|aarch64) ARCH=arm64;; *) ARCH=x64;; esac
ARCH=${TARGET_ARCH:-$ARCH}
cmake -S "$W/libserum" -B "$W/build" -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED=OFF -DBUILD_STATIC=ON -DPLATFORM=$PLAT -DARCH=$ARCH \
      -DCMAKE_C_COMPILER="$CC" -DCMAKE_CXX_COMPILER="$CXX" >/dev/null
cmake --build "$W/build" -j "$(nproc 2>/dev/null || echo 2)" --target serum_static 2>/dev/null || cmake --build "$W/build" -j 2
LIB=$(find "$W/build" -name libserum.a | head -1)
mkdir -p "$(dirname "$OUT")"
$CXX -O2 -Wall -std=c++17 -I"$W/libserum/src" -o "$OUT" "$HERE/dmd_serum.cpp" "$LIB" -lpthread
