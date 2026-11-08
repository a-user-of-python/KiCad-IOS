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
- `patches/kicad/0024-ios-complete-qt-resources-and-stock-data.patch`
  — kicad executable only, iOS, extends the patch-0023 startup
  object in `kicad/kicad.cpp` (still behind `KICAD_IOS_PORT`):
  (1) Qt resource registration is completed to the FULL bundle set
  of the Qt modules the executable links. A census of the Qt 6.9.3
  iOS kit (the same aqt archives CI installs; inventory from
  `lib/objects-Release/*/qrc_*_init.cpp.o` plus framework symbol
  tables, compared against the v6 executable's LC_SYMTAB) shows
  the linked modules carry exactly eight bundles — QtGui
  {gui_shaders, qpdf}, QtWidgets {qstyle, qstyle1, qstyle_fusion,
  qmessagebox}, QtPrintSupport {qprintdialog, qprintdialog1} — of
  which the v6 executable contained seven: `qprintdialog1` was
  never extracted, the same silent-extraction hole as v5's
  gui_shaders, one level down. All eight init functions are now
  declared and called explicitly, so no bundle's presence depends
  on an incidental reference again. The census also proved there
  is no `rhi_shaders` bundle in this kit (QtGui ships exactly two
  resource objects) and that PNG needs no plugin in 6.9.3 (the
  handler is built into QtGui; the kit's imageformats are only
  gif/ico/jpeg/svg). (2) Stock data: KiCad 10's BITMAP_STORE is
  file-based — it opens `PATHS::GetStockDataPath() +
  "/resources/images.tar.gz"` and reads every icon's PNG data
  from it; the failure mode is graceful (each icon becomes the
  built-in "image not found" placeholder), so the v1–v6 bundles,
  which ship no stock data, would open a manager window whose
  every icon is a placeholder. `GetStockDataPath()` consults the
  `KICAD_STOCK_DATA_HOME` environment variable before any
  platform branch (verified compiled into the shipped
  libkicommon), so the startup constructor now sets it — only if
  unset — to `<bundle>/share`, derived from
  `_NSGetExecutablePath` (flat layout: the bundle root is the
  executable's directory). Companion change, not in this patch:
  `scripts/package_ios.py` installs the build's own
  `$BLD/resources/images.tar.gz` at `KiCad.app/share/resources/`
  and fails the package if the archive is missing.

- `patches/kicad/0025-ios-python-home-stdlib.patch` — kicad
  executable only, iOS, extends the patch-0023/0024 startup
  constructor. Round 6 (KiCad-Spike-v8) exists because v7 — which
  signed, installed, and opened on device — then aborted at
  manager startup with KiCad's exception dialog "Failed to import
  encodings module": `PGM_BASE::InitPgm` constructs the embedded
  interpreter unconditionally (`std::make_unique<SCRIPTING>()`),
  and CPython initialisation imports the stdlib `encodings`
  package, which the bundle did not ship. The startup
  constructor now also sets (before `QApplication` exists):
  `PYTHONHOME=<bundle>/python`, but only if unset;
  `PYTHONPATH=<bundle>/python/lib/python3.13/site-packages` if
  unset/empty; and `PYTHONDONTWRITEBYTECODE=1` unconditionally.
  Why the environment works here: KiCad's own
  `scriptingSetup()` sets the Python home itself only on the
  Windows/MSVC branch (`Py_SetPythonHome`); the generic-unix
  branch this port compiles does not touch the home and only
  manages `PYTHONPATH` — recomputing it from an install path
  that does not exist on device, but PREPENDING any pre-existing
  value, so the startup object's entries survive. CPython
  resolves the stdlib to `$PYTHONHOME/lib/python3.13`, finds
  `encodings` there, and the `lib-dynload` extension modules
  load against the shipped interpreter image. Companion
  packaging changes (this repo's scripts, not upstream files):
  `stage-python-ios.sh` stages the BeeWare standard-library
  tree + the device slice's `lib-dynload` modules into the
  sysroot; `scripts/probe_dynload.py` verifies every extension
  module's undefined symbols against the iPhoneOS SDK stubs and
  the interpreter's exports before packaging; and
  `scripts/package_ios.py` installs the stdlib under
  `KiCad.app/python/` (hard-failing if `encodings` is absent;
  trimming only provably-dead weight: the CPython test suite,
  tkinter/idlelib/turtledemo — no `_tkinter` module exists for
  this platform — the test-only extension modules, and any
  module the probe proves unloadable), mirrors the build's own
  Python destination (site-packages: `pcbnew.py`, `_pcbnew.so`)
  and KiCad's stock scripting plugins into the bundle, bundles
  two official vendor PCM packages fetched and sha256-verified
  at package time (PCBWay Plug-in for KiCad 1.0.5, MIT;
  Fabrication Toolkit 5.3.0 for JLCPCB, Apache-2.0 — each with
  its vendor LICENSE included beside the code; the packages
  themselves are not vendored into this repository), and turns
  on file sharing in the generated Info.plist
  (`UIFileSharingEnabled`,
  `LSSupportsOpeningDocumentsInPlace`).

- Build-configuration change, no upstream source change — wx is
  built against the system libpng/zlib/expat (launch fix round 7,
  KiCad-Spike-v9). Round 7 exists because v8 — the first build whose
  Python initialisation passed on device — aborted ~0.74 s after
  launch inside `KICAD_MANAGER_FRAME` construction with a libmalloc
  bug report ("pointer being freed was not allocated") in
  `wx_png_destroy_read_struct` during the first `BITMAP_STORE` icon
  load. Binary census of the shipped v8 executable: it contained
  TWO libpng implementations — wx's bundled 1.6.59 (`wx_png_*`,
  372 defined symbols, the copy `wxPNGHandler` uses) and the deps
  sysroot's 1.6.43 (the copy everything else links) — whose
  `png_struct` layouts measurably diverge (the destroy routines free
  the same fields at offsets drifted by +0x08..+0x38; the IDAT
  staging buffer sits at +0x488 in the wx copy, +0x458 in the
  sysroot copy), all exported into one flat namespace
  (`-exported_symbol '_*'`), plus wx's bundled zlib beside the
  sysroot zlib. Root cause in this repo's own stage scripts:
  `scripts/stage-wx-ios.sh` configured wx with
  `CMAKE_PREFIX_PATH` naming only the Qt kit, so wx's
  `find_package(PNG)` could not see the deps sysroot, and wx's
  `build/cmake/lib/png.cmake` silently forced the bundled copy
  (zlib/expat, "sys" by default on Apple, fell back the same way).
  The fix is confined to this repo's build tooling:
  `stage-wx-ios.sh` now refuses to configure wx when the sysroot
  libpng/zlib/expat are absent (fail closed instead of the silent
  bundled fallback), puts the sysroot on wx's find path with
  explicit PNG/ZLIB/EXPAT library hints, forces
  `wxUSE_LIBPNG=sys` / `wxUSE_ZLIB=sys` / `wxUSE_EXPAT=sys`, and
  fails the stage if a bundled `libwxpng`/`libwxzlib` archive is
  produced anyway; the `wx-ios` CI job now restores the deps
  sysroot before configuring (it previously restored nothing); and
  the link probe in `scripts/stage-kicad-ios.sh` links wx's bundled
  third-party archives only when they exist. wx's bundled
  jpeg/tiff/webp archives remain (the sysroot ships no equivalents
  and they are not on the PNG icon path). Resulting invariant,
  checked on the shipped file before delivery: no image in the
  bundle defines any `wx_png_*` symbol, exactly one libpng version
  string exists bundle-wide, and the executable defines the plain
  `png_*` entry points the wx handler now binds. Upstream KiCad and
  wx sources are untouched by this round.

### KiCad patch 0026 — ios-wizard-nav-buttons (launch fix round 8, KiCad-Spike-v10)

**`common/startwizard/startwizard.cpp` + `common/CMakeLists.txt`** —
2026-11-06 — `patches/kicad/0026-ios-wizard-nav-buttons.patch`.
Device verdict for v9: the app runs and KiCad's genuine first-run
wizard renders, but the wizard's Back/Next/Cancel row is absent —
the user is stuck on page 1 ("just are not there", device report).
The generic wxWizard creates the three buttons unconditionally
(wxWizard::DoCreateControls), the shipped v9 binary contains the
creation code and the button labels, and a host build of the same
wxWidgets 3.3.4 wxQt sources against desktop Qt, driven through
KiCad's exact creation order (manager frame created hidden at
775×-1 DIP, wizard run before the frame is shown), lays the row
out correctly (80×25, visible, inside the client area) — so the
loss is specific to this port's startup environment, where two wx
mechanisms can each remove the row: wxDialog layout adaptation
(reparents all controls into a scrolled window and rebuilds the
dialog's sizer if the display metrics it samples are degenerate,
leaving the row below the scrolled fold) and any first layout
computed against a client size the dialog does not keep (a Qt
control laid out at zero size stays hidden). The patch, gated on
KICAD_IOS_PORT (the define patch 0023 sets for the kicad target;
this patch sets it for the common target the same way), disables
layout adaptation for the wizard dialog — a no-op on any healthy
display, where the adapter's MustScroll test is already 0 — and,
via wxEvtHandler::CallAfter queued before RunWizard, re-shows the
navigation buttons and re-runs the sizer layout once the modal
loop is running at the dialog's real geometry (verified on the
host wxQt build to fire inside RunWizard and to leave healthy
geometry unchanged). No upstream logic is altered; the block is
compiled only for this port.

