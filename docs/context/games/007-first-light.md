## 007 First Light (IO Interactive, 2025) Hebrew — Phase-1 groundwork DONE, 🟢 GO (2026-07-10)

New game scaffolded at `games/007_first_light/` (RECON/FEASIBILITY/PIPELINE + `tools/`). Install
`F:\Game Lab\007 First Light` (cracked: `voices38.dll` Denuvo bypass + Goldberg `steam_settings\`),
Steam appid **3768760**, detector/`games.id` candidate **`007-first-light`**. Engine = **Glacier** (the
Hitman engine — the most-modded engine in this project's peer set). **Verdict 🟢 GO, strong/low-risk** —
the container + text codec are cracked AND round-trip-proven in pure Python this session, and a shipping
**community Arabic mod already exists** (Nexus 007firstlight #11: ~48k entries, injected Arabic font, full
RTL) → the two historically-hardest gates (RTL + font-with-the-script) are PROVEN solvable on this exact
engine+game; Hebrew (RTL, no letter-shaping) is strictly easier than Arabic.

- **Container = RPKG v2 (`2KPR`) — CRACKED, pure-Python reader `tools/gl_rpkg.py` validated exact-parse on
  BOTH `Runtime\chunk0.rpkg` (20.7 GB / 284,971 files) and `chunk1.rpkg` (35.8 GB / 464,014 files)**
  (consumed == table_size, 0 error). Base header 25 B (`2KPR` + 9 + u32 file_count@0x0d + u32
  hash_header_table_size@0x11 [=file_count*20] + u32 hash_resource_table_size@0x15); file table 1 at 0x19 =
  `{u64 hash; u64 offset; u32 data_size}` (bit `0x80000000` SET ⇒ XORed; low 30 bits = compressed size, 0 ⇒
  stored); file table 2 (metadata) right after — **007-specific: 20-byte base entry** (the Hitman
  `reference_table_dummy` u32 was REMOVED on the RPKG-Tool `first-light` branch): `char[4] type(REVERSED) +
  u32 ref_table_size + u32 size_final@+8 + u32 mem + u32 vmem`, then if ref_table_size>0 a `4+9*count`
  references block. Resource read: seek → **XOR (key `DC 45 A6 9C D3 72 4C AB`, byte%8) if flagged → LZ4
  raw-block decompress to size_final**.
- **Text = LOCR (UI) + DLGE (dialogue subs) + CLNG (lang list), XTEA-encrypted UTF-8.** `tools/gl_locr.py`
  decodes LOCR/CLNG + XTEA encode/decode. **007-SPECIFIC l10n XTEA key** `{0x68AC3361, 0x562B4AA0,
  0xB9F2771F, 0x28EB3CE7}` (delta `0x9E3779B9`, 32 rounds — Hitman used `{0x53527737,…}`; 007 changed it).
  LOCR = `u8 ver` + `numLangs×u32 offset` table + per-lang `u32 numStrings` + `{u32 lineHash; u32 encLen;
  encLen XTEA bytes; u8 0}` — **lineHash shared across langs → map EN→HE by hash; strings UTF-8.**
  **164/164 chunk0 LOCRs decoded clean; LOCR ciphertext round-trip 119/119 byte-identical; Hebrew UTF-8
  clean → READ+WRITE proven.** CLNG = one bool byte per slot.
- **🔴 NO Arabic slot → LTR-slot hijack (AC2/Anno/GTA/TLOU class).** CLNG = **15 slots**, identified from
  real content: `0 xx(EN src) · 1 en · 2 fr · 3 it · 4 de · 5 es · 6 ru · 7 mx(LatAm-Spanish) · 8
  br(Portuguese) · 9 pl · 10 cn · 11 jp · 12 tc · 13 kr · 14 tr` (= Hitman-H2 langmap + kr + tr; all
  LTR/CJK). Ship Hebrew inside one LTR slot's LOCR/DLGE + swap that slot's font; user sets Text Language to
  it. Slot choice (Turkish/Spanish-variant/Polish "sacrifice", or English for zero-friction) = pipeline TBD.
- **Font = Scaleform `GFXF` (14 SWF DefineFont resources; UI is Scaleform — GFXV/GFXI/GFXA).** No shipped
  Hebrew → inject, a **known/solved class in this repo** (Witcher 3 `swf_font.py`/`swf_glyphgen.py`/
  `build_font.py`, GTA V Scaleform). Arabic mod proves injection works here.
- **bidi = VISUAL (CONFIRMED from the Arabic mod).** The user provided the Nexus Arabic installer
  (`games/007_first_light/Arabic Hesham 007 …61v8s3IG1.exe`); statically extracting its PyInstaller
  CArchive (pure-Python, NO execution → `C:/tmp/arabic_mod`) showed it bundles **`python-bidi` +
  `arabic_reshaper` + `fontTools`** = the canonical "engine does NO bidi → pre-reshape + visual-reorder
  at build" stack → **Glacier stores VISUAL.** Hebrew = visual-reverse only (no letter-shaping, simpler
  than Arabic). Their translation is `data\payload.enc` (5.1 MB, ENCRYPTED = the translator's own work
  → **we do NOT extract it**; we build Hebrew from scratch, only learned the METHOD from the libs).
- **Scope (measured): ~7,306 unique LOCR UI strings (chunk0, avg 51 ch) + ~42,156 DLGE dialogue containers
  (18,769 + 23,387) ≈ ~49k** (matches the Arabic mod's ~48k). DLGE decode format located (TonyTools
  `DLGE::Convert`) — Phase-1.5.
- **Gender oracle (user-requested "helper language for gender"):** no Arabic here → derive gender from the
  game's OWN gendered slots joined by `lineHash` (like TLOU): **Russian (6)**=speaker/addressee (-л/-ла),
  **Spanish (5)/French (2)/Italian (3)/Portuguese (8)**=referent/addressee (-o/-a) — all 5 decode with
  `gl_locr.py`; attach RU+ES/FR per line in the Phase-2 handoff (`universal/gender_oracle.py` parsers exist).
- **Tools provided by the user (`games/007_first_light/TonyTools.zip`):** `GFXFzip.exe` (GFXF Scaleform
  font unpack/repack), `HMLanguageTools.exe` (LOCR/DLGE/CLNG↔JSON — Hitman-keyed, needs `--langmap` + the
  007 key; our pure-Python codec already uses the 007 key → prefer ours, use HMLT to validate DLGE),
  `HMTextureTools.exe`, `HMAScrambler.exe`.
- **Deploy chain BUILT + offline-validated (pure-Python, 2026-07-10):** ① `tools/gl_rpkg_write.py` =
  **patch-RPKG writer** (`build_patch`, 29-byte patch header + verbatim metadata + stored/un-XORed data)
  — **identity round-trip 6/6 LOCRs byte-identical**; `gl_rpkg.py` gained patch-mode read + `by_hash`.
  ② `tools/gl_rtl.py` = VISUAL transform (`to_visual`, 3-class heb/ws/ltr run reversal, tokens/`<br/>`
  preserved) — **selftest 3/3**. ③ `tools/gl_pkgdef.py` = `packagedefinition.txt` mount codec (thumbs
  XTEA + fixed 16-B header + **zlib CRC32 over unpadded plaintext**) — **CRC + XTEA body byte-identical**;
  partitions ship **`patchlevel=0` → deploy must bump patchlevel + re-encrypt**. Deploy = drop
  `chunk0patch1.rpkg` in `Runtime\` + patchlevel-bumped packagedefinition (base chunks untouched,
  revert=delete). DRM-free, no EAC.
- **🟢 Font = BUILT.** GFXF = `BIN1` wrapper (offset-8 field is a **BIG-ENDIAN** size = 68+gfx_len; GFx at
  84; 40-B trailer) + Scaleform **GFx v14/v15**. The ~497 KB UI GFXF `01DD9580958CDC9B` carries **9
  DefineFont3** (VECTOR, 0 texture refs) — the branded UI font is **Rajdhani** (Bold/Reg/SemiBold/Medium)
  + Arya + Kimono + Noto-KNT. `tools/gl_gfxf.py` (BIN1 unwrap/rewrap + GFx tag rebuild + `swf_font`/
  `swf_glyphgen` copied from Witcher 3) — **DefineFont3 parse/serialize 46/46 byte-identical**; ADDs the 27
  Hebrew letters as new glyphs keeping the CodeTable ascending-sorted; **inject re-parses 9/9 with Hebrew.**
- **✅ MENU-PROOF BUILT + DEPLOYED (2026-07-11, awaiting the user's in-game check).**
  `work/build_menu_proof.py` (`--deploy`/`--revert`) chains it all: `gl_locr.encode` (**byte-identical to
  the game**, 88378==88378) patches 6 menu strings (Continue/Resume/Load/Credits/Options + a Latin marker
  `ZZ-007-OK-ZZ`) in **ALL 15 slots** via `gl_rtl.to_visual` (VISUAL) + Hebrew-injected Rajdhani GFXF →
  `gl_rpkg_write.build_patch` → **`chunk0patch1.rpkg`** (1.35 MB, re-reads valid: LOCR×3+GFXF×1) +
  `gl_pkgdef` patchlevel 0→1 re-encrypt → deployed into `Runtime\` (backup `packagedefinition.txt.he_backup`;
  revert = `--revert`). Proof font = Arial (final atmosphere font is a Phase-2 pick). **User: launch → main
  menu; any Hebrew (המשך/אפשרויות) or the marker confirms mount+override+font+RTL all work at once.**
- **🐛 FIRST DEPLOY DIDN'T BOOT — 3 root-caused + fixed boot-killers (2026-07-11), all in the `super`
  (=chunk0, the BOOT partition) load path so any one crashes boot:** (1) **`packagedefinition` 16-byte header
  was WRONG** — `gl_pkgdef.encrypt` shipped a hardcoded `HEADER16` constant, but the real file's first 16
  bytes (`b7 e2 ea 00 …`) are a per-file signature the engine validates → wrong magic ⇒ rejected. Fix:
  `decrypt` now RETURNS the file's real `header16` and `encrypt(plain, header16)` reuses it verbatim → identity
  is BYTE-IDENTICAL. (2) **Patch resources were stored UN-XORed (`data_size=0`)** — a form the base NEVER
  uses: ALL 164,578 stored base resources have `on_disk_size == 0x80000000` (bit31=XORed, low30=0=stored), and
  LOCR/GFXF are 100% XORed. Fix: `gl_rpkg_write.build_patch` now XORs the stored bytes (`xor_data`) and writes
  `0x80000000` — the proven-readable form. (3) **`set_patchlevel` bumped BOTH partitions** — the pkgdef has 2
  (`super`=chunk0, `base`=chunk1); the regex set patchlevel=1 on both → engine hunts for `chunk1patch1.rpkg`
  (never shipped) ⇒ crash. Fix: `set_patchlevel(plain, level, chunk_index=0)` bumps ONLY partition 0 (the one
  we ship a patch for; `base` stays 0). **Re-deployed; all offline-validated (pkgdef identity byte-identical,
  patch re-reads 4 res all `0x80000000`, Options=`תויורשפא` VISUAL, 9/9 fonts Hebrew). UNIVERSAL Glacier
  lessons: preserve the pkgdef's real 16-byte header; a patch resource MUST match the base's exact store form
  (`0x80000000` stored+XORed here); bump patchlevel ONLY for the chunk you actually ship.**
- **✅✅ ENTIRE PIPELINE PROVEN END-TO-END IN-GAME (2026-07-12) — Hebrew renders in the main menu, correct
  RTL, via a NEW deploy mechanism. The patch-RPKG path is a DEAD END; append-relocate replaces it.**
  - **🔴 patch-RPKG format crashes boot — abandoned.** Every `chunk0patch1.rpkg` (and even a `chunk1patch1`)
    crashes boot (process starts, no window, exits) — a 1-resource identity patch too. My patch bytes match
    RPKG-Tool's `generate_rpkg_from` (rpkg_gen.cpp) in EVERY audited field (magic+9-byte v2_header+hash_count+
    table_offset+table_size+patch_count, `hash_offset = table_off+table_size+patch_count*8+0x1D`, verbatim
    meta, LZ4-HC+XOR data), yet the engine rejects it. Likely a 007-specific patch difference the RPKG-Tool
    first-light branch (which only ever EXTRACTS 007 bases) never tested. **Not worth chasing — the mechanism
    below sidesteps it.** (v2_header byte@4 = chunk index: chunk0=`01 00 00 00 00 00 00 78 78`, chunk1
    `…01…`; import.cpp's is_patch `test_zero_value==0` heuristic fails for 007's `0x01…`-high-byte hashes,
    but the engine keys off the FILENAME so that's RPKG-Tool-only.)
  - **🔑 ISOLATION methodology that cracked it:** (a) `iso_test.py pkgonly` (bump `super` patchlevel, NO patch
    file) BOOTS ⇒ the packagedefinition mount+patchlevel is SAFE; a missing patch is tolerated. (b) any patch
    file present ⇒ crash ⇒ the patch FILE is the sole differentiator. (c) `work/inplace_enc_test.py` — a
    SURGICAL in-place edit of ONE LOCR INSIDE chunk0 (re-encode original content with my LZ4-HC+XOR, overwrite
    at the same offset, patch table1 `data_size` + table2 `size_final`; my HC output was EXACTLY the game's
    56340 B) BOOTS ⇒ **my LOCR encoding + meta are engine-valid; the crash was ONLY the patch STRUCTURE.**
  - **🟢 DEPLOY MECHANISM = append-relocate in chunk0 (`work/append_reloc.py`), PROVEN in-game.** For each
    edited resource: LZ4-HC+XOR the new bytes → **APPEND at chunk0 EOF** → repoint that resource's table-1
    `data_offset`→EOF + patch table-1 `data_size` + table-2 `size_final`. Header/tables/every other resource
    stay byte-identical, so the engine still parses chunk0 as the valid BASE it already loads; works for ANY
    size (grow/shrink; old bytes become a dead gap). NO patch file, NO packagedefinition change. Reversible
    (saved fields + truncate). Confirmed: `OPTIONS`→`ZZ-APPEND-OK` marker rendered; then the full menu proof
    (`work/build_proof2.py --deploy`) rendered **`אפשרויות` in clean correct-direction Hebrew** in the main
    menu (Latin `STORY`/`GO ONLINE`/`QUIT GAME` intact alongside). **bidi = VISUAL confirmed** (`gl_rtl.to_visual`
    baked it right — engine does NO bidi, matching the Arabic-mod finding). For DISTRIBUTION this ships small
    (the ~1 MB of new resource bytes + a tiny installer that does the append-relocate on the user's chunk0),
    OR revisit the patch format later.
  - **🟢 FONT = injection REQUIRED (no native Hebrew) + a GFXF SIZE LIMIT (~510 KB) is the real gate — SOLVED
    by injecting minimally.** ⚠️ An earlier claim that the font "already has Hebrew (byte-identical)" was WRONG
    — it was measured while the injected GFXF was still deployed (re-reading my own output). TRUTH (measured on
    the CLEAN font): the UI GFXF `0x01DD9580958CDC9B` (9 DefineFont3 faces: Rajdhani×4 / Noto-KNT / Arya /
    Kimono×3, orig 497,678 B) has **0 Hebrew** → `gl_gfxf.inject_hebrew` ADDs the 27 letters (U+05D0–05EA from
    Arial) per face, structurally perfect (sorted CodeTable, wide_off/wide_codes preserved, byte-aligned
    FontBoundsTable, offsets recomputed, original Latin shapes byte-identical, rebuild_gfx valid). **THE GATE:
    the engine fails to load this GFXF once it grows past ~510 KB** (empirical: orig 497,678 ✅ · Rajdhani-only
    4 faces 508,010 ✅ · Arya-only 500,261 ✅ · all 5 UI faces 520,763 ❌ → box-glyphs on any screen that uses an
    over-limit face). This is NOT a codec bug (the fonts are all valid) — it's a hard size cap on the resource.
    **FIX: inject Hebrew into ONLY the face(s) that actually render Hebrew text, staying under the cap.** The
    menu + the health-warning body both render with **Arya**, so **Arya-only injection (500,261 B) is PROVEN:
    menu `אפשרויות` renders AND the warning body is clean** (`build_proof2.py FONT_ONLY=["Arya"]`). Headroom ≈
    +10 KB over the original ⇒ ~2–4 faces max (each Arial-Hebrew face ≈ +2.5–4.6 KB). Phase 2 must map which
    face each Hebrew UI/subtitle context uses and inject that minimal set (or use a lighter Hebrew donor to
    shrink the per-face cost).
  - **The "epilepsy-warning box-glyphs" saga was the size limit, NOT pre-existing:** with the OVER-limit 5-face
    GFXF the warning body (Arya) boxed; with Arya-only (under limit) it renders English cleanly. (The isolation
    A/B: Rajdhani-only → warning OK but menu Hebrew boxed [Arya not injected]; Arya-only → BOTH OK.)
  - The community Arabic mod (PyArmor-obfuscated, `data/payload.enc` = its own encrypted translation, NOT
    extracted) bundles python `lz4`+`fontTools`+`arabic_reshaper`+`python-bidi` and has NO DLL loader → it
    uses this same loose-resource + lz4 mechanism (not a runtime loader), consistent with append-relocate; its
    font method likely also respects the size cap (minimal injection / a compact Arabic face).
- **✅ DLGE (dialogue subtitles) CRACKED + full corpus extracted + community pool LIVE (2026-07-12).**
  `tools/gl_dlge.py` decodes the DLGE container tree (WavFile/Random/Switch/Sequence). **007-specific WavFile
  layout, brute-forced against 60 DLGE (60/60 exact-consume) since the RPKG-Tool H3 layout desynced:** after
  DITL+CLNG ref-indices (8 B), each WavFile = `u8 0x01` + **13-byte header** (soundTag u32 + wavName u32 + u32
  + u8) + per language a **9-byte prefix** (wavIndex u32 + **1 byte** + ffxIndex u32) + subtitle (`u32 size;
  size XTEA bytes if !=0 else the u32=0`); **15 language slots, index 1 = English** (verified). Same 007 l10n
  XTEA key. Subtitle text carries a `//[SPEAKER]\\//{Name}\\//##COLOR#\\…\\<clean text>` metadata prefix
  (strip for the pool, re-attach at build). Validated **18,769/18,769 chunk0 + all chunk1 DLGE structural-OK**.
  `work/extract_corpus.py` dumped the full EN corpus; `work/build_ct_pool.py` categorised it by VISIBILITY and
  built the dedup-by-EN (md5-key) upload. **Corpus (raw / unique):** UI-LOCR **8,394 / 7,162** · story-subs
  (named speakers) **8,581 / 7,820** · ambient/combat barks (coded NPCs SEC*/MERC*, speaker-has-digit)
  **19,282 / 10,329** = **36,257 / 25,311**. **Community `/translate` pool LIVE** — `universal/
  community_translate.py import 007-first-light` → **25,311 unique rows**, 3 Hebrew categories
  (ממשק ותפריטים → כתוביות עלילה → דיבורי רקע, ordered by visibility), verified live on the public API
  (total 25,311 / open 25,311). games row id=`007-first-light` already existed.
- **NEXT (Phase 2 — everything GREEN, corpus + pool ready):** map which GFXF face each Hebrew UI/subtitle
  context uses → inject that minimal set under the ~510 KB cap (or a lighter Hebrew donor); delegate the
  ~25.3k translation ([[delegate-all-translation]]; gender ru/es/fr/it/br by lineHash;
  [[name-registry-and-internet-check]]);
  build via `gl_locr.encode` (byte-identical) + `gl_rtl.to_visual` + `append_reloc.deploy`; publish only on
  "פרסם". Tools: `work/{append_reloc,build_proof2,inplace_enc_test}.py`. Docs:
  `games/007_first_light/{RECON,FEASIBILITY,PIPELINE}.md`.

---


