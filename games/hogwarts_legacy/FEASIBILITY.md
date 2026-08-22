# Hogwarts Legacy — Hebrew — FEASIBILITY

## Verdict: 🟢 **GO — ALL GATES CLOSED (in-game menu proof PASSED 2026-07-04). One of the EASIEST games in the project.**

Unreal Engine 4 ships an **official Arabic locale** with real, complete Arabic UI+dialogue text;
the actual text format (`MAIN/SUB-<locale>.bin`, "AVAFDICT 2.0") is **fully cracked with a working
pure-Python read/write codec**; there is **no compression/encryption to fight** (a fresh rebuild
never needs to byte-match the original — no delta=0 nightmare); deploy is a **non-destructive
additive override pakchunk** in a community-standard `~mods` folder (never touches the shipped
game files); there is **no anti-cheat** (Denuvo protects the exe only); and — the standout
finding, now **PROVEN IN-GAME** — **Unreal Engine has native Unicode bidi (ICU)**, so Hebrew is
stored **LOGICAL** and renders correctly with **zero bidi code of our own**, a first for this project.

**✅ Menu proof user-confirmed 2026-07-04:** the deployed override pak loaded, and the Hebrew word
`כתוביות` (stored logical, no reversal, no RLM anchor) rendered **clean (no tofu) and in correct
RTL order** inside the Arabic settings menu. Both remaining gates — **bidi mode** and **font** — are
therefore CLOSED. Ready for Phase 2 (delegate translation → build via `hl_bin.encode` → deploy →
publish).

## The 5 pillars — status

| Pillar | Status | Notes |
|---|---|---|
| **Format read/write** | ✅ **SOLVED** | `work/hl_bin.py` — pure-Python codec for the "AVAFDICT 2.0" format, ported from the open-source `insomnious/parseltongue` C# tool and independently verified against all 4 real game files (decode + re-encode + re-decode round-trips semantically identical on every file). |
| **Arabic slot (free RTL)** | ✅ **SOLVED** | Official `arAE` locale, **real complete Arabic content**: MAIN 18,889/18,889 keys match EN 1:1; SUB 34,955/34,955 EN keys have an AR counterpart (+4,729 AR-only extras, out of scope). |
| **Container read/write** | ✅ **SOLVED — via existing open tooling** | Unlike every other game here, this format has a **mature, actively-maintained open-source tool**: `repak` (Rust, MIT/Apache, `trumank/repak` v0.2.3) fully supports this exact pak version (11, "Fnv64BugFix") for both read AND write. Downloaded, SHA-256-verified, proven: extracted the 4 target files with no AES key, and a repacked file round-trips byte-identical. |
| **Bidi mode** | ✅ **SOLVED — LOGICAL (native ICU bidi, PROVEN IN-GAME 2026-07-04)** | The proof stored `כתוביות` in natural reading order (no reversal, no RLM) and it rendered in **correct RTL order** in-game → Unreal's Slate/UMG applies the Unicode bidi algorithm automatically for the RTL culture. **Store text LOGICAL; write zero bidi code** — a first for this project (every custom-engine game here needed visual pre-reversal or RLM anchors). |
| **Font** | ✅ **SOLVED — NO WORK NEEDED (PROVEN IN-GAME 2026-07-04)** | The Hebrew rendered **clean with no tofu/boxes** using the vanilla Arabic-locale font → the shipped font already covers the Hebrew block. **No Composite-Font injection, no glyph work at all.** |

## Menu proof — ✅ PASSED, user-confirmed in-game (2026-07-04)

`work/build_menu_proof.py --deploy` patched 4 keys in the live `MAIN-arAE.bin` (extracted fresh
from the game's own pak), packed them into `pakchunk111-WindowsNoEditor_P.pak` (repak, version
V11, mount `../../../`), and deployed it to
`Phoenix\Content\Paks\~mods\pakchunk111-WindowsNoEditor_P.pak` — **the game's own files were never
touched** (pure additive override, verified structurally: 1 file entry, correct mount point,
`repak info` reads it back cleanly).

| Key | Vanilla Arabic | Test value | Purpose |
|---|---|---|---|
| `Menu_Options` | خيارات | **`ZZ-HL-PIPELINE-OK-ZZ`** | Pure Latin marker — proves the override pak loads at all and wins priority over `pakchunk0`, independent of any Hebrew/font question |
| `Settings_Brightness` | السطوع | **בהירות** | Real Hebrew UI word ("Brightness") |
| `Menu_Subtitles` | عرض الترجمات المصاحبة للشاشة | **כתוביות** | Real Hebrew UI word ("Subtitles") |
| `Menu_LanguageSelect` | اختيار اللغة | **בחר שפה** | Real Hebrew phrase ("Select Language") — sits on the exact screen the user needs to open to switch to Arabic |

**RESULT (user, 2026-07-04):** with the game set to Arabic (العربية), the Arabic settings menu
showed the patched **`כתוביות`** rendering as **clean readable Hebrew, correct RTL order**, inside
the otherwise-Arabic menu (see screenshot). This single result closes **both** open gates at once:
- The override pak loaded and its patched value won priority over `pakchunk0` → the whole
  extract → `hl_bin` patch → `repak pack V11` → `~mods` deploy pipeline is proven end-to-end.
- **Font:** clean glyphs, no tofu → the vanilla Arabic font already covers Hebrew → **zero font work**.
- **Bidi:** stored logical, rendered in correct reading order → **native ICU bidi → store LOGICAL,
  zero bidi code of our own.**

Revert any time: `python work/build_menu_proof.py --revert`.

## What's NOT yet done (explicitly, so nothing is assumed complete)

- **Font: no work needed** (proven in-game) — the earlier "extract the font asset" step is moot.
- The **corpus has been extracted and counted** (53,844 translatable strings) but **not
  translated** — per project policy, translation itself is always delegated to a second
  agent/local LM, never done by Claude directly (see the delegate-all-translation standing rule).
- **SUB (dialogue/subtitles)** proof was not attempted — only MAIN (UI) was patched for the menu
  proof. MAIN is now confirmed; a small SUB patch would confirm the dialogue/subtitle rendering
  path specifically (it may use a different font/widget than the settings menu). Low risk — same
  format, same locale, same engine bidi — but worth a one-line proof at the start of Phase 2.
- **Publish surfaces** (GitHub `hogwarts-legacy-hebrew-mods` repo + Worker slug + Supabase `games`
  row + `mod_version_history`) are not set up — Phase 2+.

## Scope

| | Count |
|---|---:|
| UI (`MAIN`, EN∩AR) | 18,889 |
| Subtitles/dialogue (`SUB`, EN∩AR) | 34,955 |
| **Total translatable** | **53,844** |
| Expected skip (proper nouns/codes, TBD at translation time) | not yet estimated |

## מסמכים קשורים
- באותה תיקייה: [[games/hogwarts_legacy/PIPELINE|PIPELINE]], [[games/hogwarts_legacy/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#hogwarts_legacy|CLAUDE_INDEX_games]]