**Packaging (no upstream change):** `scripts/package_ios.py` now
writes `UIUserInterfaceStyle = Light` into the app Info.plist.
Desktop KiCad is a light-theme application that mixes wx system
colours with hardcoded light colours; with no key (v9) the app
followed the device appearance and rendered the wizard white-on-
black on a dark-mode device. Verified against the Qt 6.9.3
sources: UIKit resolves each window's trait collection from the
key, QIOSTheme::colorScheme() derives the Qt colour scheme from
the window's userInterfaceStyle, the iOS system palette's dynamic
UIColors resolve to their light variants, the Fusion style (the
iOS theme's StyleNames hint) paints from that palette, and wxQt
maps wxSYS_COLOUR_* from the same palette.

### KiCad patch 0027 — ios-kiface-frameworks-search (launch fix round 9, KiCad-Spike-v11)

**`common/kiway.cpp`** — 2026-11-07 —
`patches/kicad/0027-ios-kiface-frameworks-search.patch`.
Device verdict for v10: the manager stands and the wizard completes,
but KiCad cannot load any editor kiface — the error names
`<bundle>/KiCad.app/_eeschema.kiface`. In 10.0.1,
`KIWAY::dso_search_path()` builds the kiface path from
`wxStandardPaths::Get().GetExecutablePath()` under
`#ifndef __WXMAC__` (wxQt never defines `__WXMAC__`): the executable
directory, i.e. the bundle root. The port packages the kifaces in
`Frameworks/`, where every other binary lives and where dyld
resolves their `@rpath` dependencies, so nothing loaded — the
manager's own startup preload (`PreloadAllLibraries`, which loads
the schematic and PCB kifaces as soon as the frame stands) raised
the error before any user action, and every editor launch would
have failed the same way, since all kiface loads funnel through
this one function. The patch, gated on `KICAD_IOS_PORT` (already
defined for the `common` target by patch 0026), appends the
`Frameworks` directory to the search path, so the dlopen target
becomes `<exe dir>/Frameworks/_<tool>.kiface` — the packaged
location. Desktop behaviour is untouched (the added block compiles
only for this port), and no duplicate kiface copies are shipped.

