# Until Dawn (2024 remake) — PIPELINE

## Tools (`games/until_dawn/`)

- `tools/ud_locres.py` — pure-Python Unreal LocRes (v0-v3) reader/writer.
  Ported from `akintos/UnrealLocres` (`LocresLib/LocresFile.cs`). Since we
  only ever change VALUES for EXISTING keys (never add/rename), the writer
  reuses the namespace/key hash bytes as read — no CityHash64/CRC32
  implementation needed in Python at all.
  - `info <file.locres>` — version, namespace/entry/unique-string counts.
  - `dump <file.locres> [out.json]` — flat `{ns,key,en}` list.
  - `roundtrip <file.locres> [out.locres]` — load→save→reload, diff
    (key,value) sequences + compare file size/MD5 (semantic vs. byte
    identity).
  - Python API: `load(path)` → `{version, namespaces:[{name,hash,
    entries:[{key,key_hash,value,source_hash,str_index}]}]}`; mutate
    `entries[i]['value']` in place, then `save(parsed, out_path)`.
- `tools/ud_font.py` — Hebrew glyph injection for the loose `.ufont` files
  (which `repak get` returns as bare TTF/OTF, no wrapper). Auto-detects
  outline format:
  - `glyf` (TrueType, e.g. Univers) → MERGE: copies the Hebrew block
    (U+0590–05FF) from a donor font via `DecomposingRecordingPen`+
    `TransformPen`, scaled to the target's unitsPerEm, appended to `glyf`/
    `hmtx`/every Unicode `cmap` subtable. Original Latin glyphs/metrics/
    name untouched.
  - `CFF ` (PostScript, e.g. Cotford) → glyf-merge is a no-op on CFF fonts
    → REPLACE wholesale with the donor font, masquerading its `name` table
    to the original family/style (same technique as TLOU1's DINPro→Heebo).
  - `check <font.ufont>` / `inject <target> <out> [hebrew_src.ttf]`.
- `work/build_menu_proof.py` — the Phase-1 proof build. `build` / `deploy` /
  `revert`.
  - `_repak_get()` extracts a handful of loose files (2 locres + 9 fonts)
    from the LIVE `Bates-Windows.pak` via `repak get`, cached under
    `work/_proof_cache/` so re-runs don't re-extract.
  - Patches `en/Game.locres` AND `tr/Game.locres` (each independently, own
    key/hash structure preserved) with a distinguishing Latin marker in
    `BATES_MENU_PAUSED` + shared Hebrew test values in 8 other
    menu/settings keys (see the `HEB_TEST`/`MARKERS` dicts).
  - Injects Hebrew into all 6 Univers + 3 Cotford weights via `ud_font.py`.
  - Packs the staged tree with `repak pack --version V11` (default mount
    point `../../../` already matches the base pak) into
    `pakchunk999-Windows_P.pak` — the high fake chunk number + `_P` suffix
    follows the exact convention proven working on Hogwarts Legacy, so the
    override mounts AFTER the base and wins for the 11 overlapping paths.
  - `deploy` copies the built pak into
    `Bates/Content/Paks/~mods/pakchunk999-Windows_P.pak` (additive only —
    the 8.4 GB base pak is never opened for writing). `revert` deletes that
    one file.

## Build chain for a real translation batch (Phase 2, once the slot is confirmed)

1. `repak get` the target locale's `Game.locres` (whichever slot the
   menu-proof confirms — `en` or a fallback like `tr`) from the live pak.
2. `ud_locres.load()` it; for every key present in the Hebrew translation
   map, set `entries[i]['value']`; leave every other key (untranslated /
   out of scope, e.g. bonus-material if deprioritized) untouched — the
   file's OWN key set stays authoritative, we never invent new keys.
3. `ud_locres.save()` → rebuilt `.locres` (same key/hash set, new string
   table).
4. `ud_font.inject()` the Univers (6 weights) + Cotford (3 weights) fonts
   with the FINAL chosen Hebrew donor font (see FEASIBILITY.md §Font —
   Heebo is the Phase-1 placeholder, subject to a user aesthetic pick).
5. Stage both into the `Bates/Content/...` tree exactly as
   `build_menu_proof.py` does, `repak pack --version V11`, deploy to
   `~mods/`.
6. If the confirmed slot is NOT `en`: tell the user to set Text Language
   AND Subtitle Language to that locale in Settings (Speech Language stays
   English — verified independent setting, `BATES_SETTING_SPEECHLANG`).

## Key-prefix classification (no `enum` field like WD2 — classify by key name)

The single `ST_Localized` namespace mixes UI, story dialogue, and bonus
content; a WD2-style `enum` discriminator doesn't exist here, but the
row-name (key) prefix convention is consistent enough to classify reliably:

| Prefix pattern | Count (en) | Category |
|---|---:|---|
| `BATES_*` | 764 | UI/settings/system (menus, HUD, popups, accessibility) |
| `PSPC_*` / `BM_TTS*` / `PC_LOADING` / `msgid_*` | ~30 | UI (PlayStation-link prompts, screen-reader labels, loading text) |
| `SMG<digits>_<digits>` | 11,632 | story dialogue (scene/session-coded subtitle lines) |
| `epilogue_subtitle_*` | 4 | epilogue dialogue |
| `Bonus_Material_*_Subtitle_*` / `bts_video_*` / `epilogue_ost_*` | ~266 | behind-the-scenes/making-of captions (optional, low priority — not gameplay-visible) |
| `.HOWTO` | 1 | developer note, not game text — SKIP verbatim |

A single dev-instructions row (key literally `.HOWTO`) confirms the naming
convention directly: *"This ST should be used for all new loc keys. Keys
should be explicitly named for additional context... Please use BATES_ as a
prefix."* — i.e. Ballistic Moon's own internal rule matches exactly the
classification above.

## Tokens to preserve verbatim

- `<Italic>…</Italic>` rich-text tags (same style as CP2077's markup).
- `{0}` / `{1}` style numbered format placeholders (e.g.
  `BATES_SUBTITLE_NAME_FORMAT` = `"({0})"`, `BM_TTSFORMAT_SLIDER` =
  `"Slider, {0}"`).
- Literal `\r` embedded newlines inside a single value (e.g.
  `epilogue_ost_001` = `"LOS ANGELES\rSOME YEARS LATER"`).
- Timestamp/clue-counter strings (`"1:00am – 1:27am"`, `"2 of 5 clues
  found"`) — translate the words, keep numbers/format intact.

## Activation (pending menu-proof result)

- If `en` slot loads: **no user action** — install and play (Settings still
  shows "English", subtitle text is Hebrew).
- If only a non-native slot loads (fallback, e.g. `tr`): Settings → Language
  → **Text Language** = that locale, **Subtitle Language** = that locale,
  **Speech Language** stays **English**.

## מסמכים קשורים
- באותה תיקייה: [[games/until_dawn/FEASIBILITY|FEASIBILITY]], [[games/until_dawn/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#until_dawn|CLAUDE_INDEX_games]]
