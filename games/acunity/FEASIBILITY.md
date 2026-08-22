# Assassin's Creed Unity — Hebrew translation FEASIBILITY

**Verdict: 🟢 GO — "prove the repack, then run".** AC Unity is the **strongest-positioned** AC in
this repo: it ships an **official Arabic text locale** (so the Arabic-slot RTL shortcut applies —
unlike AC2), its `scimitar` v27 container is **fully cracked and read end-to-end** by our own
pure-Python tool, and its loc text is **stored uncompressed** (readable with no codec). It is a
multi-session engineering project (like AC2/GoWR/SM2/WD2), gated — as every game here is — on a
**write/repack round-trip** and **Hebrew font glyphs**, plus one Unity-specific wrinkle (the Arabic
UI slot is an empty stub → menus need a small decision).

This document + `RECON.md` + `PIPELINE.md` are the Phase-1 foundation. **The decisive
research synthesis is `BRIEF.md` (read it first for the resolved gates + verdict).** The next
milestone is an identity repack round-trip → a single Hebrew test string in-game.

> **Research sweep (2026-07-01) resolved the open gates — see `BRIEF.md`.** Net verdict is
> **🟢 GO-WITH-CAVEATS**, gated on **one** thing: a v27 forge repack that the game loads **and
> that survives Ubisoft Connect's file-integrity check** (Connect can demand an activation key
> after a forge swap → the clean answer is likely the runtime Asset-Overrides loader, which
> leaves the on-disk forge vanilla). Three findings below are now CORRECTED/CONFIRMED:
> - **Codec = LZO CONFIRMED** (per-block mode byte: 0/1→lzo1x, 2→lzo2a, 5→lzo1c; Oodle absent).
>   Loc is STORED → translation READ needs no codec at all.
> - **Repacker = AnvilToolkit** (free, Nexus, Unity-supported, XML export/import of the
>   LocalizationPackage) — GUI-only, closed .NET → usable manually, **not launcher-bundle-able**
>   (a bundled path needs our own pure-Python forge/`.data` writer + `liblzo2`).
> - **Font is native AnvilNext DDS-atlas + `.ffd`, NOT Scaleform** (correction below), and the
>   **bidi default flips to VISUAL, NOT logical** (Unity-era Anvil had no engine RTL; RTL was
>   added only in Valhalla/Mirage — verify with the menu-proof).

---

## Why GO

