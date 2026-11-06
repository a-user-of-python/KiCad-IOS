#!/usr/bin/env python3
"""
Unhide the global symbols in the wxWidgets and Qt static archives.

Why: in this port wx and Qt are static archives linked into the
manager executable only (KiCad patches 0020-0022), and the KiCad
shared libraries resolve their wx/Qt symbols against the executable
at load time (-undefined dynamic_lookup). That only works if the
executable EXPORTS those symbols. But wx and Qt are compiled with
hidden visibility: in their Mach-O object files the globals are
stored as private externs (n_type N_EXT|N_PEXT), and ld64 carries
that into the executable (n_type 0x1e) -- present, but not exported
and not dyld-bindable from other images. Neither -export_dynamic
nor -exported_symbol '_*' promotes them (verified on the v4 and
v5-candidate executables: ~82k defined globals but only ~500-700
true externals; dyld aborted on device with "symbol not found in
flat namespace '__ZN10wxGLCanvas11SwapBuffersEv'", and a
bundle-wide symbol-closure audit counted 3,351 unresolvable wx
symbols).

This script clears the N_PEXT bit (0x10) on every defined external
symbol in the object files inside the given archives, in place.
Member layout, symbol names and the archive symbol table are
untouched (only n_type bytes change), so no re-indexing is needed.
It is idempotent, and it prints per-archive counts so the stage
log shows exactly what was changed; a run that unhides nothing at
all is a hard error (the visibility model would be wrong, and the
build would produce another unlaunchable IPA).

Scope: ONLY the wx archives and the Qt kit's archives / framework
binaries -- the statics that live in the executable and whose
symbols the libraries import. Third-party sysroot libraries
(curl, OpenCascade, ngspice, ...) are self-contained in their
home images and are not touched. This is build tooling of this
repo (it rewrites intermediate build artifacts, not upstream
sources); see MODIFICATIONS.md.

Usage: unhide_archive_symbols.py SYSROOT_LIB_DIR QT_IOS_DIR
"""

import glob
import os
import struct
import sys

N_PEXT = 0x10
N_EXT = 0x01
N_TYPE_MASK = 0x0E
N_UNDF = 0x0
FAT_MAGIC = 0xCAFEBABE  # as read big-endian below


def unhide_slice(d, base, counts):
    """Process one thin Mach-O object occupying d[base:base+size].
    Returns the number of symbols unhidden in it."""
    magic = struct.unpack_from('<I', d, base)[0]
    if magic not in (0xFEEDFACF, 0xFEEDFACE):
        return 0
    is64 = magic == 0xFEEDFACF
    ncmds = struct.unpack_from('<I', d, base + 16)[0]
    p = base + (32 if is64 else 28)
    symtab = None
    for _ in range(ncmds):
        cmd, size = struct.unpack_from('<II', d, p)
        if (cmd & 0x7FFFFFFF) == 0x2:  # LC_SYMTAB
            symtab = struct.unpack_from('<IIII', d, p + 8)
        p += size
    if not symtab:
        return 0
    symoff, nsyms, _stroff, _strsize = symtab
    esz = 16 if is64 else 12
    n = 0
    for i in range(nsyms):
        eoff = base + symoff + i * esz
        n_type = d[eoff + 4]
        if (n_type & N_EXT) and (n_type & N_PEXT) \
                and (n_type & N_TYPE_MASK) != N_UNDF:
            d[eoff + 4] = n_type & ~N_PEXT
            n += 1
    counts[0] += n
    return n


def _unhide_member(d, off, counts):
    """Process one archive member in the shared bytearray `d` at
    absolute offset `off` (thin or fat Mach-O); writes through."""
    magic_be = struct.unpack_from('>I', d, off)[0]
    if magic_be == FAT_MAGIC:
        nfat = struct.unpack_from('>I', d, off + 4)[0]
        for i in range(nfat):
            _ct, _cs, soff, _ssz = struct.unpack_from('>IIII', d, off + 8 + i * 20)
            unhide_slice(d, off + soff, counts)
    else:
        unhide_slice(d, off, counts)


def unhide_archive(path):
    """Rewrite one ar archive in place; return (members, unhidden)."""
    with open(path, 'rb') as fh:
        d = bytearray(fh.read())
    if d[:8] != b'!<arch>\n':
        return None  # not an archive (e.g. a real dylib) -- skip
    counts = [0]
    members = 0
    p = 8
    while p + 60 <= len(d):
        size_field = d[p + 48:p + 58].decode('ascii', 'replace').strip()
        try:
            size = int(size_field)
        except ValueError:
            break
        body_off = p + 60
        # Long-name members (#1/<len>) embed the name in the body;
        # the Mach-O starts after it.
        name = d[p:p + 16].decode('ascii', 'replace')
        moff = body_off
        if name.startswith('#1/'):
            try:
                moff = body_off + int(name[3:].strip())
            except ValueError:
                pass
        if moff + 4 <= body_off + size:
            _unhide_member(d, moff, counts)
        members += 1
        p = body_off + size + (size & 1)
    if counts[0]:
        with open(path, 'wb') as fh:
            fh.write(d)
    return members, counts[0]


def main():
    sysroot_lib, qtdir = sys.argv[1], sys.argv[2]
    targets = sorted(glob.glob(os.path.join(sysroot_lib, 'libwx*.a')))
    targets += sorted(glob.glob(os.path.join(qtdir, 'lib', 'lib*.a')))
    targets += sorted(glob.glob(os.path.join(qtdir, 'plugins', '*', 'lib*.a')))
    for fw in sorted(glob.glob(os.path.join(qtdir, 'lib', 'Qt*.framework'))):
        binary = os.path.join(fw, os.path.basename(fw)[:-len('.framework')])
        if os.path.isfile(binary):
            targets.append(binary)
    total = 0
    for path in targets:
        real = os.path.realpath(path)
        try:
            res = unhide_archive(real)
        except OSError as ex:
            print(f'UNHIDE {path}: ERROR {ex}')
            continue
        if res is None:
            print(f'UNHIDE {path}: not an ar archive, skipped')
            continue
        members, n = res
        total += n
        print(f'UNHIDE {path}: {members} members, {n} symbols unhidden')
    print(f'UNHIDE TOTAL: {total} symbols in {len(targets)} archives')
    if total == 0:
        print('UNHIDE FAILED: no private-extern symbols found -- the '
              'visibility model is wrong; stopping rather than '
              'building another unlaunchable IPA')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
