# Far Cry 6 — RECON (2026-07-24)

Install: `F:\Game Lab\Far Cry 6` (Ubisoft Connect / uplay, `uplay_install.*`).
Engine: **Dunia** (Far Cry family). Main engine dll `bin\FC_m64d3d12.dll` (518 MB), exe
`bin\FarCry6.exe` (tiny bootstrap). Denuvo present (`EULA-Denuvo` in install state).
Proposed `games.id` = **`farcry6`**, detector exe `FarCry6.exe`.

## Data layout
`data_final\pc\` — Dunia FAT2 archives (`<name>.fat` index + `<name>.dat` blob):
- `common.fat/.dat` (1.28 GB) — engine/UI/shared
- `common_hd.fat/.dat` — HD textures
- `worlds\fctworlds*`, `worlds\installpkg*`, `worlds\fctber_*` — world/streaming data
- `downloadcontent\dlc_{joseph,pagan,trials,vaas}\*` — the 4 DLCs
- **language packs** = the `*_english.fat` + `*_english_feminine.fat` siblings of each world/dlc
  archive. **This install only downloaded `en-US`** — there is NO `*_arabic.*` archive on disk.
- `nomad.loc` (72 B, loose, XOR-obfuscated) — a build/lang config stub, not game text.

39 `.fat` archives total. All are FAT2 **version 11**.

## 🟢 Language slots — Arabic (`ar-SA`) is an OFFICIAL text language
`uplay_install.state` registers the full supported set under
`HKEY_LOCAL_MACHINE\SOFTWARE\Ubisoft\FarCry6\Language`:
`en-US, fr-FR, ar-SA, pt-BR, zh-CN, zh-TW, es-MX, de-DE, it-IT, ja-JP, ko-KO, th-TH,
pl-PL, ru-RU, es-ES`. **`ar-SA` (Arabic, RTL) is first-class** ⇒ the Arabic-slot hijack
applies (free engine RTL/bidi), same as AC Black Flag Resynced / AC Mirage. The install's
active language = `en-US`; the ar-SA text pack was **not downloaded** (would need a
Ubisoft-Connect language-pack download, or hijack the `en-US` slot for an LTR-VISUAL build).

## Container = Dunia FAT2 v11 — CRACKED + validated (`tools/fc6_fat.py`)
FCBConverter (`JakubMarecek/FCBConverter`, based on Gibbed.Dunia2) is the reference tool but
its `BigFile.cs` only handles FAT **versions 2–9**; FC6 is **v11** (unsupported → I reversed
the v11 header). Header:
```
@0  u32 magic   = 0x46415432 "FAT2"
@4  u32 version = 11
@8  u32 platform+flags (1 = PC)
@12 u32 (0)        <- NEW in v11 vs v9
@16 u32 (0)        <- NEW in v11 vs v9
@20 u32 entryCount
@24 entries[entryCount] * 20 bytes (Gibbed EntrySerializerV9 layout)
then subfat tail (u32 count0, u32 count1, subfats...)
```
Entry (20 B = 5×u32 LE, EntrySerializerV9):
```
a = NameHash HIGH 32     (hash halves stored high-word-first: hash = b | a<<32)
b = NameHash LOW  32
c = (UncompressedSize<<2) | CompressionScheme(2)
d = Offset >> 2
e = ((Offset & 3)<<30) | CompressedSize(30)
```
- `off = (d<<2) | ((e>>30)&3)` — **VALIDATED** (a stored entry decodes to a real
  `23.bnk\0…BKHDS` Wwise bank at its offset).
- Entries are **sorted ascending by NameHash** (monotonic 19793/19793 on common.fat — the
  proof the table start/count are right).
- `real_comp = CompressedSize & 0x1FFFFFFF`; bit `0x20000000` is a flag (its exact meaning
  is unimportant for reading — data reads fine as `real_comp` bytes for LZ, `unc` bytes for stored).
- **CompressionScheme: 0 = stored (length = `unc`), 2 = "Zlib"(enum) — but see the gate below.**
  common.fat = 457 stored + 19337 scheme-2. Reader runs clean on all 39 archives.

## Name-hash = CRC64 (`tools/fc6_crc64.py`)
Reflected CRC64, init 0, table lifted verbatim from FCBConverter `CRC64.cs` (256 entries).
Path normalization (lowercase, `\`→`/`) is a guess — **NOT yet validated against a known
path→hash pair** (need a FC6 filelist). Candidate oasis paths did not hit; treat as unverified.

## Text format = OASIS (`oasisstrings_compressed.bin`) — format known, file not yet located
From FCBConverter `OasisNew.cs` (the FCND/FC6 "new" oasis handler):
`u32 (skip) · u32 magic ∈ {CRC32("oasisstrings")=0x56de5672, 0x9ba82025} · u32 sectionCount ·
per section {u32 nameCRC, u32 stringCount, per string: u32 id, u32, u32 enum, u32 mainOffset} ·
then an LZ4-compressed value blob`. The internal string VALUES are LZ4 (`LZ4Codec`); the oasis
FILE itself sits in the FAT as a **scheme-2** entry. A magic scan of ALL 114,014 stored
entries across all 39 archives found **0 stored oasis** ⇒ the oasis is scheme-2 only ⇒ reading
it requires the scheme-2 decoder (the gate).

## 🔴 THE GATE — scheme-2 decompression is UNSOLVED (community-confirmed)
FCBConverter's `EntryDecompression.DecompressZlib` is `NotImplementedException` (only a
commented FC5/FCND block-deflate design), and its `EntryCompression` only *packs* LZO1x
(scheme 1) — so FCBConverter cannot read FC6 scheme-2 at all. The engine dll embeds
zlib(1.2.x)/deflate + LZ4 + LZO, but on real scheme-2 bytes **every standard codec fails**:
- raw-deflate / zlib-wrapped at byte offsets 0–40 → no valid stream, no `0x78` magic anywhere
- LZ4 block (offsets 0/4/8/…) → "distance too far back" at the very first match
- LZO1x (lzallright) → LookbehindOverrun
- chunked-LZ4 (WD2/Disrupt LZ4LW style: LEB varint chunk-size + LZ4, linked/reset dict) → fail
- Gibbed's 8×u16 block-deflate header → absurd block counts (header not present)
The ZenHAX FC6 thread reports the same: *"compressed ones are screwed. Probably due to diff
compression algo"*, with the detailed analysis lost to the (now-defunct) XenTAX. A sampled
clean scheme-2 entry (a world/mesh archive) has entropy **6.38 bits/byte** with bytes
**0x3a/0xba/0x39/0xb9** dominating = fp16 mesh data under a light/custom transform — so the
codec is real but non-standard. **This is the single blocker; no Oodle dll ships (rules Oodle out).**

## מסמכים קשורים
- באותה תיקייה: [[games/farcry6/FEASIBILITY|FEASIBILITY]], [[games/farcry6/PIPELINE|PIPELINE]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#farcry6|CLAUDE_INDEX_games]]
