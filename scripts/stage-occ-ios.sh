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

# Fetched-tree build fix (dependency tree only; OCCT is LGPL-2.1 + exception
# and this change is disclosed in MODIFICATIONS.md): FreeType >= 2.13 made
# FT_Outline.tags unsigned char*; OCCT 7.8.1's StdPrs_BRepFont stores it in
# a const char* and only ever reads it through FT_CURVE_TAG bit masks, so
# the cast is semantics-preserving. Without it this is the single compile
# error in all 5561 OCC steps.
python3 - "$SRC/occt/src/StdPrs/StdPrs_BRepFont.cxx" <<'PYEOF'
import sys
p = sys.argv[1]
s = open(p).read()
old = "const char* aTags      = &anOutline->tags[aStartIndex];"
assert s.count(old) == 1, "BRepFont line not found"
open(p, "w").write(s.replace(old, "const char* aTags      = (const char*)&anOutline->tags[aStartIndex];", 1))
print("BRepFont freetype-tags cast applied")
PYEOF
[ $? -eq 0 ] || { echo "RESULT: OCC fetched-tree fix FAILED"; exit 3; }

cmake -S "$SRC/occt" -B "$WORK/build-occ-ios" -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE="$PWD/scripts/ios.toolchain.cmake" \
    -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
    -DCMAKE_INSTALL_PREFIX="$WORK/sysroot-occ" \
    -DBUILD_LIBRARY_TYPE=Static \
    -DBUILD_MODULE_Draw=OFF \
    -DBUILD_DOC_Overview=OFF \
    -DINSTALL_TEST_CASES=OFF \
    -DUSE_FREETYPE=ON \
    -D3RDPARTY_FREETYPE_DIR="$SYSROOT" \
    -DFREETYPE_INCLUDE_DIRS="$SYSROOT/include/freetype2" \
    -DFREETYPE_LIBRARY="$SYSROOT/lib/libfreetype.a" \
    -D3RDPARTY_FREETYPE_INCLUDE_DIR_ft2build="$SYSROOT/include/freetype2" \
    -D3RDPARTY_FREETYPE_INCLUDE_DIR_freetype2="$SYSROOT/include/freetype2" \
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
cmake --build "$WORK/build-occ-ios" -j4 -- -k 0 >> "$LOG" 2>&1
OCC_BUILD_RC=$?
echo "OCC_BUILD_RC=$OCC_BUILD_RC"
cmake --install "$WORK/build-occ-ios" >> "$LOG" 2>&1
echo "OCC_INSTALL_RC=$?"
# Honest gate (a config-file-only check previously passed a build that had
# died at step 2344/5561 with only libTKernel.a installed): require clean
# build+install RCs and a real toolkit census incl. the libs KiCad links.
TK_COUNT=$(ls "$WORK/sysroot-occ/lib/" 2>/dev/null | grep -c '^libTK.*\.a$' || true)
echo "OCC toolkits installed: $TK_COUNT"
if [ "$OCC_BUILD_RC" = "0" ] && [ -f "$WORK/sysroot-occ/lib/libTKBinL.a" ] && [ -f "$WORK/sysroot-occ/lib/libTKDESTEP.a" ] && [ "$TK_COUNT" -ge 50 ]; then echo "RESULT: OCC iOS OK"; else echo "RESULT: OCC iOS FAILED"; exit 3; fi
