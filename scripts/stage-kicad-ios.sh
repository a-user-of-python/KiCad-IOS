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
# The guard: TUs that include KiCad's bundled glad first (kicad_gl) must
# not see the real ES3 declarations afterwards (wx/qt/glcanvas.h pulls
# this shim) -- glad #defines every gl* name to its glad_gl* pointer, so
# the SDK prototypes would be rewritten into colliding declarations.
# glad already provides all types/constants in that case, so the shim
# defers to it; otherwise it forwards to the real ES3 headers.
printf '#pragma once\n#ifndef GLAD_GL_H_\n#include <OpenGLES/ES3/gl.h>\n#include <OpenGLES/ES3/glext.h>\n#endif\n' > "$WORK/glshim/GL/gl.h"
# KiCad's kiglu.h uses the macOS framework include style on __APPLE__:
# <OpenGL/gl.h> gets the same glad-aware shim, and <OpenGL/glu.h> is our
# GLU-tessellator subset header (glu/glu.h in this repo), implemented by
# glu/glu_tess_adapter.c over libtess2 (deps stage) — iOS has no GLU.
mkdir -p "$WORK/glshim/OpenGL"
cp "$WORK/glshim/GL/gl.h" "$WORK/glshim/OpenGL/gl.h"
cp "$PWD/glu/glu.h" "$WORK/glshim/OpenGL/glu.h"
xcrun --sdk iphoneos clang -target arm64-apple-ios17.0 \
    -isysroot "$(xcrun --sdk iphoneos --show-sdk-path)" -O2 \
    -I"$SYSROOT/include" -I"$PWD/glu" -c "$PWD/glu/glu_tess_adapter.c" \
    -o "$WORK/glshim/glu_tess_adapter.o" >> "$WORK/logs/kicad-ios.log" 2>&1 \
    && xcrun --sdk iphoneos clang -target arm64-apple-ios17.0 \
    -isysroot "$(xcrun --sdk iphoneos --show-sdk-path)" -O2 \
    -I"$PWD/glu" -c "$PWD/glu/glu_quadric_adapter.c" \
    -o "$WORK/glshim/glu_quadric_adapter.o" >> "$WORK/logs/kicad-ios.log" 2>&1 \
    && ar rcs "$WORK/glshim/libgluadapter.a" "$WORK/glshim/glu_tess_adapter.o" "$WORK/glshim/glu_quadric_adapter.o" \
    || echo "WARNING: GLU adapters failed to build"
SDK_PATH_IOS="$(xcrun --sdk iphoneos --show-sdk-path)"
OGL_FW="$SDK_PATH_IOS/System/Library/Frameworks/OpenGLES.framework"

# nanodbc (bundled) locates its ODBC driver manager by running the
# iodbc-config program, searching $ODBC_PATH/bin first. Our sysroot ships
# bin/iodbc-config (deps stage); point nanodbc at it.
export ODBC_PATH="$SYSROOT"

# Host build tools that KiCad would otherwise build for the target:
# 'lemon' is a single C file; KiCad's generate_lemon_grammar() stores
# $<TARGET_FILE:lemon> in the LEMON_EXE cache var without FORCE, so a
# command-line pre-seed with a host-built lemon wins and the parser
# generation steps can actually run on the macOS host.
mkdir -p "$WORK/host-tools/bin"
cc -O2 -o "$WORK/host-tools/bin/lemon" "$SRC/kicad/thirdparty/lemon/lemon.c" >> "$WORK/logs/kicad-ios.log" 2>&1 \
    || echo "WARNING: host lemon build failed"

BLD="$WORK/build-kicad-ios"
mkdir -p "$BLD"
# Scrub macOS-desktop-only link tokens baked into dependency metadata
# during the cross builds (their configure probes ran on the macOS host):
#  - curl records -lidn2 / -lsocket (no such libraries on iOS; IDN is not
#    needed and socket lives in libSystem) in libcurl.pc / curl-config /
#    its CMake config.
#  - wx-config emits -framework AppKit for any Darwin build; AppKit does
#    not exist on iOS (its role is UIKit's, already linked via Qt).
# The kicommon link failed on exactly these (run 42027866119).
for f in "$SYSROOT/bin/curl-config" "$SYSROOT/lib/pkgconfig/libcurl.pc" \
         "$SYSROOT/lib/cmake/CURL/CURLConfig.cmake" \
         "$SYSROOT/lib/cmake/CURL/CURLTargets.cmake"; do
    [ -f "$f" ] && sed -i '' -e 's/-lidn2//g' -e 's/-lsocket//g' "$f"
