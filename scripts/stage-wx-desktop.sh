#!/bin/bash
# [KiCad-IOS port] Stage: wx-desktop probe.
# Question it answers: does KiCad's patched wx fork even BUILD with the
# wxQt backend (Qt 6, macOS desktop) — the cheapest possible test of the
# wxQt bridge before any iOS cross-compiling enters the picture?
set -uo pipefail
cd "$(dirname "$0")/.."
source scripts/ci-common.sh

install_qt desktop
fetch_wx

QT_DESKTOP=""
for d in "$QT_ROOT/$QT_VERSION/macos" "$QT_ROOT/$QT_VERSION/clang_64"; do
    [ -d "$d" ] && QT_DESKTOP="$d" && break
done
echo "QT_DESKTOP=$QT_DESKTOP"
command -v ninja >/dev/null || brew install ninja

BLD="$WORK/build-wx-desktop"
mkdir -p "$BLD"
set -x
cmake -S "$SRC/wx" -B "$BLD" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DwxBUILD_TOOLKIT=qt \
    -DwxBUILD_SHARED=ON \
    -DwxBUILD_SAMPLES=OFF \
    -DwxBUILD_TESTS=OFF \
    -DwxBUILD_DEMOS=OFF \
    -DwxUSE_WEBVIEW=ON \
    -DCMAKE_PREFIX_PATH="$QT_DESKTOP" \
    2>&1 | tee "$WORK/logs/wx-desktop-configure.log"
CFG_RC=${PIPESTATUS[0]}
set +x
echo "WX_DESKTOP_CONFIGURE_RC=$CFG_RC"
if [ "$CFG_RC" != "0" ]; then
    echo "RESULT: wx CMake configure FAILED (see log)"; exit 2
fi

cmake --build "$BLD" -j"$(sysctl -n hw.ncpu)" 2>&1 | tee "$WORK/logs/wx-desktop-build.log"
BLD_RC=${PIPESTATUS[0]}
echo "WX_DESKTOP_BUILD_RC=$BLD_RC"
find "$BLD" -name "wx-config*" -o -name "libwx*" | head -20
"$BLD/wx-config" --selected-config 2>/dev/null || find "$BLD" -name wx-config -exec {} --selected-config \;
if [ "$BLD_RC" = "0" ]; then echo "RESULT: wxQt (KiCad fork) DESKTOP BUILD OK"; else echo "RESULT: wxQt desktop build FAILED"; exit 3; fi
