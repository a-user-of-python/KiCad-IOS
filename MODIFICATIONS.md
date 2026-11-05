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

4. **`src/osx/cocoa/utils_base.mm`** — 2026-11-04 —
   `patches/wx/0004-nsprocessinfo-for-wxqt.patch`.
   Extend the `wxHAS_NSPROCESSINFO` gate to `__WXQT__` so
   `wxGetOsVersion` uses `NSProcessInfo.operatingSystemVersion` under
   wxQt instead of falling back to Carbon's `Gestalt()`, which does not
   exist on iOS (CI run 41946411983). In-file notice included.

5. **`src/unix/utilsunx.cpp`** — 2026-11-04 —
   `patches/wx/0005-wxshutdown-no-system-ios.patch`.
   `wxShutdown()` called `system("init …")`; `system()` is marked
   unavailable in the iOS SDK. Extend the existing wxOSX-iPhone
   early-return branch to wxQt-on-Apple (CI run 41947031204). In-file
   notice included.

6. **`include/wx/osx/chkconf.h`** — 2026-11-04 —
   `patches/wx/0006-wxqt-ios-no-iphone-chkconf.patch`.
   Do not include the native wxOSX/iPhone port's `chkconf.h` when the
   toolkit is Qt. That header force-disables wxMenuBar, wxStatusBar,
   tooltips, combo boxes, scroll bars, drag-and-drop, MDI and more
   (because the native UIKit port lacks them); it is pulled in for ANY
   Darwin build, and under wxQt on iOS it made wxQt's own headers fail
   to compile (wxMenuBarBase incomplete; CI runs 41948131700 /
   41949832814, macro probe: wxUSE_MENUBAR 0 despite setup.h = 1). Qt
   on iOS provides all of these widgets. In-file notice included.

### wx patch 0007 — scrolwin-handler-access
- **File:** `include/wx/scrolwin.h` (wxWidgets 3.3.4)
- **Change:** The `HandleOn*` event-handler methods of `wxScrollHelperBase`
  are public again (one added `public:` label plus an in-file notice).
- **Why:** wx 3.3 moved these methods to `private`; in wx 3.2 — the version
  KiCad 10.0.1 is written and shipped against — they are public, and KiCad
  code calls them (e.g. `PANEL_PACKAGES_VIEW::OnInfoMouseWheel` calls
  `wxScrolledWindow::HandleOnMouseWheel`). Restores the wx 3.2 access
  semantics without changing any behaviour.

### KiCad 10.0.1

1. **`CMakeLists.txt`** — 2026-11-04 —
   `patches/kicad/0001-drop-webview-component.patch`.
   Drop `webview` from the `find_package(wxWidgets ... COMPONENTS ...)`
   call. wxQt has no wxWebView backend (wxUSE_WEBVIEW is forced OFF under
   wxQt), so no `libwx_*_webview` exists and the required-component check
   can never pass (minimal repro in the spike report). In-file notice
   included in the patch.

2. **`include/widgets/webview_panel.h`, `common/widgets/webview_panel.cpp`,
   `kicad/dialogs/dialog_template_selector.{h,cpp}`,
   `eeschema/widgets/panel_remote_symbol.{h,cpp}`** — 2026-11-04 —
   `patches/kicad/0002-webview-conditional.patch`.
   Make WEBVIEW_PANEL and its consumers conditional on `wxUSE_WEBVIEW`.
   wxQt has no wxWebView backend, so the types do not exist; upstream
   uses them unconditionally (this was the *only* KiCad-code error class
   in the desktop wxQt compile catalogue: ~100 diagnostics, one root
   cause). Without a backend, a stub panel with the same public API
   (minus `GetWebView()`) degrades template previews, PCM package pages
   and eeschema remote-symbol providers to a placeholder. In-file notice
   in webview_panel.h.

