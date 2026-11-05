#!/usr/bin/env bash
# Stage: CPython for iOS arm64 from BeeWare's Python-Apple-support
# (prebuilt, Apache/BSD-style PSF licence). KiCad links libpython for its
# scripting kiface and SWIG modules even with wxPython OFF; the headers
# and static library are what go into the sysroot.
source "$(dirname "$0")/ci-common.sh"
exec > >(tee "$WORK/logs/python-ios.log") 2>&1
set -ux

PY_TAG=3.13-b18
PY_ASSET=Python-3.13-iOS-support.b18.tar.gz
if [ ! -d "$WORK/python-support" ]; then
    ( cd "$WORK" && curl -sL "https://github.com/beeware/Python-Apple-support/releases/download/$PY_TAG/$PY_ASSET" -o pysupport.tar.gz \
      && mkdir -p python-support && tar -xzf pysupport.tar.gz -C python-support )
fi
find "$WORK/python-support" -maxdepth 3 | head -30
# The support tarball contains TWO xcframeworks: the real one at the top
# level and a reference copy inside testbed/. Take the top-level one
# (shortest path), then its device slice (ios-arm64, not the simulator).
XCF=$(find "$WORK/python-support" -name 'Python.xcframework' | awk '{ print length($0), $0 }' | sort -n | head -1 | cut -d' ' -f2-)
echo "XCFRAMEWORK=$XCF"
SLICE=$(find "$XCF" -type d -name 'ios-arm64' | head -1)
echo "SLICE=$SLICE"
FW=$(find "$SLICE" -maxdepth 2 -name 'Python.framework' | head -1)
echo "FRAMEWORK=$FW"
mkdir -p "$SYSROOT/lib" "$SYSROOT/include"
# The framework binary is the (static) libpython archive.
cp "$FW/Python" "$SYSROOT/lib/libpython3.13.a"
# Headers: locate Python.h inside the slice; its directory is the include root.
PYH=$(find "$SLICE" -name 'Python.h' | head -1)
echo "PYTHON_H=$PYH"
mkdir -p "$SYSROOT/include/python3.13"
cp -R "$(dirname "$PYH")/"* "$SYSROOT/include/python3.13/"
if ls -la "$SYSROOT/lib/libpython3.13.a" "$SYSROOT/include/python3.13/Python.h"; then echo "RESULT: python iOS OK"; else echo "RESULT: python iOS FAILED"; exit 3; fi