done
# The CMake target files record the same libraries as bare list items
# (idn2, not -lidn2); strip those too. (Deps now also builds curl with
# CURL_USE_LIBIDN2=OFF, so this is belt-and-braces for restored sysroots.)
for f in "$SYSROOT/lib/cmake/CURL/CURLConfig.cmake" \
         "$SYSROOT/lib/cmake/CURL/CURLTargets.cmake"; do
    [ -f "$f" ] && sed -i '' -e 's/idn2//g' -e 's/socket//g' "$f"
done
[ -f "$SYSROOT/bin/wx-config" ] && sed -i '' 's/-framework AppKit//g' "$SYSROOT/bin/wx-config"
# AppKit also rides in wx's CMake config package (lib/cmake/wxWidgets/*),
# which CMake's find_package prefers over the FindwxWidgets module.
# Scrub the token from every sysroot metadata file that carries it.
grep -rl 'AppKit' "$SYSROOT/lib" "$SYSROOT/bin" 2>/dev/null | while read -r f; do
    echo "scrubbing AppKit from $f"
    sed -i '' 's/-framework AppKit//g; s/AppKit//g' "$f"
done
echo "AppKit remaining in sysroot metadata: $(grep -rl 'AppKit' "$SYSROOT/lib" "$SYSROOT/bin" 2>/dev/null | wc -l)"

# PYTHON_FRAMEWORK: kicad/CMakeLists.txt uses it unquoted in
# set_target_properties(BUILD_RPATH) and KiCad only sets it for its own
# macOS packaging; empty = arg-count configure error (same fix as the
# desktop stage). On iOS there is no Python.framework bundle; the sysroot
# path is an inert placeholder until the packaging stage sets real rpaths.
# Qt's static frameworks are linked by KiCad as bare paths, so their own
# transitive deps must be named explicitly (run 42037298290 catalogue:
# 159 undefined symbols, all in these buckets). Qt bundles pcre2 for
# QRegularExpression inside the kit; locate it.
QT_PCRE2="$(find "$WORK/Qt" -name 'libQtBundledPcre2*.a' 2>/dev/null | head -1)"
echo "Qt bundled pcre2: ${QT_PCRE2:-NOT FOUND}"
IOS_FW="-framework CoreFoundation -framework Foundation -framework UIKit -framework Metal -framework IOKit -framework CoreGraphics -framework CoreText -framework CoreServices -framework UniformTypeIdentifiers"
IOS_EXTRA_LIBS="-lpng16 -lpcre2-16 $WORK/glshim/libgluadapter.a -ltess2 $QT_PCRE2"

# Qt for iOS is fully static: the platform plugin (libqios.a) and the
# image-format plugins only register if the executable imports them
# (Q_IMPORT_PLUGIN) — Qt-CMake apps get that generated; KiCad/wx do not,
# and nothing in wxQt does it either (grep: zero Q_IMPORT_PLUGIN in wx).
# Generate the import TU here and force-load the platform plugin into
# the manager executable (kifaces load into the same process later).
QTDIR_IOS="$WORK/Qt/6.9.3/ios"
QIOS_LIB="$(find "$QTDIR_IOS" -name 'libqios.a' 2>/dev/null | head -1)"
QGIF_LIB="$(find "$QTDIR_IOS" -name 'libqgif.a' 2>/dev/null | head -1)"
QICO_LIB="$(find "$QTDIR_IOS" -name 'libqico.a' 2>/dev/null | head -1)"
QJPEG_LIB="$(find "$QTDIR_IOS" -name 'libqjpeg.a' 2>/dev/null | head -1)"
echo "Qt plugins: qios=$QIOS_LIB gif=$QGIF_LIB ico=$QICO_LIB jpeg=$QJPEG_LIB"
PLUGIN_ITEMS=""
if [ -n "$QIOS_LIB" ]; then
    cat > "$WORK/glshim/qt_plugin_import.cpp" <<'CPPEOF'
