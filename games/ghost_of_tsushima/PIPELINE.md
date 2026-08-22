# Ghost of Tsushima DC — PIPELINE (build / deploy / publish)

Run everything with the repo `.venv` python (needs `lz4`; `fontTools` for any font work).
Container/writers are reused from `games/tlou2/tools/` unchanged. Deploy env override: `GOT_GAME`.

## Tooling (in `games/ghost_of_tsushima/`)
| File | Role |
|---|---|
| `tools/xpps.py` | KCAP `.xpps` reader + surgical `patch(data, {key_hex:text})` (append+repoint; identity byte-exact). CLI `stats`/`dump`/`find`/`export`/`selftest`. |
| `work/got_rtl.py` | `to_visual(logical)` VISUAL-bake (copied from tlou1, selftest PASS) — used only if the menu-proof shows bidi=VISUAL. |
| `work/build_menu_proof.py` | Phase-1 gate closer — patch ~6 menu keys → override psarc → `--deploy`/`--revert`. Built + validated offline. |
| `games/tlou2/tools/dsar.py` | DSAR→PSARC reader (`Psarc2`) — reads GoT unchanged. |
| `games/tlou2/tools/psarc_write.py` | inner PSARC builder — **use `flags=0x0e, compress=False` for GoT** (STORED inner). |
| `games/tlou2/tools/dsar_write.py` | DSAR wrapper (LZ4 outer, flags low-byte 0x03). |
| `notes/`, `work/REPACK_FINDINGS.md` | Phase-1 evidence. |

## Phase-1 finish — menu-proof (closes bidi + font)
```
python games/ghost_of_tsushima/work/build_menu_proof.py            # build+validate only (no game touched)
python games/ghost_of_tsushima/work/build_menu_proof.py --deploy   # drop the proof psarc into the game
python games/ghost_of_tsushima/work/build_menu_proof.py --revert   # remove it
```
Activation: Settings → Options → General → **Text Language = العربية**. Read the result per FEASIBILITY.
This decides: bidi = LOGICAL vs VISUAL, and whether the `fOnk` font already covers Hebrew.

## Phase-2 build recipe (after gates close + translation done)
The deploy mechanics are proven; the only Phase-2 engineering beyond translation is (a) widen the reader's table
scanner to enumerate ALL index sections (walk the `@0x2c` trailer directory) so dialogue tables are captured, and
(b) the dialogue **block+position** join (small-id keys collide — join EN→AR by table+index, not by key).

1. **Extract** live EN + AR (`dsar.Psarc2(gapack_misc_l).extract`) — or use `extract/`.
2. **Map** EN→HE: UI/content by large-hash key (EN↔AR key-identical); dialogue by block+position.
3. **Apply**: `overrides = {key_hex: hebrew}`; if bidi=VISUAL wrap each value in `got_rtl.to_visual`; preserve all
   tokens (PUA glyphs, `{VARS}`, `%d/%f`, `\n`). `new_ar = xpps.patch(ar_bytes, overrides)`.
4. **(If font gate)** inject Hebrew `U+05D0–05EA` into the `fOnk` in `game.sprig.texmeshman`, repack `gapack_misc_g`
   (or ship a small override psarc holding the patched `game.sprig.texmeshman`). *(sub-project — see FEASIBILITY.)*
5. **Pack override**: `inner = psarc_write.build({"/lang_arabic_text.xpps": new_ar}, flags=0x0e, compress=False)`
   → `proof = dsar_write.wrap(inner)` → write `cache_pc/psarc/zzz_hebrew.psarc` (name sorts AFTER `gapack_misc_l`).
   Internal path MUST be `/lang_arabic_text.xpps` (leading slash → md5(path) matches the engine lookup).
6. **Deploy** additive (drop the one psarc; revert = delete). Backup nothing needed (shipped archives untouched).

## Publish (like SM2/WD2/GoWR — once approved)
GitHub repo `hebrew-translation-hub/tsushima-hebrew-mods` (release with `install.py` that copies the override psarc + `--revert`)
+ Worker slug `tsushima-hebrew` (`games/steam/steam_mod_worker/src/index.js` + `wrangler deploy`) + Supabase `games`
row `id=tsushima` (availability/version/download_url) + `mod_version_history`. Optional launcher applier
`translation_manager/tsushima_mod.py` (additive drop/delete — mirrors `gowr_mod.py`; the launcher already detects
`tsushima`). Community `/translate` pool: `build_ct_strings` → `universal/community_translate.py import tsushima`.

## Gender (Phase-2, no gender debt)
No local gendered-English signal — derive gender per the universal oracle from the game's OWN gendered locales
joined by key: `lang_russian_text.xpps` (speaker/addressee, past -л/-ла) + `lang_spanish_text.xpps`/`lang_french_text.xpps`
(referent -o/-a). Attach RU/ES beside EN in the Phase-2 handoff; `gender_oracle` scan as closing QA. (Jin is male,
fixed; most player-facing address is to Jin → largely deterministic.)

## Key gotchas (do not regress)
- Inner PSARC **STORED** (`compress=False`) + **`flags=0x0e`** (GoT; TLOU2 uses 0x0c). DSAR outer LZ4 (filler `55*7`).
- Override internal path = `/lang_arabic_text.xpps` (leading slash).
- Repack is semantic-loadable, NOT byte-identical (LZ4 encoder + md5-vs-manifest data order) — fine, matches TLOU2.
- `dsar.py` crashes on the `ct=254 PADDING*` sentinel (e.g. `gapack_misc_b`); guard if extracting those. Target clean.
- Reader currently UNDERCOUNTS (~15k of ~36k) — widen the scanner before the full Phase-2 extract.

## מסמכים קשורים
- באותה תיקייה: [[games/ghost_of_tsushima/FEASIBILITY|FEASIBILITY]], [[games/ghost_of_tsushima/RECON|RECON]], [[games/ghost_of_tsushima/RESEARCH_FONT|RESEARCH_FONT]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#ghost_of_tsushima|CLAUDE_INDEX_games]]
