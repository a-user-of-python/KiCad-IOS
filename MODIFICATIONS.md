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
| wxWidgets | github.com/KiCad/wxWidgets (KiCad's patched fork) | branch `master` (exact commit recorded when the build pins it) |
| wxWidgets reference | github.com/wxWidgets/wxWidgets | tag `v3.2.8` (patch-audit baseline) |

## Changes

_None yet._ The spike is at the audit/first-build stage: upstream files are so
far used only unmodified (fetched fresh in CI, never vendored-and-edited
silently). Entries will appear here — path, date, what, why — the moment the
first patch lands.
