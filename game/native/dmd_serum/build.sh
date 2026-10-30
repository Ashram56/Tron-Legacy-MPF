#!/usr/bin/env bash
# Builds dmd_serum, the game's Serum colouriser (GPL v2), against a libserum the PLATFORM provides: libserum, its pinned
# dependencies and their build are the platform's (MPF-Godot-Packaging, the image generator); this script downloads and builds
# nothing of libserum. LIBSERUM_DIR holds the libserum headers (src/serum.h or serum.h) and the static library built for the
# target CPU (libserum.a, anywhere below it). Another CPU: CXX=... (e.g. "zig c++ -target aarch64-linux-gnu"). Never on the
# Raspberry Pi.
#   LIBSERUM_DIR=/path game/native/dmd_serum/build.sh OUT
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=$1
CXX=${CXX:-c++}
D=${LIBSERUM_DIR:-}
[ -n "$D" ] && [ -d "$D" ] || { echo "build.sh needs LIBSERUM_DIR: libserum's headers and libserum.a for the target CPU, provided by the platform (MPF-Godot-Packaging)" >&2; exit 1; }
LIB=$(find "$D" -name libserum.a | head -1)
INC=$(dirname "$(find "$D" -name serum.h | head -1)")
[ -n "$LIB" ] && [ -n "$INC" ] || { echo "LIBSERUM_DIR $D has no libserum.a or serum.h" >&2; exit 1; }
mkdir -p "$(dirname "$OUT")"
# a compiler with arguments ("zig c++ -target ...") is a word list, not one executable
$CXX -O2 -Wall -std=c++17 -I"$INC" -o "$OUT" "$HERE/dmd_serum.cpp" "$LIB" -lpthread
