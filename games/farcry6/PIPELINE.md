# Far Cry 6 — PIPELINE (planned; gated on scheme-2)

Run all tooling with the repo `.venv` python (needs `lzallright`, `lz4`, `fontTools` later).

## Tools built this session (`tools/`)
| file | role | status |
|---|---|---|
| `fc6_fat.py` | Dunia FAT2 **v11** reader — header, entry table, offsets, per-entry read | ✅ validated on all 39 archives |
| `fc6_crc64.py` | Dunia name-hash (reflected CRC64, FCBConverter table) | ⚠️ built; path-norm unvalidated |
| `fc6_codec.py` | scheme-2 chunked-deflate attempt (Gibbed 8×u16 design) | ❌ does not match FC6 data |
| `fc6_lzo.py` | LZO1x wrapper (lzallright) | ❌ FC6 scheme-2 is not LZO1x |

`python tools/fc6_fat.py <a.fat> [...]` → prints `ver / platform / entryCount / schemes /
dat-exists` per archive.

## Planned flow (once scheme-2 read is solved)
1. **Locate the oasis** — `fc6_crc64.name_hash("<oasis path>")` → find the entry across the
   `*_english.fat` (or `*_arabic.fat` if the ar-SA pack is downloaded). Validate CRC64 first.
2. **Read** the oasis entry (scheme-2 decode → oasis bytes → decode sections/strings; internal
   values are LZ4).
3. **Translate** EN→Hebrew (fleet; [[delegate-all-translation]]). LOGICAL storage if shipping
   the Arabic slot (engine bidi); VISUAL if hijacking the English slot.
4. **Re-encode** the oasis (rebuild sections + LZ4 the value blob per `OasisNew.cs`).
5. **Deploy = FAT redirect to scheme-0 stored** (no compression encoder needed):
   append the raw oasis bytes to `<archive>.dat`, rewrite that entry's descriptor to
   `scheme=0, unc=len, comp=0, off=EOF`. Back up the `.fat` once + record the `.dat` orig size;
   revert = restore fat + truncate dat (exactly the WD2 `wd2_archive.py` pattern, adapted to
   the v11 entry layout). Activation = in-game Text Language = العربية (or English for the LTR slot).
6. **Font** — inject Hebrew glyphs if the loaded font lacks them.
7. **Publish** like WD2/Anno (GitHub `farcry6-hebrew-mods` + Worker slug + Supabase `games`
   row id=`farcry6` + `mod_version_history`), price per [[mod-price-53-default]] — only on "פרסם".

## The v11 deploy descriptor (for when a redirect is written)
To redirect entry at fat byte-offset `pos` to a stored blob at dat offset `O` of length `L`:
```
c = (0 << 2) | 0                     # unc field is NOT the length for stored on read? -> set unc=L, scheme=0
c = (L << 2) | 0                     # UncompressedSize=L, scheme=0 (stored: engine reads `unc` bytes)
d = (O >> 2) & 0xFFFFFFFF
e = ((O & 3) << 30) | 0              # CompressedSize = 0 for stored
struct.pack_into("<III", fat, pos+8, c, d, e)   # a,b (hash) unchanged
```
⚠️ Verify the stored-read length convention (`unc` vs `comp`) against a real stored entry
before trusting a redirect — FC6 stored entries observed had `comp==0` and length `== unc`.

## מסמכים קשורים
- באותה תיקייה: [[games/farcry6/FEASIBILITY|FEASIBILITY]], [[games/farcry6/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#farcry6|CLAUDE_INDEX_games]]
