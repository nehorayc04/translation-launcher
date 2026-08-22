# Far Cry 6 — FEASIBILITY (2026-07-24, updated after in-game + memory-read breakthrough)

## Verdict: 🟢 GO — every render/deploy/locate gate CLOSED; one read-mechanism gate remains with a proven fallback

The initial 🟡 was upgraded after (a) the user set the game to Arabic and it **renders perfectly**
(font + bidi confirmed), and (b) a read-only **process-memory read** recovered the oasis corpus
(id,text pairs) live. The only remaining technical gate — an **offline** scheme-2 decoder — has a
working fallback (read the corpus from RAM), so the project is feasible; it is just not a
one-session job for the full pipeline.

| Gate | Status |
|---|---|
| Engine / container index (FAT2 v11) | 🟢 **CRACKED + validated** (`tools/fc6_fat.py`; not in FCBConverter, reversed from scratch) |
| Arabic (RTL) text locale | 🟢 **OFFICIAL** (`ar-SA` reg) **AND renders in-game** — user screenshot, clean RTL |
| Font (Hebrew coverage) | 🟢 **covers RTL, zero tofu** (Arabic renders clean) → Hebrew expected fine (inject if not) |
| bidi mode | 🟢 **LOGICAL + engine-native** (menu right-aligned correct) → store natural Hebrew, no VISUAL |
| Name-hash (CRC64) | 🟢 **VALIDATED** — `languages/arabic/oasisstrings.oasis.bin` (lowercase, `\`) hits the real entry |
| Oasis file located | 🟢 **`common.fat`, hash `14f790b7fb9610c2`, scheme-2, comp 1.99 MB → unc 2.52 MB** |
| Text format (oasis) | 🟢 documented (magic 0x9ba82025 + section/string layout, internal LZ4 values) |
| Deploy mechanism | 🟢 FAT redirect → **scheme-0 stored** (raw, no encoder needed), like WD2 |
| Corpus read (live) | 🟢 **PROVEN** — `tools/fc6_memdump.py` recovered 138 frontend (id,text) pairs from RAM |
| **scheme-2 OFFLINE decoder** | 🔴 **not cracked** — custom bit-packed LZ (no byte-aligned literals, entropy 6.77); needs dll RE. **Fallback: read corpus from RAM.** |

## The one remaining gate — the scheme-2 decoder (Path A is REQUIRED; Path B proven NOT viable)
Reading the oasis needs the scheme-2 decoder. It is a **custom bit-packed LZ**: the magic + all
2,948 known Arabic strings are ABSENT verbatim from the compressed bytes (literals not byte-aligned,
crib-drag can't align), entropy 6.77; zlib/LZ4/LZO all fail; no Oodle dll ships.

- **❌ Path B (live memory dump + rebuild) — TESTED AND NOT VIABLE (2026-07-24).** A full read-only
  scan of 2.35 GB RAM recovered **2,948 unique (id, Arabic-text) pairs** (`extract/fc6_full_corpus.json`)
  — but that is **incomplete and structurally insufficient**:
  - **Incomplete (~9%):** the `common.fat` oasis is 2.52 MB decompressed ≈ tens of thousands of
    strings; only a few thousand are resident at the menu (the rest load on demand). Memory can
    never hold the whole oasis at once.
  - **Two disjoint RAM layouts, neither complete:** oasis-value blobs `[u32 id][utf16]\0\0` (gave the
    2,948, HAVE ids) vs the runtime string cache `[u32 charCount][u32 type][utf16]\0\0` (has displayed
    strings like Options/Store/New-Game but NO adjacent id). No single structure maps every string→id.
  - **Rebuild needs more than (id,text):** `OasisNew.OasisSerialize` requires per string
    `id + sectionNameCRC + enumVal (+extra) + text` grouped into sections — memory gives only id+text.
  ⇒ A faithful oasis cannot be rebuilt from RAM; a partial one would break/blank most of the UI.
- **✅ Path A — RE the scheme-2 decoder in `FC_m64d3d12.dll`** (x64dbg dynamic on the running game, or
  static around the zlib/lz4/lzo xrefs). The proper, fully-offline answer — reads every oasis exactly,
  so we edit the original minimally and re-ship (scheme-0 stored). **Now well-equipped:** we have the
  exact compressed bytes (1.99 MB) + 2,948 known decompressed strings as known-plaintext to validate a
  reversed decoder. This is a focused RE task for a dedicated session.

## Recommended next step
Crack the scheme-2 decoder (Path A) — RE it from the engine dll. Once it reads the original Arabic
oasis, the rest is standard: edit → scheme-0 deploy → menu-proof (Latin marker + Hebrew LOGICAL) →
fleet-translate → publish. The `extract/fc6_full_corpus.json` 2,948-string sample is a ready
known-plaintext + a preview of the corpus.

## Scope (partial, measured live)
`common.fat` Arabic oasis = 2.52 MB decompressed (UI/system/frontend/HUD, tens of thousands of
strings). Subtitles live in the world/`installpkg` oases (many more). Base + 4 DLCs → a fleet job.
Gender oracle: the game's own gendered locales (ru/es/fr/it) + Arabic (Semitic, ideal) are all on disk.

## Why the positives are strong
- **The index is done.** FC6's FAT2 **v11** header was never in any public tool (FCBConverter
  stops at v9); reversing it (two extra v11 header u32s, count@20, entries@24, V9 20-byte
  entries with high-word-first hash) and validating it (perfect monotonic-hash sort + a stored
  `.bnk` decoding at its computed offset) is the bulk of the hard container work.
- **Arabic is first-class**, so if the pack is present the hijack inherits the engine's own
  tested RTL — unlike AC2/Anno/GTA (LTR-hijack + manual VISUAL). English-slot LTR-hijack is the
  fallback that works with what's on disk today.
- **Deploy needs no encoder.** Redirect the oasis entry to **scheme 0 (stored)** and write the
  raw (uncompressed) bytes; the engine reads it stored. This sidesteps the compression *writer*
  entirely (proven mechanism on WD2). So only the *reader* is required — and only for the ONE
  oasis file, not the general archive.

## The blocker, precisely
Reading the existing oasis text requires the FAT **scheme-2** decoder. Every standard codec
(zlib/deflate, LZ4, LZO1x, chunked-LZ4/LZ4LW, Gibbed block-deflate) fails on real scheme-2
bytes at every offset, no Oodle dll ships, and the community (ZenHAX) hit the identical wall
with the analysis lost to defunct XenTAX. Until scheme-2 is cracked, the oasis cannot be read,
so strings can't be edited and no menu-proof can be built. (Building an oasis from scratch is
blocked too — it needs the menu string-IDs, which live in the unreadable original.)

## What a next session needs to do (in order)
1. **Crack scheme-2 decompression** — the whole project hinges on it. Leads:
   - It is byte-oriented LZ-ish but non-standard; a clean text entry (high post-compression
     entropy) may behave differently than the sampled fp16-mesh entries. First **locate the
     oasis entry** (validate CRC64 with a real FC6 filelist from fcmodding.com, or find a
     known path→hash pair) so the codec is reversed on TEXT, not mesh.
   - RE the decoder inside `FC_m64d3d12.dll` (the authoritative source): find the routine that
     consumes a scheme-2 entry (x64dbg / static disasm around the zlib/lz4/lzo string xrefs).
   - Look for a newer community FC6 unpacker (post-2022) than FCBConverter.
2. **Validate CRC64** against a known FC6 path→hash pair (get a filelist).
3. **Download the `ar-SA` language pack** (Ubisoft Connect) OR commit to the English-slot LTR
   hijack; decide which slot to ship.
4. **Menu-proof** — once the oasis is readable: edit a few menu strings (Latin marker + Hebrew
   LOGICAL and VISUAL A/B), redirect the oasis entry to scheme-0 stored, launch. One screenshot
   then closes mount + font + bidi at once.
5. Font check (inject Hebrew if the Arabic-capable font lacks it — Dunia fonts are the usual
   `.fbx`/atlas class; TBD).

## Scope (estimate, unmeasured — the oasis is unreadable)
Unknown until the oasis decodes. FC6 is a large open-world AAA (Yara / Antón Castillo / Dani
Rojas) → expect tens of thousands of subtitle + UI strings across base + 4 DLCs, likely a fleet
translation. Gender oracle: use the game's own gendered locales (ru/es/fr/it) once readable;
Arabic pack (if downloaded) is the ideal Semitic oracle.

## מסמכים קשורים
- באותה תיקייה: [[games/farcry6/PIPELINE|PIPELINE]], [[games/farcry6/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#farcry6|CLAUDE_INDEX_games]]
