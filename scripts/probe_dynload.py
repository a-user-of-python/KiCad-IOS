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
# that check per module on the build machine (against the real
# iPhoneOS SDK .tbd stubs) and writes verdicts to
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
# Implementation note: the symbol tables are parsed DIRECTLY from
# the Mach-O files (LC_SYMTAB), not via `nm`. The first version of
# this probe shelled out to `xcrun nm -u` and recognised neither of
# the output spellings the runner produced -- it saw zero undefined
# symbols for every module and printed vacuous OKs (caught when a
# sanity check was added in review of the v8 stage log). Parsing
# the files removes the tool dependency and the format guessing.
# A sanity check below refuses to emit verdicts if the total
# undefined count is ever zero again.
#
# Usage: probe_dynload.py SYSROOT WORK SDK_PATH
import os
import re
import struct
import sys

DYLD_WHITELIST = {"dyld_stub_binder", "___dso_handle", "__mh_execute_header"}


def parse_macho(data):
    """(defined, undef, loads) for one Mach-O buffer (fat or thin)."""
    if len(data) >= 8 and struct.unpack_from(">I", data, 0)[0] == 0xCAFEBABE:
        # Fat binary: big-endian header, then per-arch slices.
        defined, undef, loads = set(), set(), []
        narch = struct.unpack_from(">I", data, 4)[0]
        for i in range(narch):
            aoff = 8 + i * 20
            _cpu, _sub, off, size, _al = struct.unpack_from(">IIIII", data, aoff)
            d, u, l = parse_macho(data[off:off + size])
            defined |= d
            undef |= u
            loads += l
        return defined, undef, loads
    defined, undef, loads = set(), set(), []
    if len(data) < 32:
        return defined, undef, loads
    magic = struct.unpack_from("<I", data, 0)[0]
    if magic == 0xFEEDFACF:      # 64-bit little-endian
        ncmds = struct.unpack_from("<I", data, 16)[0]
        off = 32
    elif magic == 0xFEEDFACE:    # 32-bit little-endian
        ncmds = struct.unpack_from("<I", data, 16)[0]
        off = 28
    else:
        return defined, undef, loads
    symoff = nsyms = stroff = strsize = 0
    for _ in range(ncmds):
        if off + 8 > len(data):
            break
        cmd, cmdsize = struct.unpack_from("<II", data, off)
        if cmdsize < 8:
            break
        if cmd == 0x2:           # LC_SYMTAB
            symoff, nsyms, stroff, strsize = struct.unpack_from(
                "<IIII", data, off + 8)
        elif cmd == 0xC:         # LC_LOAD_DYLIB
            nameoff = struct.unpack_from("<I", data, off + 8)[0]
            end = data.find(b"\0", off + nameoff)
            loads.append(data[off + nameoff:end].decode("utf-8", "replace"))
        off += cmdsize
    for i in range(nsyms):
        noff, ntype, _nsect, _ndesc, _nvalue = struct.unpack_from(
            "<IBBHI", data, symoff + i * 16)
        if noff == 0 or noff >= strsize or not (ntype & 0x01):
            continue             # local symbols cannot satisfy imports
        end = data.find(b"\0", stroff + noff)
        name = data[stroff + noff:end].decode("utf-8", "replace")
        if ntype & 0x0E:         # N_SECT / N_ABS / N_PBUD: defined
            defined.add(name)
        elif _ndesc & 0x40:      # NREF_TO_WEAK: weak import, binds to 0
            pass
        else:
            undef.add(name)
    return defined, undef, loads


