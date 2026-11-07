<div align="center">

# 🔌 KiCad‑iOS

### *The actual KiCad — running on iPad.*

**The real, upstream [KiCad](https://www.kicad.org/) 10.0.1, running on iOS / iPadOS.**
Not a recreation. Not a lookalike. The genuine program, rebuilt for Apple's tablets — and proven on real hardware.

[![Build Spike](https://github.com/a-user-of-python/KiCad-IOS/actions/workflows/spike.yml/badge.svg)](https://github.com/a-user-of-python/KiCad-IOS/actions/workflows/spike.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Upstream](https://img.shields.io/badge/upstream-KiCad%2010.0.1-orange.svg)](https://gitlab.com/kicad/code/kicad/-/tree/10.0.1)
[![Platform](https://img.shields.io/badge/platform-iPadOS%2017%2B-lightgrey.svg)](#-installing)
[![Status](https://img.shields.io/badge/status-runs%20on%20iPad-brightgreen.svg)](#-status)

**[🌐 Project website](https://a-user-of-python.github.io/KiCad-IOS/)**

</div>

---

> ⚠️ **Unofficial port — read this first.**
> This is an independent experiment. It is **not** affiliated with, sponsored by, or endorsed by the KiCad project or CERN. "KiCad" is a trademark of the KiCad project; the name is used here only to describe what this port is a port *of*.
> **Current reality:** the port runs. KiCad 10.0.1 builds for iOS arm64, installs on a real iPad, completes KiCad's own first-run wizard end to end, and opens the KiCad project manager — real menus, real icons, real windows — verified on hardware on 2026‑11‑06 (build v10). The work in progress is documented in the open in [`MODIFICATIONS.md`](MODIFICATIONS.md), where every change to upstream code is recorded.

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

### In active development — v11

The current build round lands the next layer, all of it already scoped and under way:

- **Editors open on tap.** The kiface module search learns the iOS bundle layout (modules live in `Frameworks/`), so the manager starts clean and each editor loads when opened.
- **Stock libraries ship in the bundle.** KiCad 10.0.1's symbol, footprint and template libraries, with the default library tables wired to them — first-run setup finds the defaults in place.
- **The manager screen, fully functional.** Every menu opens, every item acts, every button on the manager does its real job — audited control by control.
- **A floating window control.** A port-level control that floats above every window at all times, offering Close and Minimize; minimize shrinks the window and docks it to the left edge, Stage Manager style, and tapping it restores the window.
- **Windows stay on screen.** Top-level geometry is clamped to the visible area, and windows move by their titlebars.

When v11 lands, the editors get their own on-device pass: open a schematic, draw, save, reopen.

## 📲 Installing

Builds are produced by the **Spike** workflow as unsigned `.ipa` files (≈134 MB). To run one:

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
- **Libraries:** KiCad's symbol/footprint libraries carry their own license (KiCad Library License / CC BY-SA 4.0 with exception); if they are ever bundled here, that will be honoured and noted separately.

<div align="center">

*Built with respect for the KiCad project and its contributors.*
*KiCad runs on iPad. The manager is up. The editors are next.*

</div>
