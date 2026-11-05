#!/usr/bin/env bash
# Stage: KiCad for iOS arm64 — configure the ACTUAL KiCad 10.0.1 against
# the iOS wxQt build + the cross-built sysroot, then catalogue-build the
# manager target with -k 0. Prereqs assembled by the workflow job:
# work/sysroot-ios merged from the deps/occ/ngspice/python artifacts.
source "$(dirname "$0")/ci-common.sh"
exec > >(tee "$WORK/logs/kicad-ios.log") 2>&1
set -ux

export SYSROOT="$WORK/sysroot-ios"
echo "--- sysroot libs ---"
ls "$SYSROOT/lib" | head -40

if [ ! -f "$WORK/build-wx-ios/wx-config" ]; then
    bash scripts/stage-wx-ios.sh || echo "wx ios stage failed"
fi
fetch_kicad
apply_patches "$SRC/kicad" kicad
brew install swig 2>&1 | tail -1

# protoc fallback: normally restored from the deps artifact's stash;
# build the host protoc in-job if it is missing.
if [ ! -x "$WORK/host-tools/protoc" ]; then
    echo "building host protoc in-job (fallback)"
    PB_SRC_FB="$SRC/protobuf-fb"
    if [ ! -d "$PB_SRC_FB" ]; then
        git clone --depth 1 --branch v25.1 --recurse-submodules --shallow-submodules \
            https://github.com/protocolbuffers/protobuf "$PB_SRC_FB" >> "$WORK/logs/kicad-ios.log" 2>&1
    fi
    cmake -S "$PB_SRC_FB" -B "$WORK/build-protobuf-host-fb" -G Ninja \
        -DCMAKE_BUILD_TYPE=Release -Dprotobuf_BUILD_TESTS=OFF -Dprotobuf_BUILD_EXAMPLES=OFF >> "$WORK/logs/kicad-ios.log" 2>&1
    cmake --build "$WORK/build-protobuf-host-fb" -j4 --target protoc >> "$WORK/logs/kicad-ios.log" 2>&1
    mkdir -p "$WORK/host-tools"
    cp "$WORK/build-protobuf-host-fb/protoc" "$WORK/host-tools/protoc" || true
fi
ls -la "$WORK/host-tools/" || true

WXCFG="$WORK/build-wx-ios/wx-config"
"$WXCFG" --selected-config || true

BLD="$WORK/build-kicad-ios"
mkdir -p "$BLD"
cmake -S "$SRC/kicad" -B "$BLD" -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE="$PWD/scripts/ios.toolchain.cmake" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_PREFIX_PATH="$SYSROOT;$WORK/Qt/6.9.3/ios" \
    -DwxWidgets_CONFIG_EXECUTABLE="$WXCFG" \
    -DwxWidgets_CONFIG_OPTIONS="--toolkit=qt" \
    -DNGSPICE_INCLUDE_PATH="$SYSROOT/include" \
    -DNGSPICE_LIBRARY_PATH="$SYSROOT/lib" \
    -DNGSPICE_LIB_NAME=ngspice \
    -DPYTHON_LIBRARY="$SYSROOT/lib/libpython3.13.a" \
    -DPYTHON_INCLUDE_DIR="$SYSROOT/include/python3.13" \
    -DProtobuf_PROTOC_EXECUTABLE="$WORK/host-tools/protoc" \
    -DKICAD_SCRIPTING_WXPYTHON=OFF \
    -DKICAD_USE_SENTRY=OFF \
    -DKICAD_IPC_API=OFF \
    -DKICAD_BUILD_QA_TESTS=OFF \
    -DKICAD_BUILD_I18N=OFF \
    -DKICAD_INSTALL_DEMOS=OFF
CFG_RC=$?
echo "KICAD_IOS_CONFIGURE_RC=$CFG_RC"
if [ "$CFG_RC" != "0" ]; then echo "RESULT: KiCad iOS configure FAILED"; exit 2; fi

cmake --build "$BLD" -j4 --target kicad -- -k 0
BLD_RC=$?
echo "KICAD_IOS_BUILD_RC=$BLD_RC"
echo "--- error summary (unique errors) ---"
grep -E "error:" "$WORK/logs/kicad-ios.log" | sort | uniq -c | sort -rn | head -40 || true
if [ "$BLD_RC" = "0" ]; then echo "RESULT: KiCad manager built for iOS arm64"; else echo "RESULT: KiCad iOS build FAILED — see error catalogue"; exit 3; fi