def ar_members(data):
    """Yield member payloads of an ar archive (BSD/GNU variants)."""
    if not data.startswith(b"!<arch>\n"):
        return
    off = 8
    long_names = b""
    while off + 60 <= len(data):
        hdr = data[off:off + 60]
        try:
            size = int(hdr[48:58].decode("ascii", "replace").strip())
        except ValueError:
            break
        name = hdr[0:16].decode("ascii", "replace").strip()
        body = data[off + 60:off + 60 + size]
        if name == "//":
            long_names = body
        elif name.startswith("#1/"):
            nlen = int(name[3:])
            yield body[nlen:]
        elif name.startswith("/") and name[1:].isdigit():
            noff = int(name[1:])
            end = long_names.find(b"\n", noff)
            yield body
        elif name not in ("/", "__.SYMDEF", "__.SYMDEF SORTED"):
            yield body
        off += 60 + size + (size & 1)


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
    python_lib = os.path.join(sysroot, "lib", "libpython3.13.a")

    def norm(symbols):
        # Mach-O names and .tbd tokens both carry the leading
        # underscore; strip exactly one so comparison is uniform.
        return {s[1:] if s.startswith("_") else s for s in symbols}

    python_exports = set()
    with open(python_lib, "rb") as fh:
        libdata = fh.read()
    if libdata.startswith(b"!<arch>\n"):
        for member in ar_members(libdata):
            d, _u, _l = parse_macho(member)
            python_exports |= d
    else:
        # In this sysroot the "libpython3.13.a" is the BeeWare
        # framework's Mach-O binary itself, copied under that name
        # by stage-python-ios.sh -- parse it directly.
        d, _u, _l = parse_macho(libdata)
        python_exports |= d
    python_exports = norm(python_exports)
    libsystem = norm(tbd_symbols(os.path.join(sdk, "usr/lib/libSystem.B.tbd")))
    libsqlite = norm(tbd_symbols(os.path.join(sdk, "usr/lib/libsqlite3.tbd")))
    # The extension modules bind in the process-wide FLAT namespace
    # (this port's linking model), so symbols can also legitimately
    # resolve against other dylibs the app itself ships and loads at
    # startup -- concretely zlib: binascii/zlib modules reference
    # the zlib API without linking libz themselves, and the bundle
    # ships Frameworks/libz.1.dylib (KiCad's own images link it, so
    # it is loaded before any dlopen). Model that: union the
    # exports of the sysroot's standalone C dylibs the packager
    # embeds (zlib, zstd).
    bundled_exports = set()
    import glob as _glob
    for cand in _glob.glob(os.path.join(sysroot, "lib", "libz*.dylib")) + \
            _glob.glob(os.path.join(sysroot, "lib", "libzstd*.dylib")):
        with open(cand, "rb") as fh:
            d, _u, _l = parse_macho(fh.read())
        bundled_exports |= d
        print(f"probe: bundled dylib in resolution universe: "
              f"{os.path.basename(cand)} ({len(d)} exports)")
    bundled_exports = norm(bundled_exports)
    print(f"probe: Python exports={len(python_exports)} "
          f"libSystem stub symbols={len(libsystem)} "
          f"libsqlite3 stub symbols={len(libsqlite)}")

    verdicts = []
    total_undef = 0
    modules = sorted(f for f in os.listdir(dynload) if f.endswith(".so"))
    for name in modules:
        with open(os.path.join(dynload, name), "rb") as fh:
            defined, undef, loads = parse_macho(fh.read())
        universe = python_exports | libsystem | bundled_exports \
            | norm(DYLD_WHITELIST)
        if any("libsqlite3" in ld for ld in loads):
            universe |= libsqlite
        undef = norm(undef - defined)
        total_undef += len(undef)
        missing = sorted(s for s in undef if s not in universe)
        if missing:
            shown = ["_" + s for s in missing]
            verdicts.append(f"TRIM {name} {','.join(shown)}")
            print(f"probe: TRIM {name}: unresolvable: {', '.join(shown)}")
        else:
            verdicts.append(f"OK {name}")
            print(f"probe: OK {name} ({len(undef)} undefined, all resolve)")

    if total_undef == 0:
        # Sanity check: real extension modules DO carry undefined
        # symbols (every one references Py_* APIs). Zero across the
        # board means the parsing above is broken, not that the
        # modules are clean -- fail loudly instead of writing
        # vacuous OK verdicts.
        print("probe: SANITY FAILURE -- 0 undefined symbols seen "
              f"across {len(modules)} modules; symbol parsing is "
              "broken. Refusing to write verdicts.")
        sys.exit(2)
    out = os.path.join(work, "dynload-verdicts.txt")
    with open(out, "w") as fh:
        fh.write("\n".join(verdicts) + "\n")
    ntrim = sum(1 for v in verdicts if v.startswith("TRIM"))
    print(f"probe: {len(verdicts)} modules probed, {ntrim} TRIM verdicts -> {out}")


if __name__ == "__main__":
    main()
