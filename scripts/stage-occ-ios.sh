#!/usr/bin/env bash
# Stage: OpenCascade (OCCT) for iOS arm64 — KiCad requires OCC >= 7.5.
# Prior art: this workspace's cascade-ios port proved OCCT compiles for
# iOS arm64; here OCC's own CMake build produces the OpenCASCADE config
# package KiCad's find_package() consumes. Static libs, no VTK/FFmpeg/TBB.
source "$(dirname "$0")/ci-common.sh"
exec > >(tee "$WORK/logs/occ-ios.log") 2>&1
set -ux

OCC_VER=7.8.1
if [ ! -d "$SRC/occt" ]; then
    ( cd "$WORK" && curl -sL "https://github.com/Open-Cascade-SAS/OCCT/archive/refs/tags/V7_8_1.tar.gz" -o occ.tar.gz \
      && mkdir -p "$SRC/occt" && tar -xzf occ.tar.gz -C "$SRC/occt" --strip-components=1 )
fi

cmake -S "$SRC/occt" -B "$WORK/build-occ-ios" -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE="$PWD/scripts/ios.toolchain.cmake" \
    -DCMAKE_INSTALL_PREFIX="$SYSROOT" \
    -DBUILD_LIBRARY_TYPE=Static \
    -DBUILD_MODULE_Draw=OFF \
    -DBUILD_DOC_Overview=OFF \
    -DINSTALL_TEST_CASES=OFF \
    -DUSE_FREETYPE=ON \
    -DUSE_TBB=OFF \
    -DUSE_VTK=OFF \
    -DUSE_FFMPEG=OFF \
    -DUSE_RAPIDJSON=OFF \
    -DUSE_OPENGL_EXT=OFF \
    -DUSE_GLES2=OFF \
    -DUSE_D3D=OFF \
    -DUSE_XLIB=OFF \
    > "$LOG" 2>&1
echo "OCC_CONFIGURE_RC=$?"
cmake --build "$WORK/build-occ-ios" -j4 >> "$LOG" 2>&1
echo "OCC_BUILD_RC=$?"
cmake --install "$WORK/build-occ-ios" >> "$LOG" 2>&1
echo "OCC_INSTALL_RC=$?"
if ls "$SYSROOT/lib/cmake/opencascade/OpenCASCADEConfig.cmake"; then echo "RESULT: OCC iOS OK"; else echo "RESULT: OCC iOS FAILED"; exit 3; fi
