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

# --- One libpng owns the bundle (launch fix round 7) -------------------
# Until v8 this stage configured wx with CMAKE_PREFIX_PATH="$QT_IOS"
# only, so wx's find_package(PNG) could not see the deps sysroot and
# png.cmake silently forced wxUSE_LIBPNG=builtin: the executable ended
# up with TWO libpng implementations -- wx's bundled 1.6.59 (wx_png_*)
# serving wxPNGHandler, and the sysroot 1.6.43 linked by everything
# else -- whose png_struct layouts diverge, all exported into one flat
# namespace. On device (KiCad-Spike-v8) startup died inside
# wx_png_destroy_read_struct during the first BITMAP_STORE icon load
# with libmalloc's "pointer being freed was not allocated". Fix at the
# convicted layer: the sysroot is on wx's find path, wxUSE_LIBPNG is
# forced to "sys", and this stage FAILS CLOSED if the sysroot copies
# are absent or if a bundled wxpng/wxzlib archive is produced anyway
# (wx's png.cmake/zlib.cmake fall back to builtin silently when the
# find fails, so the -D alone is not sufficient). Zlib and expat ride
# the same find path (both are "sys" by default on Apple and fell back
# the same way).
PNG_LIB=""
for cand in "$SYSROOT/lib/libpng16.a" "$SYSROOT/lib/libpng.a"; do
    [ -f "$cand" ] && PNG_LIB="$cand" && break
done
if [ -z "$PNG_LIB" ] || [ ! -f "$SYSROOT/include/png.h" ] \
    || [ ! -f "$SYSROOT/lib/libz.a" ] || [ ! -f "$SYSROOT/lib/libexpat.a" ]; then
    echo "RESULT: deps sysroot incomplete (need libpng/libz/libexpat under $SYSROOT) --"
    echo "refusing to configure wx: a missing find would silently select wx's"
    echo "bundled libpng 1.6.59 next to the sysroot 1.6.43 (the v8 crash class)."
    exit 2
fi
echo "wx third-party resolution: PNG=$PNG_LIB ZLIB=$SYSROOT/lib/libz.a EXPAT=$SYSROOT/lib/libexpat.a"

set -x
cmake -S "$SRC/wx" -B "$BLD" -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE="$QT_IOS/lib/cmake/Qt6/qt.toolchain.cmake" \
    -DQT_HOST_PATH="$QT_DESKTOP" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="$SYSROOT" \
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
    -DwxUSE_LIBPNG=sys \
    -DwxUSE_ZLIB=sys \
    -DwxUSE_EXPAT=sys \
    -DPNG_PNG_INCLUDE_DIR="$SYSROOT/include" \
    -DPNG_LIBRARY="$PNG_LIB" \
    -DZLIB_INCLUDE_DIR="$SYSROOT/include" \
    -DZLIB_LIBRARY="$SYSROOT/lib/libz.a" \
    -DEXPAT_INCLUDE_DIR="$SYSROOT/include" \
    -DEXPAT_LIBRARY="$SYSROOT/lib/libexpat.a" \
    -DwxBUILD_SAMPLES=OFF \
    -DwxBUILD_TESTS=OFF \
    -DwxBUILD_DEMOS=OFF \
    -DCMAKE_PREFIX_PATH="$QT_IOS;$SYSROOT" \
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
    cmake --install "$BLD" 2>&1 | tail -2
    ls "$SYSROOT/lib/" | grep '^libwx' | head -20
    # Fail closed on the round-7 invariant: no bundled wx png/zlib
    # archives may exist, and the cache must show the system values.
    grep -E '^wxUSE_(LIBPNG|ZLIB|EXPAT):' "$BLD/CMakeCache.txt" || true
    if ls "$SYSROOT"/lib/libwxpng*.a "$SYSROOT"/lib/libwxzlib*.a >/dev/null 2>&1; then
        echo "RESULT: bundled wxpng/wxzlib archive present despite wxUSE_*=sys --"
        echo "wx silently fell back to its bundled libpng (the v8 crash class). Stopping."
        exit 3
    fi
    echo "wx third-party check: no libwxpng/libwxzlib archives (system libpng/zlib in use)"
    find "$BLD" -name "libwx*" | head -30
    # sanity: the libs must be arm64 iOS objects
    LIB=$(find "$BLD" -name "libwx_baseu-*.a" | head -1)
    [ -n "$LIB" ] && { xcrun lipo -info "$LIB" || file "$LIB"; }
    echo "RESULT: wxQt iOS BUILD OK"
else
    echo "RESULT: wxQt iOS build FAILED"; exit 3
fi
