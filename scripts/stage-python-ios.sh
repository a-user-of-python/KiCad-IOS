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
# [KiCad-IOS port] Standard library tree (launch fix round 6,
# KiCad-Spike-v8): until now only the interpreter binary and headers
# entered the sysroot, so the packaged app shipped CPython with NO
# stdlib -- and KiCad's startup constructs its embedded interpreter
# unconditionally (SCRIPTING in PGM_BASE::InitPgm), whose
# initialisation imports the `encodings` package and aborted the
# whole launch on device ("Failed to import encodings module").
# The support tarball carries the full 3.13 library as pure Python
# in Python.xcframework/lib/python3.13 (shared by all slices) plus
# the compiled extension modules per slice under
# <slice>/lib-arm64/python3.13/lib-dynload. Copy both into the
# sysroot next to libpython3.13.a; scripts/package_ios.py installs
# them into the app bundle under the PYTHONHOME the executable's
# startup object sets (patch 0025), applying the documented trims.
mkdir -p "$SYSROOT/lib/python3.13/lib-dynload"
cp -R "$XCF/lib/python3.13/." "$SYSROOT/lib/python3.13/"
cp "$SLICE/lib-arm64/python3.13/lib-dynload/"*.so "$SYSROOT/lib/python3.13/lib-dynload/"
echo "stdlib staged: $(find "$SYSROOT/lib/python3.13" -type f | wc -l) files, $(du -sh "$SYSROOT/lib/python3.13" | cut -f1)"
ls "$SYSROOT/lib/python3.13/encodings/__init__.py" "$SYSROOT/lib/python3.13/lib-dynload" | head -5
# Loadability probe over the staged extension modules, run HERE as
# well as in the kicad stage: this stage has both the sysroot tree
# and the iPhoneOS SDK, and a probe failure (including its sanity
# check) fails this stage loudly instead of letting vacuous
# verdicts reach packaging. NOTE: verdicts here are an early
# warning only -- this stage's sysroot lacks the deps stage's
# libz/libzstd, so the zlib-family modules show TRIM here; the
# BINDING verdicts are computed in the kicad stage, whose
# assembled sysroot contains those dylibs (and the shipped audit
# re-verifies closure on the final file regardless).
python3 "$PWD/scripts/probe_dynload.py" "$SYSROOT" "$WORK" "$(xcrun --sdk iphoneos --show-sdk-path)"
PROBE_RC=$?
echo "PROBE_RC=$PROBE_RC"
if [ "$PROBE_RC" -ne 0 ]; then echo "RESULT: python iOS FAILED (dynload probe)"; exit 4; fi
if ls -la "$SYSROOT/lib/libpython3.13.a" "$SYSROOT/include/python3.13/Python.h"; then echo "RESULT: python iOS OK"; else echo "RESULT: python iOS FAILED"; exit 3; fi
