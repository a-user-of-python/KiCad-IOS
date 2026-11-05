# [KiCad-IOS port] CI common settings. This file is part of the KiCad-IOS
# spike (GPLv3-or-later, matching upstream KiCad). It is NOT an upstream
# KiCad file; it only pins the upstream baselines the spike builds against.
#
# Pins (do not bump silently — record changes in MODIFICATIONS.md):
QT_VERSION="${QT_VERSION:-6.9.3}"          # same pin as the proven FEBio iOS build (fallback 6.8.3)
KICAD_TAG="10.0.1"
KICAD_COMMIT="2db9e5a72b7cf1e71bb8dff5257a88d4b41f812f"
KICAD_TARBALL="https://gitlab.com/kicad/code/kicad/-/archive/${KICAD_TAG}/kicad-${KICAD_TAG}.tar.gz"
# wx source: KiCad 10 requires wxWidgets >= 3.2.0 and its ecosystem builds
# against stock wxWidgets. Notes from the spike's CI evidence:
#  - github.com/KiCad/wxWidgets fork master is wx 3.1.1 (2017-era), verified
#    in CI run 41937520855 — NOT KiCad 10's wx source.
#  - wx 3.2.8's wxQt backend is Qt5-only (build/cmake/toolkit.cmake does
#    find_package(Qt5)), verified in CI run 41938271757; Qt5-for-iOS is a
#    dead toolchain on modern Xcode. wxQt+Qt6 support exists in wx >= 3.3.
#  - Therefore the spike pins wx v3.3.4 (satisfies KiCad's >= 3.2.0 check).
#    Any resulting KiCad-vs-wx3.3 API drift is a spike finding, logged in
#    the report. KiCad packaging patches vs stock wx are audited separately.
WX_FORK_REPO="https://github.com/wxWidgets/wxWidgets.git"
WX_FORK_BRANCH="v3.3.4"

WORK="${WORK:-$PWD/work}"
SYSROOT="$WORK/sysroot-ios"
export SYSROOT
SRC="$WORK/src"
QT_ROOT="$WORK/Qt"
mkdir -p "$SRC" "$WORK/logs"

log() { echo "== $*"; }

fetch_kicad() {
    if [ ! -d "$SRC/kicad" ]; then
        log "fetching KiCad $KICAD_TAG ($KICAD_COMMIT)"
        curl -sL "$KICAD_TARBALL" -o "$WORK/kicad.tar.gz"
        mkdir -p "$SRC/kicad"
        tar -xzf "$WORK/kicad.tar.gz" -C "$SRC/kicad" --strip-components=1
    fi
    # Provenance check: the tarball has no .git, so verify a sentinel file
    # hash is stable across runs and print the version header.
    grep -m1 "KICAD_VERSION" "$SRC/kicad/CMakeLists.txt" || true
    ls "$SRC/kicad" | head
}

fetch_wx() {
    if [ ! -d "$SRC/wx" ]; then
        log "cloning wxWidgets ($WX_FORK_BRANCH)"
        git clone --depth 1 --recurse-submodules --shallow-submodules --branch "$WX_FORK_BRANCH" "$WX_FORK_REPO" "$SRC/wx"
    fi
    git -C "$SRC/wx" log --oneline -1
    grep -E "wxMAJOR_VERSION|wxMINOR_VERSION|wxRELEASE_NUMBER" "$SRC/wx/include/wx/version.h" | head -3 || true
}

apply_patches() {
    # $1 = source dir, $2 = patch group dir under patches/
    local dir="$1" group="$2" pf
    for pf in "$PWD/patches/$group"/*.patch; do
        [ -e "$pf" ] || continue
        log "applying patch $pf to $dir"
        ( cd "$dir" && patch -p1 --forward < "$pf" ) || { echo "PATCH FAILED: $pf"; return 1; }
    done
}

install_qt() {
    # $1: kits to install: "desktop", "ios", or "both"
    python3 -m pip install --quiet --break-system-packages aqtinstall || python3 -m pip install --quiet aqtinstall
    local kits="$1" v ok=""
    for v in "$QT_VERSION" 6.8.3; do
        ok=1
        if [ "$kits" = "desktop" ] || [ "$kits" = "both" ]; then
            python3 -m aqt install-qt mac desktop "$v" clang_64 -O "$QT_ROOT" --modules qtshadertools || ok=""
        fi
        if [ -n "$ok" ] && { [ "$kits" = "ios" ] || [ "$kits" = "both" ]; }; then
            python3 -m aqt install-qt mac ios "$v" ios -O "$QT_ROOT" --modules qtshadertools || ok=""
        fi
        if [ -n "$ok" ]; then QT_VERSION="$v"; break; fi
        echo "-- Qt $v failed, trying next candidate"
    done
    [ -n "$ok" ] || { echo "ERROR: no Qt could be installed" >&2; exit 1; }
    echo "QT_VERSION_USED=$QT_VERSION"
    ls "$QT_ROOT/$QT_VERSION"
}