| Pillar | Status | Evidence (all locally verified) |
|---|---|---|
| **Archive format (read)** | ✅ solved + tool built | `scimitar` v27 container fully parsed by `tools/acu_forge.py` (header → 20-byte record array → 192-byte named descriptors → resource by name). Verified on DataPC.forge (1620 res) + others. |
| **Text location + format** | ✅ identified + read | `DataPC.forge` → `TLocalizationPackage_<Lang>` (+`_Subtitles`, `_EManual`), **char-INDEX serialization** (AC2-class), **STORED uncompressed** → extracted English (345 KB) + Arabic. |
| **Arabic slot (RTL shortcut)** | ✅ **PRESENT** | `TLocalizationPackage_Arabic` + `_Subtitles` (204 KB, real) + `_EManual`; `Support/Readme/Arabic/`. Arabic is an official MENA text locale → the engine's RTL is Ubisoft-tested. |
| **Font** | 🟡 approachable | **CORRECTED: native AnvilNext DDS-atlas + `.ffd` (Fire_Font_Descriptor), NOT Scaleform** (research CONFIRMED "fonts are DDS, not TTF", per-script atlases in the `extra` forge). Shipped font does NOT cover Hebrew ("Arabic uses a different font → blank symbols") → inject `U+05D0–05EA` into the atlas+`.ffd` (AC2/SM2/WD2 family). FFDConverter stops at AC Rogue → v27 `.ffd` reader may need adapting. |
| **Deploy / anti-cheat** | 🟡 clear-ish | Uplay/VMProtect, **no Denuvo**; asset forges **NOT integrity-checked at load** (runtime Asset-Overrides loader parses bytes with zero validation → a bad datapack just crashes, isn't rejected). ⚠️ **BUT Ubisoft Connect can demand an activation key after a forge overwrite** → prefer the runtime loader (leaves on-disk forge vanilla, verify-proof). Back up before writing. |
| **Repack (write)** | 🟡 tool exists, deploy-integrity is the gate | **AnvilToolkit repacks v27 + imports the LocalizationPackage via XML (CONFIRMED free + Unity-supported); community has shipped a game-loadable modified Unity forge.** Residual gate = the Ubisoft-Connect integrity check on `DataPC.forge` (activation-key demand) + a launcher-bundle-able pure-Python writer (AnvilToolkit is GUI-only .NET). Char-index encode is bypassed by AnvilToolkit's XML for v1. |

## Strategy (two text surfaces, decided per-surface)

1. **Subtitles → the Arabic subtitle slot.** Fill Hebrew into `TLocalizationPackage_Arabic_Subtitles`
   (a real 204 KB slot). ⚠️ **CORRECTED bidi default → store Hebrew VISUAL (pre-reversed), NOT
   logical.** Peer-reviewed research (Al-Batineh 2024/2021) shows the Unity-era AnvilNext engine
   had **no native RTL/bidi** (added only in Valhalla/Mirage); Unity's shipped Arabic looks right
   because the order was **pre-baked into the DATA**. So `visual_line`-reverse the Hebrew (AC2/WD2
   method). Confirm with the one-line proof (VISUAL correct + LOGICAL mirrored = VISUAL). **Still
   the easy win** — the slot is real and dev-tested.
2. **UI / menus → decide via the menu-proof.** The Arabic **UI** package is a 139-byte empty stub
   (Ubisoft shipped Arabic subtitles + English menus). Two options, chosen by an in-game test:
   - **(a) Populate the Arabic UI slot** with Hebrew (grow 139 B → ~English-sized). If a populated
     Arabic UI renders RTL → free RTL menus too. Cost: a size-growing forge repack.
   - **(b) Hijack an LTR UI slot** (e.g. English) + store Hebrew **VISUAL** (pre-reversed), the AC2
     method. No RTL from the engine; we bake direction. Safer if (a) doesn't render.
3. **Font.** Inject Hebrew glyphs (`U+05D0–05EA`) into the embedded/FTX font that renders the slot.

## The engineering gates (same shape as every game here — see `BRIEF.md` for full detail)

1. **DataFile chunk codec — ✅ LZO (resolved).** Compressed chunks use LZO (mode byte 0/1→lzo1x,
   2→lzo2a, 5→lzo1c; stored when src==dst); no Oodle. Loc is stored → READ needs no codec; fonts do.
2. **Forge v27 REPACK (identity round-trip) — THE deploy gate.** A free repacker exists (**AnvilToolkit**,
   Unity-supported, XML loc export/import) AND the full v27 write format is documented (index+name tables
   in lockstep + per-block/data checksums). **A 2025 community English-loc mod ships a modified
   `DataPC.forge` the game loads → the chain is proven achievable.** Residual risk = Ubisoft-Connect
   integrity (activation-key demand after a forge swap) + a launcher-bundle-able pure-Python writer
   (AnvilToolkit is GUI-only). First move: Stage-0 identity round-trip.
3. **Char-index loc encode** — decode the u16 char-index payload → translate → rebuild the char
   dictionary with Hebrew codepoints → re-encode (+ recompute checksums). AnvilToolkit's XML bypasses
   this for a manual v1; a pure-Python `acu_loc.py` is the launcher path.
4. **Hebrew font glyphs** — inject `U+05D0–05EA` into the **`.ffd` (Fire_Font_Descriptor) + DDS atlas**
   (WD2 model; FFDConverter reference), NOT a TTF.
5. **In-game bidi test — default VISUAL** (Unity-era Anvil has no engine RTL; we pre-reverse with
   `acu_rtl.py`). Confirm per surface with the menu-proof + a vanilla Arabic-slot check.

## The one real risk + how we de-risk it

**No AC Unity *text* mod is known to exist, and the loc/repack write path is unproven here.**
Mitigation = the project's standard **prove-before-invest** discipline: (1) identity repack of an
unchanged resource → game boots identically; (2) a single Hebrew test string with its glyph drawn →
proves the char-index encode + font + RTL end-to-end; **only then** scale to translation. Because
the Arabic slot + font machinery is Ubisoft-tested and the container is fully read, the residual
risk is concentrated entirely in the write/repack step.

## Difference from the other Ubisoft games in this repo

- **vs AC2** (`games/assassinscreed2/`, scimitar v25): same char-index loc + Anvil DataFile chunks +
  `.ffd`/DDS-atlas fonts + no engine bidi (**both store VISUAL**). Unity **has an Arabic locale** (AC2 had
  none) → Unity gets a real, dev-tested Arabic *subtitle* slot to hijack (still visual-reversed), whereas
  AC2 must hijack an LTR slot for everything. Unity's repacker (AnvilToolkit) supports it directly.
- **vs AC Shadows** (`games/acshadows/`, scimitar v42): ACS uses Oodle + a TTF that already carries
  Hebrew + a gated v42 repacker. Unity is older/simpler (stored loc, no Oodle for text) but its font
  likely lacks Hebrew (injection needed). Unity's repacker landscape is a 2014-era, well-modded title
  → better tool availability than ACS's Discord-gated v42 beta.
- **vs WD2/GoWR/CP2077**: those inherited a real Arabic slot too; Unity is the same play, with the
  extra wrinkle that its Arabic **UI** (not subtitles) is an empty stub.

## What is explicitly NOT yet done

- No game file modified — everything so far is read-only recon + the read tool.
- The forge **write/repack** path is not implemented or exercised.
- The char-index payload **decode** (u16 → text) is understood in shape but not implemented.
- No Hebrew glyphs drawn; no in-game verification of RTL/font.
- No translation started (by design — prove the pipeline first).
- ~~Exact compressed-chunk codec, the community repacker name, and the precise Arabic-selection
  method are pending the research sweep~~ **→ RESOLVED by the 2026-07-01 research (see `BRIEF.md`):
  codec = LZO; repacker = AnvilToolkit; selection = in-game Options / `localization.lang` /
  registry. The remaining open items are the identity round-trip, the Ubisoft-Connect
  integrity-check behavior, the VISUAL-bidi proof, and the DDS/`.ffd` font injection.**

## מסמכים קשורים
- באותה תיקייה: [[games/acunity/BRIEF|BRIEF]], [[games/acunity/PIPELINE|PIPELINE]], [[games/acunity/RECON|RECON]], [[games/acunity/RESEARCH_FONT|RESEARCH_FONT]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#acunity|CLAUDE_INDEX_games]]