3. **`cmake/FindwxWidgets.cmake`** — 2026-11-04 —
   `patches/kicad/0003-findwxwidgets-dash-i-in-paths.patch`.
   Fix an upstream bug: the module stripped the `-I` prefix from
   wx-config's include list with a global `string(REPLACE "-I" "" ...)`,
   which also eats `-I` inside directory names. A checkout path
   containing `-I` — this repo's own name, `KiCad-IOS`, appears in every
   CI path — was corrupted to `KiCadOS`, and configure failed with
   "wxWidgets wx/version.h file not found". The patch strips `-I` only
   at list-element starts; behaviour is unchanged for all other paths.
   In-file notice included in the patch.

4. **`include/kiway.h`** — 2026-11-04 —
   `patches/kicad/0004-kiway-lib-env-var-by-os.patch`.
   LIB_ENV_VAR was selected by wx port macro (`__WXMAC__`); wxQt never
   defines it, so every TU including kiway.h hit `#error Platform
   support missing` (37 diagnostics — the largest class in the desktop
   wxQt catalogue). Select by OS (`__APPLE__`) instead. In-file notice
   included in the patch.

5. **`common/eda_doc.cpp`** — 2026-11-04 —
   `patches/kicad/0005-eda-doc-mimetype-guard.patch`.
   Guard the wxMimeTypesManager fallback table and lookup on
   `wxUSE_MIMETYPE`. wxQt has no mime-types backend (wx's only impl
   needs macOS LaunchServices/legacy UTI APIs, absent on iOS), so the
   port builds wx with wxUSE_MIMETYPE=OFF. Without it the function
   takes its existing "Unknown MIME type" path; PDFs (OpenPDF) are
   unaffected. In-file notice included in the patch.

6. **`libs/kiplatform/CMakeLists.txt`, `libs/kiplatform/port/wxqt/ui.cpp`
   (new), `libs/kiplatform/port/wxqt/webview.cpp` (new)** — 2026-11-04 —
   `patches/kicad/0006-kiplatform-wxqt-port.patch`.
   kiplatform had no `qt` branch, so no KIPLATFORM::UI/WEBVIEW
   implementation was built for wxQt and libkicommon failed to link
   (the last error class in the desktop catalogue). Adds a wx-generic
   Qt-backed port implementation; macOS/GTK-only workarounds are
   no-ops, cookie functions report failure (no wxWebView backend).
   In-file notices included in the patch.

### Build-system note — SWIG pinned to 4.2.1 (no source change)
- The CI stages build SWIG 4.2.1 from source instead of using Homebrew's
  SWIG (4.5.1 at time of writing): KiCad 10.0.1's SWIG interface files use
  `PyInt_*`/`PyString_*` aliases that SWIG >= 4.3 removed from its generated
  Python runtime prelude, so 4.5-generated `pcbnew_wrap.cxx` does not
  compile. No KiCad or wx source is modified for this.

### KiCad patch 0007 — kiplatform-no-os-apple-on-ios
- **File:** `libs/kiplatform/CMakeLists.txt`
- **Change:** The macOS OS-source block (`os/apple/*.mm` + Cocoa/AppKit/
  PDFKit/WebKit framework links) is skipped when `CMAKE_SYSTEM_NAME` is
  iOS, with an in-file notice.
- **Why:** Those sources are written against AppKit, which does not exist
  on iOS. Skipping them lets the iOS link catalogue show exactly which
  `KIPLATFORM` OS functions the editors reference; those will get
  UIKit/POSIX implementations under `os/ios/` in a follow-up patch.
  Desktop macOS builds are unaffected (system name is Darwin there).

### KiCad patch 0008 — bom-plugins-wxmac-guard
- **File:** `eeschema/bom_plugins.cpp`
- **Change:** The bundled-Python command block's guard changes from
  `__APPLE__` to `__WXMAC__`, with an in-file notice.
- **Why:** The block calls `PATHS::GetOSXKicadDataDir()`, which is only
  declared/defined under `__WXMAC__`. Under wxQt, `__APPLE__` is defined
  but `__WXMAC__` is not, so the call referenced a nonexistent member.
  Every other `GetOSX*` call site in the tree already guards with
  `__WXMAC__`; with this change wxQt builds use the generic
  `PYTHON_EXECUTABLE` BOM command, exactly as Linux builds do.

