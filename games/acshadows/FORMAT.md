# AC Shadows scimitar-v42 forge — binary format (CRACKED 2026-06-17)

Reverse-engineered from local bytes + the **decompiled free AnvilToolkit v1.3.4**
(`ilspycmd`, same method as AC2). Every field below is **verified on real data**
(`DataPC_boot.forge` resource idx 36626) — including the per-block checksum, which
matches byte-for-byte on multiple blocks. This is the spec the repacker is built on.

## 1. Forge container (`scimitar` v42) — `tools/acs_forge.py`
```
Header @0:
  char[8] "scimitar"
  u8      0
  u32     version            = 42 (0x2A)
  u64 @off 13                 -> index offset
Index @indexOffset:
  u32 @ +0x0C                 = resource COUNT
  u32 @ +0x28                 = pointer to RECORD ARRAY
Record (24 bytes):
  u64 offset ; u32 timestamp ; u32 flags ; u32 size ; u32 nameHash
```
Invariant `off[n+1]==off[n]+size[n]` holds 100% (verified on the 20 GB boot.forge,
129,843/129,843). A resource blob = one or more **CompressedFileData** structures
(e.g. a small metadata CFD then the big data CFD; concatenated).

## 2. CompressedFileData (CFD) — the compressed resource payload
From `AnvilToolkit.FileTypes.AnvilNext.Containers.CompressedFileData` +
`CompressionInfo` + `DataBlock`, confirmed against bytes. **Little-endian.**
```
u64  Magic = 0x1004FA9957FBAA33        (bytes 33 AA FB 57 99 FA 04 10)
CompressionInfo (7 bytes):
  i16  Version              = 3
  u8   Algorithm            = 8  (Oodle; OodleVersions[Shadows]=9 -> oo2core_9)
  u16  MaxUncompressedBlockSize        (stored value; block size = 262144)
  u16  MaxCompressedBlockSize
i32  blockCount                        (Shadows uses the Mirage-class path: i32, not u16)
BlockInfoData: blockCount x {
  i32 uncompressedSize                 (262144, except last block = remainder)
  i32 compressedSize
}
CompressedData: blockCount x {
  u32  adler  = lzo_adler32(compBytes) = zlib.adler32(compBytes, 0)   <-- START VALUE 0
  u8[] compBytes  (compressedSize bytes; Oodle-Kraken/Mermaid; lead 0x8C)
}
```
- **THE CHECKSUM** is LZO's Adler-32 variant = standard Adler-32 but the accumulator
  starts at **0** instead of 1 → in Python exactly `zlib.adler32(data, 0) & 0xffffffff`.
  Verified: block0 stored `0x1c7c866b` == calc; block1 `0x4ea0962e` == calc. **It is a
  plain data checksum, NOT a crypto/anti-tamper hash** → a home-built Python repacker
  is fully viable (this was the make-or-break unknown).
- **Oodle**: decode auto-detects the compressor, so any valid Oodle stream loads;
  encode with Kraken (oo2core_9) → lead byte 0x8C, matching the game's blocks. If a
  re-compressed block ends up `>= uncompressedSize`, store it raw (`IsCompressed=false`
  path) — but for loc text Kraken always wins.
- Decode a CFD: read header → for each block, read `compBytes` (skip the 4-byte adler),
  `Oodle.decompress(compBytes, uncompressedSize)`, concat.
- Re-encode (repack): split data into 262144-byte blocks → Kraken-compress each →
  `adler = zlib.adler32(comp,0)` → rebuild BlockInfoData + CompressedData → write CFD.

## 3. Checksum / hash helpers seen in ATK
`System.IO.Hashing` (XxHash32/64), `Adler32`, LZO's `lzo_adler32`. The **block**
checksum is `lzo_adler32` (above). Resource `nameHash` in the forge TOC is a separate
id (not needed to repack in place — we overwrite a resource by its existing offset).

## 4. Deploy (unchanged from FEASIBILITY/PIPELINE)
Overwrite the modified resource **in place at its existing forge offset** keeping the
**same on-disk size** (pad the last block / CFD tail) so the forge TOC never shifts
(the GoWR delta-0 trick) — then deploy the patched forge into the mod slot
`DataPC_boot_patch_01.forge` (back up vanilla). In-game integrity is only the Adler-32
above (reproduced) + Denuvo (protects the exe, not asset forges — texture mods load).

## 4b. Localization storage — RESOLVED (2026-06-20): oasis `0xFADE9F44` records
**The ATK fragment `LocalizationPackage` does NOT apply to AC Shadows.** Empirically
disproven: the LocalizationPackage class hash `0x6E37B1AF` (1849465967, from
ScimitarClassRegistry) is **ABSENT** from every shipped forge — full-decompress scans of
the top-50 largest + all 25k resources in the 100KB–5MB band + the full 129,844-resource
boot.forge found **zero** occurrences. So Shadows modernized away from the AC2 fragment
serialization. (§4c below is kept only as historical reference for the AC2/Mirage family.)

