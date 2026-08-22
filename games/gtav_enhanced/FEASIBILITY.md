# GTA V Enhanced — FEASIBILITY

**Verdict: 🟢 GO — but one manual step is unavoidable.**

Every engineering gate is closed and verified. The single blocker is that GTA V Enhanced,
exactly like GTA V Legacy, ships **NG-encrypted archives whose keys only OpenIV holds**,
so the game's own vanilla text cannot be read until the user creates the OPEN `mods\`
folder once. After that one step the whole pipeline is automated.

## Why the port is cheap

| what | Legacy | Enhanced | consequence |
|---|---|---|---|
| container | RPF7 (`7FPR`) | RPF7 (`7FPR`) — measured | reader/writer reused as-is |
| text format | GXT2 | GXT2 | codec reused as-is |
| override | `mods\` + `OpenIV.asi` (`dinput8.dll`) | `mods\` + `OpenRPF.asi` (`dsound.dll`) | same mechanism, different loader |
| RTL | no bidi → store **VISUAL** | same renderer family | `visual_line()` reused |
| fonts | Scaleform `.gfx`, Hebrew injected | Scaleform `.gfx` | injected fonts reused |

**The decisive property: the translation corpus is keyed by the English source string,
not by a hash, a key name or a file name.** So it does not care what Enhanced renamed,
re-hashed or re-ordered — any English line Enhanced shares with Legacy is translated
automatically, and anything new stays English.

Validated by rebuilding the Legacy corpus through the *new* Enhanced scripts:

```
translations: 141,001 EN->HE
entries : 278,749
hebrew  : 165,093  (59.2%)
english : 113,656  fallback
token deviations: 47 distinct
```

These reproduce the documented Legacy build **exactly** (278,749 / 165,093 / 47), which
is the proof the ported code path is correct. The 59.2 % is not a coverage gap — the
remaining lines are the 51,920 deliberately-skipped codes, brand names and identifiers
plus untranslated tails, and they render as ordinary English.

## The one hard blocker 🔴

`build_hebrew.py` must overlay Hebrew on **Enhanced's own vanilla gxt2**, not on Legacy's.

> A gxt2 file **replaces an entire table**. Shipping Legacy's built file into Enhanced
> would delete every Enhanced-only key in that table — those entries would render
> **blank**, which is worse than English.

Reading Enhanced's vanilla gxt2 requires the OPEN archives, which requires OpenIV. There
is no way around it from here:

- all 220 nested archives in `update.rpf` are NG; all 97 dlcpacks are NG
- no loose `.gxt2` / `.gfx` anywhere in the install
- `rpf.cache` / `index.bin` carry no filenames
- the NG keys were rotated for the 2025 builds and are OpenIV-only

This is **the same bootstrap gap already documented for Legacy** — not a regression and
not something a better tool on our side would solve.

## Risks

- **Enhanced-only strings** — unknown until the vanilla tables are read. They stay
  English (safe). `build/coverage.json` lists every one of them, so a follow-up
  translation pass is a well-defined work item rather than a guess.
- **Font path drift** — if Enhanced moved or renamed the Scaleform libraries, the
  extractor reports it instead of silently producing an empty package.
- **Game updates** — Rockstar patches Enhanced; a patch that rewrites `update2.rpf`
  reverts the mod. Re-running the deploy restores it (same as Legacy).
- **In-game verification is still owed.** Nothing here has been seen rendering in
  Enhanced yet; the first launch after deploy is the real gate.

## Not attempted, on purpose

Defeating the NG encryption, or any integrity/anti-tamper mechanism, is out of scope for
this project. The supported path is the community's own `mods\` override.
