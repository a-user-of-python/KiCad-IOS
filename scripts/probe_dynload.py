#!/usr/bin/env python3
# [KiCad-IOS port] Per-module loadability probe for the CPython
# extension modules (lib-dynload/*.so) staged into the sysroot by
# stage-python-ios.sh. Part of the KiCad-IOS spike (GPLv3-or-later,
# matching upstream KiCad); NOT upstream KiCad code.
#
# Why this exists (launch fix round 6, KiCad-Spike-v8): each BeeWare
# extension module is linked -undefined dynamic_lookup against
# @rpath/Python.framework/Python + /usr/lib/libSystem.B.dylib (and,
# for _sqlite3, /usr/lib/libsqlite3.dylib). Whether a given module
# can actually be dlopen'd on device is decidable offline: every
# strong undefined symbol must be an export of the shipped Python
# image, of the iOS SDK's libSystem stub, or -- only for images
# that link it -- of the SDK's libsqlite3 stub. This probe performs
# that check per module on the build machine (which has the real
# iPhoneOS SDK .tbd stubs and xcrun nm), and writes verdicts to
# $WORK/dynload-verdicts.txt for scripts/package_ios.py:
#
#     OK   <module-file-name>
#     TRIM <module-file-name> <unresolvable-symbol,...>
#
# A TRIM verdict means the module provably cannot load on this
# platform (some symbol exists in none of its linked libraries),
# so packaging it would ship a broken file; the packager drops it
# and logs the drop. Weak undefined symbols are excluded (dyld
# binds them to 0). Symbols a module defines itself are excluded.
#
# Usage: probe_dynload.py SYSROOT WORK SDK_PATH
import os
import re
import subprocess
import sys

DYLD_WHITELIST = {"dyld_stub_binder", "___dso_handle", "__mh_execute_header"}


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def nm_symbols(path, *flags):
    """Last-token symbol names from an nm listing."""
    names = set()
    for line in run(["xcrun", "nm", *flags, path]).splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[-1].startswith("_"):
            names.add(parts[-1])
    return names


def nm_undefined(path):
    """Undefined symbols only: lines whose type field is 'U'."""
    names = set()
    for line in run(["xcrun", "nm", "-u", path]).splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[-2] == "U":
            names.add(parts[-1])
    return names


def tbd_symbols(path):
    if not os.path.isfile(path):
        print(f"probe: WARNING stub not found: {path}")
        return set()
    text = open(path, errors="replace").read()
    return set(re.findall(r"[A-Za-z_.$][A-Za-z0-9_.$]*", text))


def main():
    sysroot, work, sdk = sys.argv[1], sys.argv[2], sys.argv[3]
    pydir = os.path.join(sysroot, "lib", "python3.13")
    dynload = os.path.join(pydir, "lib-dynload")
    python_bin = os.path.join(sysroot, "lib", "libpython3.13.a")

    def norm(symbols):
        # nm and the .tbd stubs both spell Mach-O names with the
        # leading underscore; normalise by stripping exactly one so
        # the comparison is spelling-proof.
        return {s[1:] if s.startswith("_") else s for s in symbols}

    python_exports = norm(nm_symbols(python_bin, "-g"))
    libsystem = norm(tbd_symbols(os.path.join(sdk, "usr/lib/libSystem.B.tbd")))
    libsqlite = norm(tbd_symbols(os.path.join(sdk, "usr/lib/libsqlite3.tbd")))
    print(f"probe: Python exports={len(python_exports)} "
          f"libSystem stub symbols={len(libsystem)} "
          f"libsqlite3 stub symbols={len(libsqlite)}")

    verdicts = []
    modules = sorted(f for f in os.listdir(dynload) if f.endswith(".so"))
    for name in modules:
        path = os.path.join(dynload, name)
        loads = run(["otool", "-L", path])
        universe = python_exports | libsystem | norm(DYLD_WHITELIST)
        if "/usr/lib/libsqlite3.dylib" in loads:
            universe |= libsqlite
        undef = norm(nm_undefined(path) - nm_symbols(path, "-g"))
        missing = sorted(s for s in undef if s not in universe)
        if missing:
            shown = ["_" + s for s in missing]
            verdicts.append(f"TRIM {name} {','.join(shown)}")
            print(f"probe: TRIM {name}: unresolvable: {', '.join(shown)}")
        else:
            verdicts.append(f"OK {name}")
            print(f"probe: OK {name} ({len(undef)} undefined, all resolve)")

    out = os.path.join(work, "dynload-verdicts.txt")
    with open(out, "w") as fh:
        fh.write("\n".join(verdicts) + "\n")
    ntrim = sum(1 for v in verdicts if v.startswith("TRIM"))
    print(f"probe: {len(verdicts)} modules probed, {ntrim} TRIM verdicts -> {out}")


if __name__ == "__main__":
    main()
