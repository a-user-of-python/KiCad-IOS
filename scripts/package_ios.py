#!/usr/bin/env python3
"""
Assemble an unsigned iOS .ipa from the CMake-built KiCad.app (macOS-style
bundle) produced by stage-kicad-ios.sh.

Layout produced (iOS-flat, as dyld + iOS require):
    Payload/KiCad.app/KiCad                 (the manager executable)
    Payload/KiCad.app/Info.plist            (iOS plist written here)
    Payload/KiCad.app/Frameworks/*.dylib    (KiCad libs + sysroot dylibs)
    Payload/KiCad.app/Frameworks/*.framework (Qt frameworks actually linked)
    Payload/KiCad.app/share/                (stock data: bitmap archive,
                                             scripting plugins, addons)
    Payload/KiCad.app/python/               (PYTHONHOME: CPython 3.13
                                             stdlib + KiCad's own Python
                                             modules in site-packages)

    (No Contents/ mirror is produced: the v1 package mirrored the whole
    Frameworks tree into a macOS-shaped Contents/ tree, doubling the
    bundle to 491 MB, and the result failed signing. Dependencies
    recorded as @rpath/<name> are resolved against the sysroot and the
    Qt kit and embedded like any other library -- skipping them is what
    left libz, libzstd and Python out of the v1 package.)

Every Mach-O gets its install names rewritten to @rpath/<basename> and
the executable gains @executable_path/Frameworks as an rpath, so nothing
references CI-machine paths. Qt frameworks ship with @rpath ids already.

The user re-signs the unsigned IPA with his own tooling (Signulous), like the
other spike apps.
"""

import binascii
import glob
import hashlib
import json
import math
import os
import plistlib
import shutil
import struct
import subprocess
import sys
import zipfile
import zlib

WORK = sys.argv[1]          # $WORK
BLD = sys.argv[2]           # $WORK/build-kicad-ios
SYSROOT = sys.argv[3]
QTDIR = sys.argv[4]         # $WORK/Qt/6.9.3/ios

SRC_APP = os.path.join(BLD, "kicad", "KiCad.app")
PKG = os.path.join(WORK, "package")
APP = os.path.join(PKG, "Payload", "KiCad.app")
FW = os.path.join(APP, "Frameworks")


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def load_commands(binary):
    out = run(["otool", "-L", binary]).stdout.splitlines()
    deps = []
    for line in out[1:]:
        line = line.strip()
        if line:
            deps.append(line.split(" (")[0])
    return deps


def is_macho(path):
    if not os.path.isfile(path) or os.path.islink(path):
        return False
    with open(path, "rb") as fh:
        magic = fh.read(4)
    return magic in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xfe\xed\xfa\xcf")


# ----------------------------------------------------------------------
# App icon (2026-11-09: "the app does not have an icon"). Every IPA
# shipped through V1 carried no icon at all -- no icon files in the
# .app and no CFBundleIcons / CFBundleIconFiles in the plist -- so iOS
# showed the generic placeholder on the home screen. The icon set is
# rendered here, at package time, from KiCad's OWN upstream program
# icon: resources/bitmaps_png/png/icon_kicad_256.png, the largest
# master in the tree (the same artwork as the manager's launcher
# icon; no replacement art is designed and no third-party icon is
# used). Stdlib-only PNG decode/encode plus bilinear resampling, so
# the build runner needs no imaging library. iOS icons must be fully
# opaque: the master is a rounded square on transparency, so it is
# flattened onto the artwork's own edge blue -- sampled from the
# master itself, never hardcoded -- before resizing, and every file
# is written as RGB (no alpha channel). Fails closed: a missing or
# undecodable master, or a written file that does not verify,
# aborts packaging, the same discipline as the startup schemas.
APP_ICON_FILES = [
    ("AppIcon1024x1024.png", 1024),
    ("AppIcon60x60@2x.png", 120),
    ("AppIcon60x60@3x.png", 180),
    ("AppIcon76x76.png", 76),
    ("AppIcon76x76@2x.png", 152),
    ("AppIcon83.5x83.5@2x.png", 167),
    ("AppIcon40x40.png", 40),
    ("AppIcon40x40@2x.png", 80),
    ("AppIcon29x29.png", 29),
    ("AppIcon29x29@2x.png", 58),
]
APP_ICON_BASES = ["AppIcon29x29", "AppIcon40x40", "AppIcon60x60",
                  "AppIcon76x76", "AppIcon83.5x83.5", "AppIcon1024x1024"]


def _png_ihdr(path):
    with open(path, "rb") as fh:
        head = fh.read(33)
    if head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        raise ValueError(f"{path}: not a PNG")
    w, h, _depth, ctype = struct.unpack(">IIBB", head[16:26])
    return w, h, ctype


def _png_decode_rgba(path):
    """Decode an 8-bit RGB/RGBA non-interlaced PNG to (w, h, rgba)."""
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path}: not a PNG")
    pos = 8
    idat = b""
    w = h = ctype = None
    while pos < len(data):
        ln = struct.unpack(">I", data[pos:pos + 4])[0]
        typ = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            w, h, depth, ctype, _comp, _filt, inter = struct.unpack(
                ">IIBBBBB", chunk)
            if depth != 8 or ctype not in (2, 6) or inter != 0:
                raise ValueError(f"{path}: unsupported PNG form")
        elif typ == b"IDAT":
            idat += chunk
        pos += 12 + ln
    raw = zlib.decompress(idat)
    ch = 4 if ctype == 6 else 3
    stride = w * ch
    out = bytearray(h * stride)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        f = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if f == 1:
            for i in range(ch, stride):
                line[i] = (line[i] + line[i - ch]) & 0xFF
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif f == 3:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif f == 4:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                b = prev[i]
                c = prev[i - ch] if i >= ch else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc
                                                      else c)
                line[i] = (line[i] + pr) & 0xFF
        out[y * stride:(y + 1) * stride] = line
        prev = line
    if ch == 4:
        return w, h, bytes(out)
    rgba = bytearray(w * h * 4)
    for i in range(w * h):
        rgba[i * 4:i * 4 + 3] = out[i * 3:i * 3 + 3]
        rgba[i * 4 + 3] = 255
    return w, h, bytes(rgba)


