# AC2 LocalizationPackage — binary format spec (for a pure-Python codec)

> **STATUS 2026-06-18: the codec is BUILT + VALIDATED in pure Python.**
> `work/ac2_loc.py` decodes **4,458 real English UI strings** straight from
> `DataPC.forge` (forge → LZO2A CFD blocks → char-index → text) and re-ENCODES
> them with a verified **identity round-trip** (`decode == decode(encode)`, all
> 4,458). Decompression uses `work/ac2_lzo.py` (bundled liblzo2 via ctypes).
> Remaining for an in-game deploy: container re-wrap (CFD blocks + CRC + forge
> record size-field) + the DDS Hebrew **font atlas** (gate 2) — see PIPELINE.md.
> Key facts nailed: AC2 block compression = **LZO2A** (CompressionInfo.Algorithm
> != 1); block layout `[u16 uncompressedSize][u16 compressedSize]` then `[u32
> CRC32][compressed bytes]`, **stored when sizes are equal**; the block **CRC32 =
> standard zlib CRC-32** (AnvilToolkit's `ComputeCRC32`: init 0xFFFFFFFF, poly
> 0xEDB88320, final XOR — the original game's CRC differs/Ubisoft's, but is
> discarded on read, and AnvilToolkit's zlib CRC loads in-game); the loc payload's
> `count` is a **LE i32** at `blobStart-4` = blob length (no trailing).


Reverse-engineered 2026-06-18 by decompiling AnvilToolkit's reader/writer
(`AnvilToolkit.FileTypes.AnvilNext.UI.LocalizationPackage` + `StringTable` +
`StringFragment` + `IndexedData`, and `Containers.DataFile`/`ForgeFile`). This is
the spec needed to read AND write the loc package in Python — **no GUI tool
required**. (Method: extracted `AnvilToolkit.dll` from the .NET-5 single-file
bundle, decompiled with `ilspycmd` under `DOTNET_ROLL_FORWARD=LatestMajor`.)

The decompiled C# reference is kept in `c:\tmp\anvil_src\*.cs` (not committed —
third-party decompilation; this doc restates the format in our own words).

## Layering

```
forge (scimitar v25)               -> tools/ac2_forge.py already reads/locates this
  └─ resource bytes ("FILEDATA" header + DataFile content)
       └─ DataFile: per-sub-file [u32 id][i32 size][file-header][resource bytes...]
            └─ ScimitarClass header: ClassID + u32 Hash
                 └─ LocalizationPackage payload  ← the strings live here
```

## LocalizationPackage payload (AC2 / Brotherhood / Revelations)

Outer fields use the file's normal (little-endian for AC2 via the wrapper);
the **inner blob is BIG-ENDIAN**.

```
i32   Type
u32   Language
skip  8 bytes
u32   (read-and-DISCARDED; AnvilToolkit writes the constant 0xD27F8DB5, but the
       original game files contain a different value — do NOT search for the
       constant to locate the payload; parse the wrapper instead)
i32   blobLength
byte[blobLength] blob   ← BIG-ENDIAN below:
    u16   MaxIndexSize          (typically 255)
    u16   fragmentCount
    StringFragment[fragmentCount]   each = { u16 rightIndexOrChar, u16 leftIndex }
    u16   tableCount
    StringTable[tableCount]      each = { u32 FirstEntryID, u32 HeadersOffset, u32 EntriesOffset }
    (string-table entry arrays @ EntriesOffset, code streams @ HeadersOffset — see below)
```

### StringFragment = a string-composition tree (LZ-style dictionary)
`Decode(i)`:
- `leftIndex==0 && rightIndexOrChar==0` → `""`
- `leftIndex==0`                        → a single UTF-16 char `chr(rightIndexOrChar)`
- else                                  → `Decode(leftIndex) + Decode(rightIndexOrChar)`

So fragment[0] is `""`; leaves are single chars; internal nodes concatenate two
fragments. **On WRITE, AnvilToolkit emits only leaves** (one fragment per unique
char, sorted, `""` at index 0) — it does NOT rebuild the composite tree. The game
reads either form. A Python writer can mirror this: leaves only.

### StringTable entries (@ EntriesOffset, big-endian)
```
u16 nEntries                       (== Entries.Length - 1)
entry[0] = { ID = FirstEntryID,            Offset = u16 }
entry[k] = { ID = FirstEntryID + u16 delta, Offset = u16 }    for k = 1..nEntries
```
`Offset` values are **cumulative END positions** into the code stream.