### KiCad patch 0028 — ios-stock-eda-path (launch fix round 9, KiCad-Spike-v11)

**`common/paths.cpp`** — 2026-11-07 —
`patches/kicad/0028-ios-stock-eda-path.patch`.
Device verdict for v10: first-run setup "couldn't reach the default
libraries". Two causes. The bundle shipped no stock content (fixed
by the packaging change below). And the paths themselves were
broken: `LIBRARY_MANAGER::StockTablePath()` builds the stock
sym-lib-table / fp-lib-table paths from
`PATHS::GetStockTemplatesPath()`, which roots in
`PATHS::GetStockEDALibraryPath()`; its generic branch returns the
compiled-in `KICAD_LIBRARY_DATA`, which KiCad's CMake only sets
under `if(NOT APPLE)` — on Apple it is empty (verified: the shipped
v10 binaries contain no `share/kicad` path, and the baked
`KICAD_DATA` string is a macOS install path that does not exist in
the sandbox). Every stock path — symbols, footprints, templates,
design blocks, 3D models, and the `KICAD10_*_DIR` environment
defaults derived from them — therefore resolved relative to the
process working directory. The patch mirrors the existing Windows
branch: under `KICAD_IOS_PORT`, the stock EDA library root is
`GetStockDataPath()`, which patch 0024 already resolves to
`<bundle>/share` via `KICAD_STOCK_DATA_HOME`. Compiled only for
this port.

### KiCad patch 0029 — ios-floating-window-controls-hook (launch fix round 9, KiCad-Spike-v11)

**`kicad/kicad.cpp`** — 2026-11-07 —
`patches/kicad/0029-ios-floating-window-controls-hook.patch`.
Adds an `extern` declaration for the wxQt port's
`wxQtIOSInstallFloatingWindowControls()` (wx patch 0009) and calls
it from `APP_KICAD::OnInit()` under `KICAD_IOS_PORT`, right after
platform initialisation succeeds and before program initialisation
creates the first windows — so the floating Close/Minimize control
bar also covers the first-run wizard. No upstream logic is
altered; the call compiles only for this port.

### KiCad patch 0030 — ios-manager-execute-inprocess (launch fix round 9, KiCad-Spike-v11)

**`kicad/tools/kicad_manager_control.cpp`** — 2026-11-07 —
`patches/kicad/0030-ios-manager-execute-inprocess.patch`.
Manager-functionality audit for v11: `KICAD_MANAGER_CONTROL::
Execute()` hands the Gerber viewer, Image Converter, PCB
Calculator, Drawing Sheet Editor, Edit Other Schematic/PCB and the
text-editor action to `COMMON_CONTROL::Execute()`, which
`wxExecute()`s the standalone tool executables or the configured
external editor. This port is a single process — the bundle
contains no standalone executables and iOS cannot spawn processes
— so those Tools-menu items and launcher buttons could only fail
or silently no-op on device. Under `KICAD_IOS_PORT`, `Execute()`
routes the six KiCad tools to their in-process kiway players (the
mechanism `ShowPlayer()` already uses for the schematic and PCB
editors; a file parameter opens in the player, a directory
parameter just shows it), and the text-editor action shows an
explanatory dialog instead. `ExploreProject()` (View ▸ Open
Project Directory) likewise showed nothing on device —
`LaunchExternal()` cannot open a folder on iOS — so under the
same define it reports the project's folder and where the Files
app shows the app's Documents. Desktop paths are unchanged.

