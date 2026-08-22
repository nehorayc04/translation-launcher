# 007 First Light — PIPELINE (planned build chain)

Status: **Phase-1 groundwork DONE (container+LOCR cracked & round-trip-proven).** Below is the path to
a shipped Hebrew mod. Steps marked ✅ are proven; ⬜ are next.

## 0. Facts locked (see RECON/FEASIBILITY)
- Engine Glacier; container RPKG v2 (`gl_rpkg.py`); text LOCR/DLGE (`gl_locr.py`, 007 XTEA key).
- 15 LTR/CJK slots, no Arabic → **LTR-slot hijack + font inject**. Scope ~7.3k LOCR + ~42k DLGE.
- DRM-free (cracked). Active modding scene (RPKG-Tool `first-light`, Simple Mod Framework, ZHMModSDK).

## 1. ✅ Read chain (DONE)
- `gl_rpkg.py info/types/find/dump` — enumerate + extract any resource (xor→lz4→bytes).
- `gl_locr.py` — decode LOCR/CLNG; XTEA encode/decode; round-trip proven.

## 2. ⬜ DLGE decode (Phase-1.5 — the ~85% of scope)
- Port TonyTools `DLGE::Convert`/`Rebuild` (dialogue containers: type/index, per-language subtitle
  entries, WAV/animset refs, switch/sequence/random containers). Reference already downloaded to
  `C:/tmp/rpkg_Languages.cpp`. Build `gl_dlge.py` (decode + rebuild), validate on real chunk0/chunk1 DLGE.
- Confirm subtitle strings are the same XTEA/UTF-8 as LOCR (they are, per `Languages.cpp` line ~1023).
- **Cross-check/fallback tool available:** the user provided `TonyTools.zip` → `HMLanguageTools.exe`
  (LOCR/DLGE/CLNG ↔ JSON) — but it targets the Hitman XTEA key, so for 007 it needs `--langmap`
  (`xx en fr it de es ru mx br pl cn jp tc kr tr`) AND the 007 l10n key; our pure-Python `gl_locr.py`
  already uses the 007 key, so prefer it and use HMLanguageTools only to validate DLGE structure.

## 3. ✅ Repack — pure-Python patch-RPKG writer BUILT + offline-validated (Stage-5, container half)
- `tools/gl_rpkg_write.py` `build_patch(base, {hash:new_bytes}, out)` builds a `chunkNpatchM.rpkg` that
  overrides resources by hash. Layout (from RPKG-Tool `generate_rpkg_from.cpp`): 29-byte patch header
  (`2KPR` + 9 + file_count + table_offset + table_size + patch_count) + deletion list + file table 1
  (abs offsets) + file table 2 (verbatim metadata, `size_final` patched) + data. Overrides stored
  **UNCOMPRESSED + un-XORed** (data_size 0) — a valid resource form, avoids LZ4/XOR edge cases.
  - **Identity round-trip PROVEN offline: 6/6 real LOCRs → patch → re-read → byte-identical + meta OK.**
  - `tools/gl_rpkg.py` gained patch-mode reading (`is_patch=True`) + `by_hash`/`read_hash`.
  - The remaining half of Stage-5 = the GAME actually loading it → needs the user to launch (menu-proof).

## 4. ⬜ Font — inject Hebrew into the Scaleform GFXF (the ONE remaining hard build)
- **Format CONFIRMED (`tools/gl_rpkg.py` + a GFx tag-walk):** GFXF = **`BIN1` wrapper** (24-byte header,
  GFx at offset 84) + **Scaleform GFx v14/v15** (SWF-tag stream). The real UI font is the ~497 KB GFXF
  (and siblings) carrying **`DefineFont3` × 9** (tag 75 = **VECTOR glyph outlines**, 9 weights). The tiny
  5.9/15.9 KB GFXF are non-font UI movies. The vector fonts have **0 texture references** → NOT atlas —
  this is the **easy font class = exactly Witcher 3** (`fonts_*.redswf` DefineFont3).
- **Plan:** BIN1-unwrap → GFx → find the DefineFont3 tag(s) → **inject U+05D0–05EA glyph shapes** (from an
  atmosphere-appropriate Hebrew TTF via `fontTools`, converted to SWF shape records), add code-table +
  advance/bounds entries, keep the Latin glyphs → re-serialize the tag → patch the GFx file-length + the
  BIN1 wrapper size → into the patch RPKG. **Reuse `games/witcher3/work/{swf_font,swf_glyphgen,build_font}.py`.**
- **Tool available if needed:** user-provided `GFXFzip.exe` (BIN1↔GFx unpack/repack) + `HMTextureTools.exe`.
  The Arabic mod bundles `fontTools` → confirms this exact font-injection path works on 007.
- Glacier UI may use several GFXF — swap the one(s) the hijacked slot's menu renders through (identify by
  the menu-proof or by which DefineFont3 covers Latin/Cyrillic at UI size).

