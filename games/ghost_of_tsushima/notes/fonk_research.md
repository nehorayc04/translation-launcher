# Ghost of Tsushima DC — `fOnk` font research (crack-support dossier)

Date 2026-07-07. All offsets/counts VERIFIED by running Python against the real files
(`work/fonk_exe_probe.py`, `work/fonk_container_probe.py`, `..._probe2.py`, `..._probe3.py`).
Read-only. Target font resource: the ONLY `fOnk` in shipped data, at texmeshman byte
**0x156BFF7**. Goal = add 27 Hebrew outlines (U+05D0–05EA) + map those codepoints, so the
Arabic-slot Hebrew stops rendering as notdef tofu.

---

## 1. EXE struct/reflection layout (what supports the crack)

`GhostOfTsushima.exe` (29,284,984 B). 15 font-related ASCII strings. Two DISTINCT font paths:

### (a) The in-game vector font — the one we must edit
- **`SFontData`** @ file 0x01157DB8 sits inside a dense cluster of reflected **resource-type**
  names: `…SBitmap, SFontData, SVldbData, STbdbData, SRamFileData, SLoadable…`. These are the
  engine's loadable-resource classes.
- A parallel **KIND-name table** @ 0x0114B724 (12-byte-aligned, NUL-padded) lists the on-disk
  FourCC kinds: `LOADABLE, BITMAP, FONT (@0x0114B744), VOICE_LINE_DATABASE, TEXT_BLOCK_DATABASE`.
  → mapping is 1:1: `SLoadable=LOADABLE, SBitmap=BITMAP, SFontData=FONT, SVldbData=VOICE_LINE_DATABASE,
  STbdbData=TEXT_BLOCK_DATABASE`. **So the font resource's kind is "FONT" / SFontData.**
- A **handler-registration (vtable) table** @ 0x011628F8: records of `{8-byte tag, u64 code-ptrs…}`.
  Sequence there: `…Compass\0 PEWBK…, InWorld\0 PUBK…, FONTK\0 <ptr 0x0140_86C450> <0x0140_86C4C0>
  <0x0140_606550> <0x0140_807300> <0x0140_807310> <0x0140_4238F0> <0x0140_86EA80>…`. **`FONTK` = the
  on-disk chunk FourCC (`fOnk`) registered with its load/parse callbacks** (image base 0x140000000).
  These 6-7 code pointers are the exact functions to disassemble to recover the fOnk parser.
- **`FontGlyphs` @0x01107F10 and `FontVerts` @0x01107F20 are memory-arena/glob tag names** — they
  live among `VertexGlobData, IndexGlobData, TableOfContents, RpTable, VertexGlobData…` (heap-pool
  labels). ⇒ at runtime the engine allocates a **FontGlyphs pool** (per-glyph metric records) and a
  **FontVerts pool** (tessellated outline vertices). This is the definitive proof the font is a
  **VECTOR font baked to GPU triangles**, split into a glyph-record table + a vertex buffer — NOT a
  TTF and NOT a bitmap atlas.
- UI text-widget params (a separate param table @0x012784F0): `FONT_KIND, FONT_SIZE, SET_TEXT_DIRECT,
  H_JUST, V_JUST, EXTRA_CHARACTER_SPACING, LARGE_FONT_SIZE_FACTOR, GENERATE_QUAD, Color,
  HIGHLIGHT_COLOR, TEXT_EFFECT, effect_color, shadow_offset, halo_width`. `GENERATE_QUAD` +
  `EXTRA_CHARACTER_SPACING` confirm per-glyph quad emission with a horizontal advance.
- ⚠️ **`CreateFontW` / `AddFontMemResourceEx` / `RemoveFontMemResourceEx` (@0x01475F4E…) belong to
  the LAUNCHER/EOS overlay** (`Launcher_Font`, `Launcher_Font_Version` @0x010F2970) — a GDI Windows
  font for the pre-game launcher UI. **They are NOT the in-game menu/subtitle font.** Do not chase
  the GDI path; the in-game face is the SFontData/fOnk vector resource.

### (b) Inferred field layout (from serialized stream, see §3)
No field-NAME strings for glyphs exist in the exe (reflection uses **hashed** field/type tags, not
names — consistent with the packman using 64-bit hashes and the fOnk stream using hash-tag opcodes).
So the glyph-record fields (codepoint, advance, bearing, vert-offset, vert-count, kern) must be
recovered by (i) disassembling the 6 FONTK callbacks, or (ii) structural RE of the record stream.

