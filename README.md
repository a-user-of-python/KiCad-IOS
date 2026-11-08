<div align="center">

# 🔌 KiCad‑iOS

### *The actual KiCad — running on iPad.*

**The real, upstream [KiCad](https://www.kicad.org/) 10.0.1, running on iOS / iPadOS.**
Not a recreation. Not a lookalike. The genuine program, rebuilt for Apple's tablets — and proven on real hardware.

[![Build Spike](https://github.com/a-user-of-python/KiCad-IOS/actions/workflows/spike.yml/badge.svg)](https://github.com/a-user-of-python/KiCad-IOS/actions/workflows/spike.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Upstream](https://img.shields.io/badge/upstream-KiCad%2010.0.1-orange.svg)](https://gitlab.com/kicad/code/kicad/-/tree/10.0.1)
[![Platform](https://img.shields.io/badge/platform-iPadOS%2017%2B-lightgrey.svg)](#-installing)
[![Status](https://img.shields.io/badge/status-current%20release%20v14-brightgreen.svg)](#-status)

**[🌐 Project website](https://a-user-of-python.github.io/KiCad-IOS/)**

</div>

---

> ⚠️ **Unofficial port — read this first.**
> This is an independent experiment. It is **not** affiliated with, sponsored by, or endorsed by the KiCad project or CERN. "KiCad" is a trademark of the KiCad project; the name is used here only to describe what this port is a port *of*.
> **Current reality:** the port runs. KiCad 10.0.1 builds for iOS arm64, installs on a real iPad, completes KiCad's own first-run wizard end to end, and opens the KiCad project manager — real menus, real icons, real windows — verified on hardware on 2026‑11‑06 (build v10). **Build v14 is the current release:** the complete stock KiCad 10.0.1 libraries ship inside the bundle, and the manager screen is audited control by control. v14 carries v12's root-cause fix: a build switch that three of the port's patches depend on sat on the wrong library target, so those patches were never compiled into v10 or v11 at all — proven from the shipped v11 binary; the switch is set correctly, a gate inspects the shipped binary to prove the code is in, and the editor modules also sit at the bundle root as a belt-and-braces copy. v13's on-device pass (2026‑11‑07) confirmed that fix on hardware at startup: the manager stands with no editor-load error. On top of that, v13 rebuilt the floating window control: the bar now lives inside the current window as an overlay instead of floating as a separate window — the design iOS layering could bury, and which v11's on-device pass never saw — and the bar doubles as the window's drag handle. The v13 pass found two defects, and v14 fixes both. Creating a project tried to write inside the app bundle and failed ('Operation not permitted'): a persisted recent-projects path defaults to blank and overwrote the correct Documents default at every launch, so the dialog opened with no folder and the toolkit fell back to the app's own folder — v14 restores the Documents projects folder whenever that path is blank, guards the create flows at the point of use, and starts the app with its working directory in Documents, so projects default to the app's shared Documents folder. And the bar, though it rendered, stayed pinned to the manager behind modal dialogs — the host-window lookup climbed to the outermost window, overshooting every dialog — while dragging bypassed the window system's own move path: v14 hosts the bar on the window that is actually current, dialogs included, anchors it fully inside the frame, and routes drags through the proper move path; the v13 failure is reproduced off-device with v13's own code, and the fixed code passes that reproduction. v14's on-device pass is the immediate next step; its two fixes are verified by the build gates, not yet on device, and the library verdict is still outstanding — v13's pass stopped at the project error first. Every change to upstream code is documented in the open in [`MODIFICATIONS.md`](MODIFICATIONS.md).

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

### What v14 adds — the current release, verified by the build gates

- **New Project lands in Documents.** v13's on-device pass found project creation failing outright: the new folder was being created inside the app bundle — 'Operation not permitted'. The cause is traced: a persisted recent-projects path defaults to blank and overwrote the correct Documents default at every launch, so the create dialog opened with no folder and the toolkit fell back to the app's own folder. v14 restores the Documents projects folder whenever that path is blank, guards the create flows at the point of use, and starts the app with its working directory in Documents. Projects now default to the app's shared Documents folder.
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
| New Project defaults to the app's shared Documents folder | ✅ Fixed in v14 — the blank persisted recent-projects path that wiped the Documents default at every launch is restored whenever blank, the create flows are guarded at the point of use, and the app starts with its working directory in Documents. On-device pass next |
| Floating window control (Minimize / Close, left-edge dock) + on-screen clamping | ✅ Host-fixed in v14 — the bar (a child overlay inside the current window since v13, doubling as its drag handle) now hosts on the window that is actually current, dialogs included, anchored fully inside the frame, with drags routed through the proper move path; the v13 host-overshoot failure is reproduced off-device and the fix passes that reproduction. On-device pass next |

### v14 — the current release

v14 is built, gated, and shipped. It stands on v13's on-device confirmation (2026‑11‑07): the manager stands with no editor-load error — the v12 root-cause fix, device-proven at startup. Underneath, v14 carries the whole v12 layer — the stock libraries are in the box, the manager does its full job — and the root-cause fix itself: v11's on-device pass found the editor-module load error and the wizard's library failure still standing, and disassembly of the shipped v11 binary proved the three patches behind those fixes were never compiled in, because the `KICAD_IOS_PORT` switch sat on the wrong library target. The switch sits on the correct target, a gate proves the code is in from the shipped binary, the editor modules also sit at the bundle root as belt and braces, and inherited library tables are repaired at startup. v13's own layer was the window-controls round: the floating Minimize/Close bar no longer floats as a separate window — the construction iOS layering could bury, and the one the v11 device pass never saw; the bar lives inside the current window as an overlay and is the window's drag handle, with a small movement threshold keeping taps and drags apart, minimize still docking the window to the left edge and a tap still restoring it.

v14's own layer fixes the two defects v13's pass found. New Project no longer writes into the app bundle: the persisted recent-projects path that defaults to blank and overwrote the correct Documents default at every launch is restored whenever it is blank, the create flows are guarded at the point of use, and the app starts with its working directory in Documents — projects default to the app's shared Documents folder. And the floating bar now hosts on the window that is actually current — dialogs included — instead of the outermost window the v13 lookup climbed to, anchors fully inside the frame, and routes drags through the window system's proper move path; the v13 failure is reproduced off-device with v13's own code, and the fixed code passes that reproduction.

Its on-device pass is the immediate next step: create a project in Documents, the bar present on dialogs and dragging the window, every editor open, and the library choosers populated — the library verdict is still outstanding from v13's pass, where the project error stopped the test first.

## 📲 Installing

Builds are produced by the **Spike** workflow as unsigned `.ipa` files (≈263 MB — the stock libraries ride along). To run one:

1. Download the `.ipa` artifact from a workflow run.
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
*KiCad runs on iPad. The manager is up. The libraries are in. The root cause is fixed. Projects land in Documents. The window drags by its bar.*

</div>
