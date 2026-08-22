# VirtualDJ 2026 Hebrew — FEASIBILITY

**Verdict: 🟢 GO — easiest tier in the project (pending one in-app proof).**

The whole read→build→deploy chain is proven offline; the only thing left to confirm is the RTL/font
render in the app (the standard Phase-1 menu proof, already deployed for the user to check).

## Why it's easy
| Gate | Status |
|---|---|
| Container | 🟢 loose plain-UTF-8 XML, no offsets/checksums/compression → **no repack, identity round-trip free** |
| Text found | 🟢 `Languages\Arabic.xml` (carved from the exe's `languages.zip`), 3,894 id-keyed strings |
| Arabic/RTL slot | 🟢 official Arabic locale (`iso="ar"`), user already set `language=Arabic` |
| Deploy | 🟢 drop ONE file in `%LOCALAPPDATA%\VirtualDJ\Languages\` — no admin, fully reversible |
| Anti-cheat/DRM | 🟢 none (it's a config file in the user profile) |
| id-mapping | 🟢 keys identical across langs → EN→HE by key; Arabic = quality cross-ref |
| Codec | 🟢 built + round-trip-verified (`tools/vdj_lang.py`) |

## The two real questions (both decided by the deployed menu proof)
1. **bidi/RTL** — does VirtualDJ reorder Hebrew RTL for the `iso="ar"` locale?
   - If YES → store **LOGICAL** (natural Hebrew), zero bidi code. (Most likely — Arabic ships as an
     official language, so the app must already render Arabic RTL; Hebrew inherits it.)
   - If NO → store **VISUAL** (pre-reversed per line), like WD2-menus / AC2 / Anno. A `visual_line`
     transform would then be added to the builder (small, well-trodden in this repo).
2. **Font coverage** — does the skin font have Hebrew glyphs? Arabic renders officially, so the font is
   Unicode and almost certainly covers U+05D0–05EA too. If tofu → inject/replace the skin font (skins are
   downloaded on demand into `Skins\`; low risk, deferred until the proof says so).

## Activation (confirmed mechanism)
Options → **language = Arabic (العربية)** — the dropdown has no "Hebrew", and it's already set. The user
just (re)starts VirtualDJ.

## Scope (for Phase 2)
- **UI: 3,081** strings (Config/Settings/Columns/ContextMenu/Messages/Errors/tooltips/Plugins/…).
- **VDJScript command docs (`Actions`): 813** — technical help text; translate later or keep English.
- **Total: 3,894** (~212K chars). Arabic pro-translation covers 3,051/3,073 UI keys = strong cross-ref.
- No subtitles (it's an app, not a game) → the UI/subtitle split is UI-only.
- No gender-variant fields (single string per key) → no dual-gender backfill trap.

## Menu proof — DEPLOYED (awaiting user)
`work/build_menu_proof.py --deploy` wrote `%LOCALAPPDATA%\VirtualDJ\Languages\Arabic.xml` = the Arabic
skeleton with 15 high-visibility overrides: 1 Latin marker (`RootElements/Sampler` → `ZZ-VDJ-OK-ZZ`,
proves the folder file overrides the embedded Arabic) + 14 Hebrew strings (browser column headers Title/
Artist/Length/Key/Genre/Year/Comment/Rating + folders Local Music/My Lists/My Music/History/Desktop/
Crates). **User: (re)start VirtualDJ (language already Arabic) → the marker + Hebrew appear in the browser
column headers and the left folder tree.** Report back: marker shown? Hebrew correct direction (RTL) or
reversed? any tofu? Revert anytime: `python work/build_menu_proof.py --revert`.

## Known caveats / plan B
- If a folder `Arabic.xml` does NOT override the embedded copy (marker doesn't appear): plan B = write
  `Hebrew.xml` in the folder and set `settings.xml <language>Hebrew</language>` directly (bypasses the
  hardcoded dropdown); the app loads a language by name from settings.
- VirtualDJ auto-updates; a new build re-embeds `languages.zip` but the folder override persists
  (re-verify after a major update).

## מסמכים קשורים
- באותה תיקייה: [[games/virtualdj/PIPELINE|PIPELINE]], [[games/virtualdj/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#virtualdj|CLAUDE_INDEX_games]]