---

## 2. Container format (packman + texmeshman) & compression answer

Stack (already solved at the archive layer): **DSAR (LZ4 blocks) → PSARC v1.4 (zlib 64 KB blocks) →
inner file `game.sprig.texmeshman`** (108,445,889 B) inside `gapack_misc_g.psarc`. Reader
`games/tlou2/tools/dsar.py`; writers `psarc_write.py` + `dsar_write.py`.

### texmeshman = `NAMS` container (raw once extracted)
- Head: `4E 41 4D 53` ("NAMS") + version `01 1D 01 00` + **two u64 content hashes**
  (0x07 96A6C2…, …), then `00000000`, then a size-ish field, then a **`0xFF`-delimited resource-path
  string table** — readable inline: `…eagle_costume_pants_mtl.msac|g.4d0bedfec30bbca663fc79e5ab3dc217`,
  `hero_arc…`. So NAMS = [header][name/path table][resource bodies].
- **NOT internally compressed (the fOnk sub-resource is RAW).** Magic scan of the whole 108 MB file:
  `lz4frame=0, zstd=0`; `zlib 78 9c = 683`, `78 da = 566` — but a 108 MB file expects ~1654 random
  hits of ANY 2-byte value, so 683/566 are **below chance = noise, not real zlib streams**. Printable
  ratio 0.489 + visible ASCII paths + FourCC tags inline ⇒ the extracted texmeshman is a raw
  serialized container. **Compression lives ONLY at the PSARC(zlib)/DSAR(LZ4) layers** — which
  `psarc_write`/`dsar_write` already rebuild. ⇒ **We can edit fOnk in the decompressed texmeshman
  directly, then re-pack; no per-resource font decompressor is needed** (this removes the biggest
  feared unknown from RECON/font.md).

### packman = `game.sprig.packman` (68,823 B) = the texmeshman index
- Header (24 B): `u64 hash0=0x584F47F6193B15D8`, `u64 hash1=0xB54DA39BA4691087`, `u32 count_a=3621`,
  `u32 count_b=3614`.
- **Sorted u64 resource-id array** from 0x18, ascending, ids carry the top bit (`0x8000…`→`0xFFFF…`),
  step mostly +2 with jumps: `0x80013E8A3870AA1E, +2, +2, +2, +2, 0x…AA83, …`. Ids are 64-bit
  name-hashes (same id space as the texmeshman resources).
- After the id array comes a **u64 offset/size table** (values like `0x1082A1, 0x123C28, 0x672E5CE,
  0x6A2807A, 0x710B897…` = ascending offsets in the 0..108 MB range, some entries 0). **The exact
  record stride is NOT a flat `id[N]|off[N]` pair** — the fOnk texmeshman offset 0x156BFF7 is not a
  literal table entry (addressing is id-hash→indirect, and part of the table holds values >file size
  = likely uncompressed-layout offsets or {offset,size} packed differently). Fully pinning the stride
  needs one more RE pass; NOT required to edit fOnk (we already have its texmeshman byte offset).
- Practical takeaway: to resize the fOnk resource you must patch its packman offset/size entry AND
  every downstream resource's offset (like GoWR's WTOC) — OR keep the edit **same-total-size**
  (delta-0), which sidesteps the packman entirely. Delta-0 is the recommended first attempt.

---

## 3. The fOnk payload = raw structured record stream (crackable, not opaque)

- Tag `fOnk` (`66 4F 6E 6B`) @ 0x156BFF7. Immediately after: `0B 8D 90 | B1 39 79 8E | 3B F2 …`.
- **Span ≈ 1.75 MB**: entropy stays 7.0–7.9 from the tag until a sharp **drop to H=4.5 at
  ~0x172BFF7** (structured low-entropy data begins there = the next resource / vertex block). So the
  font resource is roughly **0x156BFF7 → ~0x172C000**. (Large because it covers Latin + full Arabic +
  CJK + Cyrillic + Greek + Thai for all shipped locales.)
