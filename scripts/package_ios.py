#!/usr/bin/env python3
"""
Assemble an unsigned iOS .ipa from the CMake-built KiCad.app (macOS-style
bundle) produced by stage-kicad-ios.sh.

Layout produced (iOS-flat, as dyld + iOS require):
    Payload/KiCad.app/KiCad                 (the manager executable)
    Payload/KiCad.app/Info.plist            (iOS plist written here)
    Payload/KiCad.app/Frameworks/*.dylib    (KiCad libs + sysroot dylibs)
    Payload/KiCad.app/Frameworks/*.framework (Qt frameworks actually linked)
    Payload/KiCad.app/Contents/Frameworks/  (mirror of the dylibs: KiCad's
        own path logic is macOS-bundle-shaped; the mirror gives its
        dlopen-based kiface search a Contents/Frameworks to find)

Every Mach-O gets its install names rewritten to @rpath/<basename> and
the executable gains @executable_path/Frameworks as an rpath, so nothing
references CI-machine paths. Qt frameworks ship with @rpath ids already.

The user re-signs the unsigned IPA with his own tooling (Signulous), like the
other spike apps.
"""

import os
import plistlib
import shutil
import subprocess
import sys

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
    # They are dlopen'd by KiCad at runtime, so they live both in
    # Frameworks/ (for dyld) and in the Contents/PlugIns mirror below.
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
    embed_dylibs = {}       # basename -> source path
    embed_frameworks = {}   # framework name -> source dir
    queue = list(binaries)
    seen = set()
    while queue:
        binary = queue.pop()
        if binary in seen:
            continue
        seen.add(binary)
        for dep in load_commands(binary):
            if dep.startswith("@") or dep.startswith("/usr/lib/") or dep.startswith("/System/"):
                continue
            base = os.path.basename(dep)
            if ".framework/" in dep:
                fwname = dep.split(".framework/")[0].split("/")[-1] + ".framework"
                srcdir = dep.split(fwname)[0] + fwname
                if fwname not in embed_frameworks and os.path.isdir(srcdir):
                    embed_frameworks[fwname] = srcdir
                    queue.append(os.path.join(srcdir, fwname.replace(".framework", "")))
                continue
            if base not in embed_dylibs:
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
            if dep != f"@rpath/{depbase}":
                run(["install_name_tool", "-change", dep, f"@rpath/{depbase}", binary])
        if binary == dst_exe:
            run(["install_name_tool", "-add_rpath", "@executable_path/Frameworks", binary])

    # Mirror dylibs under Contents/Frameworks for KiCad's macOS-shaped
    # bundle path logic (kiface dlopen search).
    mirror = os.path.join(APP, "Contents", "Frameworks")
    os.makedirs(mirror, exist_ok=True)
    plug_mirror = os.path.join(APP, "Contents", "PlugIns")
    os.makedirs(plug_mirror, exist_ok=True)
    for name in sorted(os.listdir(FW)):
        src = os.path.join(FW, name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(mirror, name))
            if name.endswith(".kiface"):
                shutil.copy2(src, os.path.join(plug_mirror, name))

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