## 5. ✅ bidi mode = VISUAL (confirmed from the Arabic mod)
- The Nexus Arabic installer bundles `python-bidi` + `arabic_reshaper` → **engine does NO bidi → store
  VISUAL**. Build `gl_rtl.py` `to_visual` (reuse WD2/GTA `visual_line`: reverse Hebrew runs + run order,
  keep Latin/digits/`{0}`/`<br/>` forward, split on `<br/>`/`\n`). **Hebrew needs NO reshaping** (unlike
  Arabic). Menu-proof (Stage-6) confirms in-game.
- Note: their translation is `data\payload.enc` (5.1 MB, encrypted) — the translator's own work; **we do
  NOT extract it.** We only learned the METHOD (visual + font inject) from the bundled libraries.

## 6. ⬜ Menu-proof (Stage-6)
- Translate ONLY the main-menu / settings LOCR strings of the hijacked slot → font inject → repack →
  deploy → user sets Text Language = <hijacked slot> → screenshot. Confirms: repack loads, RTL correct,
  font renders (no tofu), numbers/`{0}`/`<br/>` intact. **User is the final gate.**

## 7. ✅ Deploy/mount codec BUILT (`tools/gl_pkgdef.py`) + deploy target locked
- **Mount:** `packagedefinition.txt` decrypted (thumbs XTEA `{0x71482CF0,…}` + fixed 16-byte header +
  **zlib CRC32 over the unpadded plaintext** — verified). Its partitions ship **`patchlevel=0` → NO
  patches load**, so the deploy must bump `patchlevel` (>=1) and re-encrypt. `gl_pkgdef.py`
  (`decrypt`/`encrypt`/`set_patchlevel`) — **codec verified: CRC + XTEA body byte-identical** to the
  game file (only the 16 ignored header bytes differ, exactly as RPKG-Tool does).
- **Deploy:** drop `chunk0patch1.rpkg` into `Runtime\` + write the patchlevel-bumped
  `packagedefinition.txt` (back up the original). Base chunk0/chunk1 untouched (Steam-verify safe);
  revert = delete the patch + restore packagedefinition. Hard-code `F:\Game Lab\007 First Light\Runtime`;
  never `C:\Games`.
- **Activation:** in-game Options → Text/Subtitle Language = <hijacked slot> (audio independent → English VO kept).
- **EAC/Denuvo:** none blocking (SP, cracked, Denuvo=exe-only).

## 8. ⬜ Translation (Phase-2 — delegate)
- Per [[delegate-all-translation]]: Claude builds tooling + agent handoff, never translates.
- Build the community `/translate` pool + agent handoff (LOCR by lineHash; DLGE by container/line).
  Categories by visibility: UI/menus (LOCR) first, then story dialogue (DLGE), then barks.
- **Gender oracle (user-requested — use a helper language for gender):** no Arabic slot here, so derive
  gender from the game's OWN gendered localizations, joined by `lineHash` (GENDER_ORACLE_ROLLOUT.md,
  same as TLOU which also had no Arabic). **5 gendered slots ship in-game, all decode with `gl_locr.py`:**
  **Russian (slot 6)** = speaker/addressee gender (past `-л/-ла`, short adjectives) · **Spanish (5) /
  French (2) / Italian (3) / Portuguese (8)** = referent/addressee gender (`-o/-a`, participles).
  Attach RU + ES/FR beside EN in every Phase-2 handoff line → correct Hebrew gender from line 1 (no
  guessing); `gender_oracle.py` parsers (`ru_addressee`/`ru_speaker`/`es_referent`) already exist.
- Name registry + web-verified Hebrew spellings (Bond canon) BEFORE translating ([[name-registry-and-internet-check]]).

## 9. ⬜ Publish (only on explicit "פרסם")
- GitHub `007-first-light-hebrew-mods` + Worker slug + Supabase `games` id `007-first-light` +
  `mod_version_history`, like SM2/WD2/Anno/GoWR. Detector already needs a `007-first-light` pattern
  (+ exe `007FirstLight.exe`) added to `game_detector.py`, key == Supabase `games.id`.

## Wishlist / de-risk quick wins for next session
- Extract 1 GFXF → confirm SWF magic (`FWS`/`CWS`/`ZWS`) + DefineFont tag → lock the font path.
- Decode 1 DLGE end-to-end → confirm the ~42k dialogue scope + subtitle string layout.
- Check whether the Nexus Arabic mod ships as a patch RPKG (its structure reveals the exact deploy +
  which slot it hijacked + VISUAL-vs-LOGICAL).

## מסמכים קשורים
- באותה תיקייה: [[games/007_first_light/FEASIBILITY|FEASIBILITY]], [[games/007_first_light/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#007_first_light|CLAUDE_INDEX_games]]
