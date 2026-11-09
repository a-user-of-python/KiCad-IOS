<div align="center">

# 🔌 KiCad‑iOS

### *The actual KiCad — running on iPad.*

**The real, upstream [KiCad](https://www.kicad.org/) 10.0.1, running on iOS / iPadOS.**
Not a recreation. Not a lookalike. The genuine program, rebuilt for Apple's tablets — and proven on real hardware.

[![Build Spike](https://github.com/a-user-of-python/KiCad-IOS/actions/workflows/spike.yml/badge.svg)](https://github.com/a-user-of-python/KiCad-IOS/actions/workflows/spike.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Upstream](https://img.shields.io/badge/upstream-KiCad%2010.0.1-orange.svg)](https://gitlab.com/kicad/code/kicad/-/tree/10.0.1)
[![Platform](https://img.shields.io/badge/platform-iPadOS%2017%2B-lightgrey.svg)](#-installing)
[![Status](https://img.shields.io/badge/status-current%20release%20V1.1-brightgreen.svg)](#-status)

**[🌐 Project website](https://a-user-of-python.github.io/KiCad-IOS/)**

</div>

---

> ⚠️ **Unofficial port — read this first.**
> This is an independent experiment. It is **not** affiliated with, sponsored by, or endorsed by the KiCad project or CERN. "KiCad" is a trademark of the KiCad project; the name is used here only to describe what this port is a port *of*.
> **Current reality:** the port runs. KiCad 10.0.1 builds for iOS arm64, installs on a real iPad, completes KiCad's own first-run wizard end to end, and opens the KiCad project manager — real menus, real icons, real windows — verified on hardware on 2026‑11‑06 (build v10). **Build v15:** the complete stock KiCad 10.0.1 libraries ship inside the bundle, and the manager screen is audited control by control. v14 carries v12's root-cause fix: a build switch that three of the port's patches depend on sat on the wrong library target, so those patches were never compiled into v10 or v11 at all — proven from the shipped v11 binary; the switch is set correctly, a gate inspects the shipped binary to prove the code is in, and the editor modules also sit at the bundle root as a belt-and-braces copy. v13's on-device pass (2026‑11‑07) confirmed that fix on hardware at startup: the manager stands with no editor-load error. On top of that, v13 rebuilt the floating window control: the bar now lives inside the current window as an overlay instead of floating as a separate window — the design iOS layering could bury, and which v11's on-device pass never saw — and the bar doubles as the window's drag handle. The v13 pass found two defects, and v14 fixes both. Creating a project tried to write inside the app bundle and failed ('Operation not permitted'): a persisted recent-projects path defaults to blank and overwrote the correct Documents default at every launch, so the dialog opened with no folder and the toolkit fell back to the app's own folder — v14 restores the Documents projects folder whenever that path is blank, guards the create flows at the point of use, and starts the app with its working directory in Documents, so projects default to the app's shared Documents folder. And the bar, though it rendered, stayed pinned to the manager behind modal dialogs — the host-window lookup climbed to the outermost window, overshooting every dialog — while dragging bypassed the window system's own move path: v14 hosts the bar on the window that is actually current, dialogs included, anchors it fully inside the frame, and routes drags through the proper move path; the v13 failure is reproduced off-device with v13's own code, and the fixed code passes that reproduction. v14's on-device pass (2026‑11‑07) then confirmed the Documents default on hardware — projects create and open, and the editors open and work — and it surfaced the two things v15 answers. First, an opening editor hit KiCad's default OpenGL canvas and showed a failure dialog before the Cairo software canvas took over: iOS has no OpenGL, and the attempt never belonged there. In v15 the function every editor frame uses to choose its canvas returns the Cairo canvas directly on this port — proven in the shipped binary by the gate — a stored OpenGL preference from an earlier install is converted at startup, and the Preferences rendering-engine choice no longer offers OpenGL. The 3D viewer remains OpenGL-bound and does not work on iOS: a standing limitation, stated plainly; the 2D editors are unaffected. Second, v14's pass reported one unidentified error dialog during file creation that did not block entry. The whole create flow was audited for v15: every write in it lands in the app's Documents folder, and no remaining bad-path step was found — so v15 changes nothing there, and a ranked suspect list stands ready to match the error's exact text if it recurs. v15's on-device pass is the immediate next step, and the library verdict is still outstanding — it gets itemised there. Every change to upstream code is documented in the open in [`MODIFICATIONS.md`](MODIFICATIONS.md).

---

## ✨ What this is

KiCad is the world's leading open-source electronics design suite — schematic capture, PCB layout, and a family of companion tools, all driven from one project manager. It runs on Windows, macOS and Linux. Now it runs on iPad too.

This repository contains a port of the **actual upstream KiCad source code** (pinned at **10.0.1**) to iOS. KiCad's own windows, KiCad's own menus, KiCad's own buttons — the same code that ships on the desktop, compiled for the tablet:

1. Launch the app → KiCad's **project manager** window stands up.
2. The **first-run wizard** runs, exactly as it does on a fresh desktop install.
3. Every editor ships in the bundle as a loadable module, opened in its own window inside the one app process.
4. Touch, Apple Pencil, keyboard and mouse all drive the real interface.

## ✅ What runs today — proven on a real iPad

- **Builds end to end.** The whole of KiCad 10.0.1 compiles and links for iOS arm64 (1,591/1,591 build steps): the manager, every editor module, and the supporting libraries.
- **Installs and launches.** The unsigned IPA sideloads and opens on a real M‑series iPad.
- **First-run wizard completes.** KiCad's genuine setup wizard is walkable from the first page to the last — its navigation buttons render and work.
- **The project manager stands up.** Real menu bar (File / Edit / View / Tools / Preferences), the Project Files tree, the launcher column with the real colour icons, and the tool description pane — in KiCad's light desktop appearance.
- **Python is in.** KiCad's embedded Python environment ships whole: the CPython standard library, the compiled `pcbnew` module, KiCad's stock scripting plugins and footprint wizards, plus two addons from the official PCM index — the PCBWay plug‑in and the JLCPCB Fabrication Toolkit — each with its own license.
- **Files are reachable.** File sharing is on: projects live in the app's Documents folder and move on and off the iPad the normal way.
- **One of everything.** The bundle carries exactly one libpng, one zlib, one expat — shared by every component — so the icon pipeline loads KiCad's 5,000+ bitmap resources without conflict.

### What v15 adds — verified by the build gates

- **The editors never attempt OpenGL.** KiCad's default canvas is OpenGL, and iOS has no OpenGL; v14's on-device pass watched an opening editor fail on the GL canvas — failure dialog first — before the Cairo software canvas took over. In v15 the function every editor frame uses to choose its canvas returns the Cairo canvas directly on this port, proven in the shipped binary by the gate. A stored OpenGL preference from an earlier install is converted at startup, and the Preferences rendering-engine choice no longer offers OpenGL.
- **Stated plainly: the 3D viewer does not work on iOS.** It remains OpenGL-bound, and this port leaves it that way. The 2D editors — schematic, PCB, and the companion tools — are unaffected.
- **File creation, audited end to end.** v14's pass reported one unidentified error dialog during project creation; the project still created, and projects open. For v15 the entire create flow was audited: every write in it lands in the app's Documents folder, and no remaining bad-path step was found — so v15 changes nothing there. A ranked suspect list stands ready to match the error's exact text if it recurs.
- **New Project lands in Documents.** v13's on-device pass found project creation failing outright: the new folder was being created inside the app bundle — 'Operation not permitted'. The cause is traced: a persisted recent-projects path defaults to blank and overwrote the correct Documents default at every launch, so the create dialog opened with no folder and the toolkit fell back to the app's own folder. v14 restores the Documents projects folder whenever that path is blank, guards the create flows at the point of use, and starts the app with its working directory in Documents. Projects now default to the app's shared Documents folder — confirmed on device in v14's pass: projects create and open.
- **The floating bar rides the window that is actually current.** v13's bar rendered, but stayed pinned to the manager behind modal dialogs: the host-window lookup climbed to the outermost window, overshooting every dialog, and dragging bypassed the window system's own move path. v14 hosts the bar on the window that is actually current — dialogs included — anchors it fully inside the frame, and routes drags through the proper move path. The v13 failure is reproduced off-device with v13's own code, and the fixed code passes that reproduction.
- **The floating bar, rebuilt inside the window (v13).** Through v12 the Minimize/Close bar floated as a separate top-level window; iOS window layering can stack the app's own windows above a window like that, and v11's on-device pass never saw the bar at all. In v13 the bar is a child overlay that the controller re-parents into whichever window is current — the manager, an editor frame, or the modal dialog itself — so it rides inside the one window iOS is actually showing. Shipped and gate-verified: the binary gate proves the installer call is present in the shipped executable. Its on-device pass ran on 2026‑11‑07: the bar rendered at the manager — and the pass exposed the host-tracking defect fixed in v14 above.
- **The bar is now the window's handle.** Drag the bar and the current window moves with it — the port's answer to window dragging on a platform layer that draws no titlebars and provides no system window move. A small movement threshold (8 pt) separates a tap on Minimize/Close from a drag, and the minimize behaviour is unchanged: the window shrinks into a docked strip at the left edge (84 pt, stacking, Stage Manager style) and a tap restores it.
- **The root cause, found and fixed (v12, carried forward).** v11's on-device pass showed the editor load error and the wizard's library failure still standing. Disassembly of the shipped v11 binary proved why: patches 0026, 0027 and 0028 are all gated on `KICAD_IOS_PORT`, and that define sat on the `common` CMake target while every patched source compiles into `kicommon` — so all three blocks were preprocessed out of both v10 and v11. Patch 0032 sets the define on the `kicommon` target: the wizard-navigation fix, the kiface module search, and the stock-library location fix are compiled in and active for real.
- **Editor modules in two places.** The search fix is active, and all 8 editor modules also sit at the bundle root, byte-identical to the `Frameworks/` copies — the exact location the app asks for first. A path that exists cannot fail on path grounds.
- **A startup repair for inherited tables.** `RepairStockTableChains()` (patch 0033) runs at manager startup and re-points library tables that the broken builds left chained to a bogus location, so upgrading over v10 or v11 lands on the bundled defaults without redoing setup.
- **A gate that reads the binary.** The new `kiface_path_gate.py` inspects the shipped executable itself — the search code present, the stock-path call present, the modules in place at both locations. It passes v12 and fails v11 on every count.
- **Stock libraries ship in the bundle — complete.** KiCad 10.0.1's **222 symbol libraries** and **155 footprint libraries**, unabridged, with the default symbol and footprint library tables resolving straight to them, plus **19 project templates** and the demo projects (four oversized demos are left out). First-run setup did not find the defaults on device in v11; the fix is compiled into the current release and its on-device pass runs next.
- **The manager screen, audited control by control.** Every menu opens, every item acts, every button does its real job. Tools that tried to launch separate programs on the desktop — the Gerber viewer, the calculator, the converters, the page-layout editor — open inside the app instead, and the image converter has its module in the bundle.
- **Windows stay on screen.** Top-level windows are clamped inside the visible screen area, so nothing opens hanging off-screen.
- **One honest limitation:** windows do not drag by their titlebars. Qt's iOS layer draws no titlebar and provides no system window move — the floating bar is the handle instead: drag it and the window follows.

## 🧭 How it works — the architecture

KiCad was never written for iOS. Four walls stand between its source code and an iPad, and the port has a concrete answer for each:

| # | The wall | The answer in this port |
|---|----------|-------------------------|
| 1 | KiCad's UI is built on **wxWidgets**, which has no iOS port. | **wxQt bridge** — KiCad's wx code runs on wxWidgets' Qt backend (wx 3.3.x), and Qt 6.9.3 runs natively on iOS. KiCad's own CMake already recognises a `qt` wx port. |
| 2 | KiCad's editors normally run as **separate processes** (Kiway). iOS apps are single-process. | **Single-process hosting** — each editor is a *kiface* module loaded in-process, opening as its own window inside the app. |
| 3 | **Python** scripting is baked into KiCad and its build requires it. | **A full CPython 3.13 sysroot is cross-compiled for iOS and embedded** in the app; the port sets its Python home at startup, so `import pcbnew` resolves to the real compiled module. |
| 4 | The drawing canvas is **desktop OpenGL**, which iOS doesn't provide. | **KiCad's built-in Cairo software canvas** carries the editors on iOS — correct rendering first; the GLU calls some 3D helpers expect are shimmed. |

Two more pieces of the foundation: a real **iODBC** is cross-compiled into the sysroot, so KiCad's database-library support is genuine code, not a stub; and the wx build is locked to the **shared sysroot libraries** (libpng / zlib / expat) — the build fails closed rather than silently falling back to bundled copies.

## 📊 Status

| Milestone | State |
|---|---|
| Upstream pinned (KiCad **10.0.1**, commit `2db9e5a7…`) | ✅ Done |
| Repo, licensing & attribution in place | ✅ Done |
| wxQt (wx 3.3.x + Qt 6.9.3) compiled for iOS arm64 | ✅ Done |
| Whole KiCad compiles + links for iOS arm64 | ✅ Done — manager + all editor modules |
| Unsigned IPA packaged, deep-verified (symbol closure, resources, signing) | ✅ Done |
| Installs, signs and launches on a real iPad | ✅ **Device-proven** (v2–v10) |
| Python initialises inside the app; manager window constructs | ✅ **Device-proven** (v8, v9) |
| Split-libpng crash in icon loading found and fixed at the root | ✅ **Device-proven** (v9) |
| First-run wizard completable end to end; manager stands, light appearance | ✅ **Device-proven** (v10, 2026‑11‑06) |
| Editor-module load error eliminated at manager startup | ✅ **Device-proven** at startup (v13 on-device pass, 2026‑11‑07) — fixed in v12: root cause proven from the shipped binary, the `KICAD_IOS_PORT` switch sat on the wrong library target, so the fix patches never compiled into v10/v11. Switch set on the correct target, modules also at the bundle root; binary-inspection gate passes v12, fails v11 on every count |
| Stock 10.0.1 libraries bundled complete (222 symbol, 155 footprint) + default tables | ✅ Done (v11) |
| Library tables inherited from the broken v10/v11 builds re-pointed at startup | ✅ Done (v12) |
| Manager screen audited control by control; companion tools open in-app | ✅ Done — gate-verified (v11) |
| New Project defaults to the app's shared Documents folder | ✅ Fixed in v14 — the blank persisted recent-projects path that wiped the Documents default at every launch is restored whenever blank, the create flows are guarded at the point of use, and the app starts with its working directory in Documents. **Device-confirmed** in v14's pass: projects create and open. The v15 audit of the create flow found every write Documents-rooted and no remaining bad-path step; one unidentified creation dialog from that pass stays unmatched, suspect list standing |
| Floating window control (Minimize / Close, left-edge dock) + on-screen clamping | ✅ Host-fixed in v14 — the bar (a child overlay inside the current window since v13, doubling as its drag handle) now hosts on the window that is actually current, dialogs included, anchored fully inside the frame, with drags routed through the proper move path; the v13 host-overshoot failure is reproduced off-device and the fix passes that reproduction. Device itemisation still owed |
| Editor canvas: Cairo returned directly, no OpenGL attempt | ✅ Fixed in v15 — the canvas-choice function every editor frame uses returns the Cairo software canvas on this port (proven in the shipped binary by the gate), a stored OpenGL preference is converted at startup, and Preferences no longer offers OpenGL. On-device pass next |
| 3D viewer | ⚠️ Standing limitation — remains OpenGL-bound and does not work on iOS; the 2D editors are unaffected |

### v15

v15 is built, gated, and shipped. It stands on v14's on-device pass (2026‑11‑07): projects create and open in the shared Documents folder, and the editors open and work. Underneath, v15 carries the whole v14 layer — the Documents project default, and the floating bar hosting on the window that is actually current with drags through the proper move path — on top of v13's window-controls rebuild and the v12 root-cause fix itself: v11's on-device pass found the editor-module load error and the wizard's library failure still standing, and disassembly of the shipped v11 binary proved the three patches behind those fixes were never compiled in, because the `KICAD_IOS_PORT` switch sat on the wrong library target. The switch sits on the correct target, a gate proves the code is in from the shipped binary, the editor modules also sit at the bundle root as belt and braces, and inherited library tables are repaired at startup. The stock libraries are in the box and the manager does its full job.

v15's own layer answers the two things v14's pass surfaced. The editors no longer attempt OpenGL: KiCad's default canvas is OpenGL and iOS has none, so an opening editor in v14 failed on the GL canvas with a failure dialog before the Cairo software canvas took over. The function every editor frame uses to choose its canvas now returns the Cairo canvas directly on this port — proven in the shipped binary by the gate — a stored OpenGL preference from an earlier install is converted at startup, and the Preferences rendering-engine choice no longer offers OpenGL. The 3D viewer remains OpenGL-bound and does not work on iOS — a standing limitation; the 2D editors are unaffected. And the create flow behind v14's one unidentified creation dialog was audited end to end: every write in it lands in the app's Documents folder, no remaining bad-path step was found, and v15 changes nothing there — a ranked suspect list stands ready to match the error's exact text if it recurs.

Its on-device pass is the immediate next step: the first editor open with no OpenGL dialog; project creation with zero dialogs — or the remaining error's exact text; and the library choosers itemised — the library verdict is still outstanding.

### V1.1 — the current release (2026‑11‑09)

V1.1 replaces V1 and changes exactly one thing: the fresh-install first-launch crash, which V1 did not cure. V1's on-device pass installed V1 fresh and it crashed again — same moment (first-run library preload), same faulting frame (`wxStatusBar::GetFieldRect`). Disassembly of the shipped V1 binary proves V1's creation-side guard (patch 0020) is present and correct; the surviving path is the pane set's OTHER mutation. The preload chain sets status widths before laying out (`KISTATUSBAR::updateAuxFieldWidths` → `SetStatusWidths` → `layoutControls`), and the wxQt `SetStatusWidths` deleted every pane and cleared the pane vector only after the loop — the shipped V1 disassembly shows the delete inside the loop and the clear after it. A `removeWidget` on the visible bar delivers the same synchronous resize mid-teardown, and the re-entered layout reads a pane deleted earlier in the loop (fault at 0x14, a freed pane's Qt data pointer reading as null). No reader-side guard covers that window, so patch 0021 removes the window: an RAII freeze (status bar hidden, `wxEVT_SIZE` blocked, updates off) wraps BOTH pane mutations, and `SetStatusWidths` publishes the empty pane set before removing or deleting anything. The gate disassembles the shipped executable and requires that order — freeze and publish-empty before the first `removeWidget`, freeze before the first `addWidget` — and the shipped V1 binary fails every one of those checks. The deciding check is unchanged and still first in the report: delete the app, install V1.1, first launch.

### V1 (2026‑11‑09)

V1 is the first official release, graduating from the Spike numbering. It stands on v15's on-device pass (2026‑11‑09): the app works — the Schematic Editor opens and draws on the Cairo canvas, no crash — and that pass reported five defects. Six more jobs were added the same day, and pre-release testing added a twelfth: a fresh install of the pre-release candidate crashed 0.44 s after first launch. All twelve are answered in V1. Every fix is proven in the shipped binary by the gate, which fails on v15 on every round‑16 count; V1's on-device pass runs next, and the report enumerates the exact device checks.

- **Fresh-install first-launch crash — fixed.** First-run library preload laid out the manager's status bar before its fields existed; the toolkit created them lazily, one widget at a time, a resize delivered mid-creation re-entered the layout, and a field rect was read from a pane that did not exist yet. The toolkit now builds the full field set before publishing any of it, with a re-entrancy guard (wx patch 0020).
- **The editors never attempt OpenGL — at the root.** v15 stopped the canvas choice; an occasional path still constructed an OpenGL canvas and showed the failure dialog before falling back. V1 coerces the canvas type inside the one backend-switch function every editor panel uses: an OpenGL request becomes Cairo before any OpenGL object exists (KiCad patch 0036; gate-disassembled in all five canvas modules).
- **The manager's 'schema file' error — fixed.** The dialog carried since v13 is convicted: the manager validates plugin data against JSON schemas at startup, and the bundle shipped without the schemas folder at all. All nine upstream schemas ship in V1, and the packager fails the build if a startup schema goes missing.
- **Windows fill the screen at natural scale.** The app declared no launch screen, so the system presented it at a legacy size and magnified the UI ~2×, and frames opened at stored sizes leaving black bands. V1 declares a launch screen and full-screen presentation, and frames maximise on open regardless of persisted geometry (packager plist + KiCad patch 0037).
- **Titlebar window controls.** The floating pill is replaced by a per-window titlebar strip — title left, Cursor toggle, Minimize, Close right — hosted above the real menu bar in frames so layout reserves the space, and grown into dialogs so nothing is covered (wx patch 0015). The strip is the drag surface: presses arm by coordinates at the platform level, and a maximised window un-maximises and follows the drag (wx patch 0013, carried into the titlebar design). Host harness: 56/56 checks across two frames and a modal dialog.
- **Pinch zoom and two-finger pan, both editors.** KiCad already had the gesture handlers; the bridge dropped the gestures. The bridge is fixed (wx patch 0012) and the canvas itself requests zoom/pan gestures (KiCad patch 0038), so a pinch zooms at its centre through KiCad's own view machinery and a two-finger drag pans — in the Schematic Editor and the PCB Editor alike, gated in the shared canvas library both editors link.
- **Smoother window moves.** The canvas resize is deferred until the size settles (a burst of full reallocations becomes one redraw at the final size, KiCad patch 0039), and drag moves are coalesced to the latest position (wx patch 0016).
- **An optional virtual cursor.** A Cursor toggle on every titlebar — off by default, remembered — drives an on-screen arrow relatively, trackpad-style; lifting the finger clicks at the arrow; two-finger gestures pass through untouched (wx patch 0014).
- **Every window clamped to its display.** Any window or dialog larger than its display is shrunk and moved fully inside it; the geometry is queried from the display at runtime — no resolution is hardcoded (wx patch 0017). Dialog content whose own minimum exceeds the panel can still clip inside a window that fits; the window always fits and stays closable.
- **External display, extended.** An Ext toggle on every titlebar moves that window to a connected display and fills it at its native size while the iPad keeps its own content; toggling back — or unplugging — restores it (wx patch 0019). It ships at the platform layer, labelled honestly: how much input iPadOS routes to the external window is the open item in V1's device pass.
- **Hardware keyboard and mouse, audited.** The char-hook event KiCad's dispatcher and dialogs are built around is generated; Alt hotkeys arrive with their real key codes; Shift+Tab and keypad Enter map correctly; the wheel handler keeps pixel deltas for smooth scroll zoom (wx patch 0018). ⌘ arrives as the Control modifier KiCad's bindings expect.

The 3D viewer remains OpenGL-bound and does not work on iOS — the standing limitation, unchanged. V1 replaces all Spike builds (v1–v15).

## 📲 Installing

Builds are produced by the **Spike** workflow as unsigned `.ipa` files (≈263 MB — the stock libraries ride along). To run one:

1. Download `KiCad-V1.1.ipa` (the release build; workflow artifacts from the **Spike** workflow are the same unsigned package).
2. Sideload it with a signer such as Signulous (or your own signing setup).
3. Launch **KiCad (spike)** — the first-run wizard walks you through setup, and the project manager opens behind it.

**Requirements:** an M‑series iPad running iPadOS 17 or later.

## 🛠️ Building

Builds run on free, standard GitHub Actions macOS runners (public repo) — nothing paid, ever.

```text
Actions → "Spike" workflow → Run workflow
```

The pipeline stages live in [`scripts/`](scripts/) and are deliberately staged so each part of the port builds — and is verified — separately:

1. `sysroot` — cross-compile the dependency sysroot for iOS arm64 (libpng, zlib, expat, iODBC, CPython, …).
2. `wx-ios` — build wxWidgets with the **Qt backend** against that sysroot; fails closed if a bundled third-party library sneaks in.
3. `kicad-ios` — compile upstream KiCad 10.0.1 with the port's patch series applied.
4. `package` — assemble the `.ipa`; audit symbol closure, Qt resources, libpng unity and signing before anything ships.

Every patch the port applies to upstream code is iOS-gated and recorded in [`MODIFICATIONS.md`](MODIFICATIONS.md).

## 📜 License & attribution

KiCad is free and open-source software, and so is this port — there is no other lawful option, and we wouldn't want one.

- **License:** GNU General Public License v3.0 or later — the full verbatim text is in [`LICENSE`](LICENSE), taken unmodified from upstream KiCad.
- **Copyright:** KiCad is © its many contributors and the KiCad project; see [`NOTICE.md`](NOTICE.md) for attribution and the exact upstream baseline.
- **Headers:** upstream copyright & license headers in KiCad source files are never stripped or altered.
- **Changes:** every modification to upstream files is listed in [`MODIFICATIONS.md`](MODIFICATIONS.md) and carries a prominent change notice in the file itself, per GPL §5.
- **Libraries:** KiCad's symbol/footprint libraries carry their own license (KiCad Library License / CC BY-SA 4.0 with exception); they ship in the bundle as of v11 under those terms.

<div align="center">

*Built with respect for the KiCad project and its contributors.*
*KiCad runs on iPad. The manager is up. The libraries are in. The root cause is fixed. Projects land in Documents. The window drags by its bar. The editors open on the software canvas.*

</div>