### wx patch 0009 — qt-ios-window-geometry-and-floating-controls (launch fix round 9, KiCad-Spike-v11)

**`src/qt/window.cpp` + `src/qt/toplevel.cpp`** (wxWidgets 3.3.4) —
2026-11-07 —
`patches/wx/0009-qt-ios-window-geometry-and-floating-controls.patch`.
All changes are inside `#if defined( Q_OS_IOS )` in the wxQt port;
nothing changes for any other platform or for desktop wxQt.

*Geometry clamp.* Device verdict for v10: the app's floating
(Stage Manager) window sometimes clips off the screen; a black
band sits above the manager content. In this port a wx top-level
is a QWidget/QWindow inside the single UIKit window; Qt 6.9.3's
iOS QPA implements neither `QPlatformWindow::startSystemMove()` nor
`startSystemResize()` (no occurrences in the iOS QPA sources) and
draws no window decorations, so there is no titlebar to drag —
limitation (ii) of the round brief is not achievable without QPA
bridge surgery and is recorded as such in the spike report. What
the port can own is initial geometry: `wxWindowQt::DoMoveWindow()`
moved top-levels with no clamping at all. The patch clamps
top-level positions into `QGuiApplication::primaryScreen()->
availableGeometry()` (which the iOS QPA maintains as the root
view's bounds, so it tracks the Stage Manager scene) in
`DoMoveWindow()`, and intersects a frame's geometry with the
available area once more in `wxTopLevelWindowQt::Show()` before
the window first appears (shrinking a window larger than the
screen, which a position-only clamp cannot fix). Sizes themselves
are otherwise untouched.

*Floating window controls.* The substitute for the missing native
controls, built to the user's design: a small always-on-top bar
("Minimize" / "Close" text buttons, installed by patch 0029's
`OnInit` hook) that floats at the top-right of the screen above
every app window. An application-level Qt event filter tracks the
current window (the most recently shown/activated real top-level:
frames and dialogs, excluding menus, tooltips and the bar itself)
and hit-tests the bar's buttons in the filter, so taps reach it
even while a modal dialog is up — Qt delivers input events to the
application event filters before modal delivery restrictions
apply. Close calls the current window's ordinary `close()`, so
each window keeps its own wx close semantics (the manager runs
KiCad's normal quit flow). Minimize animates the window's
geometry to an 84 pt-wide strip docked at the left edge (stacked
downward from the top when several windows are docked), first
suspending the widget and QWindow minimum sizes that would
otherwise forbid the strip width; tapping a docked strip animates
it back to its saved geometry and restores the minimum sizes.
Window geometry animation is plain QWidget property animation —
no QPA support is needed.

### KiCad patch 0031 — ios-bitmap2component-kiface (launch fix round 9, KiCad-Spike-v11)

**`bitmap2component/CMakeLists.txt`** — 2026-11-07 —
`patches/kicad/0031-ios-bitmap2component-kiface.patch`.
New-file finding of the round-9 manager audit: bitmap2component
is the one KiCad tool upstream builds executable-only — there is
no `_bitmap2component.kiface` in any KiCad install — even though
`bitmap2cmp_main.cpp` implements the complete KIFACE interface
(`BMP2CMP::IFACE`, `CreateKiWindow` → `BITMAP2CMP_FRAME`) exactly
like the other tools. On desktop this is invisible because the
manager launches the executable (the path patch 0030 reroutes).
This single-process port has no executable to launch, so the
patch adds the missing kiface MODULE target, mirroring
pcb_calculator's: same sources minus `common/single_top.cpp`
(the standalone launcher glue), `OUTPUT_NAME`/`PREFIX`/`SUFFIX`
from the standard kiface variables, the executable's own link
set, and `BUILD_KIWAY_DLL;COMPILING_DLL` on the KIFACE source so
the getter is exported, plus the APPLE matched-set block the
other tools carry (`LIBRARY_OUTPUT_DIRECTORY` to the bundle's
PlugIns dir — the directory the packager collects kifaces from —
with the standard install RPATH). Upstream's target definitions
are untouched; the addition compiles the same sources a second
way. (First v11 CI run proved the point: the module built and
linked, but without the output-directory block it landed in the
build tree's `bitmap2component/` folder and the packager quite
correctly never saw it.)

### Content (no upstream change) — stock libraries and demos bundled (launch fix round 9, KiCad-Spike-v11)

2026-11-07 — `scripts/stage-kicad-ios.sh`,
`scripts/package_ios.py`, `scripts/ci-common.sh`. The stage now
fetches the official KiCad library repos at tag 10.0.1
(kicad-symbols `7058584a0fbe9aa2f1c9ff2acf7847726ff6922c`,
kicad-footprints `3d2b27e687a44c97f02109afb2acfeebbc8dd75f`,
kicad-templates `3ed4538b0f965d821df63a5fffc4441e723cfe7f`; pins in
ci-common.sh) and fails closed on incomplete trees. The packager
installs the layout KiCad's own CMake installs use: all 222
`.kicad_symdir` symbol libraries (+ the `.sp` file) to
`share/symbols`, all 155 `.pretty` footprint libraries to
`share/footprints`, and `sym-lib-table` + `fp-lib-table` + the
templates repo's `Projects/*` and `Worksheets/*.kicad_wks` to
`share/template` (232.6 MB + 155.8 MB + 5.3 MB uncompressed).
Upstream's `KICAD_PACK_SYM_LIBRARIES` option packs the symdirs
into single `.kicad_sym` files; this port ships the repo-native
symdir form with the repos' own checked-in tables (KiCad 10 loads
both forms; running the library repos' pack machinery in CI was
avoided). There is no design-block library in the 10.0.1 content
set (the kicad-design-blocks project has no 10.0.1 tag), so that
stock table is created empty by setup, as upstream does when the
file is absent. The 10.0.1 demo projects are bundled to
`share/demos` (the manager's File ▸ Open Demo Project item only
exists when that directory does) EXCEPT four projects that are
mostly one huge board/model file each — vme-wren (126 MB),
jetson-agx-thor-baseboard (97 MB), cm5_minima (50 MB),
tiny_tapeout (31 MB); the other 32 projects (50 MB) ship
complete. The trim, and the exact resulting bundle size growth,
are disclosed in the spike report.

### KiCad patch 0032 — ios-kicommon-define (launch fix round 10, KiCad-Spike-v12)

**`common/CMakeLists.txt`** — 2026-11-07 —
`patches/kicad/0032-ios-kicommon-define.patch`.
The v11 device verdict convicted the whole KICAD_IOS_PORT family
in libkicommon: the manager still raised the bundle-root
`_eeschema.kiface` dlopen error at startup. Disassembly of the
shipped v11 `libkicommon` is unambiguous — `KIWAY::dso_search_path`
contains no "Frameworks" append (its only `wxFileName::AppendDir`
call is the pre-existing one inside the
`KICAD_RUN_FROM_BUILD_DIR` branch) and
`PATHS::GetStockEDALibraryPath` contains no `GetStockDataPath`
call: the iOS blocks of patches 0026, 0027 and 0028 were all
preprocessed out. The cause is a target mix-up in patch 0026: it
added `target_compile_definitions( common PRIVATE KICAD_IOS_PORT )`,
but `kiway.cpp`, `paths.cpp` and `startwizard/startwizard.cpp`
are all in `KICOMMON_SRCS`, compiled by the `kicommon` SHARED
target into libkicommon — the `common` STATIC target compiles
none of them, so the define reached no patched source. (The
round-8 wizard fix's device success in v10 is thereby
re-attributed to that round's `UIUserInterfaceStyle = Light`
plist change, not to patch 0026's then-inert startwizard block.)
This patch adds the same define, under the same
`CMAKE_SYSTEM_NAME STREQUAL "iOS"` guard, to the `kicommon`
target — the one change that makes patches 0026–0028 real. No
upstream logic is altered.

### Packaging (no upstream change) — kiface modules also at the bundle root (launch fix round 10, KiCad-Spike-v12)

2026-11-07 — `scripts/package_ios.py`. The packager now also
copies the eight kiface modules to the app bundle root, byte-
identical to the final Frameworks copies. Two rounds reasoned
about the kiface path while the device kept dlopening
`<exe dir>/_<tool>.kiface`; with patch 0032 the Frameworks
search is genuinely compiled in, and the root copies cover the
path the device demonstrably constructs — a path that exists
cannot fail on path grounds. A kiface's dependencies are
`@rpath` names resolved through `@executable_path`-based
rpaths, independent of the kiface's own location; the Python
module's separate `_pcbnew.so` copy is untouched. Cost: the
eight modules total 160,119,512 bytes uncompressed, disclosed
in the spike report.

### KiCad patch 0033 — ios-library-table-chain-repair (launch fix round 10, KiCad-Spike-v12)

**`include/libraries/library_manager.h`,
`common/libraries/library_manager.cpp`, `kicad/kicad.cpp`** —
2026-11-07 — `patches/kicad/0033-ios-library-table-chain-repair.patch`.
The upgrade half of the library failure. The wizard's
USE_DEFAULTS flow freezes the then-computed ABSOLUTE stock
table path into the user's global tables as a chained row
(nickname "KiCad"); in v10/v11 that path was built from the
empty compiled-in `KICAD_LIBRARY_DATA` (patch 0028 inert, see
patch 0032), so the chain target does not exist and the stock
libraries never load. Nothing upstream repairs this on later
launches: the user table file parses, so
`GlobalTablesValid()` stays true and the wizard's library page
is never offered again; the one upstream rewrite of such rows
lives in the wizard's IMPORT-settings flow, which an in-place
upgrade never runs. This patch adds
`LIBRARY_MANAGER::RepairStockTableChains()` (iOS-gated,
declared and defined only in this port's build) and calls it
from the manager's startup, just before the start wizard runs
and before `LoadGlobalTables`: for each global table type, if
the chained "KiCad" row names a file that is not a valid table
while the stock table path computed now is valid, the row is
re-pointed at the current stock path and the table saved —
the same rewrite upstream's migration performs, hoisted to
every launch. Fresh installs and users' own chained tables
are untouched. Upstream logic is not altered.

### wx patch 0010 — qt-ios-floating-controls-child-overlay-and-drag (launch fix round 11, KiCad-Spike-v13)

**`src/qt/toplevel.cpp`** (wxWidgets 3.3.4) — 2026-11-07 —
`patches/wx/0010-qt-ios-floating-controls-child-overlay-and-drag.patch`.
Reworks only the floating-controls block patch 0009 added; still
entirely inside `#if defined( Q_OS_IOS )`, no other platform or
desktop wxQt behaviour changes.

*Why.* Device verdict for v11 (the same bar code shipped in v12):
the floating Minimize/Close bar was never seen — not over the
first-run wizard, not over the manager. The install hook itself
was proven present in the shipped executable (patch 0029's call
compiles into the `kicad` target; disassembly shows
`APP_KICAD::OnInit` calling the installer), so the defect is in
the bar's construction. As built by patch 0009 the bar is a
separate top-level `QWidget` (`Qt::Tool | Qt::FramelessWindowHint
| Qt::WindowStaysOnTopHint`). On Qt's iOS QPA every top-level
window becomes its own `UIWindow` and stacking between UIWindows
is governed by `windowLevel`: a non-modal tool window earns no
level above the ordinary windows, a modal dialog does get a
raised level, and `QWidget::raise()` does not reorder UIWindows.
The bar was first shown during the modal wizard; every later
window stacked above it, and the controller never recovered,
because at the Qt level the bar stayed "visible" (so it was
never re-shown) while `raise()` changed nothing on screen. Its
position was also computed against the SCREEN's top-right
corner, which under Stage Manager can be outside the app's
window entirely.

*Fix — the bar stops being a window.* It is now a plain child
widget that the controller re-parents into whichever top-level
window is current — the manager, an editor frame, or the modal
dialog itself. Inside one `UIWindow`, Qt child stacking is
deterministic: a child raised last paints and hit-tests above
its siblings, and as part of a modal window the bar's buttons
receive input through the normal path (the application-filter
hit-test from patch 0009 is kept as belt-and-braces). The
controller tracks a most-recent-first history of real windows:
the bar re-attaches and re-raises whenever the current window
changes, and when a dialog closes the bar falls back to the
window beneath. The bar rides at the host window's own top-right
corner and follows its resizes. Because the bar is a child, a
host the application destroys (the stack-allocated wizard,
a torn-down editor frame) destroys the bar too: the bar members
are `QPointer`s, the controller drops them on the bar's Destroy
event, refresh after a Destroy cascade is deferred to the event
loop, and `refreshBar()` builds a fresh bar when it finds none.
A docked (minimized) window never hosts the bar — it is narrower
than the bar — so Minimize detaches the bar before the dock
animation and re-hosts it on the next window down, or hides it
when none is left.

*Window dragging.* The iOS QPA has no titlebars and no
`startSystemMove()`, so the bar doubles as the move handle:
a press on its non-button area arms a drag of the host window;
past an 8 pt threshold the window follows the pointer
(absolute-delta positioning, clamped to the screen's available
geometry with the same rule patch 0009 put in
`wxWindowQt::DoMoveWindow()`), and the child bar follows for
free. Moving the Qt widget directly is the same input a desktop
window manager's move produces, and wxQt absorbs it through its
ordinary Qt move-event handling. Docked strips get the same
tap-versus-drag distinction: a strip press is now tracked
instead of restoring immediately; a release that never crossed
the threshold restores the window, a drag repositions the strip
itself (it stays docked; its saved restore geometry is
untouched), and strip presses are swallowed either way so the
squished frame beneath never receives them. Presses are also
ignored while a popup menu owns the screen, so a menu item that
happens to overlap the bar's rectangle is never stolen.

*Verification.* Code presence is gated from the shipped bytes
(the binary gate asserts `APP_KICAD::OnInit` calls the
installer — a regression guard; it passed v11/v12 too, since
installation was never the defect). The controller logic is
host-verified: the patched block, extracted verbatim, was run
under desktop Qt on the offscreen platform — 27 checks covering
attach/position, re-parenting into a dialog, fallback on dialog
hide and on window close, recreation after host destruction,
drag threshold and delta, dock/strip tap/drag/restore, and the
Close button all pass. Whether the bar is visible on the iPad
is, as ever, the device's verdict.

### KiCad patch 0034 — ios-user-files-in-documents (launch fix round 12, KiCad-Spike-v14)

**`kicad/kicad.cpp`, `common/eda_base_frame.cpp`,
`kicad/tools/kicad_manager_control.cpp`** (KiCad 10.0.1) —
2026-11-07 — `patches/kicad/0034-ios-user-files-in-documents.patch`.
Three additions, all inside `#ifdef KICAD_IOS_PORT`; no upstream
logic is altered and other platforms are unaffected.

*Why.* On device in v13, creating a project failed: the manager
tried to create the project's folder inside the application
bundle ("Operation not permitted"), which is read-only. The
port's rule is that user files live in the app's shared
Documents folder, and the Documents-rooted user tree
(Documents/KiCad/10.0/projects and siblings) was already built
correctly — the default never reached it. Traced end to end:
`EDA_BASE_FRAME::commonInit()` sets the manager's MRU path to
`PATHS::GetDefaultUserProjectsPath()`, but the manager frame's
constructor then loads the window settings, and
`EDA_BASE_FRAME::LoadWindowSettings()` assigns
`m_mruPath = aCfg->mru_path` unconditionally. The persisted
value defaults to "" and, until a project has been loaded once,
stays "" (the settings are saved back unchanged), so the
correct default is wiped on every launch. The New Project
dialog takes its default directory from `GetMruPath()`; with it
empty, the wxQt file dialog is constructed with an empty
directory, Qt's file dialog falls back to the process working
directory, and iOS launches the app with its working directory
inside the bundle — so the folder the user names is created
there and refused.

*What.* (1) `LoadWindowSettings()`: after the assignment, an
empty MRU path is restored to
`PATHS::GetDefaultUserProjectsPath()` — the layer where the
default is lost; this repairs every consumer of `GetMruPath()`
at once (New Project, Open Project and Save Project To in the
manager, and the legacy-project import). (2) At the point of
use: `KICAD_MANAGER_CONTROL::newProjectDirectory()` and the
template route of `NewProject()` substitute the same default
when their computed default directory is empty (the template
route derives it from the current project's path, which is
empty when no project is open). (3) Belt and braces in
`APP_KICAD::OnInit()`, before the first window exists:
`wxSetWorkingDirectory( KIPLATFORM::ENV::GetDocumentsPath() )`,
so any remaining fallback that resolves against the working
directory lands in Documents rather than the bundle. All paths
the port itself locates (stock data, kiface modules, Python)
are absolute and unaffected; editor Save defaults derive from
the open project and were not part of the defect.

*Verification.* The binary gate (the round-10 kiface gate,
extended) inspects the shipped executable: it disassembles
`LoadWindowSettings`, `newProjectDirectory`, `NewProject` and
`OnInit` and counts calls to
`PATHS::GetDefaultUserProjectsPath`, `wxSetWorkingDirectory`
and `KIPLATFORM::ENV::GetDocumentsPath`. Measured on the v13
binary the counts are 0 / 1 / 1 / 0 / 0 (the two 1s are the
dialogs' pre-existing sidebar shortcuts); the gate requires
>= 1 / 2 / 2 / 1 / 1 and fails v13 on every count. Whether a
new project now actually lands in Documents is the device's
verdict.

### wx patch 0011 — qt-ios-floating-controls-modal-host-and-wx-drag (launch fix round 12, KiCad-Spike-v14)

**`src/qt/toplevel.cpp`** (wxWidgets 3.3.4) — 2026-11-07 —
`patches/wx/0011-qt-ios-floating-controls-modal-host-and-wx-drag.patch`.
Confined to the floating-controls block patches 0009/0010 added;
still entirely inside `#if defined( Q_OS_IOS )`.

*Why.* The v13 device screenshots show the bar DOES render — a
dark pill at the manager's top-right — so the round-11 child
overlay works. It never moved onto the modal folder-error
dialog, though: it stayed on the manager behind the dialog,
which covered the bar's left (Minimize) half, and dragging
still did not work for the user. Root cause, reproduced on the
host harness: the block's `windowOf()` resolved an event object
to a window by walking the QObject parent chain to the
OUTERMOST widget ancestor. wxQt creates every dialog's Qt
widget parented to its owner frame's widget (and KiCad's modal
dialogs — the first-run wizard included — are all parented), so
the walk overshoots the dialog and lands on the owner frame:
the controller's "current window" was pinned to the manager
for every dialog, and the bar could never leave it. Dragging
had its own defect: the drag path moved the raw QWidget with a
hand-copied clamp, bypassing `wxWindowQt::DoMoveWindow()` —
the path whose iOS clamp patch 0009 added — and desyncing wx's
geometry bookkeeping from the widget's real position.

*What.* `windowOf()` now returns `QWidget::window()`, which
honours the window flags and yields the dialog itself.
`pickHost()` first prefers `QApplication::activeModalWidget()`
while a modal dialog is up, so events from the window beneath
cannot pull the bar back mid-session. `positionBar()` anchors
with a 12 pt margin on both axes (the bar previously sat 10 pt
in with an 8 pt top), takes the host width from the wx-level
size (`wxWindowQt::QtRetrieveWindowPointer` + `GetSize()`)
when the host is a wx window, and the host's Move events now
re-anchor alongside Resize; `refreshBar()` settles the bar's
size with `adjustSize()` after (re)parenting and re-anchors
once more after the current event cascade via a deferred call,
so a host placed by Stage Manager after its Show event still
ends with the bar fully inside its top-right corner. Drags
route through a helper that calls `wxWindowQt::Move()` for wx
windows — the `DoMoveWindow()` path, clamp included — and
keeps the plain Qt move only for windows with no wx
counterpart. The bar is now fully opaque with solid buttons
and at least 44 pt tall, so it cannot blend into the window or
the surround. Everything else is preserved: child-overlay
design, the 8 pt tap-versus-drag threshold,
minimize-to-left-dock strip and tap restore, popup-menu
exclusion.

*Verification.* The reworked block, extracted verbatim, was
run under desktop Qt on the offscreen platform: the round-11
27-check harness passes (its corner-anchor check now expects
the new 12/12 margin), and a modal reproduction added this
round — a QMessageBox parented to the manager window, exec'd
the way wxQt shows KiCad's dialogs, and the same again after a
file dialog teardown — failed 2 of its 3 scenarios against the
v13 block (the bar never re-hosted) and passes all of them
against this one. A binary guard in the extended gate asserts
the shipped executable carries the new stylesheet literals and
not the old translucent one. Bar visibility over dialogs, drag
feel, and the dock/restore behaviour on the iPad remain the
device's verdict.

### KiCad patch 0035 — ios-cairo-canvas-default (launch fix round 13, KiCad-Spike-v15)

**`common/eda_draw_frame.cpp`, `kicad/kicad.cpp`,
`common/dialogs/panel_common_settings.cpp`,
`eeschema/dialogs/dialog_import_symbol_select.cpp`,
`eeschema/CMakeLists.txt`** (KiCad 10.0.1) —
2026-11-07 — `patches/kicad/0035-ios-cairo-canvas-default.patch`.
Five changes, every code change inside `#ifdef KICAD_IOS_PORT`;
no upstream logic is altered and other platforms are unaffected.

*Why.* On device in v14 the editors open and work, but the first
editor raised "Could not use OpenGL, falling back to software
rendering". iOS has no OpenGL; this port's canvas is the Cairo
software canvas, settled when the port was designed. Upstream
persists the canvas choice as `graphics.canvas_type`, whose
compiled-in default is `GAL_TYPE_OPENGL`, and every editor frame
resolves its canvas through
`EDA_DRAW_FRAME::loadCanvasTypeSetting()` — so on first run and
with any stored OpenGL value, the GAL attempted OpenGL, failed
its feature check, showed the dialog, and only then fell back.
A stored value from an earlier build would keep forcing the
attempt on every launch.

*What.* (1) `loadCanvasTypeSetting()` returns
`GAL_TYPE_CAIRO` immediately under the port define, before the
stored value is read — the single choke point every frame's
canvas resolution flows through, covering first run and
carried-over configurations alike. (2) `APP_KICAD::OnInit()`
coerces the stored `m_Graphics.canvas_type` to
`GAL_TYPE_CAIRO` before any window exists: a few previews (the
symbol chooser's fallback branch, the schematic colour-settings
preview, the footprint preview panel) read the stored value
directly instead of resolving through (1); the coerced value is
what the settings manager saves back, so a stored OpenGL value
heals. (3) The Preferences rendering-engine choice is hidden
(mirroring the `__WXMAC__` hide in the same constructor) and its
data transfer writes `GAL_TYPE_CAIRO` unconditionally — the
choice does not exist on this port and cannot write OpenGL
back. (4) The symbol-import dialog's preview widget, the one
place upstream passes `GAL_TYPE_OPENGL` literally, passes
`GAL_TYPE_CAIRO`. (5) `eeschema/CMakeLists.txt` defines
`KICAD_IOS_PORT` for the `eeschema_kiface_objects` target —
the same per-target define patches 0023/0026/0032 place on the
`kicad`, `common` and `kicommon` targets — so change (4)
compiles in; no other port blocks exist in the eeschema
sources, so the define activates nothing else. The 3D viewer
is not touched: it is genuinely OpenGL-bound and remains a
named limitation of the port rather than something faked.

*Verification.* The patch series 0001–0035 applies cleanly to
the pristine 10.0.1 sources. The extended binary gate asserts
from the shipped bytes that, in every editor kiface,
`loadCanvasTypeSetting` is the trivial constant return (the
v14 body disassembles to 161 instructions calling `Pgm()` and
`wxGetEnv`; the gate fails v14 on exactly this count), that the
executable's `OnInit` calls `PGM_BASE::GetCommonSettings`
(v14: 0 calls), and that the symbol-import dialog passes
GAL_TYPE 2, not 1, to its preview widget. Whether the OpenGL
dialog is truly gone on the iPad remains the device's verdict.
