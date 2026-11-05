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
        -DCMAKE_PREFIX_PATH="$SYSROOT" \
        -DBUILD_SHARED_LIBS=OFF \
        "$@" 2>&1 | tee "$WORK/logs/dep-$name-configure.log" || return 1
    cmake --build "$bld" -j"$JOBS" 2>&1 | tee "$WORK/logs/dep-$name-build.log" || return 1
    cmake --install "$bld" >>"$WORK/logs/dep-$name-build.log" 2>&1 || return 1
    echo "DEP_OK $name"
}

get() { # $1 url  $2 dir
    if [ ! -d "$WORK/deps-src/$2" ]; then
        curl -sfL "$1" -o "$WORK/deps-src/$2.tar.gz" || { echo "DOWNLOAD FAILED: $1"; return 1; }
        mkdir -p "$WORK/deps-src/$2"
        tar -xf "$WORK/deps-src/$2.tar.gz" -C "$WORK/deps-src/$2" --strip-components=1 || { echo "EXTRACT FAILED: $1"; return 1; }
    fi
    echo "$WORK/deps-src/$2"
}

get_git() { # $1 repo  $2 tag  $3 dir  $4 extra clone args
    if [ ! -d "$WORK/deps-src/$3" ]; then
        git clone --depth 1 --branch "$2" $4 "https://github.com/$1" "$WORK/deps-src/$3" || { echo "CLONE FAILED: $1"; return 1; }
    fi
    echo "$WORK/deps-src/$3"
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
step libgit2 build_cmake_dep libgit2   "$(get_git libgit2/libgit2 v1.9.0 libgit2 "")" -DBUILD_CLI=OFF -DBUILD_TESTS=OFF -DUSE_HTTPS=OFF -DUSE_SSH=OFF -DREGEX_BACKEND=builtin

# protobuf: host build first for protoc, then iOS lib with that protoc.
# protobuf's release tarball omits the abseil submodule contents; clone with submodules instead.
PB_SRC="$(get_git protocolbuffers/protobuf v25.1 protobuf "--recurse-submodules --shallow-submodules")"
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

# ---------------------------------------------------------------- meson
# pixman / cairo / fontconfig are meson projects. One generated cross file.
SDK_PATH="$(xcrun --sdk iphoneos --show-sdk-path)"
export PKG_CONFIG_PATH="$SYSROOT/lib/pkgconfig"
export PKG_CONFIG_LIBDIR="$SYSROOT/lib/pkgconfig"

cat > "$WORK/meson-ios-cross.txt" <<EOF2
[binaries]
c = 'clang'
cpp = 'clang++'
objc = 'clang'
objcpp = 'clang++'
ar = 'ar'
strip = 'strip'
pkg-config = 'pkg-config'

[properties]
needs_exe_wrapper = true

[built-in options]
c_args = ['-arch', 'arm64', '-target', 'arm64-apple-ios16.0', '-isysroot', '$SDK_PATH']
cpp_args = ['-arch', 'arm64', '-target', 'arm64-apple-ios16.0', '-isysroot', '$SDK_PATH']
c_link_args = ['-arch', 'arm64', '-target', 'arm64-apple-ios16.0', '-isysroot', '$SDK_PATH']
cpp_link_args = ['-arch', 'arm64', '-target', 'arm64-apple-ios16.0', '-isysroot', '$SDK_PATH']
objc_args = ['-arch', 'arm64', '-target', 'arm64-apple-ios16.0', '-isysroot', '$SDK_PATH']
objcpp_args = ['-arch', 'arm64', '-target', 'arm64-apple-ios16.0', '-isysroot', '$SDK_PATH']
objc_link_args = ['-arch', 'arm64', '-target', 'arm64-apple-ios16.0', '-isysroot', '$SDK_PATH']
objcpp_link_args = ['-arch', 'arm64', '-target', 'arm64-apple-ios16.0', '-isysroot', '$SDK_PATH']

[host_machine]
system = 'darwin'
cpu_family = 'aarch64'
cpu = 'arm64'
endian = 'little'
EOF2

fetch_tar() { # $1 url, $2 dest dir name
    local url="$1" name="$2"
    if [ ! -d "$SRC/$name" ]; then
        log "fetch $url"
        ( cd "$WORK" && curl -sL "$url" -o "$name.tar" && mkdir -p "$SRC/$name" && tar -xf "$name.tar" -C "$SRC/$name" --strip-components=1 ) >> "$LOG" 2>&1
    fi
}

build_meson() { # $1 srcdir, rest: options
    local dir="$1"; shift
    log "meson build $dir $*"
    rm -rf "$dir/build-ios"
    meson setup "$dir/build-ios" "$dir" --cross-file "$WORK/meson-ios-cross.txt" \
        --prefix "$SYSROOT" --libdir lib --buildtype release -Ddefault_library=static "$@" >> "$LOG" 2>&1
    meson compile -C "$dir/build-ios" >> "$LOG" 2>&1
    meson install -C "$dir/build-ios" >> "$LOG" 2>&1
}

command -v meson >/dev/null || pip3 install --quiet meson

fetch_tar https://www.cairographics.org/releases/pixman-0.44.2.tar.gz pixman
build_meson "$SRC/pixman" -Dtests=disabled -Ddemos=disabled -Dgtk=disabled; mark pixman-meson

fetch_tar https://www.freedesktop.org/software/fontconfig/release/fontconfig-2.15.0.tar.xz fontconfig
build_meson "$SRC/fontconfig" -Dtools=disabled -Dtests=disabled -Ddoc=disabled -Dcache-build=disabled; mark fontconfig-meson

fetch_tar https://www.cairographics.org/releases/cairo-1.18.2.tar.xz cairo
build_meson "$SRC/cairo" -Dtests=disabled -Dspectre=disabled -Ddocumentation=disabled -Dxcb=disabled -Dxlib=disabled -Dglib=disabled -Dfontconfig=enabled -Dfreetype=enabled -Dpng=enabled -Dquartz=enabled -Dtee=disabled; mark cairo-meson

probe "fontconfig/fontconfig.h" "cairo/cairo.h" "pixman-1/pixman.h"
echo "RESULT: iOS dependency sysroot stage complete (cmake set + meson set), failed:$FAILED"