def _png_encode_rgb(path, w, h, rgb):
    def chunk(typ, payload):
        return (struct.pack(">I", len(payload)) + typ + payload
                + struct.pack(">I", binascii.crc32(typ + payload)
                              & 0xFFFFFFFF))
    raw = b"".join(b"\x00" + rgb[y * w * 3:(y + 1) * w * 3]
                   for y in range(h))
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 6))
           + chunk(b"IEND", b""))
    with open(path, "wb") as fh:
        fh.write(png)


def _resize_bilinear_rgb(rgb, sw, sh, dw, dh):
    if (sw, sh) == (dw, dh):
        return rgb
    out = bytearray(dw * dh * 3)
    for dy in range(dh):
        fy = (dy + 0.5) * sh / dh - 0.5
        y0 = int(math.floor(fy))
        ty = fy - y0
        ya = min(max(y0, 0), sh - 1)
        yb = min(max(y0 + 1, 0), sh - 1)
        for dx in range(dw):
            fx = (dx + 0.5) * sw / dw - 0.5
            x0 = int(math.floor(fx))
            tx = fx - x0
            xa = min(max(x0, 0), sw - 1)
            xb = min(max(x0 + 1, 0), sw - 1)
            o = (dy * dw + dx) * 3
            for c in range(3):
                p00 = rgb[(ya * sw + xa) * 3 + c]
                p01 = rgb[(ya * sw + xb) * 3 + c]
                p10 = rgb[(yb * sw + xa) * 3 + c]
                p11 = rgb[(yb * sw + xb) * 3 + c]
                top = p00 + (p01 - p00) * tx
                bot = p10 + (p11 - p10) * tx
                out[o + c] = int(top + (bot - top) * ty + 0.5)
    return bytes(out)