### Code stream / DecodeString (@ HeadersOffset, big-endian)
Per table, `consumed = 0`, decode each entry until `consumed == entry.Offset`:
```
b = readByte; consumed += 1
if   b <  MaxIndexSize : append fragment[b + 1]
elif b == 0xFF         : num = readInt16(BE); consumed += 2; append fragment[num + 1]
else                   : b2 = readByte; consumed += 1
                         num2 = ((b<<8)|b2) - (MaxIndexSize*255); append fragment[num2 + 1]
```
With `MaxIndexSize==255` and <256 unique chars, every code is a single byte
`b = charIndex-1` → `fragment[b+1]` = that char. (The 0xFF / two-byte forms only
appear when a package has ≥255 unique characters.)

## Encode (WRITE) — mirrors AnvilToolkit exactly
1. Collect all unique characters across every entry's string; **sort**; insert
   `""` at index 0 → `list`.
2. Fragments = one leaf per `list` item (`rightIndexOrChar = ord(char)`, `leftIndex = 0`;
   index 0 = the empty fragment `(0,0)`).
3. For each entry string, for each char: `num = list.index(char)`;
   `num<255` → write `byte(num-1)`; else → write `0xFF` + `int16(num-1)`.
4. Entry `Offset` accumulates the bytes written (1 or 3 per char), stored cumulatively.
5. Re-pack the blob (IndexedData → fragments → tableCount → tables → per-table
   entry arrays + code streams), fixing `EntriesOffset`/`HeadersOffset`.
6. ReadXml groups entries into tables: a new table every time `ID - table.FirstID
   >= 32767` OR the table reaches 50 entries.

## Wrapper / container (DataFile + forge) — the AC2 loc IS LZO-compressed

Corrected after deeper decompilation (`CompressedFileData`/`DataBlock`/
`CompressionInfo`/`Manager`): the loc payload lives inside **CompressedFileData**
blocks, LZO1X-compressed. Layout of one CompressedFileData (little-endian, the
magic confirms LE here):
```
u64  magic = 0x1004FA9957FBAA33
CompressionInfo: i16 Version, u8 Algorithm, u16 MaxUncompressedBlockSize, u16 MaxCompressedBlockSize
u16  blockCount                                  (AC2 default path)
blockInfo[blockCount]:  u16 compressedSize, u16 uncompressedSize   (each block)
blocks[blockCount]:     u32 CRC32(block), byte[compressedSize] compressedData
```
- `Algorithm == 2` → **LZO1X** (verified: `Manager.Decompress` routes LZO1X*/
  LZO2A/LZO1C to `LZO.Decompress`; block where compressedSize==uncompressedSize is
  **stored** raw). A DataFile holds ≥2 CompressedFileData (a small header CFD +
  the big data CFD).
- **LZO via the bundled DLL, no install:** `AnvilToolkit`'s `Libs/lzo.dll` is full
  **liblzo2** (exports `lzo1x_decompress`, `lzo1x_1_compress`, `__lzo_init_v2`, …).
  Call it from Python with **`ctypes.CDLL`** (it is **__cdecl** — `WinDLL`/stdcall
  corrupts the stack and crashes). `lzo_init` returns -1 with guessed type-sizes but
  decompress still works; a stored block (csz==usz) needs no LZO at all. Verified:
  the first CFD parses + its stored block extracts correctly. (Remaining: nail the
  exact CFD framing within the DataFile for the big data CFD; then decode strings.)
- There **is** a per-block **CRC32** (recompute on write). The `GetFileSignature`
  block (timestamp + "Repacked using…" + CRC32 of the author name) is AT metadata,
  not required by the game. The discarded u32 in the loc payload is still a constant
  marker, not a content CRC.
- Name→hash in the forge entry = **CRC64** of the filename (only needed when
  ADDING a resource; replacing one in place keeps its existing hash).

## WRITE without implementing LZO compression
`Manager.Compress` returns the input unchanged for unsupported algos, and
`DataBlock` stores raw when `Settings.EnableCompression==false`. So a re-encoded
payload can be written as **stored blocks** (`compressedSize == uncompressedSize`,
no LZO compress needed — only the per-block CRC32) IF the game accepts stored
blocks for this CFD. If it requires LZO, `lzo1x_1_compress` from the bundled DLL
covers it. Either way the COMPRESS direction is available; only DECOMPRESS is
strictly needed to read the originals.

## In-place patch strategy (simplest deploy, avoids a full forge rewrite)
Because resources are stored at 0x800-aligned offsets with the true size in the
record, a re-encoded payload that fits within the old resource's padded slot can
be written in place (update the record's size field only). If Hebrew makes it
larger, fall back to the full forge rewrite (ForgeFile port). Validate by
re-reading with `tools/ac2_forge.py` + decoding.

## מסמכים קשורים
- באותה תיקייה: [[games/assassinscreed2/FEASIBILITY|FEASIBILITY]], [[games/assassinscreed2/PIPELINE|PIPELINE]], [[games/assassinscreed2/RECON|RECON]], [[games/assassinscreed2/RESEARCH_SMALLSIZE|RESEARCH_SMALLSIZE]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#assassinscreed2|CLAUDE_INDEX_games]]
