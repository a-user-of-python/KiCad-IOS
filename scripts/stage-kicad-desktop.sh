#!/bin/bash
# [KiCad-IOS port] Stage: kicad-desktop.
# Question it answers: does the ACTUAL KiCad 10.0.1 source CONFIGURE and
# COMPILE against wxQt (desktop first — isolates "KiCad vs wxQt" problems
# from "iOS cross-compile" problems)? Builds the `kicad` manager target.
# Requires stage-wx-desktop to have run in the same workspace (re-runs it
# if its build dir is missing).
set -uo pipefail
cd "$(dirname "$0")/.."
source scripts/ci-common.sh

if [ ! -f "$WORK/build-wx-desktop/wx-config" ]; then
    bash scripts/stage-wx-desktop.sh || echo "wx desktop stage failed; continuing to capture KiCad configure behaviour anyway"
fi
fetch_kicad
apply_patches "$SRC/kicad" kicad

log "installing KiCad desktop build deps (brew)"
brew install boost glm cairo pixman freetype harfbuzz curl opencascade glew ngspice protobuf fontconfig zstd libgit2 libmagic unixodbc 2>&1 | tail -3
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


# brew's ngspice ships no libngspice (KiCad's Findngspice fails with
# "NGSPICE library missing"); build it from the pinned source, the same
# remedy KiCad's own message suggests (get_libngspice_so.sh equivalent).
NGH="$WORK/ngspice-host"
if [ ! -f "$NGH/lib/libngspice.dylib" ]; then
    log "building libngspice (host) from source"
    if [ ! -d "$SRC/ngspice" ]; then
        ( cd "$WORK" && curl -sL "https://distfiles.macports.org/ngspice/ngspice-44.2.tar.gz" -o ngspice.tar.gz \
          && mkdir -p "$SRC/ngspice" && tar -xzf ngspice.tar.gz -C "$SRC/ngspice" --strip-components=1 )
    fi
    # Xcode 26 libc++ forbids user specialization of std::is_compound
    # (builtin-backed; dual<T> is compound anyway). Remove the redundant
    # specialization from the fetched cppduals header (ngspice dep tree).
    python3 - "$SRC/ngspice/src/include/cppduals/duals/dual" <<'PYEOF'
import sys
p = sys.argv[1]
s = open(p).read()
block = "/// Duals are compound types.\ntemplate <class T>\nstruct is_compound<duals::dual<T>> : true_type {};\n"
assert block in s, "cppduals block not found"
open(p, "w").write(s.replace(block, "", 1))
print("cppduals is_compound specialization removed")
PYEOF
    ( cd "$SRC/ngspice" && ./configure --with-ngshared --without-x --disable-openmp --prefix="$NGH" >> "$WORK/logs/ngspice-host.log" 2>&1 \
      && make -j"$(sysctl -n hw.ncpu)" >> "$WORK/logs/ngspice-host.log" 2>&1 \
      && make install >> "$WORK/logs/ngspice-host.log" 2>&1 ) || echo "libngspice host build FAILED (see log)"
fi
ls "$NGH/lib/" | grep ngspice || true

WXCFG="$WORK/build-wx-desktop/wx-config"
"$WXCFG" --selected-config || true

BLD="$WORK/build-kicad-desktop"
mkdir -p "$BLD"
set -x
cmake -S "$SRC/kicad" -B "$BLD" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_PREFIX_PATH="$(brew --prefix);$QT_ROOT/$QT_VERSION/macos;$QT_ROOT/$QT_VERSION/clang_64" \
    -DwxWidgets_CONFIG_EXECUTABLE="$WXCFG" \
    -DwxWidgets_CONFIG_OPTIONS="--toolkit=qt" \
    -DCMAKE_C_FLAGS="-I$WORK/glshim" \
    -DCMAKE_CXX_FLAGS="-I$WORK/glshim" \
    -DNGSPICE_INCLUDE_PATH="$NGH/include" \
    -DNGSPICE_LIBRARY_PATH="$NGH/lib" \
    -DNGSPICE_LIB_NAME=ngspice \
    -DPYTHON_FRAMEWORK="$(ls -d "$(brew --prefix)"/opt/python@3.*/Frameworks/Python.framework 2>/dev/null | sort -V | tail -1)" \
    -DPYTHON_LIBRARY="$(ls "$(brew --prefix)"/opt/python@3.*/Frameworks/Python.framework/Versions/3.*/lib/libpython3.*.dylib 2>/dev/null | sort -V | tail -1)" \
    -DPYTHON_INCLUDE_DIR="$(ls -d "$(brew --prefix)"/opt/python@3.*/Frameworks/Python.framework/Versions/3.*/include/python3.* 2>/dev/null | sort -V | tail -1)" \
    -DOCC_INCLUDE_DIR="$(brew --prefix opencascade)/include/opencascade" \
    -DOCC_LIBRARY_DIR="$(brew --prefix opencascade)/lib" \
    -DKICAD_SCRIPTING_WXPYTHON=OFF \
    -DKICAD_SPICE=OFF \
    -DKICAD_USE_SENTRY=OFF \
    -DKICAD_IPC_API=OFF \
    -DKICAD_BUILD_QA_TESTS=OFF \
    -DKICAD_BUILD_I18N=OFF \
    -DKICAD_INSTALL_DEMOS=OFF \
    2>&1 | tee "$WORK/logs/kicad-desktop-configure.log"
CFG_RC=${PIPESTATUS[0]}
set +x
echo "KICAD_DESKTOP_CONFIGURE_RC=$CFG_RC"
if [ "$CFG_RC" != "0" ]; then
    echo "RESULT: KiCad configure against wxQt FAILED (see log)"; exit 2
fi

# Build the manager and everything it pulls in (common, gal, kifaces...).
# Keep going on error (-k 0) so the log enumerates ALL failing units, not
# just the first — this stage is a catalogue-generating machine.
cmake --build "$BLD" -j"$(sysctl -n hw.ncpu)" --target kicad eeschema_kiface pcbnew_kiface gerbview_kiface cvpcb_kiface pcb_calculator_kiface pl_editor_kiface scripting_kiface bitmap2component -- -k 0 2>&1 | tee "$WORK/logs/kicad-desktop-build.log"
BLD_RC=${PIPESTATUS[0]}
echo "KICAD_DESKTOP_BUILD_RC=$BLD_RC"
echo "--- error summary (unique errors) ---"
grep -E "error:" "$WORK/logs/kicad-desktop-build.log" | sort | uniq -c | sort -rn | head -40 | tee "$WORK/logs/kicad-desktop-errors.txt" || true
if [ "$BLD_RC" = "0" ]; then echo "RESULT: KiCad manager built against wxQt (desktop)"; else echo "RESULT: KiCad desktop build FAILED — see error catalogue"; exit 3; fi