def _install_app_icons():
    master = None
    for cand in (os.path.join(WORK, "src", "kicad", "resources",
                              "bitmaps_png", "png", "icon_kicad_256.png"),
                 os.path.join(WORK, "src", "kicad", "resources",
                              "bitmaps_png", "icons", "icon_kicad.png")):
        if os.path.isfile(cand):
            master = cand
            break
    if master is None:
        raise SystemExit("app icon: upstream icon_kicad master not found")
    w, h, rgba = _png_decode_rgba(master)
    # Background: the artwork's own edge blue, sampled just inside the
    # top edge (opaque there), so the flattened corners read as the
    # artwork's own field under the iOS icon mask.
    sx, sy = w // 2, max(1, h // 32)
    si = (sy * w + sx) * 4
    if rgba[si + 3] != 255:
        raise SystemExit("app icon: background sample is not opaque")
    bg = rgba[si:si + 3]
    rgb = bytearray(w * h * 3)
    for px in range(w * h):
        a = rgba[px * 4 + 3]
        if a == 255:
            rgb[px * 3:px * 3 + 3] = rgba[px * 4:px * 4 + 3]
        elif a == 0:
            rgb[px * 3:px * 3 + 3] = bg
        else:
            inv = 255 - a
            for c in range(3):
                rgb[px * 3 + c] = (rgba[px * 4 + c] * a
                                   + bg[c] * inv + 127) // 255
    flat = bytes(rgb)
    for name, size in APP_ICON_FILES:
        _png_encode_rgb(os.path.join(APP, name), size, size,
                        _resize_bilinear_rgb(flat, w, h, size, size))
    # Fail-closed verification of what was just written: the 1024
    # marketing icon must read back at exactly 1024x1024 as RGB (color
    # type 2 -- no alpha channel for iOS to reject), every other file
    # at its declared size, and every plist base name must resolve to
    # at least one real file in the bundle root.
    for name, size in APP_ICON_FILES:
        vw, vh, vct = _png_ihdr(os.path.join(APP, name))
        if (vw, vh) != (size, size) or vct != 2:
            raise SystemExit(
                f"app icon: {name} verifies as {vw}x{vh} type {vct}, "
                f"expected {size}x{size} type 2")
    for base in APP_ICON_BASES:
        if not any(os.path.isfile(os.path.join(APP, base + suffix))
                   for suffix in (".png", "@2x.png", "@3x.png")):
            raise SystemExit(f"app icon: plist base {base} has no file")
    with open(os.path.join(APP, "AppIcon1024x1024.png"), "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()
    print(f"app icon packaged: {len(APP_ICON_FILES)} files from "
          f"{os.path.basename(master)} (bg #{bg[0]:02x}{bg[1]:02x}"
          f"{bg[2]:02x}); AppIcon1024x1024.png sha256 {digest}")


def main():
    if os.path.isdir(PKG):
        shutil.rmtree(PKG)
    os.makedirs(FW)

    # The iOS toolchain's CMake bundle step puts the executable at
    # kicad/kicad.app/kicad (lowercase bundle, exe at bundle root),
    # while KiCad's own bundle assembly uses KiCad.app/Contents/... —
    # locate the real executable instead of assuming either layout.
    src_exe = None
    for cand in (os.path.join(BLD, "kicad", "kicad.app", "kicad"),
                 os.path.join(SRC_APP, "Contents", "MacOS", "kicad")):
        if os.path.isfile(cand):
            src_exe = cand
            break
    if src_exe is None:
        for root, _dirs, files in os.walk(os.path.join(BLD, "kicad")):
            if "kicad" in files and is_macho(os.path.join(root, "kicad")):
                src_exe = os.path.join(root, "kicad")
                break
    if src_exe is None:
        print("FATAL: manager executable not found under", os.path.join(BLD, "kicad"))
        sys.exit(1)
    print("manager executable:", src_exe)
    dst_exe = os.path.join(APP, "KiCad")
    shutil.copy2(src_exe, dst_exe)
    os.chmod(dst_exe, 0o755)

    # KiCad's own dylibs from the build bundle
    src_fw = os.path.join(SRC_APP, "Contents", "Frameworks")
    binaries = [dst_exe]
    for name in sorted(os.listdir(src_fw)):
        src = os.path.join(src_fw, name)
        if os.path.isfile(src) and not os.path.islink(src) and is_macho(src):
            dst = os.path.join(FW, name)
            shutil.copy2(src, dst)
            binaries.append(dst)

    # Kiface modules + 3D plugins, if the full build produced them.
    # They are dlopen'd by KiCad at runtime from Frameworks/, like
    # every other binary in the bundle.
    plugins_dir = os.path.join(SRC_APP, "Contents", "PlugIns")
    kifaces = []
    if os.path.isdir(plugins_dir):
        for name in sorted(os.listdir(plugins_dir)):
            src = os.path.join(plugins_dir, name)
            if name.endswith(".kiface") and os.path.isfile(src):
                dst = os.path.join(FW, name)
                shutil.copy2(src, dst)
                binaries.append(dst)
                kifaces.append(name)
        d3 = os.path.join(plugins_dir, "3d")
        if os.path.isdir(d3):
            for name in sorted(os.listdir(d3)):
                src = os.path.join(d3, name)
                if os.path.isfile(src) and is_macho(src):
                    dst = os.path.join(FW, name)
                    shutil.copy2(src, dst)
                    binaries.append(dst)
                    kifaces.append("3d/" + name)
    print("kifaces/plugins packaged:", ", ".join(kifaces) or "(none)")

    # Walk load commands until the embed set stops growing: any dep that
    # lives in the sysroot, the Qt kit, or the build tree gets embedded.
    # Deps recorded as @rpath/<name> are resolved against the sysroot
    # and the Qt kit too -- the v1 walk skipped every "@" dep, which is
    # how libz.1.dylib, libzstd.1.dylib and Python (all recorded as
    # @rpath loads) were left out of the v1 package entirely.
    #
    # EMBED_ALIASES maps a dep's file name in the sysroot to the name
    # it must carry in the bundle: KiCad's PYTHON_LIBRARY points at
    # the BeeWare CPython dylib, which the python stage stores in the
    # sysroot under a static-archive name; the built binaries record
    # it (and dyld looks for it) as plain "Python".
    EMBED_ALIASES = {"libpython3.13.a": "Python"}
    rpath_search_dirs = [os.path.join(SYSROOT, "lib"),
                         os.path.join(QTDIR, "lib")]

    def find_embed_source(base):
        names = [base] + [k for k, v in EMBED_ALIASES.items() if v == base]
        for name in names:
            for d in rpath_search_dirs:
                cand = os.path.join(d, name)
                if os.path.isfile(cand):
                    return cand
        return None

    embed_dylibs = {}       # basename -> source path
    embed_frameworks = {}   # framework name -> source dir
    unresolved = set()
    queue = list(binaries)
    seen = set()
    while queue:
        binary = queue.pop()
        if binary in seen:
            continue
        seen.add(binary)
        for dep in load_commands(binary):
            if dep.startswith("/usr/lib/") or dep.startswith("/System/"):
                continue
            if ".framework/" in dep:
                fwname = dep.split(".framework/")[0].split("/")[-1] + ".framework"
                if fwname in embed_frameworks or os.path.isdir(os.path.join(FW, fwname)):
                    continue
                srcdir = None
                if not dep.startswith("@"):
                    cand = dep.split(fwname)[0] + fwname
                    if os.path.isdir(cand):
                        srcdir = cand
                if srcdir is None:
                    for d in rpath_search_dirs:
                        if os.path.isdir(os.path.join(d, fwname)):
                            srcdir = os.path.join(d, fwname)
                            break
                if srcdir is not None:
                    embed_frameworks[fwname] = srcdir
                    queue.append(os.path.join(srcdir, fwname.replace(".framework", "")))
                else:
                    # The framework bundle exists nowhere (the sysroot
                    # carries the BeeWare Python dylib as a bare file,
                    # libpython3.13.a): embed its binary flat, under
                    # its own name -- the install-name rewrite below
                    # normalises this dep to @rpath/<binary name>.
                    binbase = EMBED_ALIASES.get(os.path.basename(dep),
                                                os.path.basename(dep))
                    if binbase in embed_dylibs \
                            or os.path.exists(os.path.join(FW, binbase)):
                        continue
                    src = find_embed_source(binbase)
                    if src is not None:
                        embed_dylibs[binbase] = src
                        queue.append(src)
                    else:
                        unresolved.add(dep)
                continue
            base = EMBED_ALIASES.get(os.path.basename(dep), os.path.basename(dep))
            if base in embed_dylibs or os.path.exists(os.path.join(FW, base)):
                continue
            if dep.startswith("@"):
                src = find_embed_source(base)
                if src is not None:
                    embed_dylibs[base] = src
                    queue.append(src)
                else:
                    unresolved.add(dep)
                continue
            if os.path.isfile(dep):
                embed_dylibs[base] = dep
                queue.append(dep)

    for base, src in sorted(embed_dylibs.items()):
        dst = os.path.join(FW, base)
        if not os.path.exists(dst):
            shutil.copy2(src, dst)
            binaries.append(dst)

    for fwname, srcdir in sorted(embed_frameworks.items()):
        dst = os.path.join(FW, fwname)
        if not os.path.exists(dst):
            shutil.copytree(srcdir, dst, symlinks=True)
            binaries.append(os.path.join(dst, fwname.replace(".framework", "")))

    if unresolved:
        print("WARNING: deps that could not be resolved or embedded:")
        for dep in sorted(unresolved):
            print("   UNRESOLVED:", dep)

    # ------------------------------------------------------------------
    # Python runtime (launch fix round 6, KiCad-Spike-v8).
    #
    # KiCad initialises its embedded CPython during manager startup
    # (SCRIPTING in PGM_BASE::InitPgm) and CPython imports the stdlib
    # `encodings` package during initialisation; up to v7 the bundle
    # shipped the interpreter binary with NO standard library, and
    # startup aborted on exactly that import. Patch 0025 points
    # PYTHONHOME at <app>/python in the executable's startup object;
    # this step stocks that tree from the same BeeWare sysroot the
    # interpreter came from, and mirrors in KiCad's own Python
    # components from the build tree.
    # ------------------------------------------------------------------
    def dir_stats(root):
        n = b = 0
        for r, _d, fs in os.walk(root):
            for f in fs:
                n += 1
                b += os.path.getsize(os.path.join(r, f))
        return n, b

    def collect_macho(root):
        found = []
        for r, _d, fs in os.walk(root):
            for f in fs:
                p = os.path.join(r, f)
                if is_macho(p):
                    os.chmod(p, 0o755)
                    found.append(p)
        return found

    py_src = os.path.join(SYSROOT, "lib", "python3.13")
    if not os.path.isdir(py_src):
        print("FATAL: Python stdlib missing from sysroot:", py_src,
              "(re-run the python-ios stage)")
        sys.exit(1)
    py_dst = os.path.join(APP, "python", "lib", "python3.13")
    os.makedirs(py_dst, exist_ok=True)
    shutil.copytree(py_src, py_dst, dirs_exist_ok=True)

    # Trims -- provably-dead weight ONLY, each logged with its size:
    #   * test/        CPython's own regression suite (35 MB); its
    #                  only consumers are CPython developers.
    #   * idlelib/     the IDLE editor; its GUI toolkit module
    #                  (_tkinter) does not exist in the iOS build.
    #   * tkinter/, turtledemo/   same reason: no _tkinter module
    #                  exists for this platform, so none of it can
    #                  ever be imported successfully.
    #   * lib-dynload test modules (_test*, _ctypes_test,
    #     _xxtestfuzz): extension modules whose only importer is
    #     the trimmed test suite.
    #   * modules the dynload probe (scripts/probe_dynload.py)
    #     proved cannot load on this platform at all.
    trim_log = []

    def trim_path(path, why):
        if not os.path.exists(path):
            return
        if os.path.isdir(path):
            n, b = dir_stats(path)
            shutil.rmtree(path)
        else:
            n, b = 1, os.path.getsize(path)
            os.remove(path)
        trim_log.append(f"{os.path.relpath(path, py_dst)} "
                        f"({n} files, {b} bytes) -- {why}")

    for d in ("test", "idlelib", "tkinter", "turtledemo"):
        trim_path(os.path.join(py_dst, d),
                  "provably dead on this platform (see packager notes)")
    dynload_dst = os.path.join(py_dst, "lib-dynload")
    if os.path.isdir(dynload_dst):
        for name in sorted(os.listdir(dynload_dst)):
            stem = name.split(".")[0]
            if stem.startswith("_test") or stem == "_ctypes_test" \
                    or stem == "_xxtestfuzz":
                trim_path(os.path.join(dynload_dst, name),
                          "CPython test-suite extension module")
    verdicts_file = os.path.join(WORK, "dynload-verdicts.txt")
    if os.path.isfile(verdicts_file):
        for line in open(verdicts_file):
            parts = line.split(None, 2)
            if len(parts) >= 2 and parts[0] == "TRIM":
                syms = parts[2].strip() if len(parts) > 2 else "?"
                trim_path(os.path.join(dynload_dst, parts[1]),
                          f"probe_dynload: cannot load on iOS "
                          f"(unresolvable: {syms})")
    else:
        print("WARNING: no dynload-verdicts.txt -- probe did not run; "
              "packaging all extension modules unprobed")
    for t in trim_log:
        print("python trim:", t)

    encodings = os.path.join(py_dst, "encodings", "__init__.py")
    if not os.path.isfile(encodings):
        print("FATAL: encodings package missing from packaged stdlib:",
              encodings)
        sys.exit(1)
    n_dyn = len([f for f in os.listdir(dynload_dst)
                 if f.endswith(".so")]) if os.path.isdir(dynload_dst) else 0
    if n_dyn == 0:
        print("FATAL: no extension modules in packaged lib-dynload")
        sys.exit(1)
    n_py, b_py = dir_stats(os.path.join(APP, "python"))
    print(f"python stdlib packaged: {n_py} files, {b_py} bytes "
          f"({n_dyn} extension modules kept)")

    # KiCad's own Python modules: the build copies pcbnew.py and
    # _pcbnew.so into its bundle-shaped PYTHON_DEST (a
    # Python.framework site-packages inside the built KiCad.app).
    # Mirror that directory wholesale into the PYTHONHOME
    # site-packages, where the interpreter's site machinery (and the
    # startup object's PYTHONPATH) finds them. _pcbnew.so is a copy
    # of _pcbnew.kiface: source the bytes from the copy already
    # placed in Frameworks/ so both go through the same install-name
    # rewrite below (falling back to the build's own copy if the
    # kiface is somehow absent).
    site_dst = os.path.join(py_dst, "site-packages")
    os.makedirs(site_dst, exist_ok=True)
    sp_glob = os.path.join(SRC_APP, "Contents", "Frameworks",
                           "Python.framework", "Versions", "*",
                           "lib", "python*", "site-packages")
    sp_dirs = sorted(glob.glob(sp_glob))
    if not sp_dirs:
        print("WARNING: build produced no Python.framework "
              "site-packages (glob:", sp_glob, ") -- KiCad Python "
              "modules NOT packaged")
    for sp in sp_dirs:
        for name in sorted(os.listdir(sp)):
            src = os.path.join(sp, name)
            if not os.path.isfile(src):
                continue
            if name == "_pcbnew.so":
                kiface_copy = os.path.join(FW, "_pcbnew.kiface")
                if os.path.isfile(kiface_copy):
                    shutil.copy2(kiface_copy,
                                 os.path.join(site_dst, "_pcbnew.so"))
                    print("site-packages: _pcbnew.so <- Frameworks/"
                          "_pcbnew.kiface (same bytes, module name)")
                else:
                    shutil.copy2(src, os.path.join(site_dst, name))
                    print("site-packages: _pcbnew.so <- build copy "
                          "(kiface missing from bundle!)")
            else:
                shutil.copy2(src, os.path.join(site_dst, name))
                print(f"site-packages: {name} "
                      f"({os.path.getsize(src)} bytes)")

    # KiCad's stock scripting plugins + footprint wizards: the
    # install rule ships pcbnew/python/plugins/ to
    # <data>/scripting/plugins, and the plugin loader
    # (kicadplugins.i LoadPlugins) searches the stock scripting
    # path's plugins/ subdirectory first. Mirror it under the
    # bundle's stock root (share/ == the KICAD_STOCK_DATA_HOME the
    # startup object sets).
    plugins_dst = os.path.join(APP, "share", "scripting", "plugins")
    stock_plugins = os.path.join(WORK, "src", "kicad", "pcbnew",
                                 "python", "plugins")
    if os.path.isdir(stock_plugins):
        os.makedirs(plugins_dst, exist_ok=True)
        shutil.copytree(stock_plugins, plugins_dst, dirs_exist_ok=True)
        n_sp, b_sp = dir_stats(plugins_dst)
        print(f"stock scripting plugins packaged: {n_sp} files, "
              f"{b_sp} bytes -> share/scripting/plugins")
    else:
        print("WARNING: KiCad stock scripting plugins not found at",
              stock_plugins)

    # Vendor addons (PCBWay / JLCPCB Fabrication Toolkit): official
    # PCM packages fetched + sha256-verified by the stage script
    # (see stage-kicad-ios.sh; pinned to the KiCad official PCM
    # repository's listed versions). PCM's own install transform
    # (kicad/pcm/pcm_task_manager.cpp) maps a package zip's
    # plugins/<contents> to <3rdparty>/plugins/<identifier with
    # '.'->'_'>/<contents>; we mirror that layout into the stock
    # scripting plugins directory the loader searches first, and
    # keep each package's metadata.json + vendor LICENSE alongside
    # the code for attribution.
    addons_dir = os.path.join(WORK, "addons")
    status_file = os.path.join(addons_dir, "STATUS.txt")
    addon_status = {}
    if os.path.isfile(status_file):
        for line in open(status_file):
            parts = line.split()
            if len(parts) == 3 and parts[0] == "ADDON":
                addon_status[parts[1]] = parts[2]
    for key in ("pcbway", "jlcpcb"):
        zpath = os.path.join(addons_dir, key + ".zip")
        if addon_status.get(key) != "OK" or not os.path.isfile(zpath):
            print(f"ADDON NOT PACKAGED: {key} (stage fetch status: "
                  f"{addon_status.get(key, 'unknown')})")
            continue
        with zipfile.ZipFile(zpath) as zf:
            meta = json.loads(zf.read("metadata.json"))
            clean_id = meta["identifier"].replace(".", "_")
            dest = os.path.join(plugins_dst, clean_id)
            os.makedirs(dest, exist_ok=True)
            n_add = 0
            for info in zf.infolist():
                if not info.filename.startswith("plugins/") \
                        or info.filename.endswith("/"):
                    continue
                rel = info.filename[len("plugins/"):]
                if ".." in rel.split("/"):
                    continue
                target = os.path.join(dest, rel)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, "wb") as fh:
                    fh.write(zf.read(info.filename))
                n_add += 1
            with open(os.path.join(dest, "metadata.json"), "wb") as fh:
                fh.write(zf.read("metadata.json"))
        lic = os.path.join(addons_dir, key + "-LICENSE")
        if os.path.isfile(lic):
            shutil.copy2(lic, os.path.join(dest, "LICENSE"))
        n_add, b_add = dir_stats(dest)
        print(f"addon packaged: {meta['name']} {meta['versions'][0]['version']} "
              f"({meta['identifier']}, license {meta['license']}) -> "
              f"share/scripting/plugins/{clean_id} ({n_add} files, "
              f"{b_add} bytes)")

    # Every Mach-O now under python/ joins the rewrite pass below:
    # it normalises their @rpath/Python.framework/Python load (the
    # BeeWare spelling) to @rpath/Python, the install name the
    # bundled interpreter image carries -- without it dyld cannot
    # match the extension modules' twolevel references to the
    # already-loaded Python image and every dlopen would fail.
    for p in collect_macho(os.path.join(APP, "python")):
        if p not in binaries:
            binaries.append(p)
    for p in collect_macho(plugins_dst):
        if p not in binaries:
            binaries.append(p)

    # Rewrite install names: own id -> @rpath/<base>, deps -> @rpath/<base>
    for binary in binaries:
        if not is_macho(binary):
            continue
        base = os.path.basename(binary)
        # dylibs and framework binaries get an @rpath id; the exe must not.
        if binary != dst_exe:
            run(["install_name_tool", "-id", f"@rpath/{base}", binary])
        for dep in load_commands(binary):
            if dep.startswith("/usr/lib/") or dep.startswith("/System/"):
                continue
            depbase = os.path.basename(dep)
            depbase = EMBED_ALIASES.get(depbase, depbase)
            if dep != f"@rpath/{depbase}":
                run(["install_name_tool", "-change", dep, f"@rpath/{depbase}", binary])
        if binary == dst_exe:
            run(["install_name_tool", "-add_rpath", "@executable_path/Frameworks", binary])

    # No Contents/ mirror and no bundle-root kiface copies: the v1
    # package mirrored every Frameworks file into
    # Contents/Frameworks (+ Contents/PlugIns) as a hedge for
    # KiCad's macOS-shaped kiface search, doubling the bundle to
    # 491 MB; the signing service refused it. v10's device run then
    # proved KiCad 10.0.1's generic kiface search (KIWAY::
    # dso_search_path) resolves <exe dir>/_<tool>.kiface -- the
    # bundle root -- so the editors failed to load at all. Since
    # launch fix round 9 (KiCad-Spike-v11), KiCad patch 0027
    # redirects that search to <exe dir>/Frameworks under
    # KICAD_IOS_PORT: the Frameworks/ copies packaged here ARE the
    # dlopen targets, and no duplicates are shipped.

    # KiCad stock data (launch fix round 5, KiCad-Spike-v7): KiCad
    # 10's BITMAP_STORE is file-based -- it opens an asset archive at
    # <stock data>/resources/images.tar.gz and every icon in every
    # window (starting with the manager's own toolbar/launcher) reads
    # its PNG data from it; a missing archive degrades every icon to
    # the built-in "image not found" placeholder. Patch 0024 points
    # PATHS::GetStockDataPath() at <app>/share via the
    # KICAD_STOCK_DATA_HOME environment variable, set by the
    # executable's iOS startup object. The full build produces the
    # archive at $BLD/resources/images.tar.gz (the same file desktop
    # installs as share/kicad/resources/images.tar.gz). Package it or
    # fail: a bundle without it is a known-broken deliverable.
    stock_src = os.path.join(BLD, "resources", "images.tar.gz")
    if not os.path.isfile(stock_src):
        print("FATAL: stock bitmap archive missing:", stock_src)
        sys.exit(1)
    stock_dst_dir = os.path.join(APP, "share", "resources")
    os.makedirs(stock_dst_dir, exist_ok=True)
    shutil.copy2(stock_src, os.path.join(stock_dst_dir, "images.tar.gz"))
    print("stock data packaged: share/resources/images.tar.gz",
          os.path.getsize(stock_src), "bytes")

    # KiCad JSON schemas (round 16, KiCad-Spike-v16): KiCad locates its
    # JSON validation schemas at <stock data>/schemas/*.json (the
    # JSON_SCHEMA_VALIDATOR paths are built as
    # PATHS::GetStockDataPath() + "schemas"). Three constructors run at
    # ordinary startup and wxLogError "schema file '%s' not found" when
    # the file is absent: API_PLUGIN_MANAGER (built by PGM_BASE in
    # every app, api.v1.schema.json) and PLUGIN_CONTENT_MANAGER (built
    # by the manager frame at startup, pcm.v1.schema.json +
    # pcm.v2.schema.json). Desktop installs compose that one directory
    # from three source dirs (api/CMakeLists.txt, kicad/pcm/
    # CMakeLists.txt, common/CMakeLists.txt for resources/schemas);
    # this packager never ran cmake --install and never copied any of
    # them, so every v7-v15 bundle shipped without share/schemas/ and
    # the manager raised the modal "schema file
    # '/private/var/containers/Bundle/Application/.../share/schemas/
    # ...' not found" error (the v13-v15 "file creation" error whose
    # text was never captured until the v15 device screenshots).
    # Package the full union or fail: a bundle without these files is
    # a known-broken deliverable.
    schemas_dst_dir = os.path.join(APP, "share", "schemas")
    os.makedirs(schemas_dst_dir, exist_ok=True)
    schema_src_dirs = [
        os.path.join(WORK, "src", "kicad", "resources", "schemas"),
        os.path.join(WORK, "src", "kicad", "kicad", "pcm", "schemas"),
        os.path.join(WORK, "src", "kicad", "api", "schemas"),
    ]
    n_schemas = 0
    for src_dir in schema_src_dirs:
        if not os.path.isdir(src_dir):
            print("FATAL: schema source dir missing:", src_dir)
            sys.exit(1)
        for name in sorted(os.listdir(src_dir)):
            if name.endswith(".json"):
                shutil.copy2(os.path.join(src_dir, name),
                             os.path.join(schemas_dst_dir, name))
                n_schemas += 1
    for required in ("pcm.v1.schema.json", "pcm.v2.schema.json",
                     "api.v1.schema.json"):
        if not os.path.isfile(os.path.join(schemas_dst_dir, required)):
            print("FATAL: required schema not packaged:", required)
            sys.exit(1)
    print(f"stock data packaged: share/schemas/ ({n_schemas} files)")

    # KiCad stock libraries (launch fix round 9, KiCad-Spike-v11):
    # the first-run setup could not reach the default libraries in
    # v10 because the bundle shipped no stock content at all (and,
    # pre-patch-0028, the generic stock EDA path root was empty on
    # Apple builds). The stage fetched the pinned official library
    # repos (10.0.1) into $WORK/kicad-libs; package the installed
    # layout KiCad's own CMake installs use:
    #   share/symbols/    *.kicad_symdir trees + *.sp
    #   share/footprints/ *.pretty trees
    #   share/template/   sym-lib-table + fp-lib-table, the template
    #                     repo's Projects/* dirs and Worksheets/*.kicad_wks
    # Patch 0028 roots PATHS::GetStockEDALibraryPath() at the stock
    # data home (<app>/share, patch 0024), so the default global
    # tables -- copied into the user settings by the setup wizard,
    # chaining to share/template/{sym,fp}-lib-table whose rows expand
    # ${KICAD10_SYMBOL_DIR}/${KICAD10_FOOTPRINT_DIR} to these trees --
    # resolve inside the bundle. Fail hard on missing trees: a bundle
    # whose setup cannot reach the default libraries must not ship.
    libs_root = os.path.join(WORK, "kicad-libs")
    sym_src = os.path.join(libs_root, "symbols")
    fp_src = os.path.join(libs_root, "footprints")
    tpl_src = os.path.join(libs_root, "templates")
    for d in (sym_src, fp_src, tpl_src):
        if not os.path.isdir(d):
            print("FATAL: stock library tree missing:", d)
            sys.exit(1)
    share_dir = os.path.join(APP, "share")

    def tree_bytes(root):
        total = 0
        for dp, _dn, fn in os.walk(root):
            for f in fn:
                total += os.path.getsize(os.path.join(dp, f))
        return total

    sym_dst = os.path.join(share_dir, "symbols")
    os.makedirs(sym_dst, exist_ok=True)
    n_symdir = 0
    for name in sorted(os.listdir(sym_src)):
        src = os.path.join(sym_src, name)
        if name.endswith(".kicad_symdir") and os.path.isdir(src):
            shutil.copytree(src, os.path.join(sym_dst, name))
            n_symdir += 1
        elif name.endswith(".sp") and os.path.isfile(src):
            shutil.copy2(src, os.path.join(sym_dst, name))
    fp_dst = os.path.join(share_dir, "footprints")
    os.makedirs(fp_dst, exist_ok=True)
    n_pretty = 0
    for name in sorted(os.listdir(fp_src)):
        src = os.path.join(fp_src, name)
        if name.endswith(".pretty") and os.path.isdir(src):
            shutil.copytree(src, os.path.join(fp_dst, name))
            n_pretty += 1
    tpl_dst = os.path.join(share_dir, "template")
    os.makedirs(tpl_dst, exist_ok=True)
    shutil.copy2(os.path.join(sym_src, "sym-lib-table"),
                 os.path.join(tpl_dst, "sym-lib-table"))
    shutil.copy2(os.path.join(fp_src, "fp-lib-table"),
                 os.path.join(tpl_dst, "fp-lib-table"))
    n_tpl = 0
    projects_src = os.path.join(tpl_src, "Projects")
    for name in sorted(os.listdir(projects_src)):
        src = os.path.join(projects_src, name)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(tpl_dst, name))
            n_tpl += 1
    n_wks = 0
    for dp, _dn, fn in os.walk(os.path.join(tpl_src, "Worksheets")):
        for f in fn:
            if f.endswith(".kicad_wks"):
                shutil.copy2(os.path.join(dp, f), os.path.join(tpl_dst, f))
                n_wks += 1
    if n_symdir < 200 or n_pretty < 100 or n_tpl == 0 or n_wks == 0:
        print("FATAL: stock library packaging incomplete:",
              n_symdir, "symdirs,", n_pretty, "pretty,",
              n_tpl, "templates,", n_wks, "worksheets")
        sys.exit(1)
    print("stock libraries packaged:", n_symdir, "symbol libraries",
          tree_bytes(sym_dst), "bytes;", n_pretty, "footprint libraries",
          tree_bytes(fp_dst), "bytes; template:", n_tpl, "projects,",
          n_wks, "worksheets,", tree_bytes(tpl_dst), "bytes")

    # Stock demo projects (launch fix round 9): the manager's File
    # menu only offers "Open Demo Project" when PATHS::
    # GetStockDemosPath() (<app>/share/demos) exists, so bundle the
    # 10.0.1 demos -- minus the four projects that are mostly a
    # single huge board/model file (126 MB, 97 MB, 50 MB, 31 MB of
    # the 355 MB total); the other 32 projects (50 MB) are complete.
    # The trim is disclosed in MODIFICATIONS.md and the spike report.
    demos_src = os.path.join(WORK, "src", "kicad", "demos")
    DEMOS_EXCLUDE = {"vme-wren", "jetson-agx-thor-baseboard",
                     "cm5_minima", "tiny_tapeout"}
    if os.path.isdir(demos_src):
        demos_dst = os.path.join(share_dir, "demos")
        os.makedirs(demos_dst, exist_ok=True)
        n_demo = 0
        for name in sorted(os.listdir(demos_src)):
            src = os.path.join(demos_src, name)
            if os.path.isdir(src) and name not in DEMOS_EXCLUDE:
                shutil.copytree(src, os.path.join(demos_dst, name))
                n_demo += 1
        print("stock demos packaged:", n_demo, "projects",
              tree_bytes(demos_dst), "bytes (trimmed:",
              ", ".join(sorted(DEMOS_EXCLUDE)) + ")")

    # App icon set (see _install_app_icons): rendered from KiCad's
    # upstream program icon into the bundle root before the plist is
    # written, so the declarations below resolve to real files.
    _install_app_icons()

    plist = {
        "CFBundleExecutable": "KiCad",
        "CFBundleIdentifier": "com.user.kicadspike",
        "CFBundleName": "KiCad",
        "CFBundleDisplayName": "KiCad (spike)",
        # Icon declarations for a manually packaged app: the flat
        # CFBundleIconFiles list plus the CFBundleIcons primary-icon
        # dictionary, both naming base names whose @2x/@3x files sit
        # in the bundle root (rendered above). The 1024 marketing
        # icon is included in the same lists.
        "CFBundleIconFiles": APP_ICON_BASES,
        "CFBundleIcons": {
            "CFBundlePrimaryIcon": {
                "CFBundleIconFiles": list(APP_ICON_BASES),
            },
        },
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "10.0.1",
        "CFBundleVersion": "10.0.1",
        "LSRequiresIPhoneOS": True,
        "MinimumOSVersion": "17.0",
        "UIDeviceFamily": [2],
        "UISupportedInterfaceOrientations": [
            "UIInterfaceOrientationPortrait",
            "UIInterfaceOrientationLandscapeLeft",
            "UIInterfaceOrientationLandscapeRight",
        ],
        # Presentation (round 16, KiCad-Spike-v16): declare a launch
        # screen and require full screen. Up to v15 this plist carried
        # NO launch-screen declaration of any kind (no
        # UILaunchStoryboardName, no UILaunchScreen, no launch images)
        # and UIRequiresFullScreen was False. An app that declares no
        # launch screen is not treated as native-resolution by iPadOS:
        # it is presented at a legacy screen size and the system scales
        # and letterboxes that surface onto the real panel -- the v15
        # device evidence (2026-11-09) exactly: the manager window in a
        # middle band with large black areas above/below, and the whole
        # UI (menus, text, icons) rendered uniformly ~2x too big,
        # because every point of the legacy surface is magnified.
        # UIScreen is the single value the whole stack reads --
        # QIOSScreen takes its geometry from UIScreen.bounds and its
        # devicePixelRatio from UIScreen.scale, wxQt's display/window
        # code passes QScreen geometry through unchanged, and KiCad
        # lays out in those same units -- so a wrong UIScreen size
        # distorts everything downstream at once, and no downstream
        # layer can correct it. The control case is the FEBio Studio
        # app on the same iPad with the same Qt 6.9.3 kit, which
        # renders full-screen at natural scale: its Info.plist declares
        # UILaunchStoryboardName=LaunchScreen (with a compiled
        # LaunchScreen.storyboardc in the bundle) and
        # UIRequiresFullScreen=True, and both executables carry the
        # same LC_BUILD_VERSION (platform ios, sdk 26.5, minos 17.0),
        # which rules out an old-SDK letterbox as the difference.
        # UILaunchScreen as an empty dict is the file-free form of the
        # same declaration (it is one of the launch-screen keys
        # iPadOS accepts, needs no compiled storyboard in the bundle,
        # and the FEBio Spike IPA ships exactly this key); the launch
        # image it produces is blank, matching the black launch this
        # app already shows. UIRequiresFullScreen=True additionally
        # opts out of Split View / Stage Manager resizing, which the
        # Qt iOS QPA + wxQt window model cannot honour anyway: KiCad's
        # frames are desktop windows inside one app surface (patch
        # 0037 maximizes them to fill it), not independently resizable
        # scenes.
        "UILaunchScreen": {},
        "UIRequiresFullScreen": True,
        "NSPrincipalClass": "UIApplication",
        # File access (launch fix round 6, KiCad-Spike-v8): expose the
        # app's sandbox Documents folder in the Files app / Finder and
        # allow opening documents in place. This is the folder KiCad
        # resolves its user paths against on this port: the iOS
        # kiplatform layer's KIPLATFORM::ENV::GetDocumentsPath() is
        # wxStandardPaths::GetDocumentsDir() (the sandbox Documents
        # dir), and PATHS::getUserDocumentPath() builds
        # Documents/KiCad/10.0/{scripting,plugins,symbols,footprints,
        # 3rdparty,projects,...} on it -- so projects and libraries
        # dropped into the shared folder are exactly where KiCad
        # looks for them.
        "UIFileSharingEnabled": True,
        "LSSupportsOpeningDocumentsInPlace": True,
        # Appearance (launch fix round 8, KiCad-Spike-v10): pin the
        # app to the light appearance. Desktop KiCad is a light-theme
        # application: it mixes wx system colours with hardcoded light
        # colours and does not adapt to a dark system appearance. With
        # no UIUserInterfaceStyle key (v9 and earlier) the app followed
        # the device appearance, and on a dark-mode device the whole
        # wxQt UI resolved dark -- the first-run wizard rendered white
        # text on a black page, with widget backgrounds a different
        # colour from the page around them. The key propagates through
        # every layer this port renders with, verified against the
        # Qt 6.9.3 sources: UIKit resolves each QUIWindow's trait
        # collection from it, QIOSTheme::colorScheme() reads the
        # window's userInterfaceStyle and reports Qt::ColorScheme::
        # Light, the iOS system palette's dynamic UIColors (label,
        # systemGroupedBackground, secondarySystemBackground, ...)
        # resolve to their light variants, the Fusion style (the iOS
        # theme's StyleNames hint) paints from that palette, and wxQt
        # maps wxSYS_COLOUR_* from the same palette -- so the wizard,
        # the manager and every dialog render with desktop KiCad's
        # light colours.
        "UIUserInterfaceStyle": "Light",
    }
    with open(os.path.join(APP, "Info.plist"), "wb") as fh:
        plistlib.dump(plist, fh)

    # Belt-and-braces: duplicate every kiface module at the bundle
    # root (launch fix round 10, KiCad-Spike-v12). Device evidence
    # across v10 and v11: the manager's startup library preload
    # dlopens "<exe dir>/_<tool>.kiface" -- the bundle root -- and
    # raised "Failed to load shared library" for it on both builds,
    # because patch 0027's Frameworks redirect never reached the
    # shipped libkicommon (its KICAD_IOS_PORT define sat on the
    # `common` CMake target, which compiles none of the patched
    # sources; patch 0032 puts the define on the `kicommon` target,
    # so the Frameworks search is live in v12 as well). Shipping the
    # modules in BOTH places means every kiface path the loader has
    # ever constructed on device names a file that exists. The
    # copies are taken from the final Frameworks bytes (after all
    # install-name rewriting above), so the two populations are
    # byte-identical; a kiface's dependencies are @rpath names
    # resolved through @executable_path-based rpaths, which do not
    # depend on the kiface's own location. Cost: the eight modules
    # total 160,119,512 bytes uncompressed.
    root_kifaces = []
    for name in sorted(os.listdir(FW)):
        src = os.path.join(FW, name)
        if name.endswith(".kiface") and os.path.isfile(src):
            shutil.copy2(src, os.path.join(APP, name))
            root_kifaces.append(name)
    print("kiface bundle-root copies:", ", ".join(root_kifaces) or "(none)")

    ipa = os.path.join(WORK, "KiCad-Spike-unsigned.ipa")
    if os.path.exists(ipa):
        os.remove(ipa)
    run(["zip", "-qry", ipa, "Payload"], cwd=PKG)

    print("embedded dylibs:", ", ".join(sorted(embed_dylibs)) or "(none)")
    print("embedded frameworks:", ", ".join(sorted(embed_frameworks)) or "(none)")
    print("IPA:", ipa, os.path.getsize(ipa), "bytes")
    print("final otool -L of executable:")
    print(run(["otool", "-L", dst_exe]).stdout)


if __name__ == "__main__":
    main()
