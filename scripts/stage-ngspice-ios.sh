#!/usr/bin/env bash
# Stage: ngspice for iOS arm64 — KiCad 10.0.1 requires it unconditionally
# (find_package(ngspice REQUIRED), CMakeLists.txt:884). Autotools cross
# build with --with-ngshared (libngspice). Codemodel .cm bundles are
# dlopen'd at runtime by desktop ngspice; on iOS they cannot load — a
# runtime limitation of the simulator leaf, noted in the spike report.
# Compiler wrappers are single-token scripts: libtool cannot parse a
# multi-word $CC and aborts with "cannot build a shared library".
source "$(dirname "$0")/ci-common.sh"
exec > >(tee "$WORK/logs/ngspice-ios.log") 2>&1
set -ux

NG_VER=44.2
if [ ! -d "$SRC/ngspice" ]; then
    ( cd "$WORK" && curl -sL "https://distfiles.macports.org/ngspice/ngspice-$NG_VER.tar.gz" -o ngspice.tar.gz \
      && mkdir -p "$SRC/ngspice" && tar -xzf ngspice.tar.gz -C "$SRC/ngspice" --strip-components=1 )
fi
NGDUAL_HDR="$SRC/ngspice/src/include/cppduals/duals/dual"
# Xcode 26 libc++ forbids user specialization of std::is_compound
# (it is builtin-backed; dual<T> is compound anyway). Remove the
# redundant specialization from the fetched cppduals header.
python3 - "$NGDUAL_HDR" <<'PYEOF'
import sys
p = sys.argv[1]
s = open(p).read()
block = "/// Duals are compound types.\ntemplate <class T>\nstruct is_compound<duals::dual<T>> : true_type {};\n"
assert block in s, "cppduals block not found"
open(p, "w").write(s.replace(block, "", 1))
print("cppduals is_compound specialization removed")
PYEOF
SDK_PATH="$(xcrun --sdk iphoneos --show-sdk-path)"
# iOS compat shim: ngspice's frontend calls system() in seven places
# (shell command, hardcopy via external tools, gnuplot launch). system()
# is marked unavailable in the iOS SDK and process spawning is impossible
# on iOS, so map those calls to a no-op returning failure. Forced-include
# runs before any TU code: it pulls in the real stdlib.h first, then
# defines the macro, so no upstream file is modified.
cat > "$WORK/ngspice-ios-compat.h" <<'COMPAT'
#include <stdlib.h>
static int ngspice_ios_system(const char *cmd) { (void) cmd; return -1; }
#define system ngspice_ios_system
COMPAT
cat > "$WORK/cc-ios.sh" <<WRAP
#!/bin/sh
exec clang -arch arm64 -target arm64-apple-ios16.0 -isysroot "$SDK_PATH" -include "$WORK/ngspice-ios-compat.h" "\$@"
WRAP
cat > "$WORK/cxx-ios.sh" <<WRAP
#!/bin/sh
exec clang++ -arch arm64 -target arm64-apple-ios16.0 -isysroot "$SDK_PATH" -include "$WORK/ngspice-ios-compat.h" "\$@"
WRAP
chmod +x "$WORK/cc-ios.sh" "$WORK/cxx-ios.sh"
export CC="$WORK/cc-ios.sh"
export CXX="$WORK/cxx-ios.sh"
export CPPFLAGS="-I$SYSROOT/include"
export LDFLAGS="-L$SYSROOT/lib -arch arm64"
cd "$SRC/ngspice"
./configure --host=arm64-apple-darwin --build=x86_64-apple-darwin \
    --prefix="$SYSROOT" --without-x --with-ngshared --disable-debug --disable-openmp \
    > "$LOG" 2>&1
echo "NG_CONFIGURE_RC=$?"
make -j4 >> "$LOG" 2>&1
NG_MAKE_RC=$?
echo "NG_MAKE_RC=$NG_MAKE_RC"
make install >> "$LOG" 2>&1
echo "NG_INSTALL_RC=$?"
find "$SYSROOT" -name '*ngspice*' | head
if [ "$NG_MAKE_RC" = "0" ] && ls "$SYSROOT/lib/" | grep -q ngspice && [ -f "$SYSROOT/include/ngspice/sharedspice.h" ]; then
    echo "RESULT: ngspice iOS OK"
else
    echo "RESULT: ngspice iOS FAILED"; exit 3
fi
