#!/usr/bin/env bash
# Stage: ngspice for iOS arm64 — KiCad 10.0.1 requires it unconditionally
# (find_package(ngspice REQUIRED), CMakeLists.txt:884). Autotools cross
# build, static, no X11. Codemodel .cm bundles are dlopen'd at runtime by
# desktop ngspice; on iOS they cannot load — a runtime limitation of the
# simulator leaf, noted in the spike report; the library itself is what
# the KiCad build links.
source "$(dirname "$0")/ci-common.sh"
exec > >(tee "$WORK/logs/ngspice-ios.log") 2>&1
set -ux

NG_VER=44.2
if [ ! -d "$SRC/ngspice" ]; then
    ( cd "$WORK" && curl -sL "https://distfiles.macports.org/ngspice/ngspice-$NG_VER.tar.gz" -o ngspice.tar.gz \
      && mkdir -p "$SRC/ngspice" && tar -xzf ngspice.tar.gz -C "$SRC/ngspice" --strip-components=1 )
fi
SDK_PATH="$(xcrun --sdk iphoneos --show-sdk-path)"
export CC="clang -arch arm64 -target arm64-apple-ios16.0 -isysroot $SDK_PATH"
export CXX="clang++ -arch arm64 -target arm64-apple-ios16.0 -isysroot $SDK_PATH"
export CPPFLAGS="-I$SYSROOT/include"
export LDFLAGS="-L$SYSROOT/lib -arch arm64"
cd "$SRC/ngspice"
./configure --host=arm64-apple-darwin --build=x86_64-apple-darwin \
    --prefix="$SYSROOT" --without-x --enable-static --disable-shared \
    --with-ngshared --disable-debug --disable-openmp \
    > "$LOG" 2>&1
echo "NG_CONFIGURE_RC=$?"
make -j4 >> "$LOG" 2>&1
echo "NG_MAKE_RC=$?"
make install >> "$LOG" 2>&1
echo "NG_INSTALL_RC=$?"
find "$SYSROOT" -name '*ngspice*' | head
if ls "$SYSROOT/include/ngspice/sharedspice.h"; then echo "RESULT: ngspice iOS OK"; else echo "RESULT: ngspice headers missing"; exit 3; fi