How AC Shadows actually stores text — **two kinds, both LITERAL UTF-16LE**:
- **Oasis line records (the translatable dialogue)** — each localized line is a field
  record inside a serialized ScimitarClass:
  ```
  [ lineID u64 ][ 0xFADE9F44 u32 ][ 00 ][ convID u64 ][ 0000 u32 ][ charLen u32 ][ UTF-16LE text ]
  ```
  `0xFADE9F44` (bytes `44 9F DE FA`) is the localized-string field-type tag. The u64
  **immediately before** the tag is the unique **Oasis line-ID** (the cross-language key);
  the u64 after is a shared conversation/group id. `charLen` = UTF-16 code-unit count.
  Tool: `tools/acs_oasis.py` (`scan`/`dump`/`extract`). Verified: boot.forge idx 36626 =
  10/10 lines with unique lineIDs; idx 27887 = 84 Yasuke/Nobunaga conversation lines.
  **Distributed, no master table** (densest resource = 84 records). Corpus:
  boot **14,084** + patch_01 **10,979** + patch_02 **7,921** → **16,725 unique lineIDs**
  (15,997 after dropping markup-only). The per-language SOUND forges have **0** records
  (pure audio); the `*_dlc.forge` (Vault/Rift/CrystalCave/WhiteRoom) have **0** (non-narrative).
- **Bare UI strings** — settings/menu resources store plain `[u32 charLen][UTF-16LE]` with
  **no inline oasis id** (e.g. idx 40549 settings descriptions; the proof-of-load edits these
  via `acs_repack.py`). Not yet community-uploadable (no stable key → would need a
  `resourceHash:index` composite key for round-trip).

**Uploaded** the 15,997 dialogue lines to the community pool (`/translate`, game
`ac-shadows`) via `universal/community_translate.py import` (2026-06-20). `string_key` =
decimal Oasis lineID, `source_en` = the English text.

**Deploy-side open question (unchanged gate):** the dialogue resources carry the ENGLISH
text inline; where the per-language (Arabic) copy of each lineID lives — same resource vs a
separate package — is not yet confirmed, so the Hebrew write-back path keyed by lineID is
still unproven. The bare-UI proof-of-load (idx 40549, same-size in-place) remains the only
demonstrated write path.

## 4c. (historical) ATK fragment LocalizationPackage — NOT used by Shadows

### LocalizationPackage format (from decompiled ATK — `AnvilToolkit.FileTypes.AnvilNext.UI`)
```
header: i32 Type ; u32 Language ; skip 12 ; u32 (skip) ; i32 num ; read `num` bytes -> BIG-ENDIAN:
  IndexedData:
    u16 MaxIndexSize ; u16 fragCount ; fragCount x StringFragment{ u16 rightIndexOrChar, u16 leftIndex }
      Decode: left==0&&right==0 -> "" ; left==0 -> UTF-16 code unit `right` ;
              else fragments[right].String + fragments[left].String   (binary tree of fragments)
  u16 tableCount ; tableCount x StringTable{ u32 FirstEntryID, u32 HeadersOffset, u32 EntriesOffset }
  per table @EntriesOffset: u16 n ; entry0={FirstEntryID, u16 offset} ; entryK={FirstEntryID+u16 delta, u16 offset}
  per table @HeadersOffset: DecodeString(reader, IndexedData, entry.offset) — reads fragment codes
    until numConsumedCodes==offset, concatenating fragment strings.
```
- **TO DO:** implement this decoder (extract `{oasisID: text}` for ALL languages incl.
  Arabic → community upload + the EN source) and the matching ENCODER (re-serialize Hebrew
  into the fragment dictionary, or — since Hebrew letters can be added as new single-char
  fragments — append Hebrew fragments + repoint entries) for the RTL in-game write. The
  DecodeString code-reading loop tail still needs reading from `LocalizationPackage.cs`.

## 5. Tooling (this project)
- `tools/acs_forge.py` — forge TOC reader (+ raw/extract).
- `tools/acs_oodle.py` — oo2core_9 Kraken decode+encode (lead 0x8C verified).
- `tools/acs_cfd.py` — CompressedFileData decode + **encode/repack** (this spec).
- Decompiled ATK source kept at `c:\tmp\atk_src\` (CompressedFileData.cs / DataBlock.cs
  / CompressionInfo.cs / Manager.cs / DataStorage.cs / Game.cs) for reference.

## מסמכים קשורים
- באותה תיקייה: [[games/acshadows/FEASIBILITY|FEASIBILITY]], [[games/acshadows/PIPELINE|PIPELINE]], [[games/acshadows/PLAN_HEBREW|PLAN_HEBREW]], [[games/acshadows/RECON|RECON]], [[games/acshadows/RESEARCH_FONT|RESEARCH_FONT]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#acshadows|CLAUDE_INDEX_games]]
