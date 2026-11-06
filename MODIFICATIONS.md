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

### KiCad patch 0012 — nanodbc-iodbc-wide-traits-guard
- **File:** `thirdparty/nanodbc/nanodbc/nanodbc.cpp` (KiCad's bundled
  nanodbc, which carries a KiCad-specific addition)
- **Change:** KiCad's Apple/Clang≥17 `char_traits` shim is skipped when
  `NANODBC_USE_IODBC_WIDE_STRINGS` is defined (condition plus in-file
  notice).
- **Why:** The shim defines `std::char_traits<NANODBC_SQLCHAR>` for
  platforms where libc++ dropped the generic template. With iODBC wide
  strings — the only ODBC configuration on iOS — `NANODBC_SQLCHAR` is
  `SQLWCHAR`, i.e. `wchar_t`, and libc++ still provides the standard
  `char_traits<wchar_t>`, so the shim is a redefinition error
  (iOS build run 42014900926, the only error in 85 attempted steps).
  The shim remains in place for the non-wide `unsigned char`
  configuration it was written for (e.g. the desktop unixODBC build).

### KiCad patch 0013 — kiplatform-ios-os-layer
- **Files:** New directory `libs/kiplatform/os/ios/` (app.cpp,
  drivers.cpp, environment.mm, io.cpp, policy.cpp, printing.cpp,
  secrets.cpp, sysinfo.cpp) + one block in
  `libs/kiplatform/CMakeLists.txt` selecting them (with Security and
  CFNetwork frameworks) when `CMAKE_SYSTEM_NAME` is iOS.
- **Why:** With the macOS and Linux OS branches excluded on iOS
  (patches 0007/0011), the libkicommon link enumerated exactly the
  missing OS surface (iOS build run 42046911806: 12 undefined
  `KIPLATFORM::` functions). This patch implements that surface — plus
  the rest of the functions the same files define, which the manager
  and editor links will require — by porting KiCad's own os/apple and
  os/unix implementations to the APIs iOS provides:
  - `SECRETS`: the macOS Keychain implementation verbatim — the
    Security framework C API (SecItem*) is identical on iOS.
  - `ENV` paths: wxStandardPaths (wxQt → QStandardPaths) and
    NSFileManager for the caches directory.
  - `ENV::GetSystemProxyConfig`: the macOS implementation's CFNetwork
    core (CFNetworkCopySystemProxySettings /
    CFNetworkCopyProxiesForURL / PAC evaluation via NSURLSession) —
    all available on iOS; wxCFStringRef conversions replaced with
    plain CFString helpers since wxCFStringRef is wxOSX-only.
  - `IO`: POSIX implementations (the macOS SeqFOpen, stat/chmod
    permission helpers, fnmatch TimestampDir, mmap MAPPED_FILE) —
    all plain POSIX on iOS.
  - `APP`/`POLICY`: the macOS stub semantics.
  - Honest platform gaps, documented in-file: `ENV::MoveToTrash`
    returns false (iOS has no Trash API for apps; KiCad's callers fall
    back to permanent deletion) and `PRINTING::PrintPDF` returns
    PRINT_RESULT::UNSUPPORTED (iOS printing is the asynchronous UIKit
    print controller, which does not fit this synchronous API).

### Dependency note — libtess2 + GLU tessellator adapter (no KiCad source change)
- iOS has no GLU; KiCad's OpenGL GAL uses the GLU tessellator
  (gluNewTess/gluTess*) for polygon fills. The deps stage builds
  **libtess2** (zlib licence) for iOS, with one disclosed fetched-tree
  edit: `typedef float TESSreal;` → `typedef double TESSreal;` in its
  tesselator.h, so tessellated vertices keep GLU's GLdouble precision.
- The spike repo's `glu/` directory carries a small adapter
  (glu.h + glu_tess_adapter.c, GPLv3) exposing the GLU tessellator
  subset KiCad names, implemented over libtess2: contours are buffered
  and tessellated at gluTessEndPolygon, and output vertices are
  replayed through the registered VERTEX_DATA callback in triangle
  order (the same stream GLU produces once an EDGE_FLAG callback is
  registered, which is how KiCad configures it). Self-intersections
  are computed inside libtess2's sweep, so COMBINE_DATA is accepted
  but never invoked. KiCad sources are untouched.

- `patches/kicad/0014-findocc-tkvcaf-static.patch` — FindOCC: add TKVCAF
  to the searched OCC toolkits. The OCE 3D plugin uses TPrsStd drivers;
  with a shared OCC they resolve transitively, with the static iOS OCC
  they must be named. (Found in CI run 42065865033: 4 undefined
  TPrsStd_* symbols in libs3d_plugin_oce.so.)