#include <QtCore/QtPlugin>
Q_IMPORT_PLUGIN(QIOSIntegrationPlugin)
Q_IMPORT_PLUGIN(QGifPlugin)
Q_IMPORT_PLUGIN(QICOPlugin)
Q_IMPORT_PLUGIN(QJpegPlugin)
CPPEOF
    ls "$QTDIR_IOS/include/QtCore/QtPlugin" || echo "QtPlugin header NOT at include/QtCore"
    xcrun --sdk iphoneos clang++ -target arm64-apple-ios17.0 \
        -isysroot "$(xcrun --sdk iphoneos --show-sdk-path)" -O2 -std=c++17 \
        -I"$QTDIR_IOS/include" -I"$QTDIR_IOS/include/QtCore" \
        -I"$QTDIR_IOS/lib/QtCore.framework/Headers" -F"$QTDIR_IOS/lib" \
        -include arm_acle.h \
        -c "$WORK/glshim/qt_plugin_import.cpp" \
        -o "$WORK/glshim/qt_plugin_import.o"
    PLUGIN_RC=$?
    echo "PLUGIN_TU_RC=$PLUGIN_RC"
    PLUGIN_ITEMS_CMAKE=""
    PLUGIN_D_ARG=""
    if [ "$PLUGIN_RC" = "0" ]; then
        PLUGIN_ITEMS="$WORK/glshim/qt_plugin_import.o -Wl,-force_load,$QIOS_LIB $QGIF_LIB $QICO_LIB $QJPEG_LIB"
        # Semicolon list for patch 0018's target_link_options; the
        # trailing frameworks are the Qt iOS platform plugin's own
        # dependencies (QuartzCore/Photos/AudioToolbox seen undefined
        # in run 42086627018's lemon link, which received these items
        # globally by mistake -- they are manager-exe-only now).
        PLUGIN_ITEMS_CMAKE="$WORK/glshim/qt_plugin_import.o;-Wl,-force_load,$QIOS_LIB;$QGIF_LIB;$QICO_LIB;$QJPEG_LIB;-framework QuartzCore;-framework Photos;-framework AudioToolbox"
        PLUGIN_D_ARG="-DKICAD_IOS_PLUGIN_ITEMS=$PLUGIN_ITEMS_CMAKE"
    else
        echo "WARNING: Qt plugin import TU failed to compile"
    fi
fi
echo "PLUGIN_ITEMS: $PLUGIN_ITEMS"

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
    -DLEMON_EXE="$WORK/host-tools/bin/lemon" \
    $PLUGIN_D_ARG \
    -DKICAD_SCRIPTING_WXPYTHON=OFF \
    -DKICAD_USE_SENTRY=OFF \
    -DKICAD_IPC_API=OFF \
    -DKICAD_BUILD_QA_TESTS=OFF \
    -DKICAD_BUILD_I18N=OFF \
    -DKICAD_INSTALL_DEMOS=OFF \
    -DCMAKE_C_FLAGS="-I$WORK/glshim -DNANODBC_USE_IODBC_WIDE_STRINGS" \
    -DCMAKE_CXX_FLAGS="-I$WORK/glshim -DwxUSE_OPENGL_EMULATION=1 -DwxHAS_OPENGL_ES -DNANODBC_USE_IODBC_WIDE_STRINGS" \
    -DCMAKE_SHARED_LINKER_FLAGS="$IOS_FW $IOS_EXTRA_LIBS" \
    -DCMAKE_MODULE_LINKER_FLAGS="$IOS_FW $IOS_EXTRA_LIBS" \
    -DCMAKE_EXE_LINKER_FLAGS="$IOS_FW $IOS_EXTRA_LIBS" \
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
if [ "$BLD_RC" != "0" ]; then echo "RESULT: KiCad iOS build FAILED — see error catalogue"; exit 3; fi
echo "RESULT: KiCad manager built for iOS arm64"

# Full build: every remaining target (all kifaces incl. eeschema/
# pcbnew, 3d-viewer, tools) with -k 0.
cmake --build "$BLD" -j4 -- -k 0
FULL_RC=$?
echo "KICAD_IOS_FULL_BUILD_RC=$FULL_RC"
echo "--- full-build error summary (unique errors) ---"
grep -E "error:" "$WORK/logs/kicad-ios.log" | sort | uniq -c | sort -rn | head -40 || true
if [ "$FULL_RC" = "0" ]; then echo "RESULT: FULL KiCad build (all kifaces) OK for iOS arm64"; else echo "RESULT: full build incomplete — see catalogue above"; fi

# Package whatever built (manager + any kifaces) into an unsigned IPA
# (the user re-signs with his own tooling). Runs last so the kifaces are
# included. See scripts/package_ios.py for the layout rules.
python3 "$PWD/scripts/package_ios.py" "$WORK" "$BLD" "$SYSROOT" "$QTDIR_IOS"
echo "PACKAGE_RC=$?"