### Dependency-tree build fix — OCCT 7.8.1 vs FreeType >= 2.13 (in-stage, fetched tree only)
- **File:** `src/StdPrs/StdPrs_BRepFont.cxx` in the OCCT tree fetched by
  `scripts/stage-occ-ios.sh` (the repo ships no OCCT copy; the edit is
  applied to the freshly fetched tree on every CI run and asserted).
- **Change:** `const char* aTags = &anOutline->tags[...]` gains a
  `(const char*)` cast.
- **Why:** FreeType 2.13 changed `FT_Outline.tags` to `unsigned char*`;
  OCCT 7.8.1 predates that. `aTags` is only read through `FT_CURVE_TAG`
  bit masks, so the cast is semantics-preserving. This was the single
  compile error in OCCT's 5561 build steps for iOS. OCCT is LGPL-2.1 with
  the Open CASCADE exception; the change is disclosed here per its terms.

### KiCad patch 0009 — wx-static-on-ios
- **File:** `CMakeLists.txt`
- **Change:** The unconditional `--static=no` appended to
  `wxWidgets_CONFIG_OPTIONS` is skipped when `CMAKE_SYSTEM_NAME` is iOS.
- **Why:** The iOS wxWidgets build is static (`wxBUILD_SHARED=OFF`, the
  only sensible form for an iOS app bundle); with `--static=no`,
  wx-config reports no libraries and `find_package(wxWidgets)` fails at
  CMakeLists.txt:1102. Desktop builds are unaffected.

### KiCad patch 0010 — panel-plugins-ipc-guard
- **File:** `pcbnew/dialogs/panel_pcbnew_action_plugins.cpp`
- **Change:** The constructor's `Bind` and destructor's `Unbind` of
  `EDA_EVT_PLUGIN_AVAILABILITY_CHANGED` are wrapped in
  `#ifdef KICAD_IPC_API`, with an in-file notice.
- **Why:** That event is defined in `common/api/api_plugin_manager.cpp`,
  which is compiled into kicommon only when the IPC API is enabled.
  Eeschema and `pcb_edit_frame` guard their uses of it; this panel did
  not — an upstream inconsistency that stays invisible in upstream builds
  (IPC always on there) but fails the `_pcbnew.kiface` link in IPC-off
  builds such as this port. Behaviour with IPC on is unchanged.

### wx patch 0008 — glcanvas-opengles-wxqt-ios
- **File:** `build/cmake/init.cmake` (wxWidgets 3.3.4)
- **Change:** The OpenGL setup branch that special-cases the iPhone port
  (`WXOSX_IPHONE`: OpenGLES/QuartzCore/GLKit frameworks, no desktop GL
  search) is also taken for wxQt when `CMAKE_SYSTEM_NAME` is iOS.
- **Why:** For wxQt-iOS, wx fell through to `find_package(OpenGL)`, which
  fails on iOS (only OpenGLES exists), so wx silently disabled
  wxGLCanvas and never built the `gl` library — but KiCad requires the
  wx `gl` component. wxQt's glcanvas implementation itself is pure Qt
  (QOpenGLContext/QOpenGLWidget) and works with a GLES context. The
  stages additionally shim `<GL/gl.h>` to the OpenGLES ES3 headers for
  the wx/KiCad compiles (stage-level include dir, no source change).

### KiCad patch 0011 — kiplatform-no-os-unix-on-ios
- **File:** `libs/kiplatform/CMakeLists.txt`
- **Change:** The `os/unix` branch is skipped when `CMAKE_SYSTEM_NAME`
  is iOS (one condition plus an in-file notice).
- **Why:** CMake reports iOS as `UNIX`, so the iOS configure took the
  Linux branch, which hard-requires libsecret-1 and Poppler (GNOME /
  Linux printing facilities that do not exist on iOS) and would compile
  the Linux OS sources. Together with patch 0007 (which skips the macOS
  branch), iOS now selects no OS source set; the link catalogue will
  enumerate exactly which `KIPLATFORM` OS functions need iOS
  implementations under `os/ios/`.
