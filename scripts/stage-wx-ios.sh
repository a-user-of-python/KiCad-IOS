#!/bin/bash
# [KiCad-IOS port] Stage: wx-iOS.
# Question it answers: does wxWidgets (KiCad fork) with the wxQt backend
# CROSS-COMPILE for iOS arm64 against Qt 6's iOS kit?
set -uo pipefail
cd "$(dirname "$0")/.."
source scripts/ci-common.sh

install_qt both
fetch_wx
apply_patches "$SRC/wx" wx

QT_IOS="$QT_ROOT/$QT_VERSION/ios"
QT_DESKTOP=""
for d in "$QT_ROOT/$QT_VERSION/macos" "$QT_ROOT/$QT_VERSION/clang_64"; do
    [ -d "$d" ] && QT_DESKTOP="$d" && break
done
echo "QT_IOS=$QT_IOS QT_DESKTOP=$QT_DESKTOP"
test -f "$QT_IOS/lib/cmake/Qt6/qt.toolchain.cmake" || { echo "Qt iOS toolchain file missing"; exit 2; }
command -v ninja >/dev/null || brew install ninja

# wx/qt/glcanvas.h includes <GL/gl.h>; iOS has no such header. Shim it to
# the OpenGLES ES1 headers (same trick as the desktop stage's OpenGL shim;
# ES1 because wx's GL emulation layer below targets the fixed-function
# ES1 entry points).
mkdir -p "$WORK/glshim/GL"
printf '#pragma once\n#include <OpenGLES/ES1/gl.h>\n#include <OpenGLES/ES1/glext.h>\n' > "$WORK/glshim/GL/gl.h"

BLD="$WORK/build-wx-ios"
mkdir -p "$BLD"
set -x
cmake -S "$SRC/wx" -B "$BLD" -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE="$QT_IOS/lib/cmake/Qt6/qt.toolchain.cmake" \
    -DQT_HOST_PATH="$QT_DESKTOP" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_OSX_DEPLOYMENT_TARGET=16.0 \
    -DwxBUILD_TOOLKIT=qt \
    -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
    -DwxBUILD_SHARED=OFF \
    -DwxUSE_MENUS=ON \
    -DwxUSE_MENUBAR=ON \
    -DwxUSE_SECRETSTORE=OFF \
    -DwxUSE_MIMETYPE=OFF \
    -DwxUSE_JOYSTICK=OFF \
    -DwxUSE_XRC=OFF \
    -DwxBUILD_SAMPLES=OFF \
    -DwxBUILD_TESTS=OFF \
    -DwxBUILD_DEMOS=OFF \
    -DCMAKE_PREFIX_PATH="$QT_IOS" \
    -DCMAKE_C_FLAGS="-I$WORK/glshim" \
    -DCMAKE_CXX_FLAGS="-I$WORK/glshim -DwxUSE_OPENGL_EMULATION=1 -DwxHAS_OPENGL_ES" \
    2>&1 | tee "$WORK/logs/wx-ios-configure.log"
CFG_RC=${PIPESTATUS[0]}
set +x
echo "WX_IOS_CONFIGURE_RC=$CFG_RC"
echo "--- generated wx setup.h feature values (diagnostic) ---"
grep -h 'define wxUSE_MENUS\|define wxUSE_MENUBAR\|define wxUSE_WEBVIEW' "$WORK"/build-wx-ios/lib/wx/include/*/wx/setup.h | sort -u || true
echo "--- macro probe (defs.h in the iOS wx environment) ---"
SETUP_DIR=$(echo "$WORK"/build-wx-ios/lib/wx/include/*/ | awk '{print $1}')
SDK_PATH="$(xcrun --sdk iphoneos --show-sdk-path)"
printf '#include "wx/defs.h"\n' > "$WORK/probe.cpp"
clang++ -target arm64-apple-ios16.0 -isysroot "$SDK_PATH" -D__WXQT__ -DWXBUILDING \
    -I"${SETUP_DIR%/}" -I"$SRC/wx/include" -dM -E "$WORK/probe.cpp" 2>/dev/null | \
    grep -E 'define (wxUSE_MENUBAR|wxUSE_MENUS|__WXOSX|__WXDARWIN|__WXQT__)' | sort -u || true
if [ "$CFG_RC" != "0" ]; then
    echo "RESULT: wx iOS CMake configure FAILED (see log)"; exit 2
fi

cmake --build "$BLD" -j"$(sysctl -n hw.ncpu)" 2>&1 | tee "$WORK/logs/wx-ios-build.log"
BLD_RC=${PIPESTATUS[0]}
echo "WX_IOS_BUILD_RC=$BLD_RC"
if [ "$BLD_RC" = "0" ]; then
    # Install wx into the sysroot like every other dependency: KiCad's
    # FindwxWidgets verifies each -l with find_library, and the iOS
    # toolchain confines find_library to the find-root paths (the
    # sysroot) — a build-tree wx outside it can never verify.
    cmake --install "$BLD" --prefix "$SYSROOT" 2>&1 | tail -2
    ls "$SYSROOT/lib/" | grep '^libwx' | head -20
    find "$BLD" -name "libwx*" | head -30
    # sanity: the libs must be arm64 iOS objects
    LIB=$(find "$BLD" -name "libwx_baseu-*.a" | head -1)
    [ -n "$LIB" ] && { xcrun lipo -info "$LIB" || file "$LIB"; }
    echo "RESULT: wxQt iOS BUILD OK"
else
    echo "RESULT: wxQt iOS build FAILED"; exit 3
fi
