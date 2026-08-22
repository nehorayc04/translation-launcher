# A Plague Tale: Requiem — PIPELINE (how to build + deploy)

Everything runs from `games/plague_tale_requiem/work/` with plain Python
(only `pt_text.py` / `pt_rtl.py`; the font sub-project, if needed, adds tooling).
Game files live at `D:\Games\A Plague Tale - Requiem` (staging/test copy).

## Tools (`work/`)
| file | role |
|---|---|
| `pt_text.py` | TRTEXT codec: `parse` / `load_map` / `write_overrides` (surgical, byte-preserving) / `category` / `counts`. `python pt_text.py selftest` proves the identity round-trip. |
| `pt_rtl.py` | `to_stored(logical_hebrew)` — the RTL storage transform (logical Hebrew, LTR islands reversed, `{STR_}` tokens verbatim). `python pt_rtl.py` self-tests it against the game's Arabic conventions. |
| `build_proof.py` | Phase-1 menu proof. Non-destructive by default; `--deploy` writes `tt23.pc`+`.IGN` (backup `.he_backup`); `--revert` restores. |
| `extract_corpus.py` | dumps `extract/en.json`, `extract/ct_strings.json` (community-pool format), `extract/report.txt`. |

## Menu proof (Phase 1 — do this FIRST, before any translation)
```bash
cd games/plague_tale_requiem/work
python build_proof.py            # writes work/_proof_tt23.pc (inspect, non-destructive)
python build_proof.py --deploy   # backs up + writes the game's tt23.pc AND tt23.IGN
# launch APlagueTaleRequiem_x64.exe -> Options -> Text language = العربية (Arabic)
# check the Options + Chapter Selection screens: Hebrew glyphs? RTL correct?
#   numbers on the right? {STR_} intact? no crash?
python build_proof.py --revert   # restore the original Arabic
```
Outcome decides the font gate (glyphs render ⇒ zero font work; tofu ⇒ inject).

## Full build (Phase 2, after translation is delegated + merged)
Given a `hebrew.json` = `{KEY: hebrew_logical}` from the translation agents:
```python
import pt_text as T, pt_rtl as R, json
heb = json.load(open("hebrew.json", encoding="utf-8"))
overrides = {k: R.to_stored(v) for k, v in heb.items()}
# always build from the pristine backup so re-runs are deterministic
T.write_overrides("<game>/TRTEXT/tt23.pc.he_backup", "<game>/TRTEXT/tt23.pc", overrides)
```
* Game must be **closed** (file is read at load).
* Deploy the SAME output to `tt23.IGN` too (the `.IGN` variant), unless the proof
  proves only `.pc` is read.
* The transform is deterministic (no timestamps/random) → rebuild reproduces the
  same bytes (needed for version-tracking + publish verify).

## Font injection (ONLY if the proof shows tofu)
Separate sub-project against `FONT/ENGLISH.DPC` (Zouna `Fonts_Z` atlas):
1. Unpack with `APT_DPC_Tool` (or `bff`) → locate the `BIG_ARABIC` `Fonts_Z` +
   its `Bitmap_Z` atlas + the material.
2. Inject 27 Hebrew glyphs (U+05D0–05EA) into free atlas cells (or a taller
   atlas): add a `Character` per glyph (material_index + UV rect + descent);
   `CharacterID` = the glyph's UTF-8 bytes reversed + null-padded.
3. Repack (LZ4). ⚠️ APT_DPC_Tool import is buggy / bff Requiem is PARTIAL — expect
   to fix/RE the repacker first; validate the DPC re-loads before drawing glyphs.
4. Font choice: a period-fitting Hebrew serif (David / Frank Ruehl), user-confirmed.

## Publish (Phase 3, after in-game confirmation)
Same as SM2/WD2/Anno:
* GitHub release repo `plague-tale-requiem-hebrew-mods` (zip the `tt23.pc` [+ the
  patched `FONT/ENGLISH.DPC` if injected] + a self-contained installer + readme).
* Worker slug `plague-tale-requiem-hebrew` in `games/steam/steam_mod_worker/src/index.js`.
* Supabase `games` row `plague-tale-requiem` (version / release_stage / download_url)
  + `mod_version_history` via `universal/publish_version.py`.
* Launcher (optional): a `plague_tale_requiem_mod.py` native applier (overwrite
  `tt23.pc` from a bundled/downloaded payload, backup + revert) + RPCs + a card.
  Deploy is loose-file, so this is simple.

## Activation (for the readme / launcher note)
In-game **Options → Text language = العربية (Arabic)**. English voice is kept
automatically (audio language is independent). Revert = restore `tt23.pc.he_backup`.

## מסמכים קשורים
- באותה תיקייה: [[games/plague_tale_requiem/FEASIBILITY|FEASIBILITY]], [[games/plague_tale_requiem/RECON|RECON]], [[games/plague_tale_requiem/RESEARCH_FONTSIZE|RESEARCH_FONTSIZE]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#plague_tale_requiem|CLAUDE_INDEX_games]]
