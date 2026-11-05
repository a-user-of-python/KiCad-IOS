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

# [KiCad-IOS port] KiCad 10.0.1's SWIG interface files use PyInt_*/PyString_* aliases
# that SWIG >= 4.3 dropped from its Python runtime prelude; brew now ships
# 4.5.1, whose generated pcbnew_wrap.cxx fails against Python 3 headers.
# Build the SWIG KiCad 10 was written against (4.2.1) from source instead.
if [ ! -x "$WORK/swig421/bin/swig" ]; then
  # Official release tarball first (ships a generated configure).
  ( cd "$WORK" && curl -sL "https://github.com/swig/swig/releases/download/v4.2.1/swig-4.2.1.tar.gz" -o swig421.tgz && tar -xzf swig421.tgz ) >> "$WORK/logs/swig421.log" 2>&1
  if [ ! -x "$WORK/swig-4.2.1/configure" ]; then
    ( cd "$WORK" && curl -sL "https://github.com/swig/swig/archive/refs/tags/v4.2.1.tar.gz" -o swig421.tgz && tar -xzf swig421.tgz ) >> "$WORK/logs/swig421.log" 2>&1
  fi
  brew install automake autoconf bison 2>&1 | tail -1
  # Xcode's bundled bison (2.3) rejects the -Wall flag SWIG's Makefile
  # passes; brew's bison is keg-only, so prepend it explicitly.
  export PATH="$(brew --prefix bison)/bin:$PATH"
  ( cd "$WORK/swig-4.2.1" && { [ -x ./configure ] || ./autogen.sh; } && ./configure --prefix="$WORK/swig421" --without-pcre && make -j8 && make install ) >> "$WORK/logs/swig421.log" 2>&1 || echo "SWIG421 BUILD FAILED — see logs/swig421.log"
fi
if [ -x "$WORK/swig421/bin/swig" ]; then
  export PATH="$WORK/swig421/bin:$PATH"
else
  echo "falling back to brew swig (known pcbnew_wrap issue) so the run still catalogues"
  brew install swig 2>&1 | tail -1
fi
swig -version | head -2


# protoc fallback: normally restored from the deps artifact's stash;
# build the host protoc in-job if it is missing.
if [ ! -x "$WORK/host-tools/bin/protoc" ]; then
    echo "building host protoc in-job (fallback)"
    PB_SRC_FB="$SRC/protobuf-fb"
    if [ ! -d "$PB_SRC_FB" ]; then
        git clone --depth 1 --branch v25.1 --recurse-submodules --shallow-submodules \
            https://github.com/protocolbuffers/protobuf "$PB_SRC_FB" >> "$WORK/logs/kicad-ios.log" 2>&1
    fi
    cmake -S "$PB_SRC_FB" -B "$WORK/build-protobuf-host-fb" -G Ninja \
        -DCMAKE_BUILD_TYPE=Release -Dprotobuf_BUILD_TESTS=OFF -Dprotobuf_BUILD_EXAMPLES=OFF >> "$WORK/logs/kicad-ios.log" 2>&1
    cmake --build "$WORK/build-protobuf-host-fb" -j4 --target protoc >> "$WORK/logs/kicad-ios.log" 2>&1
    mkdir -p "$WORK/host-tools/bin" "$WORK/host-tools/include/google/protobuf"
    cp "$WORK/build-protobuf-host-fb/protoc" "$WORK/host-tools/bin/protoc" || true
    cp "$PB_SRC_FB/src/google/protobuf/"*.proto "$WORK/host-tools/include/google/protobuf/" 2>/dev/null || true
fi
ls -la "$WORK/host-tools/" || true

# Prefer the sysroot-installed wx-config (see stage-wx-ios.sh: FindwxWidgets
# can only verify libraries that live under a find-root path).
WXCFG="$SYSROOT/bin/wx-config"
[ -x "$WXCFG" ] || WXCFG="$WORK/build-wx-ios/wx-config"
"$WXCFG" --selected-config || true