- `patches/kicad/0015-wxfilename-includes.patch` — add the missing
  `<wx/filename.h>` include to pagelayout_editor's design_inspector.cpp
  and gerbview's dialog_draw_layers_settings.cpp. Both use wxFileName;
  wxMac/wxGTK headers provide it transitively, wxQt does not. (CI run
  42065865033.)
- Correction to patch 0013: the iOS `PRINTING::PrintPDF` definition
  originally carried a second `bool fit_to_page` parameter that the
  KiCad 10.0.1 header does not declare (it came from a newer KiCad's
  macOS implementation); the definition now matches the header exactly.
  (CI run 42065865033: undefined PrintPDF in _eeschema.kiface.)
- GLU adapter extended: `glu/glu_quadric_adapter.c` implements the GLU
  quadric subset KiCad's 3D viewer uses (gluNewQuadric/gluDeleteQuadric/
  gluQuadricNormals/gluQuadricDrawStyle/gluSphere/gluCylinder/gluDisk/
  gluPartialDisk) plus gluPerspective, emitted as triangles through
  KiCad's own glad pointers with a null-guard (no legacy GL entry
  points exist under OpenGL ES, so the calls no-op there rather than
  crash). Same licence and disclosure terms as the tessellator adapter.
- Build-flag note: the iOS stage defines NANODBC_USE_IODBC_WIDE_STRINGS
  globally. Bundled nanodbc's CMake sets it directory-locally (iODBC
  only), so on iOS the library was compiled with the wide-string API
  while KiCad's consumers were not — eeschema referenced u16string
  nanodbc overloads the library does not provide. A global define makes
  the API uniform. No source change. (CI run 42065865033.)

- `patches/kicad/0016-grid-checkbox-internal-linkage.patch` — KiCad's
  grid_checkbox.cpp carries a verbatim copy of wx's private
  wxGetContentRect (the file says so itself). Give the copy internal
  linkage: with a static wxWidgets (iOS), wx's own copy inside
  libwx_core collides with it; shared wx never exports the symbol.
  (CI run 42075801437: duplicate symbol in _eeschema/_pcbnew links.)
- `patches/kicad/0017-nanosvg-missing-statics.patch` — give
  nsvg__parseXML and nsvg__colors internal linkage in KiCad's bundled
  nanosvg. Every other nsvg__ helper in the file is already `static`;
  these two were missed. wxWidgets bundles its own nanosvg (bmpsvg);
  with static wx the two global definitions collide in the kiface
  links. (CI runs 42075801437, 42105125045. An earlier attempt used
  -fvisibility=hidden on the nanosvg target; ld64 still reported the
  duplicates, so the fix moved to the source.)

- `patches/kicad/0018-kicad-exe-qt-plugin-items.patch` — kicad
  executable only: apply the stage-provided KICAD_IOS_PLUGIN_ITEMS
  link options (Qt static plugin import object + force-loaded
  libqios + image-format plugin archives + their frameworks). Qt for
  iOS is fully static, so the plugins register only if the host
  executable imports them; scoping this to the manager executable
  keeps build tools (lemon) and standalone utilities out of the Qt
  plugin closure. (CI run 42086627018.)
- `patches/kicad/0019-kicad-exe-ios-entry-point.patch` — kicad
  executable only, iOS: add `-Wl,-e,_qt_main_wrapper` so dyld enters
  the manager through Qt's iOS entry point. qt_main_wrapper (in the
  QIOS plugin the executable already force-loads, patch 0018) runs
  UIApplicationMain with Qt's application delegate, which then calls
  the executable's main (wxEntry) with a UIApplication in existence.
  Qt's EntryPointPrivate module applies this same option to apps
  linking Qt6::Core as a CMake target; KiCad links Qt as bare
  framework paths, so it never arrived. Without it the app aborted
  on launch inside QIOSIntegration's constructor ("You are creating
  QApplication before calling UIApplicationMain") — device crash
  report captured with KiCad-Spike-v2.ipa, 2026-11-05. No behaviour
  change on other platforms (iOS-only block).
