# Ghost of Tsushima DC — repack / identity round-trip gate (Phase 1)

Verified 2026-07-07 against the REAL install `F:/Games/Ghost of Tsushima DC`.
Tooling reused verbatim from TLOU2 (`games/tlou2/tools/{dsar.py,psarc_write.py,dsar_write.py}`).
Scripts here: `probe.py`, `inner_probe.py`, `roundtrip.py`, `roundtrip2.py`, `diffanalyze.py`.

## Verdict — REPACK PROVEN (semantically loadable). Byte-identity: NO (expected, fine).

The container stack is IDENTICAL to The Last of Us Part II Remastered:
**OUTER DSAR v3.1 (LZ4, 256 KB chunks) → INNER PSARC v1.4 (blocks STORED, blockSize 0x10000).**
The existing TLOU2 reader/writers work on GoT with NO code change (two small caveats below).

### What was proven on `gapack_misc_p.psarc` (1,162,699 B, 26 files):
- **L2 inner semantic** — rebuild inner PSARC, re-parse, all 26 files byte-exact: **PASS**
- **L3 DSAR wrap → read back** (models the game's own load path) — all files byte-exact: **PASS**
- **L4 single-file replace** (swap the largest file for an identical copy): **PASS**
- **STORED-inner size match** — `psarc_write.build(..., compress=False)` reproduces the
  EXACT inner size **2,254,050 B == original** (proves GoT ships stored-inner + LZ4-outer).
- **FREE GROWTH** — rebuild with a file doubled, wrap, read back: **PASS**. PSARC self-describes
  offsets, so **no delta-0 padding constraint**: the Hebrew `.xpps` may be LARGER than the
  17 MB Arabic slot.

### Why byte-identity is NOT achieved (all cosmetic, none affect loading):
1. **DSAR/LZ4 encoder** — python-lz4 output ≠ the shipping encoder byte-for-byte (both decompress fine).
2. **DSAR on-disk layout** — the game 16-byte-aligns each chunk and uses reserved filler `55*7`
   (flags byte0=0x03); `dsar_write.py` packs contiguously with filler `54 55*6`. Purely container bookkeeping.
3. **Inner file-DATA order** — the game's TOC is md5-sorted (for binary search) but the DATA blocks
   are laid in *manifest* order (a different permutation); `psarc_write` lays data in md5 order.
   → 2.06M/2.25M data bytes differ *positionally*, content identical (semantic PASS).

## Deploy facts (for Phase 2)
- **Inner MUST be STORED** (`compress=False`). Per the TLOU2 engine lesson, a zlib-compressed
  inner block is mis-decoded by the ND engine ("UNKNOWN STRING"); the DSAR/LZ4 outer does compression.
- **Safe delta = free growth** (no padding math).
- **Target archive** `gapack_misc_l.psarc` (1.43 GB on disk / inner 2,099,298,364 B, 495 inner files,
  flags=0xe): `/lang_arabic_text.xpps` (17,064,240 B, the Hebrew slot) + `/lang_english_text.xpps`
  (16,583,124 B, source) are single inner entries → the deploy edit is a **single-file replace** of
  `lang_arabic_text.xpps`. (Rebuilding a 2 GB DSAR is heavy but the same proven code path; a per-file
  in-place patch could be added later for speed. NOT attempted here — no game files touched.)
- Deploy MECHANISM (mods folder vs loose override vs core replace) is a SEPARATE Phase-1 gate — not in scope.
- Whether the GoT *engine itself* (not just our modelled reader) mounts a rebuilt DSAR is the same
  end-gate TLOU2 closed in-game; the STORED-inner requirement carries over and was honored here.

## Format notes for a GoT writer (deltas vs TLOU2)
- Inner PSARC header `flags = 0x0e` (TLOU2 uses 0x0c) — `psarc_write.build(flags=0x0e)`. blockSize 0x10000, entrySize 30, comp field literal `zlib`.
- DSAR reserved filler = `55 55 55 55 55 55 55`; chunks 16-byte aligned on disk.
- **ct=254 padding-sentinel**: some archives (`gapack_misc_b`) have a DSAR entry `compType=254, cs=0`
  whose region is inner-PSARC alignment padding (on-disk literal `PADDING*`). `dsar.py` CRASHES on it
  (lz4 on empty input). Our writer never emits ct=254 (uses LZ4/stored), and round-trips are accepted,
  so it's a READER gap only. Guard needed before extracting any archive that contains it (`misc_p` and
  the target lang files are clean).
