#!/usr/bin/env bash
# Builds PinMAME (pinned) with the ARM hook of Tron-Legacy-LE-ROM-Decryption rules/tools/trace and tron_ref with a DMD dump.
# Usage: build_tron_ref.sh WORKDIR ASSET_REPO_DIR   (the ROM is never part of this; put trn_174h.zip in $TRON_ROMS)
# Run: TRON_ROMS=DIR PINMAME_NOJIT=1 TRON_DMDLOG=out.dmd ./tron_ref scenario.txt out.jsonl
# .dmd = per change: <double t><int32 w><int32 h><int32 depth> then w*h bytes (shade 0-15). Verified 2026-10-30.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
W=$1; A=$2; T=$A/rules/tools/trace; mkdir -p "$W"; cd "$W"
git clone -q https://github.com/vpinball/pinmame pinmame && git -C pinmame checkout -q 540bbb1e2b7fd9e9a69947ca23de2c28662e0534
cd pinmame
git apply --exclude=src/libpinmame/libpinmame.cpp "$T/pinmame_arm_hook.patch"
# the patch's libpinmame.cpp hunk (appended at the end of the file) no longer applies to current PinMAME: append it
sed -n '/libpinmame.cpp/,$p' "$T/pinmame_arm_hook.patch" | grep '^+' | grep -v '^+++' | sed 's/^+//' >> src/libpinmame/libpinmame.cpp
cp cmake/libpinmame/CMakeLists.txt . && mkdir -p build && cd build
cmake -DPLATFORM=linux -DARCH=x64 -DBUILD_STATIC=OFF -DCMAKE_BUILD_TYPE=Release .. && make -j4
cd ../..
cp "$T/tron_ref.cpp" . && patch -s tron_ref.cpp < "$HERE/tron_ref_dmddump.diff"
g++ -O2 -std=c++17 -Ipinmame/src/libpinmame tron_ref.cpp -Lpinmame/build -lpinmame -lpthread -Wl,-rpath,$PWD/pinmame/build -o tron_ref