- `patches/kicad/0020-wx-qt-single-instance-link.patch` — top-level
  CMakeLists, iOS only: withhold the wx/Qt library list from the
  library and module targets and give it to the executable targets
  instead. wxWidgets and Qt are static archives in this port, so
  every KiCad image that linked them carried its own copy of their
  statics: the shipped v3 binaries each defined their own
  `wxAppConsoleBase::ms_appInstance` (verified in the executable,
  libkicommon, libkigal and _eeschema.kiface). The manager's
  wxEntry set the executable's copy, libkicommon's
  `PGM_BASE::App()` read its own still-null copy, and
  `PGM_KICAD::OnPgmInit` dereferenced the null wxApp pointer at
  +156 (device crash report 2026-11-05: SIGSEGV, fault address
  0x127 = `&wxApp::m_appDisplayName` inside a null wxApp; the entry
  chain of patch 0019 worked — the stack reached OnInit/OnPgmInit).
  With the patch, library/module targets leave their wx/Qt symbols
  undefined and the stage script adds `-undefined dynamic_lookup`
  to the shared/module link flags, so they bind at load time to the
  single copies in the manager executable, which the same stage
  links with `-Wl,-export_dynamic`. One wx/Qt state per process,
  as in a desktop build with shared wx. No behaviour change on
  other platforms (both the stash/clear and the relink are inside
  `CMAKE_SYSTEM_NAME STREQUAL "iOS"` blocks). Two link-detail
  iterations during the v4 round, both recorded here: the relink
  must use the plain `target_link_libraries` signature (CMake
  forbids mixing it with the keyword signature KiCad itself uses;
  run 42153711965), and the relink list must include the six
  single-top editor executables (eeschema, pcbnew, gerbview,
  pl_editor, pcb_calculator, bitmap2component), which are separate
  executables and otherwise fail with undefined wx symbols
  (run 42155182542). Those standalone apps are not part of the
  spike IPA; they are relinked only to keep the full build green.
- `patches/kicad/0021-wx-force-load-and-export.patch` — top-level
  CMakeLists, iOS only: amend patch 0020's executable relink to
  (a) `-force_load` every wx component archive into the executable
  targets and (b) add `-Wl,-exported_symbol,_*` to those targets.
  Device evidence (KiCad-Spike-v4.ipa, crash report 2026-11-06):
  with patch 0020 alone the app died in `dyld4::prepare`, before
  any app code ran — "symbol not found in flat namespace
  `__ZN10wxGLCanvas11SwapBuffersEv`", referenced by libkigal.
  Two distinct holes, both consequences of the dynamic_lookup
  arrangement: static-archive extraction is demand-driven by the
  executable's own references, so wx objects the manager never
  references (the whole gl component among them) were never
  extracted; and the wx/Qt globals that were extracted landed in
  the executable almost entirely as private externs (n_type
  0x1e — of ~82k defined globals only ~504 were true externals),
  which dyld cannot bind from other images. `-export_dynamic`
  does not fix that: it only preserves globals against LTO. A
  bundle-wide symbol-closure audit of the shipped v4 IPA
  (LC_SYMTAB of every image; every undefined symbol must be
  defined by a shipped image or a system library) counted 3,351
  unresolvable symbols, all of them wx — dyld had simply
  reported the first. `-force_load` extracts every object of
  each wx component archive; `-exported_symbol '_*'` promotes
  the executables' globals to real exports, restoring the flat
  namespace the libraries resolve against. The Qt framework
  binaries stay demand-driven: no shipped library references a
  Qt symbol the executables do not already pull in, and a wx
  object newly extracted by `-force_load` pulls the Qt symbols
  it needs from the Qt archives in the same link. The stage
  script additionally links a 3-symbol probe with these exact
  options against the real archives before the build and stops
  if they do not export, and counts the built executable's
  defined externals after the build. No behaviour change on
  other platforms (iOS-only blocks, like patch 0020).
- `patches/kicad/0022-kicad-only-force-load-export.patch` —
  top-level CMakeLists, iOS only: narrow patch 0021's
  force_load/export options to the `kicad` manager target only.
  Evidence (CI run 42210442013, the first v5 candidate): with
  the options on every executable, `idfcyl` and `idfrect`
  failed to link — force-loading all of wx drags in the full
  Qt closure (QtGui's harfbuzz objects need Qt's bundled
  harfbuzz archive), which those minimal tools do not link.
  The standalone executables are separate processes that
  nothing dlopens against; they keep patch 0020's plain relink
  (green in v4). The same run proved the second correction
  this round is built on: `-exported_symbol '_*'` DID reach
  ld64 (visible, quoted, in the link lines) but does not
  promote the archives' private-extern globals — the candidate
  manager still exported only 725 symbols, with
  `wxGLCanvas::SwapBuffers` present (force_load worked) but
  private. An export list only selects among symbols that are
  exportable to begin with; wx/Qt's hidden visibility is baked
  into their object files as N_PEXT. The stage script's
  unhide step (below) removes it at the source.
