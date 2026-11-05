# MODIFICATIONS — GPL §5 change log

Per §5 of the GNU General Public License, modified files must carry prominent
notices stating that they were changed and the date of the change. This file is
the running index of **every** modification this port makes to upstream files.
Each modified upstream file also carries an in-file notice of the form:

```text
// [KiCad-IOS port] Modified <YYYY-MM-DD> for iOS: <what changed and why>.
// This file is part of KiCad, GPLv3-or-later; see the upstream header above.
```

## Upstream baselines

| Component | Source | Baseline |
|---|---|---|
| KiCad | gitlab.com/kicad/code/kicad | tag `10.0.1`, commit `2db9e5a72b7cf1e71bb8dff5257a88d4b41f812f` |
| wxWidgets | github.com/wxWidgets/wxWidgets | tag `v3.3.4` — see note below |
| wxWidgets audited | github.com/wxWidgets/wxWidgets `v3.2.8`; github.com/KiCad/wxWidgets `master` | 3.2.8's wxQt is Qt5-only; the KiCad fork's master is wx 3.1.1 (2017) and is not KiCad 10's wx source |

## Changes

### wxWidgets v3.3.4

1. **`build/cmake/toolkit.cmake`** — 2026-11-04 —
   `patches/wx/0001-filter-qt-test-genex-definitions.patch`.
   Filter compile definitions containing `TARGET_PROPERTY` out of the set wx
   exports via wx-config. Qt6::Test's exported testcase definitions
   (`QT_TESTCASE_BUILDDIR=...` generator expressions) otherwise leak into
   every wx consumer; KiCad's CMake generation then fails in pcbnew's SWIG
   custom command ("$<TARGET_PROPERTY:prop> may only be used with binary
   targets"). In-file notice included in the patch.

2. **`include/wx/osx/core/private.h`** — 2026-11-04 —
   `patches/wx/0002-no-carbon-under-wxqt.patch`.
   Skip the `<Carbon/Carbon.h>` include and the legacy Carbon helper
   declarations when building the Qt port. Carbon does not exist in the
   iOS SDK; under wxQt the helpers' implementations (wxOSX GUI sources)
   are never built, but wxBase's CoreFoundation sources include this
   header and failed with "'Carbon/Carbon.h' file not found"
   (CI run 41944060930). In-file notice included in the patch.

3. **`include/wx/osx/private.h`** — 2026-11-04 —
   `patches/wx/0003-osx-private-header-wxqt-branch.patch`.
   Add a `__WXQT__` branch to the private-header dispatch. Without it,
   wxQt (which defines neither `__WXOSX_IPHONE__` nor `__WXOSX_COCOA__`)
   falls through to the wxBase/macOS branch that includes
   `<ApplicationServices/ApplicationServices.h>` — absent from the iOS
   SDK (CI run 41944760546). In-file notice included in the patch.

### KiCad 10.0.1

1. **`CMakeLists.txt`** — 2026-11-04 —
   `patches/kicad/0001-drop-webview-component.patch`.
   Drop `webview` from the `find_package(wxWidgets ... COMPONENTS ...)`
   call. wxQt has no wxWebView backend (wxUSE_WEBVIEW is forced OFF under
   wxQt), so no `libwx_*_webview` exists and the required-component check
   can never pass (minimal repro in the spike report). In-file notice
   included in the patch.
