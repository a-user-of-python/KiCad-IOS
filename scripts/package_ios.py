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

import glob
import json
import os
import plistlib
import shutil
import subprocess
import sys
import zipfile

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

    plist = {
        "CFBundleExecutable": "KiCad",
        "CFBundleIdentifier": "com.user.kicadspike",
        "CFBundleName": "KiCad",
        "CFBundleDisplayName": "KiCad (spike)",
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
        "UIRequiresFullScreen": False,
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