- Build tooling (this repo's own
  `scripts/unhide_archive_symbols.py`, not an upstream file) —
  2026-11-06: before the KiCad configure, clear the N_PEXT
  (private-extern) bit on every defined external symbol in the
  wx component archives and the Qt kit's archives/framework
  binaries, in place. wx and Qt are compiled with hidden
  visibility; under patch 0020's arrangement their globals must
  be exported by the manager executable for the
  `-undefined dynamic_lookup` libraries to bind at load time,
  and N_PEXT is exactly what stops ld64 exporting them (v4:
  ~82k defined globals in the executable, ~504 true externals;
  bundle symbol-closure audit: 3,351 unresolvable wx symbols).
  Only n_type bytes change — member layout, symbol names and
  the archive index are untouched; the step is idempotent,
  prints per-archive counts, and fails the stage if it unhides
  nothing. Third-party sysroot libraries are not touched:
  their symbols already resolve inside their home images.
  This rewrites intermediate build artifacts, not upstream
  sources; it is recorded here for transparency like every
  other change that shapes the shipped binary.
- Build tooling (this repo's own `scripts/package_ios.py`, not an
  upstream file) — 2026-11-05: (1) the dependency walk no longer
  skips `@rpath/...` loads; they are resolved against the sysroot
  and the Qt kit and embedded (with the libpython3.13.a → Python
  name alias; framework-style loads whose bundle exists nowhere are
  embedded as the bare binary), and anything still unresolvable is
  printed as UNRESOLVED in the stage log. The old skip is what left
  libz.1.dylib, libzstd.1.dylib and Python out of the v1 package.
  (2) The Contents/Frameworks + Contents/PlugIns mirror of the
  whole Frameworks tree is removed: it doubled the v1 bundle to
  491 MB and the result failed signing. Restore it only if a
  device run proves an editor actually searches there.
- `patches/kicad/0023-ios-qt-resource-registration-and-rhi-env.patch`
  — kicad executable only, iOS: (a) `kicad/CMakeLists.txt` defines
  `KICAD_IOS_PORT` for the manager target; (b) under that define,
  `kicad/kicad.cpp` gains a file-scope startup object whose
  constructor runs at executable load, before `main`, and (1)
  declares and calls `qInitResources_gui_shaders()`,
  `qInitResources_qstyle1()` and `qInitResources_qstyle_fusion()` —
  exactly what Qt's `Q_INIT_RESOURCE` macro expands to (the macro
  itself needs Qt headers, which that translation unit does not
  include). Device evidence (KiCad-Spike-v5.ipa, crash report
  2026-11-06): the app passed dyld, entered through
  `qt_main_wrapper`, and died ~0.15 s after launch in
  `QRhiMetal::setGraphicsPipeline` (fault address 0x368 = a member
  offset from a null base) on the first window paint
  (`QWidgetWindow::handleExposeEvent` →
  `QBackingStoreDefaultCompositor::flush`). Root cause, proven by
  binary inspection: Qt for iOS is statically linked and KiCad
  links Qt as bare paths rather than CMake targets, so the
  resource-initialiser objects in the Qt archives were never
  extracted — the v5 executable embeds zero `.qsb` resource
  entries and none of these init symbols, while the FEBio Studio
  executable (same Qt 6.9.3 build, CMake-linked, renders fine on
  the same iPad) contains `qInitResources_gui_shaders` and both
  backingstorecompose shaders. Without the `gui_shaders` resource,
  the compositor's precompiled shaders
  (`:/qt-project.org/gui/painting/shaders/backingstorecompose.*.qsb`)
  do not exist, its Metal graphics pipelines fail to create (a
  `qWarning`, invisible on iOS), the pipeline stays null, and the
  first flush dereferences it. On iOS every widget window flushes
  through `QRhiBackingStore` and that compositor, so no window can
  paint. The two QtWidgets style resources are the same trap in
  the same archives and are registered alongside. The startup
  constructor also (2) sets `QT_WIDGETS_RHI=0` before QApplication
  exists — opting widget top-levels out of RHI-composited flushing
  wherever Qt evaluates that choice
  (`QBackingStoreRhiSupport`/`QWidgetPrivate::q_evaluateRhiConfig`);
  belt-and-braces next to the resource fix, since KiCad's canvases
  in this port are Cairo/software — and (3) sets
  `QT_LOGGING_RULES=qt.rhi.*=true;qt.qpa.*=true` so the next launch
  failure carries its reason in the log instead of a bare fault
  address. No behaviour change on other platforms (the C++ is
  behind `KICAD_IOS_PORT`, defined only by the iOS-only CMake
  block).