# GL/gl.h shim for KiCad/wx headers under iOS (see stage-wx-ios.sh) and
# OpenGL find presets: KiCad calls find_package(OpenGL REQUIRED), which
# fails on iOS (no desktop GL framework); pre-seed it with OpenGLES.
mkdir -p "$WORK/glshim/GL"
printf '#pragma once\n#include <OpenGLES/ES3/gl.h>\n#include <OpenGLES/ES3/glext.h>\n' > "$WORK/glshim/GL/gl.h"
SDK_PATH_IOS="$(xcrun --sdk iphoneos --show-sdk-path)"
OGL_FW="$SDK_PATH_IOS/System/Library/Frameworks/OpenGLES.framework"

# nanodbc (bundled) locates its ODBC driver manager by running the
# iodbc-config program, searching $ODBC_PATH/bin first. Our sysroot ships
# bin/iodbc-config (deps stage); point nanodbc at it.
export ODBC_PATH="$SYSROOT"

BLD="$WORK/build-kicad-ios"
mkdir -p "$BLD"
# PYTHON_FRAMEWORK: kicad/CMakeLists.txt uses it unquoted in
# set_target_properties(BUILD_RPATH) and KiCad only sets it for its own
# macOS packaging; empty = arg-count configure error (same fix as the
# desktop stage). On iOS there is no Python.framework bundle; the sysroot
# path is an inert placeholder until the packaging stage sets real rpaths.
cmake -S "$SRC/kicad" -B "$BLD" -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE="$PWD/scripts/ios.toolchain.cmake" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_PREFIX_PATH="$SYSROOT;$WORK/Qt/6.9.3/ios" \
    -DwxWidgets_CONFIG_EXECUTABLE="$WXCFG" \
    -DwxWidgets_CONFIG_OPTIONS="--toolkit=qt" \
    -DNGSPICE_INCLUDE_PATH="$SYSROOT/include" \
    -DNGSPICE_LIBRARY_PATH="$SYSROOT/lib" \
    -DNGSPICE_LIB_NAME=ngspice \
    -DOCC_INCLUDE_DIR="$SYSROOT/include/opencascade" \
    -DOCC_LIBRARY_DIR="$SYSROOT/lib" \
    -DPYTHON_LIBRARY="$SYSROOT/lib/libpython3.13.a" \
    -DPYTHON_FRAMEWORK="$SYSROOT" \
    -DPYTHON_INCLUDE_DIR="$SYSROOT/include/python3.13" \
    -DProtobuf_PROTOC_EXECUTABLE="$WORK/host-tools/bin/protoc" \
    -DKICAD_SCRIPTING_WXPYTHON=OFF \
    -DKICAD_USE_SENTRY=OFF \
    -DKICAD_IPC_API=OFF \
    -DKICAD_BUILD_QA_TESTS=OFF \
    -DKICAD_BUILD_I18N=OFF \
    -DKICAD_INSTALL_DEMOS=OFF \
    -DCMAKE_C_FLAGS="-I$WORK/glshim" \
    -DCMAKE_CXX_FLAGS="-I$WORK/glshim -DwxUSE_OPENGL_EMULATION=1 -DwxHAS_OPENGL_ES" \
    -DCMAKE_SHARED_LINKER_FLAGS="-framework CoreFoundation" \
    -DCMAKE_MODULE_LINKER_FLAGS="-framework CoreFoundation" \
    -DCMAKE_EXE_LINKER_FLAGS="-framework CoreFoundation" \
    -DOPENGL_INCLUDE_DIR="$OGL_FW/Headers" \
    -DOPENGL_opengl_LIBRARY="$OGL_FW" \
    -DOPENGL_gl_LIBRARY="$OGL_FW"
CFG_RC=$?
echo "KICAD_IOS_CONFIGURE_RC=$CFG_RC"
if [ "$CFG_RC" != "0" ]; then echo "RESULT: KiCad iOS configure FAILED"; exit 2; fi

cmake --build "$BLD" -j4 --target kicad -- -k 0
BLD_RC=$?
echo "KICAD_IOS_BUILD_RC=$BLD_RC"
echo "--- error summary (unique errors) ---"
grep -E "error:" "$WORK/logs/kicad-ios.log" | sort | uniq -c | sort -rn | head -40 || true
if [ "$BLD_RC" = "0" ]; then echo "RESULT: KiCad manager built for iOS arm64"; else echo "RESULT: KiCad iOS build FAILED — see error catalogue"; exit 3; fi
