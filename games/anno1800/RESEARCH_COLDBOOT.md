# Anno 1800 — Cold-Boot Hebrew Research (2026-07-27)

**User's target:** game language = **English** (English menu + English live web panels),
**full Hebrew visible from COLD BOOT, with NO manual language switch**.

**VERDICT: 🔴 BLOCKED-BY-PROTECTION.**
The only clean/direct route — statically patching the engine's language-class check that
decides glyph-atlas breadth at cold boot — is blocked because that check lives inside
**Denuvo + VMProtect-virtualized code that is STILL FULLY PRESENT in the current build**
(and defeating it is out of scope). No editable data lever, no atlas cache on disk, no prior
art, and no dormant Hebrew/Arabic language slot exists. The two shipped end-states remain the
only practical options; the user's chosen **(B) English + one language re-init per launch**
stands. One **experimental, unproven** route (a DLL/Python mod that auto-fires the re-init at
boot) is the only path to the exact target that does not defeat DRM — ranked below with its
risks. This was **read-only** research: nothing in the install or `Documents\Anno 1800\` was
modified, and no game was launched.

---

## ITEM 1 — Protection status of the CURRENT `Anno1800.exe` (the decisive question)

**Result: Denuvo + VMProtect are fully present and UNCHANGED from the 2026-06 baseline.**

Install found via Steam (not Ubisoft Connect):
`C:\Program Files (x86)\Steam\steamapps\common\Anno 1800\Bin\Win64\Anno1800.exe`
(a second empty Steam library entry exists at `E:\SteamLibrary\...\Anno 1800` — no files).
File: **430,808,600 bytes (410.85 MB)**, mtime 2026-06-21 (install date), PE TimeDateStamp
2024-11-11 (VMProtect commonly preserves the real link stamp — not evidence of age).

### Measured PE section table (`pefile`)

| Section | VSize | RawSize | Entropy | Characteristics |
|---|---:|---:|---:|---|
| `.text` | 82,608,128 | 82,608,128 | 6.462 | CODE / EXEC / READ |
| `.xtext` | 16,302,080 | 16,299,008 | 4.915 | INIT_DATA / READ |
| `.rdata` | 6,811,648 | 4,453,888 | 1.951 | CODE / READ / **WRITE** |
| `.sxdata` | 3,358,720 | 512 | 0.000 | CODE / READ |
| `.sdata` | 151,552 | 149,504 | 5.432 | CODE / READ |
| **`.text1`** | **320,849,349** | **320,849,408** | **6.903** | **CODE / EXEC / READ / WRITE (RWX)** |
| `.data2` | 58,596 | 58,880 | 4.413 | CODE / READ |
| `.xdata` | 277 | 512 | 3.919 | CODE / EXEC / READ |
| `.idata` | 36 | 512 | 1.183 | CODE / READ / WRITE |
| `.debug$P` | 10,400 | 10,752 | 4.629 | CODE / EXEC / READ |
| `.edata` | 5 | 512 | 1.053 | CODE / EXEC / READ |
| `.udata` | 634 | 1,024 | 5.183 | CODE / EXEC / READ |
| **`.xtls`** | 97 | 512 | 2.290 | **CODE / EXEC / READ / WRITE (RWX) ← ENTRY POINT** |
| `.reloc` | 11,984 | 12,288 | 7.624 | CODE / READ / WRITE |
| `.impdata` | 53,896 | 54,272 | 5.689 | INIT_DATA / READ |
| `.data` | 3,354,816 | 3,355,136 | 7.206 | INIT_DATA / READ |
| `.rsrc` | 37,808 | 37,888 | 7.922 | INIT_DATA / READ |
| `.link` | 2,903,680 | 2,904,064 | 6.442 | INIT_DATA / DISCARDABLE / READ |

- **Entry point is in `.xtls`** (`AddressOfEntryPoint = 0x19a40020`), a tiny 97-byte
  **RWX** section — the classic VMProtect bootstrap stub. SizeOfImage = 436,555,776 (416.33 MB).
- **`.text1` = 306 MB, RWX (EXECUTE|READ|WRITE)** — the VMProtect/Denuvo virtualized-code
  container; real engine code is decrypted/reconstructed into it at runtime.
- **`.reloc` = 12,288 bytes = 0.0028 % of SizeOfImage** — trivially small for a 416 MB image
  (the real base-reloc directory is a separate 2.9 MB `.link`, `MEM_DISCARDABLE`).
- Section names `.xtext / .sxdata / .xdata / .xtls / .udata / .impdata / .text1 / .link` are a
  textbook **VMProtect** fingerprint (all present in the actual section table, not just strings).

### DRM string scan (streamed over the whole 430 MB file)

- **`denuvo` ×9** — genuine, with context: `denuvo_dl`, `denuvo_atd` (Denuvo anti-tamper-
  diagnostics module names), **`Denuvo Timing`** (runtime timing check), `super_diagnosis.bin`.
- **`vmprotect` ×2** — genuine: the crash-reporter flag **`vmprotectedbuild`** literally
  declares the build VMProtect-protected.
- `uplay` ×107, `ubisoft` ×46, `upc_r2` ×2, `steam_api` ×2 — Ubisoft Connect + Steam wrappers.
- No `Themida`/`WinLicense`/`SecuROM`/`Arxan` markers.

### Public cross-check

No **official** Denuvo removal. As of the latest information, all legitimate versions of
Anno 1800 require **Ubisoft Connect + Denuvo Anti-Tamper + VMProtect**. (A January-2026
community crack — "End of an era" — exists, but that is an unofficial crack, not an official
removal, and is out of scope.)

**Conclusion:** identical to the 2026-06 baseline (306 MB RWX `.text1`, entry in `.xtls`,
~12 KB `.reloc`). The language-class decision code the user needs to change is inside the
Denuvo+VMProtect-virtualized `.text1`. A static byte-patch is therefore **not possible without
defeating the protection**, which is out of scope. **The exe is off-limits.**

---

## ITEM 2 — Can a mod trigger the language re-init automatically at boot?

The user's own observation: switching language live in-game rebuilds the atlas BROAD, so the
whole problem reduces to "invoke that same re-init once, automatically, at boot." Findings:

### The integrated loader is XML-only (cannot run code)
The exe carries the **integrated** mod loader (string `EnableModLoader`, plus `ModOp`,
`ModOps`, `ModOpTemp`, `.//ModOpContent`, `Unknown ModOp`, `Load mods`, `Unload all mods`,
`{} active mods:`, `mod-loader.log`). Every one of these is **XML/ModOp/XPath patching** of
`data/config/...` files. There is **no** DLL-mod / code-hook string for the integrated loader.
An XML ModOp patches *data*; it cannot call a runtime function, so it **cannot** trigger the
language re-init. The user's live-deployed mod already uses exactly this (XML `texts_*.xml`
ModOps) — it is structurally incapable of the auto-reinit.

