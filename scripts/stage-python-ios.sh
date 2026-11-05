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
XCF=$(find "$WORK/python-support" -name 'Python.xcframework' -maxdepth 4 | head -1)
echo "XCFRAMEWORK=$XCF"
SLICE=$(find "$XCF" -type d -name 'ios-arm64' | head -1)
echo "SLICE=$SLICE"
FW=$(find "$SLICE" -maxdepth 1 -name 'Python.framework' | head -1)
mkdir -p "$SYSROOT/lib" "$SYSROOT/include"
# framework binary is the static libpython archive; headers inside Headers/
cp "$FW/Python" "$SYSROOT/lib/libpython3.13.a" || find "$FW" -name '*.a' -exec cp {} "$SYSROOT/lib/libpython3.13.a" \;
cp -R "$FW/Headers" "$SYSROOT/include/python3.13"
ls -la "$SYSROOT/lib/libpython3.13.a" "$SYSROOT/include/python3.13/Python.h" && echo "RESULT: python iOS OK" || echo "RESULT: python iOS FAILED"
