<div align="center">

# 🔌 KiCad‑iOS

### *The actual KiCad — running on iPad.*

**An experimental port of the real, upstream [KiCad](https://www.kicad.org/) source code to iOS / iPadOS.**
Not a recreation. Not a lookalike. The genuine program, rebuilt for Apple's tablets.

[![Build Spike](https://github.com/a-user-of-python/KiCad-IOS/actions/workflows/spike.yml/badge.svg)](https://github.com/a-user-of-python/KiCad-IOS/actions/workflows/spike.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Upstream](https://img.shields.io/badge/upstream-KiCad%2010.0.1-orange.svg)](https://gitlab.com/kicad/code/kicad/-/tree/10.0.1)
[![Platform](https://img.shields.io/badge/platform-iPadOS-lightgrey.svg)](#)
[![Status](https://img.shields.io/badge/status-spike%20%2F%20work%20in%20progress-yellow.svg)](#-honest-status)

</div>

---

> ⚠️ **Unofficial spike — read this first.**
> This is an independent experiment. It is **not** affiliated with, sponsored by, or endorsed by the KiCad project or CERN. "KiCad" is a trademark of the KiCad project; the name is used here only to describe what this port is a port *of*.
> **Current reality:** this repository is at the *investigation & first-build* stage. There is no finished app yet, and nothing here should be read as claiming one. Progress — including hard blockers, when we hit them — is documented in the open in [`MODIFICATIONS.md`](MODIFICATIONS.md) and the spike reports.

---

## ✨ What this is

KiCad is the world's leading open-source electronics design suite — schematic capture, PCB layout, and a family of companion tools, all in one project manager. It runs on Windows, macOS and Linux… but not on the iPad in your bag.

This project asks a simple question with a complicated answer:

> **Can the actual KiCad program — its own source code, its own windows, its own buttons — run on an M‑series iPad?**

The goal experience:

1. Launch the app → KiCad's familiar **project manager** window appears.
2. Tap **Schematic Editor** → the real `eeschema` opens in its own window.
3. Tap **PCB Editor** → the real `pcbnew` opens in its own window.
4. Every button, switch, toggle and control is **really there and really works** — with touch, Apple Pencil, keyboard and mouse.

## 🧭 How it works — the route

KiCad was never written for iOS. Four walls stand between its source code and an iPad, and this port has a deliberate answer for each:

| # | The wall | The route around it |
|---|----------|--------------------|
| 1 | KiCad's UI is built on **wxWidgets**, which has no iOS port. | **wxQt bridge** — KiCad's wx code runs on wxWidgets' Qt backend (`wxQt`), and Qt *does* run on iOS (proven in this workspace by a full Qt Widgets app port). KiCad's own CMake already recognises a `qt` wx port. KiCad's patched wx fork is audited patch-by-patch against wxQt. |
| 2 | KiCad's editors normally run as **separate processes** (Kiway). iOS apps are single-process. | **Single-process hosting** — each editor opens as its own window inside one app process. |
| 3 | **Python** scripting is baked into desktop builds. | **Off.** Built with scripting disabled — schematic/footprint library import (`.kicad_sym` / `.kicad_mod`) is core KiCad code and needs no Python. |
| 4 | The drawing canvas is **desktop OpenGL**, which iOS doesn't provide. | **Correctness first:** KiCad's built-in software (Cairo) fallback canvas for the spike; GL translation (Zink over MoltenVK) is the stretch goal. |

Under the hood, the heavy lifting reuses a Qt‑for‑iOS toolchain (Qt 6 via `aqtinstall`, desktop + iOS kits) already proven on a shipping Qt Widgets iPad app.

## 📊 Honest status

| Milestone | State |
|---|---|
| Upstream pinned (KiCad **10.0.1**, commit `2db9e5a7…`) | ✅ Done |
| Repo, licensing & attribution in place | ✅ Done |
| wx fork patch audit vs. wxQt | 🔄 In progress |
| wxQt compiled for iOS (arm64) | ⏳ Not yet |
| KiCad configured for iOS (scripting off) | ⏳ Not yet |
| KiCad project manager launches on iPad | ⏳ Not yet |
| Schematic / PCB editors open as windows | ⏳ Not yet |
| Real `.kicad_sch` edited on device | ⏳ Not yet |

*This table is updated as the spike moves. A well-evidenced "this is blocked, and here is exactly why" is a valid spike outcome — a fake UI is not.*

## 🛠️ Building

Builds run on free, standard GitHub Actions macOS runners (public repo) — nothing paid, ever.

```text
Actions → "Spike" workflow → Run workflow
```

The pipeline stages live in [`scripts/`](scripts/) and are deliberately staged so each wall above is attacked — and its result logged — separately:

1. `qt` — install Qt 6 (desktop + iOS kits).
2. `wx` — build wxWidgets (KiCad's fork) with the **Qt backend** for iOS arm64.
3. `kicad-configure` — configure upstream KiCad 10.0.1 against that wx, scripting **off**.
4. `kicad-build` — compile as far as the source allows; package an unsigned `.ipa` if a binary links.

## 🗺️ Roadmap

- [x] Pin upstream, set up repo & GPL hygiene
- [ ] Catalogue KiCad's wx-fork patches; mark each *carried / workaround / blocker*
- [ ] wxQt-for-iOS compiles and links a test frame
- [ ] KiCad CMake configure passes for iOS
- [ ] `common` + `gal` libraries compile
- [ ] Project manager binary links; packaged as unsigned IPA
- [ ] Manager launches on device; editors open as windows (single-process Kiway)
- [ ] Touch pass: every control reachable & operable by finger, Pencil, keyboard + mouse
- [ ] Stretch: open & edit a real `.kicad_sch`; GL canvas via Zink/MoltenVK

## 📜 License & attribution

KiCad is free and open-source software, and so is this port — there is no other lawful option, and we wouldn't want one.

- **License:** GNU General Public License v3.0 or later — the full verbatim text is in [`LICENSE`](LICENSE), taken unmodified from upstream KiCad.
- **Copyright:** KiCad is © its many contributors and the KiCad project; see [`NOTICE.md`](NOTICE.md) for attribution and the exact upstream baseline.
- **Headers:** upstream copyright & license headers in KiCad source files are never stripped or altered.
- **Changes:** every modification to upstream files is listed in [`MODIFICATIONS.md`](MODIFICATIONS.md) and carries a prominent change notice in the file itself, per GPL §5.
- **Libraries:** KiCad's symbol/footprint libraries carry their own license (KiCad Library License / CC BY-SA 4.0 with exception); if they are ever bundled here, that will be honoured and noted separately.

<div align="center">

*Built with respect for the KiCad project and its contributors.*
*If this spike succeeds, the credit is upstream's. If it fails, the report will say exactly where.*

</div>