### The standalone loader CAN run code — but the path is unproven
`xforce/anno1800-mod-loader` (archived 2023-08, "now integrated into the game") and its
maintained fork `jakobharder/anno1800-mod-loader` support three mod types:
`"...XML auto merging and **DLL based mods**"` and `"Access to the **Anno python api**, the
game has an internal python API, **I am not yet at a point where I can say how much you can do
with it**..."`. The game genuinely embeds **Python 3.5** (`python35.dll` +
`data/script/lib/**` inside `data0.rda`), and the exe exposes the runtime symbols
`SetTextLanguage`, `GetTextLanguage`, `TextLanguageInitialisedEvent`,
`rdgs::CAccountSettings::InitializeTextAndAudioLanguage`, `UI-Flow: Start Waiting for
TextLanguage`.

So a **DLL mod** or a **Python mod** loaded by the *standalone* proxy-DLL loader is a
code-execution path that does **not** modify the packed exe (this is the game's own sanctioned
mod mechanism — not DRM circumvention). **But every step is unproven:**
1. The **Anno Python API is undocumented and unmapped even by the loader's own author** — no
   known language / re-init call is exposed to Python mods.
2. A **DLL mod calling the internal `SetTextLanguage`** would have to locate and call that
   function inside the VMProtect-**virtualized** `.text1` with the correct object/context —
   i.e. reverse-engineering the protected code (the same wall as the static patch, moved to
   runtime).
3. The broad-atlas rebuild is (per the baseline) triggered by switching to a **CJK-class**
   language; whether calling `SetTextLanguage("English")` with the *unchanged* value re-bakes
   at all is unknown (likely a no-op). The reliable trigger would be "switch to Korean, then
   back to English" driven programmatically — again through the internal API.
4. Injecting a third-party DLL into a Denuvo-protected process risks anti-tamper interaction
   (historically the loader hooks RDA filesystem loading, which Denuvo tolerated and Ubisoft
   integrated — but a *new* code path that calls into the language subsystem is untested).

