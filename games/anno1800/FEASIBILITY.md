# Anno 1800 — Hebrew translation feasibility

**Source:** live Steam install `C:\Program Files (x86)\Steam\steamapps\common\Anno 1800` (single install). Proposed `games.id` = `anno1800`. Engine: Ubisoft Mainz / Blue Byte, the in-house "Anno"/RDA engine. Findings below were empirically confirmed against the real install and adversarially verified by a multi-agent workflow — nothing here is assumed.

## Verdict

# 🟢 GO — both gates PROVEN in-game (2026-06-21)

> **UPDATE 2026-06-21 (user-confirmed in-game):** the two gates below are **closed**.
> A diagnostic proof mod (`Documents\Anno 1800\mods\zzz_hebrew_proof\`) flipped main-menu
> labels via ModOp + injected font. Result: (1) the injected **Frank Ruehl font renders
> Hebrew perfectly** (no tofu); (2) an A/B on working menu GUIDs (New Game 154000 /
> Options 154002 / Credits 10438) showed **VISUAL-stored Hebrew reads correctly while
> LOGICAL reads reversed** → the native HUD is **NON-bidi** (WD2-menu/AC2 class) → store
> **VISUAL**. `build_mod.py` now defaults to VISUAL (`visual_line` = WD2's proven
> `_visual_line`). Phase 2 (translation, ~28,165 GUIDs) is unblocked. The original
> pre-proof analysis is kept below for the record.

The **easiest DEPLOY of any game in the project** — a pure loose-file text-override mod, no `.rda` repack, no anti-cheat, English locale kept intact. The two gates (native-HUD bidi mode, font glyphs) were the only unknowns; both are now resolved in-game: store **VISUAL**, ship the injected Frank Ruehl font.

| Factor | State | Detail |
|---|---|---|
| Archive format | ✅ cracked | RDA "Resource File V2.2"; pure-Python read-only reader proven (`work/rda_reader.py`) |
| Text spine | ✅ located | `data0.rda → data/config/gui/texts_english.xml` (3,869,738 B), **28,165** GUID/text records |
| Id-mapping | ✅ | numeric `<GUID>` shared across all 12 LTR languages → same slot in every `texts_<lang>.xml` |
| Encoding | ✅ UTF-8 | Hebrew stores identically to any LTR slot |
| Arabic slot (free RTL) | ❌ none | NO Arabic locale shipped → no engine RTL pipeline to inherit (the AC2-class case) |
| Deploy mechanism | ✅ trivial | loose-file mod, mod loader built into the game, no DLL, no repack, no admin |
| Anti-cheat / DRM | ✅ none | no EAC/BattlEye; `Documents\…\mods\` survives Ubisoft Connect "Verify files" |
| **Native-HUD bidi (logical vs visual)** | ⏳ **gate 1** | UNPROVEN — no Anno RTL mod has ever existed; needs an in-game proof string |
| **Hebrew font injection** | ⏳ **gate 2** | no shipped font has Hebrew glyphs → injection required, but LOW complexity (loose TTFs) |
| CEF stat-panel direction | ⏳ gate 3 (minor) | auxiliary web panels get free ICU bidi; optional scoped `direction:rtl` CSS |

## The mechanism — hijack an LTR slot, keep the locale

Anno 1800 declares **zero Arabic locale** (shipped: en, fr, de, ru, it, es, pl, ja, ko, zh-CN, zh-TW). So unlike CP2077 / SM2 / WD2 / GoWR there is **no engine Arabic-RTL pipeline to inherit for free** — this is the **AC2-class case**. The approach is therefore the LTR-slot hijack: ship Hebrew **inside `texts_english.xml`**, and the user keeps in-game Language = **English**. The voice-over is preserved automatically — `engine.ini` exposes `"TextLanguage"` and `"AudioLanguage"` as **separate keys**, so English text-slot ≠ English audio is fine, but here we don't even touch audio.

Because we override the English text slot in place, the in-game language selector stays on English and the mod auto-loads on top — no registry edit, no locale-id reverse-engineering, no `engine.ini` write.

## Where the text lives (the spine)

- **`data0.rda → data/config/gui/texts_english.xml`** — 3,869,738 bytes. ⚠️ Note: the per-language **`en_us0.rda` is Wwise voice AUDIO, not text** — the text for ALL languages lives in `data0.rda` as sibling `texts_<lang>.xml` files (`texts_{english,french,german,russian,spanish,italian,polish,chinese,taiwanese,japanese,korean,brazilian,portuguese}.xml`).
- **Schema** (UTF-8, CRLF): `<TextExport><Texts>` then repeated
  ```xml
  <Text><GUID>nnnnnn</GUID><Text>the string</Text></Text>
  ```
  The numeric `<GUID>` is the id-key **shared across every language** (same GUID = same slot in every `texts_<lang>.xml`) → this IS the id-mapping for translation. Verified firsthand against the extracted file (`<GUID>109692</GUID>` … `<GUID>109697</GUID>` consecutive records).
- **28,165** EN GUID/text records (measured). Cross-checked against German: **28,160 shared GUIDs**, of which **25,167 are genuinely localized** (DE ≠ EN; the rest are proper nouns / numbers left identical). **~4%** of records carry inline markup / placeholders to preserve byte-exact.
- Real samples — GUID 190465 "Anglerfish", 100998 "Icebreaker", 101065 "Expedition Lighthouse", 100684 "Old Nate's Harbour", 800701 "That's the spot!".

### Scope & corpus character

~**28,165** base strings; the count **grows with DLC / Season Pass** (~1.5–2× → roughly **40–60k** for a fully-DLC'd install). The corpus is **UI/content-dominant** — buildings, goods, production chains, quests, expeditions, the in-game newspaper, the encyclopedia, achievements, tutorials, tooltips — with only a **thin spoken-subtitle / quest-narration tail**. It is a city-builder: dialogue-light compared to CP2077 / SM2 / WD2, which makes the translation pass lighter and lowers the bidi risk surface (most text is short UI labels, not flowing mixed-script prose).

## Engine format (RDA "Resource File V2.2")

Archives are RDA "Resource File V2.2" — `maindata\data0.rda` … `data33.rda` (base content) plus per-language `en_us0.rda` / `de_de0.rda` / `fr_fr0.rda` / `ru_ru0.rda` (voice audio). This is an **open, well-documented format**. A **pure-Python, read-only reader is built and proven** at `games/anno1800/work/rda_reader.py`: it never loads a multi-GB archive into RAM — it seeks the tail/header and walks the singly-linked block chain (each 32-byte BlockInfo points to the NEXT block), zlib-inflating only the directory + the one file you extract. The full V2.2 binary layout (header 0x318, `firstBlockOffset` u64 @0x310, 32-byte BlockInfo chain at block tails, 560-byte DirEntry with `name[520]` UTF-16LE) is documented in that reader's docstring. We need this reader only for the **one-time READ extraction** of `texts_english.xml`; **repack is never required** (see deploy).

## Deploy — the easy part (loose-file mod, no repack)

This is where Anno is the cleanest of any game in the portfolio:

- **Loose-file mod, NO `.rda` repack.** Drop a `mods/<modname>/` folder under either `<install>/mods/` or (preferred) **`Documents\Anno 1800\mods\`**. The Documents path takes precedence, is immune to Ubisoft Connect "Verify files", and needs **no admin**.
- **Mod loading is built into the game.** The xforce/anno1800-mod-loader was integrated into Anno 1800 itself; the standalone repo is archived. There is **no DLL to install**.
- **Mod contents:**
  - `modinfo.json` — the manifest.
  - `data/config/gui/texts_english.xml` — a **ModOp XML patch** keyed by GUID (NOT a full file replacement). Schema:
    ```xml
    <ModOps>
      <ModOp Type="add" Path="/TextExport/Texts">
        <Text><GUID>100998</GUID><Text>שובר קרח</Text></Text>
      </ModOp>
    </ModOps>
    ```
    Adding a `<Text>` for an existing base GUID **overrides it**. ModOp `Type` options: `Add` / `Replace` / `Merge` / `Remove` / `AddNextSibling` / `AddPrevSibling`, selecting nodes by `Path` / `GUID`.
  - `data/fonts/<injected TTFs>` — the Hebrew-glyph-injected fonts as loose-file overrides.
  - (optional) a scoped CSS mod for the CEF stat panels (`direction:rtl`).
- **No anti-cheat** — no EAC, no BattlEye. RdaConsole (CLI) + RDAExplorer (GUI) exist for extract/repack, but are needed only for the one-time READ extraction — we have our own reader, so we never repack.
- **Activation:** user sets in-game UI Language = English; the mod auto-loads on top. **Removal = delete the folder.** Fully reversible.
- **Precedent:** full loose-file translation mods exist and prove the texts-override mechanism — the Ukrainian Nexus mod (539) replaces the RU slot, Czech (310), Russian overhaul (136). **No RTL precedent exists anywhere**, which is exactly why the two gates below are unproven rather than known-good.

## Gate 1 — native-HUD RTL render (the #1 unknown)

- The **main HUD is the engine's NATIVE GUI** (XML/binary layouts; UI art = `data/ui/*.dds` textures; `data/config/gui/` holds only the texts XML + a credits HTML), rendered with loose **TTF fonts in `data/fonts/`** — it is **NOT** CEF.
- **CEF / Chromium 108.4.13** (Chromium 108.0.5359.125, `libcef.dll`) drives **only auxiliary web panels** — the statistics / charts views (d3 / nvd3 / jquery under `data/config/http`), the debug console, and likely the Ubisoft Connect overlay. Those panels DO get full ICU / HarfBuzz bidi (logical → RTL for free); they are not the HUD.
- **Native-HUD bidi mode = UNPROVEN.** No Anno RTL / Arabic / Hebrew mod has ever existed and the engine never shipped an RTL locale, so we cannot know from precedent whether the native renderer does bidi (store **LOGICAL** Hebrew and let the engine reorder) or is non-bidi (store **VISUAL** / pre-reversed, the WD2-menu / AC2-class behavior). **Only a single in-game proof string settles it.** Default-safe assumption until proven: VISUAL may be required.

## Gate 2 — Hebrew font injection (the #2 unknown, but LOW complexity)

- **NO shipped font contains Hebrew** (U+05D0–U+05EA) — confirmed by cmap-checking all 15 `data/fonts/*.ttf`: `metaoffcpro-norm` + `metaserifoffcpro-medium` (Meta, the likely main HUD faces), `kelvinch*` (serif, the Belle-Époque headers), `heuristica*` (serif), `roboto-light` / `roboto-regular` — all Latin + Cyrillic only; `dfhei5a` / `dfpt_b5` / `md_cgothic_l` are CJK. → **Hebrew glyph injection is required** or every Hebrew string renders as tofu.
- **But the complexity is LOW.** They are plain **loose TTFs**, so we merge Hebrew glyphs into the Anno TTFs with `fontTools` and ship them as loose-file overrides (`data/fonts/*.ttf`) — far simpler than CP2077's CR2W TTF-embed or the SM2 / WD2 / GoWR DDS-atlas injection. The only sub-unknown is **which font the HUD actually draws** — so inject into **all** Latin UI fonts to be safe and let the proof string reveal the active one.
- **Atmosphere pick:** **Frank Ruhl Libre** (OFL serif, period-appropriate for the 1800s Belle-Époque look) for headers, with **Heebo / David** for body.

## Gate 3 — CEF stat-panel direction (minor)

The CEF web panels already get free ICU bidi, but they default to LTR layout. A **scoped `direction:rtl` CSS mod** (over `data/config/http`) fixes alignment in the statistics / charts views. Low effort, cosmetic, and only relevant to the auxiliary panels — not blocking.

## Comparison to prior games

| Game | Free RTL slot | Native bidi proven | Font work | Repack needed | Anti-cheat | Deploy difficulty |
|---|---|---|---|---|---|---|
| CP2077 | ✅ Arabic | ✅ | CR2W TTF embed | yes (WolvenKit) | no | medium |
| SM2 | ✅ Arabic | ✅ (cohtml) | DDS atlas | yes (TOC rewrite) | no | medium |
| WD2 | ✅ Arabic | ✅ (subs only; menu locked) | DDS atlas | yes (.loc encoder) | ⚠️ EAC | hard |
| GoWR | ✅ Arabic | ✅ | DDS atlas | yes (WAD/WTOC + LZ4) | no | hard |
| AC Shadows | ✅ Arabic | ✅ (in-game proven) | none (font ships Hebrew) | yes (v42 forge — gated) | no (Denuvo on exe only) | blocked |
| AC2 (classic) | ❌ none (LTR hijack) | ❌ no engine bidi → visual | DDS atlas | yes (forge v25) | no | medium |
| **Anno 1800** | ❌ none (LTR hijack) | ⏳ **unproven** | **loose TTF merge (simplest)** | **NO** | **none** | **easiest** |

Anno is the **easiest deploy in the portfolio** — loose-file, no repack, no anti-cheat, keep-locale. It shares **AC2's "no Arabic slot"** problem (must hijack the English slot) and an **unproven native bidi like WD2's menus** (could be visual-only). But its **font work is the simplest** anywhere here: plain loose TTFs merged with fontTools, no CR2W embed and no DDS atlas. The net is: the hard parts that broke every prior game (repack, anti-cheat, locale gating) are all absent — the only risk left is the one cheap in-game test.

## Next steps / open gates

The decisive move is a **single in-game proof mod** — do not invest in a full translation run until it clears:

1. **Build the proof mod (loose-file):** pick a high-visibility, always-on-screen menu GUID (e.g. a main-menu button or a settings label), write a one-string ModOp override in `data/config/gui/texts_english.xml`, inject Hebrew glyphs into **all** Latin UI fonts (`metaoffcpro-norm`, `metaserifoffcpro-medium`, `kelvinch*`, `heuristica*`, `roboto*`) and ship them under `data/fonts/`. Deploy to `Documents\Anno 1800\mods\`.
2. **Launch and read the screen** — this resolves both gates at once:
   - **Gate 1:** does the string read RTL (logical bidi works → store LOGICAL) or mirror-reversed (non-bidi → store VISUAL / pre-reversed)?
   - **Gate 2:** does the Hebrew render as real glyphs (font injection correct) or tofu (wrong font / cmap)? — and which font face it used reveals the active HUD font.
3. **Gate 3 (optional, parallel):** add a scoped `direction:rtl` CSS mod for the CEF stat panels.
4. **If the proof clears** → run the standard pipeline: extract the EN spine → translate EN→Hebrew with the local-LM trio (token-budget batching, `validate()` + strike/park, atomic resumable state — copy the SM2 trio as the template; preserve every inline markup/placeholder byte-exact) → emit the full ModOp `texts_english.xml` keyed by GUID + the injected fonts → deploy loose → **publish** (GitHub release + Worker slug `anno1800-hebrew` + Supabase `games` row + `mod_version_history`, the 4 surfaces in lockstep). If gate 1 turns out VISUAL, add a build-time `visual()` pre-reversal pass (FriBidi / python-bidi; Hebrew needs no joining) before emitting the ModOp, exactly like WD2's UI path.

## Sources

- **RDA tooling / format:** anno-mods/RdaConsole (CLI), lysannschlegel/RDAExplorer (GUI, GPL-3) — extract/repack reference (read-only use here).
- **Mod loader:** xforce/anno1800-mod-loader (integrated into the game; standalone repo archived).
- **Modding / ModOp schema:** anno-mods/modding-guide; anno1800.fandom.com → "Modding".
- **Translation-mod precedent:** Nexus Mods Anno 1800 — Ukrainian (539, RU-slot replacement), Czech (310), Russian overhaul (136). No RTL precedent on any.
- **No Arabic locale:** Ubisoft devtrackers / community — "no Arabic planned" for Anno 1800 PC.

## מסמכים קשורים
- באותה תיקייה: [[games/anno1800/PIPELINE|PIPELINE]], [[games/anno1800/RECON|RECON]], [[games/anno1800/RESEARCH_COLDBOOT|RESEARCH_COLDBOOT]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#anno1800|CLAUDE_INDEX_games]]
