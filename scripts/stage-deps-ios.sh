#!/bin/bash
# [KiCad-IOS port] Stage: deps-iOS (part 1 — the CMake-friendly deps).
# Builds a static iOS arm64 sysroot of the libraries KiCad 10.0.1's
# CMake REQUIRES unconditionally (see spike report): zlib, zstd, libpng,
# freetype, harfbuzz, expat, curl (SecureTransport), libgit2, protobuf
# (+ host protoc). Meson-based deps (pixman/cairo/fontconfig), OCC,
# ngspice and Python are separate follow-up stages.
# Output: $WORK/sysroot-ios/{include,lib} + tarball artifact.
set -uo pipefail
cd "$(dirname "$0")/.."
source scripts/ci-common.sh

SYSROOT="$WORK/sysroot-ios"
mkdir -p "$SYSROOT" "$WORK/deps-src"
TC="$PWD/scripts/ios.toolchain.cmake"
JOBS="$(sysctl -n hw.ncpu)"

build_cmake_dep() {
    # $1 name  $2 srcdir  $3 extra cmake args...
    local name="$1" src="$2"; shift 2
    local bld="$WORK/deps-build-$name"
    log "building $name for iOS"
    cmake -S "$src" -B "$bld" -G Ninja \
        -DCMAKE_TOOLCHAIN_FILE="$TC" \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="$SYSROOT" \
        -DBUILD_SHARED_LIBS=OFF \
        "$@" 2>&1 | tee "$WORK/logs/dep-$name-configure.log" || return 1
    cmake --build "$bld" -j"$JOBS" 2>&1 | tee "$WORK/logs/dep-$name-build.log" || return 1
    cmake --install "$bld" >>"$WORK/logs/dep-$name-build.log" 2>&1 || return 1
    echo "DEP_OK $name"
}

get() { # $1 url  $2 dir
    if [ ! -d "$WORK/deps-src/$2" ]; then
        curl -sL "$1" -o "$WORK/deps-src/$2.tar.gz"
        mkdir -p "$WORK/deps-src/$2"
        tar -xf "$WORK/deps-src/$2.tar.gz" -C "$WORK/deps-src/$2" --strip-components=1
    fi
    echo "$WORK/deps-src/$2"
}

FAILED=""
step() { local label="$1"; shift; "$@" || FAILED="$FAILED $label"; }

step zlib      build_cmake_dep zlib      "$(get https://zlib.net/fossils/zlib-1.3.1.tar.gz zlib)" -DZLIB_BUILD_EXAMPLES=OFF
# zstd's CMakeLists lives in build/cmake
ZSTD_SRC="$(get https://github.com/facebook/zstd/releases/download/v1.5.6/zstd-1.5.6.tar.gz zstd)"
step zstd      build_cmake_dep zstd      "$ZSTD_SRC/build/cmake" -DZSTD_BUILD_PROGRAMS=OFF -DZSTD_BUILD_TESTS=OFF
step libpng build_cmake_dep libpng    "$(get https://download.sourceforge.net/libpng/libpng-1.6.43.tar.gz libpng)" -DPNG_SHARED=OFF -DPNG_TESTS=OFF -DZLIB_ROOT="$SYSROOT"
step freetype build_cmake_dep freetype  "$(get https://download.savannah.gnu.org/releases/freetype/freetype-2.13.3.tar.gz freetype)" -DFT_DISABLE_BROTLI=ON -DFT_DISABLE_BZIP2=ON -DFT_DISABLE_HARFBUZZ=OFF -DFT_DISABLE_PNG=ON -DFT_DISABLE_ZLIB=OFF
step harfbuzz build_cmake_dep harfbuzz  "$(get https://github.com/harfbuzz/harfbuzz/releases/download/8.5.0/harfbuzz-8.5.0.tar.xz harfbuzz)" -DHB_HAVE_FREETYPE=ON -DHB_BUILD_SUBSET=OFF -DHB_BUILD_UTILS=OFF
step expat build_cmake_dep expat     "$(get https://github.com/libexpat/libexpat/releases/download/R_2_6_3/expat-2.6.3.tar.gz expat)" -DEXPAT_BUILD_EXAMPLES=OFF -DEXPAT_BUILD_TESTS=OFF -DEXPAT_BUILD_TOOLS=OFF
step curl build_cmake_dep curl      "$(get https://curl.se/download/curl-8.10.1.tar.gz curl)" -DCURL_USE_SECTRANSP=ON -DCURL_USE_LIBSSH2=OFF -DBUILD_CURL_EXE=OFF -DBUILD_TESTING=OFF -DUSE_NGHTTP2=OFF -DCURL_ZLIB=ON
step libgit2 build_cmake_dep libgit2   "$(get https://github.com/libgit2/libgit2/releases/download/v1.9.0/libgit2-1.9.0.tar.gz libgit2)" -DBUILD_CLI=OFF -DBUILD_TESTS=OFF -DUSE_HTTPS=OFF -DUSE_SSH=OFF -DREGEX_BACKEND=builtin

# protobuf: host build first for protoc, then iOS lib with that protoc.
PB_SRC="$(get https://github.com/protocolbuffers/protobuf/releases/download/v25.1/protobuf-25.1.tar.gz protobuf)"
if [ ! -x "$WORK/deps-build-protobuf-host/protoc" ]; then
    log "building host protobuf (protoc)"
    cmake -S "$PB_SRC" -B "$WORK/deps-build-protobuf-host" -G Ninja \
        -DCMAKE_BUILD_TYPE=Release -Dprotobuf_BUILD_TESTS=OFF -Dprotobuf_BUILD_EXAMPLES=OFF \
        2>&1 | tee "$WORK/logs/dep-protobuf-host-configure.log"
    cmake --build "$WORK/deps-build-protobuf-host" -j"$JOBS" --target protoc 2>&1 | tee "$WORK/logs/dep-protobuf-host-build.log"
fi
if [ -x "$WORK/deps-build-protobuf-host/protoc" ]; then
    build_cmake_dep protobuf "$PB_SRC" -Dprotobuf_BUILD_TESTS=OFF -Dprotobuf_BUILD_EXAMPLES=OFF \
        -Dprotobuf_BUILD_PROTOC_BINARIES=OFF -DProtobuf_PROTOC_EXECUTABLE="$WORK/deps-build-protobuf-host/protoc" \
        || FAILED="$FAILED protobuf"
else
    FAILED="$FAILED protobuf-host"
fi

echo "--- sysroot contents ---"
find "$SYSROOT" -name "*.a" | sort | tee "$WORK/logs/sysroot-libs.txt"
if [ -n "$FAILED" ]; then echo "RESULT: deps part 1 PARTIAL — failed:$FAILED"; exit 3; fi
echo "RESULT: deps part 1 OK"