- **It is NOT compressed** — a compressed blob can't contain a 5-byte motif recurring ~1074 times.
  Two recurring serialization tokens dominate:
  - marker `B1 39 79 8E` — 32 hits in the first 1 MB, gaps clustering at multiples of 16 (16/80/480/880…).
  - field/type opcode **`10 ?? ?? 77 [8E|0E|CE|4E]`** — 1074 hits; the trailing byte cycles through
    `{8E,0E,CE,4E}` (~170 each) and a second tier `{8C,0C,CC,4C}` (~60 each): low nibble `0xE`/`0xC`
    fixed, **high 2 bits = a 2-bit field**. Record gaps cluster at 16/32/48/64/80/96 ⇒
    **16-byte-aligned records**.
  ⇒ This is Sucker Punch's tagged reflection serialization (same "sprig" stream style as the rest of
  the texmeshman), with **hashed** field tags. The FontGlyphs table (per-glyph {codepoint, advance,
  bearing, vert start, vert count}) and the FontVerts array (2D outline points, likely s16/half) live
  in this stream. Recovering the exact record = disassemble the 6 FONTK callbacks OR diff records for a
  known glyph.

---

## 4. Community precedent & tools (what exists — and doesn't)

- **NO font/fOnk precedent anywhere.** Every GoT PC modding tool stops at three resource types:
  `.xmesh` (models), `.sps` (textures→DDS), `.xpps` (text). ResHax #759 explicitly documents only
  xpps/xmesh/sps/h2o; the texmeshman is treated purely as a **name-lookup DB for mesh→texture**, never
  parsed for fonts. The fOnk crack is a genuine first — no external tool to lean on.
- **Container-level tools (usable, MIT/open):** GoTExtractor (Glumboi, C#, Nexus #65 / github.com/
  Glumboi/GoTExtractor, built on UnPSARC), UnPSARC (rm-NoobInCoding v2.3+), the GoT Mesh Extractor
  (Nexus #796) + GoT Toolkit for Blender (#819) + SilverEzredes `fmt_GoT_SPS` Noesis plugin (sps↔dds).
  In-repo `games/tlou2/tools/*` is the validated DSAR/PSARC path (use it, not the C# tools).
- **Text/localization precedent (proves edit+repack+load, incl. non-shipped langs):** GoT Translation
  Tool (Nexus #809, xpps editor), Austronesian Lang Pack (#807, hijacks the Greek slot, ships
  `gapack_misc_z*.psarc` into `cache_pc/psarc/`), commercial **Persian RTL** localization (farsisaz/
  gamesub/elaymedia). Caveat: Persian rides the **Arabic script** already in the font — it does NOT
  prove Hebrew-glyph coverage (exactly our gate). Community rule: new text ≤ original byte length
  (offset-table constraint) — our `xpps.py` already grows freely.
- **Engine internals (sprig/reflection/packman/texmeshman) are UNDOCUMENTED publicly** — no inFamous/
  Sucker Punch format write-up, no ImHex/010 template for fOnk. The `.sprig` serialization is the
  engine's runtime reflection dump; reversing it here is original work.

---

## 5. Recommended crack path (from the above)
1. **Confirm span**: cut texmeshman[0x156BFF7 : ~0x172C000], it's the raw SFontData. (Same-size edit ⇒
   ignore the packman; only the fOnk bytes change, then `psarc_write`+`dsar_write` re-pack.)
2. **Recover the record layout** — best signal-to-noise: disassemble the 6 FONTK callbacks at the
   pointers in the exe handler table @0x011628F8 (image base 0x140000000 → e.g. 0x14086C450) in
   IDA/Ghidra to read the glyph-record struct + FontVerts element format directly. Fallback: diff the
   records for two known Arabic glyphs to locate codepoint/advance/vert-offset fields.
3. **Find the codepoint→glyph lookup** inside fOnk (the notdef-tofu proves it exists) and add 27
   entries for U+05D0–05EA pointing at 27 new glyph records; append their outlines to the FontVerts
   region. Watch for a **GoWR-style off-by-one / codepoint-range gate** (see
   `games/godofwar_ragnarok/work/gowr_font.py`) — Hebrew is a disjoint block, so the lookup may be a
   sorted/ranged table that must be extended, not just appended.
4. Keep total size constant if possible (pad/reuse) for a delta-0 first proof; else patch the packman
   offset table + downstream offsets.

Tools written this session: `work/fonk_exe_probe.py`, `work/fonk_container_probe.py`,
`work/fonk_container_probe2.py`, `work/fonk_container_probe3.py`.