This is the **only route to the exact target (A-rendering + B-label) that does not defeat
DRM**, but it is speculative, requires in-game experimentation (out of read-only scope here),
and may still collide with the virtualized code. Ranked as the top *experimental* option below.

### No command-line / engine.ini lever exists
`Documents\Anno 1800\config\engine.ini` is JSON; the only text keys are
`"TextLanguage": "English"`, `"AudioLanguage": "English"`, `"UseHighResUITextures"`, and the
dev flag `"GetTextsFromToolOne"`. There is **no** font / glyph / atlas / charset / breadth /
preload key anywhere in it. An exe string-scan for real `-flag` CLI switches returned only
garbage (code fragments from the decrypted `.text1`); the language config keys present
(`TextLanguage`, `SetTextLanguage`, `[Options TextLanguage]`, `GetTextsFromToolOne`,
`EnableGeneratedConfigs`, `PreloadConfigs`) contain nothing that widens the cold-boot atlas.

---

## ITEM 3 — Font / glyph-atlas cache on disk (pre-seed or delete?)

**Ruled out — there is no glyph-atlas cache on disk.** A read-only sweep of
`Documents\Anno 1800\`, `%LOCALAPPDATA%`, `%APPDATA%`, `%LOCALAPPDATA%\Ubisoft Game Launcher`
found only:
- the user's **own mod fonts** (`Documents\Anno 1800\mods\zzz_hebrew_translation\data\fonts\*.ttf`);
- `Documents\Anno 1800\shaders\precompiled\pso_cache.xml` — a **GPU pipeline-state-object
  cache** (D3D12 PSOs), unrelated to glyphs; deleting it only forces a shader recompile;
- Ubisoft launcher web-UI fonts (`Roboto-Regular.ttf`) — irrelevant.

The narrow atlas is **rebuilt in memory at each boot** from the fonts + the exe's language-class
decision. There is nothing on disk to pre-seed or delete to widen it.

---

## ITEM 4 — Prior art: any Anno 1800 mod that adds a non-shipped script?

**Negative — no precedent exists, and the AC-Unity precedent does not transfer.**
- The only font-related Anno 1800 mod found is a **Turkish font fix** (Nexus mod 74) — Turkish
  is **Latin-script + extended**, not a new script.
- Anno staff stated (2022 dev tracker) there are **no plans for an Arabic localization** of the
  Anno series.
- The "Thai font" discussion on Steam is for **Anno 117: Pax Romana** (the sequel), not Anno 1800.
- **The `hebrew` / `arabic` / `thai` strings in the exe are FALSE POSITIVES** — they are
  **Python 3.5 `encodings` codec aliases** (`csisolatinhebrew`, `iso8859_8`, `mac_arabic`,
  `iso8859_11`=Thai), embedded because the game ships Python 3.5. They are **not** Anno
  language tokens, so there is **no dormant Hebrew/Arabic language slot** to activate. (Verified
  by extracting the byte-context of every occurrence.)
- **Why the AC-Unity Thai breakthrough does not apply:** AC Unity (AnvilNext 2.0) gates
  rendering on a **codepoint→font routing table in editable forge data**, and its glyph
  coverage was the open problem. Anno's engine is different: the Hebrew **glyph coverage is
  already SOLVED** (the injected glyphs render fine after a live switch), and the *only*
  remaining gate is **cold-boot atlas BREADTH decided by a hardcoded language-class branch in
  DRM-protected code** — not a data table and not a font-routing problem. Different engine,
  different gate.

---

## ITEM 5 — Any other data lever / third end state?

**None found.** Independently confirmed across three configuration surfaces that the
atlas-breadth decision is **not exposed as editable data**:
1. `engine.ini` — only `TextLanguage` / `AudioLanguage` / `UseHighResUITextures` (item 2).
2. `data0.rda` → `data/config/gui/` — contains exactly the **13 shipped `texts_<lang>.xml`**
   (brazilian, chinese, english, french, german, italian, japanese, korean, polish,
   portuguese, russian, spanish, taiwanese) — **no hebrew/arabic/thai**, and **no per-language
   font/charset/atlas binding file**.
3. `data0.rda` → `data/config/export/main/asset/assets.xml` (90.9 MB master asset registry) —
   extracted read-only and scanned: **no FontLibrary/per-language font binding element and no
   `GlyphRange`/`CharSet`/`CodePage`/`Atlas*`/`GlyphSet`/`ScriptType`/`Broad*`/`Preload*`
   field**. The 97 `<Range>` elements are gameplay ranges; a single global `<FontRendering>`
   element carries no per-language breadth control.

This corroborates the 2026-06 baseline ("per-language binding records byte-identical CJK vs LTR
except name + font GUID; no charset list / Unicode-range table / broad flag anywhere"). There
is no third data-driven end-state.

---

## Ranked options

1. **Keep end-state (B) — English + one manual re-init per launch (current).**
   Zero risk, zero new work, English label + English web panels. This is the shipped state and
   the honest recommendation until/unless option 2 or 3 changes the picture.

2. **[EXPERIMENTAL, the only path to the exact target without defeating DRM] Auto-fire the
   language re-init at boot via a code mod.** Install the *standalone* `jakobharder` (xforce)
   proxy-DLL loader and add a **DLL mod or Python mod** that, once at startup, drives the
   language flow the way a live switch does (ideally: switch to a CJK-class language, then back
   to English) — giving A's broad cold-boot atlas with B's English label/web content.
   **Unknowns that must be resolved by in-game testing (out of scope for this read-only pass),
   in order of risk:** (a) does the Anno Python API expose language control at all? (b) if not,
   can a DLL mod call the internal `SetTextLanguage`/re-init without reaching into the
   VMProtect-virtualized code? (c) does the standalone loader coexist with the *integrated*
   loader + Denuvo without tripping anti-tamper? (d) does a same-value re-init re-bake, or is a
   CJK round-trip required? Risk: **medium-high**; reward: exactly the user's target. Would need
   a dedicated hands-on session; do NOT promise it works until (a)-(d) are demonstrated.

3. **Set a trip-wire for a future Denuvo removal.** Ubisoft has stripped Denuvo from many
   titles years post-launch. **Re-run the PE measurement (`scratchpad/anno_pe_measure.py`) after
   every Anno 1800 update.** If a future build shows the entry point back in a normal `.text`,
   a normal-sized `.reloc`, no 306 MB RWX `.text1`, and no `denuvo`/`vmprotectedbuild` strings,
   THEN a static patch of the language-class check becomes legitimate: the check sits near
   `TextLanguageInitialised` (baseline VA `0x140227522`) as a comparison of the language index
   against the CJK range (indices ~6-9). Zero-cost to re-check; opens the whole problem if it
   ever lands.

4. **End-state (A) — ship on the Korean slot (available TODAY, zero risk).** If the user ever
   values cold-boot Hebrew over the label/web-content, the Korean slot already delivers perfect
   Hebrew from boot with no switch; the cost is the language menu reading 한국어 and Korean live
   web panels. Rejected by the user, but it is the one *guaranteed* way to get cold-boot Hebrew
   today.

### Ruled out (with reason)
- **Static exe patch of the language-class check** — Denuvo+VMProtect present (item 1); out of scope.
- **Pre-seed / delete an atlas cache** — no glyph-atlas cache exists on disk (item 3).
- **Editable data config for atlas breadth** — none in engine.ini, `config/gui`, or `assets.xml` (items 2, 5).
- **Activate a dormant Hebrew/Arabic language slot** — the exe `hebrew`/`arabic` strings are Python codec aliases, not language slots (item 4).
- **XML/ModOp mod to auto-reinit** — XML ModOps patch data, cannot run code (item 2).
- **AC-Unity-style font-routing edit** — different engine; Anno's gate is a cold-boot atlas-breadth code branch, not a data font-routing table (item 4).

---

## Reproduction / tooling (all read-only, in scratchpad)
- `anno_pe_measure.py <exe>` — section table, entry-point section, `.reloc` ratio, entropy,
  data dirs, TLS, imports. **Re-run after any game update (option 3).**
- `anno_drm_scan.py <exe>` — streamed DRM marker scan (denuvo/vmprotect/themida/…).
- `anno_str_scan.py <exe>` — ASCII+UTF-16 string extraction, filtered for CLI/config/font/lang.
- `anno_ctx.py` / inline `data.find` — byte-context extraction (used to expose the Python-codec
  false positives).
- `games/anno1800/work/rda_reader.py grep|extract` — read-only RDA archive access (used on
  `data0.rda` for `config/gui` + `assets.xml`).

## מסמכים קשורים
- באותה תיקייה: [[games/anno1800/FEASIBILITY|FEASIBILITY]], [[games/anno1800/PIPELINE|PIPELINE]], [[games/anno1800/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#anno1800|CLAUDE_INDEX_games]]
