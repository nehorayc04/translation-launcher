# Battlefield 6 — RECON

Install (this session): `Game Lab/Battlefield 6/` (a separate `SP/` subtree holds the
standalone singleplayer/campaign build — its own `bf6.exe` + `Data/Win32/`). EA DICE,
Frostbite engine. Cracked/repacked (RUNE: `steam_api64.rne` + `steam_emu.ini`), EA
AntiCheat binaries present (`EAAntiCheat.GameServiceLauncher.{exe,dll}`). File dates
Nov 2025 (recent AAA title for this project's timeline).

## Directory layout

```
Battlefield 6/
  bf6.exe                          main build exe
  SP/bf6.exe (own Data tree)       standalone singleplayer/campaign build
  Data/
    layout.toc                    top-level manifest (DIFFERENT format — see below)
    chunkmanifest                 unencrypted, readable — language/install-package list
    initfs_Win32, SP_initfs_Win32 init filesystem blob (same ToCVersion/Sig/Xor shape)
    Win32/
      characters.toc / globals.toc / ui.toc / vehicles.toc / weapons.toc   per-category superbundle indices
      loc/en.toc, loc/voen.toc     tiny (620B) EMPTY stubs in this repack — no bundles/chunks
      game/glaciermp/levels/<map>/<map>.toc   per-level superbundle indices (plaintext dir names — leak level list even unread: mp_abbasid, mp_badlands, mp_eastwood, ...)
      installation/<package>/     actual payload: cas.digest + cas_NN.cas (up to ~1GB each)
        commonbase/                the big base-game payload (~9.8 GB across 10 cas files) + en/ + voen/ subfolders (each with their OWN tiny cas.digest + cas_NN.cas — text + English VO)
        GRA_SAN1_DLC, SAN2_GRA_DLC, initialexperienceinstallpackage, freetrialinstallpackage, grainstallpackage, san2installpackage
      installation/*/voen/loc/{vobr,vocn,vode,voen,voes,vofr,voit,voja,voko,vomx,vopl}.toc   10 VO languages present; NO voar (no Arabic VO — expected, MENA localization is usually text-only)
```

**Only `en` (text) + `voen` (English voice) are installed locally.** No other TEXT
language pack (including Arabic) is present on disk in this repack — the language
selector's other slots exist as *chunkmanifest entries* (with an `installPackageId`)
but their payload isn't downloaded here. Getting real Arabic text requires acquiring
that install package (Phase 2 prerequisite, not yet done).

## `chunkmanifest` — unencrypted, human-readable TLV, confirms official Arabic

Not compressed, not signed like the `.toc` files — a flat key-value record stream
(`FMT.Db.DbObject`-style: length-prefixed field names + typed values). Direct hex/string
read (no tool needed) shows dozens of `{id, empty, language}` and
`{id, empty, installPackageId, language}` records. Full language list observed:

```
ArabicSA · BrazilianPortuguese · English · French · German · Italian · Japanese ·
Korean · Polish · Simplified Chinese · Spanish · SpanishMex · Traditional Chinese
```

This matches EA's own public Battlefield Bulletin language announcement for BF6, and an
EA Forums thread ("support for Arabic screen reader and UI icons") whose *complaint* is
scoped to accessibility tooling, not garbled/broken RTL text — implying Arabic renders
correctly today. `ArabicSA` = "Arabic (Saudi Arabia)" locale code, consistent with how
EA has labeled Arabic in Battlefield titles since BF4/BF1 for the MENA market.

## `.toc` container format — cracked this session

Two DIFFERENT formats coexist under the same `.toc` extension:

1. **`layout.toc`** (and likely `initfs_Win32`/`SP_initfs_Win32`) — **CRACKED this
   session** (`tools/bf6_dbobject.py`). Same 556-byte header as every other `.toc`
   (magic/sig/xor, `NullDeobfuscator` for BF6), then ONE top-level **DbObject**: a
   generic, fully self-describing recursive key-value binary format used across the whole
   engine (found via `FMT.FileTools.Readers.DbReader.ReadDbObject()`, decompiled in full).
   Encoding, one recursive field at a time: `byte tag`; `type = tag & 0x1F`; if
   `(tag & 0x80) == 0` a null-terminated field NAME follows; then by type — `1`=Array,
   `2`=Dict (both: a 7-bit-varint BYTE LENGTH, then child fields consumed until that many
   bytes are read), `6`=Bool(1B), `7`=String(7-bit-varint length + UTF-8 bytes, incl. its
   own trailing NUL), `8`=Int32 LE, `9`=Int64 LE, `11`=Float LE, `12`=Double LE,
   `15`=Guid(16B raw), `16`=Sha1(20B raw), `19`=ByteArray(7-bit-varint length + bytes).
   Ported to Python (`read_db_object`) and validated against the REAL `Data/layout.toc`
   (199,466 B): decodes cleanly into `superBundles`(82 real names), `installManifest.
   installChunks`(**135** real per-package/per-language install chunks, 21 fields each),
   `packages`(9 real install-package names + sizes, e.g. `Installation_san1installpackage`
   = 18,567,357,057 B — a very plausible real BF6 install-package size). **This is the
   THIRD independent confirmation of a real, content-bearing Arabic locale** — a whole
   dedicated `installation/commonbase/ar` install chunk exists with `language=ArabicSA`,
   `alwaysInstalled=True`, alongside every other language's own chunk (br/cn/de/en/es/fr/
   it/ja/ko/mx/pl/tw + a `vo*` voice-over set per language, `voar` notably ABSENT —
   confirms "text yes, voice no" for Arabic, matching the recon's VO-folder finding).
2. **Per-category/per-level `.toc`** (`characters.toc`, `globals.toc`, `ui.toc`,
   `vehicles.toc`, `weapons.toc`, `loc/en.toc`, `game/glaciermp/levels/*/*.toc`, …) — read
   by `FMT.Core.TOCFile.Read()` / the BF6 plugin's `BF6TOCFile` override. **This is the
   one implemented in `tools/bf6_toc.py`.**

### Byte layout (per-category `.toc`, confirmed + validated)

```
offset  size  field         notes
0       8     ToCVersion    observed constant b"\x00\xd1\xce\x01\x00\x00\x00\x00"
8       256   ToCSig        opaque; almost certainly an RSA-2048 signature (tamper detect)
264     292   ToCXor        opaque reserved/build-stamp region (name suggests XOR use
                             elsewhere/historically; NOT decoded on read, stored verbatim)
556     ...   MetaData      12x int32 BIG-ENDIAN (+3 more if TocFlags has bit 0x4 set):
                              BundleReferenceOffset, BundleOffset, BundleCount,
                              ChunkFlagOffsetPosition, ChunkGuidOffset, ChunkCount,
                              ChunkEntryOffset, Unk1_Offset, NameOffset, DataOffset,
                              Unk9_Count, TocFlags,
                              [CompressedStringCount, CompressedStringTableCount,
                               CompressedStringOffset]  (present in every non-empty file
                               observed so far — TocFlags == 4 == COMPRESSED_STRINGS)
```

All the fields after `MetaData` (`BundleReferenceOffset`, `BundleOffset`,
`ChunkGuidOffset`, `ChunkEntryOffset`, `NameOffset`, `DataOffset`,
`CompressedStringOffset`) are **relative to 556** (i.e. absolute file offset =
`556 + field value`), per `FMT.Core.TOCFile.Read()`/`BF6TOCFile.ReadChunkData()` (both
consistently do `nativeReader.Position = 556 + MetaData.XxxOffset`).

**⚠️ There is NO decryption/deobfuscation call anywhere in this read path** — confirmed
by decompiling `FMT.Core.TOCFile` in full (1,783 lines) and grep'ing for
`Deobfuscat|Aes|Decrypt|KeyBytes|KeyManager` → zero hits. The only place `Aes.Create()`
appears in the whole FMT.FileTools assembly is inside
`FMT.FileTools.Readers.BinarySbReader.ReadDbObject()`, gated behind a **per-bundle magic
marker check** (`(ReadUInt(BigEndian) ^ 0x7065636E) == 3286619587`) — i.e. AES-CBC
(`Key = IV = keyBytes`, the same quirk documented for BFV/older titles) is only used for
bundles that opt into that specific marker, and only if the profile supplies
`KeyBytes` (BF6's profile supplies none). Whether any real BF6 bundle actually sets that
marker is **unconfirmed** — the header/TOC-level read validated below never needs it.

### Validation (real files, `tools/bf6_toc.py`)

| File | bundles | chunks | notes |
|---|---:|---:|---|
| `characters.toc` (947,851 B) | 314 | 5,322 | all offsets small + monotonic + in-bounds |
| `globals.toc` (1,693,090 B) | 126 | 2,645 | same |
| `ui.toc` (464,146 B) | 248 | 7,349 | same |
| `vehicles.toc` (308,787 B) | 82 | 1,561 | same |
| `weapons.toc` (10,254,423 B) | 9,101 | 9,183 | same |
| `loc/en.toc` (620 B) | 0 | 0 | correct empty-stub decode (no bundles/chunks locally) |
| `loc/voen.toc` (620 B) | 0 | 0 | same |
| `layout.toc` | — | — | **wrong format** (see above) — garbage if parsed as MetaData, expected |

## CAS payload — confirmed NOT encrypted, contains readable structure

`installation/commonbase/cas_01.cas` (and every `cas_NN.cas`) starts with a short binary
chunk header then literal ASCII **"RIFF"** + size + **"EBX"**/"EBXD" (a RIFF-style
container wrapping a classic Frostbite EBX resource), followed by readable embedded
asset path strings (e.g. `common/fx/destructimesh/metalp__i`). This is the same
EBX/RES/Chunk resource model as every other Frostbite title — text localization
(`LocalizedStringResource`/StringId-keyed, per general Frostbite/community-mod
precedent) should live in an EBX or RES payload somewhere in these CAS blobs, reached
via a bundle's chunk/res list once decompressed (bundle compression codec not yet
confirmed for BF6 — see FEASIBILITY.md gate #1).

## How FMT (Frostbite Modding Tool) was used for this recon

`FMT-26.10.9654.14105` (github.com/FMTDev/FMT.Releases, released 2026-06-07, sha256
`715ee3c38bf0faa77069a6332e672e7b3bc2bd245f4fbf80dd6296cf9cf52051`) was **downloaded and
statically inspected only — never executed** (running a third-party GUI tool against the
live game files is the user's call, not something done autonomously here). Findings
saved to `notes/`:

- `notes/FMT_BF6Profile.json` — the profile FMT ships for BF6 (`"EARLY WIP"`,
  `CanLaunchMods:false`, `AssetCompiler:"NullAssetCompiler"` — read-only tool state).
- `notes/FMT_decompiled_BF6Plugin/` — `BF6TOCFile.cs`, `BF6AssetLoader.cs`,
  `BF6CacheReader.cs`/`BF6CacheWriter.cs`/`BF6CacheHelpers.cs`,
  `BF6KnownHashesToNames.cs`, `BF6TextureResourceReader.cs` — decompiled directly
  (normal small .NET DLLs).
- The core `FMT.Core.TOCFile` / `FMT.FileTools.Readers.BinarySbReader{,V2}` classes live
  inside `FMT.exe`'s **.NET single-file bundle** (325 MB, no top-level managed metadata —
  ilspycmd fails on it directly). They were recovered by scanning the whole file for
  valid embedded `MZ`→`e_lfanew`→`PE\0\0` triples (628 found), matching known class-name
  string hits to the nearest containing assembly, slicing that assembly out to its own
  `.dll`, and decompiling the extraction. Not saved to `notes/` (large/derivative;
  the relevant structure is fully transcribed into this doc + `tools/bf6_toc.py`
  instead).
- **`ilspycmd` gotcha hit + fixed:** the globally-installed version (8.2.0.7535) throws
  `System.ArgumentException: Argument must be between 0 and 2 (fieldCount)` inside
  `DecompilerTypeSystem.InitializeAsync` on any assembly built against **.NET 10**
  (BF6Plugin.dll's embedded PDB path shows `net10.0`) — a real ILSpy/.NET-10-metadata
  compat bug in that version. Fixed by `dotnet tool install -g ilspycmd --version
  9.1.0.7988` (the just-prior `10.0.x`/`10.1.x` releases have a broken NuGet package —
  `DotnetToolSettings.xml` missing — and fail to install entirely). Also note: this
  machine's dotnet global-tools/NuGet paths are redirected under
  `AntigravityProfiles\translation-profile3\` (profile isolation, see root CLAUDE.md) —
  `~/.dotnet/tools/ilspycmd.exe` is NOT where the freshly-installed shim actually lands.

## Bundle NAME recovery — cracked + working (`tools/bf6_toc.py`, `tools/bf6_bundle_grep.py`)

Bundle names are not plain null-terminated strings — they're packed into a **custom
binary Huffman tree** (`FMT.Core.CompressedStringHandler`, decompiled in full):
`CompressedStringTable` (int32 BE array, a flattened binary tree — a negative node
value `v` is a leaf meaning character `chr(-1-v)`, `0x00` terminates) + `CompressedStringNames`
(uint32 BE array, the packed bitstream, consumed LSB-first per 32-bit word). Each
bundle's `BundleNameOffset` field (from its 16-byte entry in the bundle table at
`556+BundleOffset`) is simply the **starting bit index** into that shared bitstream.
Ported to Python as `read_huffman_string()` — **no external codec needed at all**, this
is a small from-scratch bit-tree walk. Validated by decoding all 248 real bundle names
in `ui.toc` (and more across `characters.toc`/`globals.toc`/`vehicles.toc`) — clean,
readable, sensible paths like `win32/common/hardware/weapons/boltaction/sv98m/pkg_sv98m_bundle`.

**High-signal finds from real bundle names (`bf6_bundle_grep.py`):**
- `ui.toc` has **one small (321 B) font-configuration bundle per UI language**, incl.
  `win32/common/ui/assets/fonts/fontconfiguration_languageformat_arabicsa` (idx 185) —
  sitting alongside `..._english`, `..._german`, `..._french`, `..._japanese`,
  `..._korean`, `..._spanish`, `..._polish`, `..._russian`, `..._simplifiedchinese`,
  `..._traditionalchinese`, `..._brazilianportuguese`, `..._spanishmex`, and a
  `..._worstcase` fallback. **No Hebrew entry** (expected) — Hebrew will ride the
  `arabicsa` slot per the Arabic-hijack principle; this bundle is the natural place to
  eventually check/patch font-language routing once its EBX content is readable.
- `globals.toc` has a **per-language legal-text bundle** for ~21 languages incl.
  `win32/common/ui/legal/arabicsa/legaltexts_arabicsa_bundle` — confirms `ArabicSA` is a
  fully "real", content-bearing locale (not just a stub language-selector entry), and
  gives a second, independent per-language-content precedent beyond the font bundle.
- No bundle anywhere searched so far is named anything like `*string*`/`*localiz*`/
  `*text*` (besides the legal-text ones) or `*dialog*`/`*subtitle*`/`*narrative*` — the
  main UI-label/weapon-name/subtitle string TABLE is not organized as its own
  discoverably-named bundle at this level. It likely lives either (a) embedded as an
  EBX/RES resource *inside* another bundle (e.g. a `flow_mainmenu`-family bundle), or
  (b) inside the dedicated `loc`-package CAS blobs referenced by chunk data rather than
  bundle data (see next section) — not yet resolved.

## The `loc` package CAS blob — a live clue: it's ALSO Huffman-coded

`Data/Win32/installation/commonbase/en/loc/en.toc` (a *different* file from
`Data/Win32/loc/en.toc`, but byte-identical/620 B and likewise decodes to a legitimate
empty 0-bundle/0-chunk stub) sits next to a real **`en/cas_01.cas` (1,155,072 B)** — so
the actual English text payload is NOT indexed via this `.toc`'s bundle/chunk tables at
all; it must be reached some other way (see "open items" below).

A raw string-scan of that CAS blob found mostly opaque/compressed bytes, but ONE
completely plaintext, highly informative line survived: a debug/log format string —
`"Entry = 0x300d   Char = '_'  Frequency =     1 ( 0.00%)"` — this is a textbook
Huffman-table-builder debug trace (character + bit-code + observed frequency), i.e. the
**actual localized text is very likely ALSO Huffman-coded**, the same general technique
already cracked for bundle names above (though almost certainly a *different*, larger
tree built from real character frequencies across the whole loc corpus, not the same
tree). This is a strong, concrete lead for the next session, not a guess from nothing.

## CAS payload block framing (from `BF6TOCFile`/`FMT.Core.TOCFile.ReadDataBlock`)

Once a bundle's CAS location is known, each data sub-block inside `ReadDataBlock` is
framed as an 8-byte header + payload:

```
[0:4]  BE int32   compressed size (mask off the top byte — it's reused as a flag nibble)
[4:6]  2 bytes     num4; (num4 & 0xFF00)>>8 = extra high bits of the decompressed size
                   when non-zero low nibble; low byte of num4 & 0x7F = COMPRESSION METHOD
                   (0 = stored/raw, decompressed size == compressed size; nonzero = a
                   codec id — not yet mapped to Oodle/zstd/lz4/Huffman specifically)
[6:8]  BE u16      low 16 bits of decompressed size
[8:]   payload     `decompressed size` bytes of method-encoded data
```

This is the piece that will let a future session actually pull bytes out of a CAS file
once the *offset* into that file is known — see the next section for what's still
missing to get there.

## CASBundle per-bundle byte layout — CRACKED (the fix was a wrong class, not wrong bytes)

The generic `FMT.Core.TOCFile.ReadCasBundles` (used for the first attempt above) is
**NOT what BF6 actually uses**. `notes/FMT_decompiled_BF6Plugin/BF6Plugin/BF6TOCFile.cs`
— saved to `notes/` in the very first pass of this project's BF6 work, but not
re-examined for this specific method until now — contains `BF6TOCFile`, a **BF6-specific
override** of `ReadCasBundles` with a genuinely different byte layout:

- **9× int32 BE header fields** (not 8): `unk1, unk2, FlagsOffset, EntriesCount,
  EntriesOffset, HeaderSize, unk4, unk5, unk6` — 9×4 = 36 bytes, which is exactly why
  `HeaderSize` reads as 36 for every single bundle in every `.toc` (the generic class's
  8-field/32-byte reading was simply one field short, throwing every downstream offset
  off).
- **The flag sentinel is `128` (`0x80`), not `1`.** `if (Flags[j] == 128)`.
- **The flagged-entry prefix is 8 bytes, not 4**: `isInPatch:int16 BE` (as bool),
  `catalogPersistentIndex:int32 BE`, `cas:int16 BE` (truncated to a byte) — then the
  usual `offset:u32 BE` + `size:u32 BE`. An unflagged entry (`Flags[j] != 128`) has NO
  prefix at all and inherits catalog/cas/patch from the most recent flagged entry.
- **The catalog value on disk is the chunk's `persistentIndex` field from `layout.toc`**
  (a large, possibly-negative int), looked up via `IFileSystemService.CatalogsIndexed
  [persistentIndex]` — NOT the small ordinal `bf6_catalog.py` otherwise resolves
  bundles to. `bf6_catalog.build_persistent_index_map()` converts one to the other.

Ported to Python as the (rewritten) `tools/bf6_toc.py:read_cas_bundle()`.
**Fully validated against real bytes**: every entry across every bundle tried forms a
clean, self-consistent chain (`offset[n+1] == offset[n] + size[n]`), resolves to a REAL
file that exists on disk, and — the decisive proof — **the actual bytes at the resolved
offset are a genuine `RIFF`+`EBX`/`EBXD` resource containing a plaintext, readable
embedded asset path**. For `fontconfiguration_languageformat_arabicsa` (bundle 185 in
`ui.toc`), the 14 small entries (indices 1–14, each ~230–290 B, catalog=
`installation/initialexperienceinstallpackage` [no language suffix — a shared, "always
installed" catalog], cas=1) decode to:

```
Common/UI/Assets/Fonts/FontBFText/BFText-Regular-TC   (Traditional Chinese)
Common/UI/Assets/Fonts/FontBFText/BFText-Regular-KR   (Korean)
Common/UI/Assets/Fonts/FontAssets/BFText/BFText-Regular   (base/Latin, no suffix)
Common/UI/Assets/Fonts/FontBFText/BFText-Regular-JP   (Japanese)
Common/UI/Assets/Fonts/FontBFText/BFText-Regular-SC   (Simplified Chinese)
Common/UI/Assets/Fonts/FontBFText/BFText-Regular-AR   (Arabic!)
Common/UI/Assets/Fonts/FontBFSubHeadlineMono/BF_SUB_HEADLINE_MONO_REGULAR_FIXED
... (8 more BFHeadline/BFSubHeadline weight/style variants)
```

This is the **first real, plaintext, human-meaningful content extracted from a BF6
bundle in this project** — and it directly confirms this bundle genuinely references a
dedicated Arabic font face (`BFText-Regular-AR`) alongside every other script's own
regional face. Entries 0 and 15+ are much bigger (3.2 KB up to 4.5 MB) and are the
actual compressed font atlas/glyph binary data referenced by these paths — reading
those needs the Oodle compression-method mapping (next gate), but the INDEX/addressing
problem — the actual subject of "catalog resolution" — is now **fully closed**.

## Catalog resolution — CRACKED this session (`tools/bf6_catalog.py`)

The missing link identified in the prior pass — mapping a bundle's `CASBundle.Catalog`
byte to a real `installation/<package>/` folder — is now solved, via
`FrostySdk.FileSystem.ProcessCatalogs` / `FMT.ServicesManagers.FileSystemService.{
ProcessLayouts,GetFilePath}` (both decompiled in full from newly-carved assemblies:
`FMT.ServicesManagers.dll` — found exactly where predicted last session — and
`FMT.FileTools.Readers.DbReader`, the generic DbObject reader described above).

- **`Catalog.Name`** = `installChunk["installBundle"]` if present, else
  `"win32/" + installChunk["name"]` — read straight from `layout.toc`'s
  `installManifest.installChunks[]` (see above).
- **`FileSystemService.GetFilePath(catalogIndex, cas, patch)`** = simply
  `Catalogs[catalogIndex].Name + "/cas_" + cas.ToString("D2") + ".cas"` (prefixed
  logically by `native_data/`/`native_patch/`, which maps onto our real `Data/Win32/`
  tree once the `Win32/` prefix baked into `Name` is stripped).
- **The catalog INDEX (the `CASBundle.Catalog` byte, 0–255) is a plain 0-based ORDINAL
  POSITION** in `installChunks`, assigned in iteration order, skipping any chunk with
  `testDLC == True`. It is NOT the chunk's own `persistentIndex` field (a separate,
  unrelated signed int used only for an optional secondary lookup dict).
- Ported to Python as `build_catalog_list()` + `resolve_cas_path()`. Validated: 135
  catalogs total; index 26 = `Win32/installation/commonbase/ar` (ArabicSA), index 30 =
  `Win32/installation/commonbase/en` (English) — matching the real on-disk
  `installation/commonbase/{ar,en}/` folders exactly by position.

## Chunk resolution — CRACKED (`tools/bf6_chunk.py`)

Chunks are a SECOND, simpler content-addressing mechanism alongside bundles (whole
standalone resources referenced by GUID, not packed into a bundle's ebx/res lists).
Ported `BF6TOCFile.ReadChunkData`/`FindCatalogCasPatch` (same BF6-specific override
class that solved the CASBundle mystery above) — `{isInPatch:int16 BE, catalogPersistent
Index:int32 BE, cas:int16 BE}` (identical 8-byte shape to a flagged CASBundle entry) +
`dataOffset:u32 BE` + `size:u32 BE` per chunk, 16 bytes/entry. **Validated on `ui.toc`'s
real 7,349 chunks — zero exceptions, all resolve to real files.** Content check: a raw
string-scan of the first ~400 chunks surfaced `Lavf56.40.101` repeatedly (a libavcodec/
FFmpeg muxer signature) — `ui.toc`'s chunks are cutscene/UI **video and audio** assets,
not text. A dead end for localization specifically, but a fully working, reusable tool.

## The REAL internal SuperBundle format — CRACKED (`tools/bf6_bundle.py`)

Went one layer deeper: decompiled `FMT.Core.{SBHeaderInformation,BundleReader}` (the
class that `CASDataReader.ReadFromReader` — found via `ReadCasBundlesFromCasFiles` —
actually calls to parse a bundle's raw bytes). This is the classic, community-documented
Frostbite "SuperBundle" structure: a small header + SHA1 hash table + three lists
(`ebx`, `res`, `chunks`), where **each list entry's real DATA is a SEPARATE
`CasBundleEntry`** in the SAME bundle's resolved chain — i.e. `CasBundleEntry[0]` is
ALWAYS this metadata blob (names, sizes, resource types), and `CasBundleEntry[1..N]`
are the actual payload bytes for entry 0, 1, 2, … of the combined ebx+res+chunks list,
in that exact order.

**Key discovery: MIXED endianness, different from the outer container.** `size` (the
header's own first field) is big-endian like everything else in the outer `.toc`/
`CASBundle` system — but EVERY OTHER field inside the SuperBundle (`totalCount`,
`ebxCount`, `resCount`, `chunkCount`, `stringOffset`, `metaOffset`, `metaSize`, and every
per-entry field in the ebx/res/chunk lists) is **little-endian** — i.e. the inner bundle
payload is written in the shipping platform's NATIVE byte order (Win32 = x86 = LE),
while the outer catalog/index system is platform-normalized BE. This wasn't obvious from
the decompiled C# (the `Endian` enum's numeric tags don't map onto one global rule) —
found by testing candidate byte orders against real bytes until the structural math
checked out exactly: `metaOffset` (computed from the header) landed EXACTLY on the true
cumulative byte length of everything before it (36-byte header + N×20B SHA1 + 8B/ebx +
(8+4+16+8)B/res), a very strong, unambiguous validation signal.

**Fully validated against `fontconfiguration_languageformat_arabicsa` (bundle 185)**:
its metadata blob decodes to EXACTLY 14 ebx + 14 res entries (28 total, matching
`totalCount`), every single name/size/resType read correctly, and every one of the 28
data entries' resolved byte ranges match what the earlier raw-chain-following pass had
already found empirically (the 14 small EBX descriptors + 14 larger RES payloads,
resType `104436933` for all — the font-atlas resource type, not yet named).

## Finding the actual localization TEXT resource — HIT A GENUINE WALL

`FMT.FileTools.ResourceType` — a real, explicit-valued enum (found as a literal
NUL-separated name blob in a small not-yet-carved assembly, then confirmed as a proper
C# enum in its full decompile) — has `LocalizedStringResource = 1585851909u`. Built
`tools/bf6_find_loc.py` to scan every bundle's `res` list across every `.toc` for this
exact value.

**Result: 0 hits across all 9,871 bundles in all 5 gameplay `.toc` files
(characters/globals/ui/vehicles/weapons), 0 parse failures.** This is a clean, exhaustive,
conclusive negative — the actual translatable text is NOT stored as a
`LocalizedStringResource` inside any bundle these files reference. Combined with the
earlier finding that the dedicated `loc/en.toc` files (both `Data/Win32/loc/en.toc` and
the per-package `installation/commonbase/en/loc/en.toc`) decode to a **genuinely empty
stub — 0 bundles, 0 chunks** — the conclusion is: **BF6's localized text is not routed
through the `.toc`/bundle/chunk asset system AT ALL.** The large adjacent `en/cas_01.cas`
(1,155,072 B) must be loaded by a completely separate, dedicated localization subsystem
that reads the whole file directly and parses its own internal format — not indexed by
any mechanism this session has cracked. The one lead (a debug string suggesting Huffman
coding) is **not** from `FMT.Core.CompressedStringHandler` — that class (already fully
decompiled and ported for bundle names) has zero debug-logging code at all, so the
string is a genuine EA/DICE build-tool leftover baked into the shipped file, not a
pointer to any FMT-known format. **This specific format has zero reference code
anywhere in FMT and no community precedent found (see FEASIBILITY.md) — cracking it
would require from-scratch, blind binary analysis of the raw CAS bytes with no ground
truth to validate against**, a fundamentally different (and much harder/more
open-ended) kind of task than everything solved earlier this session, all of which had
*some* FMT code trail to follow even when initially misidentified.

## Open items for the next Phase-1 session

Container index, bundle names, `layout.toc`, catalog resolution, per-bundle byte-range
extraction, chunk resolution, and the real internal SuperBundle format are now ALL
solved and validated (see above). What's left:

1. **Crack the loc-package CAS format** (see "Finding the actual localization TEXT
   resource" above — the genuine remaining wall). This is from-scratch, blind binary
   analysis of `installation/<package>/<lang>/loc/cas_01.cas` with zero reference code
   or community precedent — a fundamentally harder, more open-ended task than anything
   solved earlier this session. No shortcut found; needs dedicated, patient byte-level
   work in a future session (entropy/structure analysis, trying known compression
   magics, searching for length-prefixed record patterns, etc.).
2. Wire up Oodle (`oo2core_9_win64.dll` ships with the game — no borrowing needed) and
   confirm the bundle-content compression-method-id mapping (see "CAS payload block
   framing" above) for the larger entries (font atlas textures etc.) — the small
   ~250 B RIFF/EBX entries decoded above needed NO decompression at all, so this is
   only needed for bigger binary blobs (e.g. the font atlas resource, resType
   `104436933`, not yet named/decompressed).
3. Get the Arabic (`ArabicSA`) language pack installed locally (not present in this
   repack) to have a real Arabic skeleton + an in-game RTL/font test target.
4. Determine whether `ToCSig` is verified at load (write-path gate) — completely
   unexplored; a repack could be silently rejected by the game for reasons that have
   nothing to do with content correctness.
5. Check the Arabic font FACE content (`BFText-Regular-AR`, now a known, resolved
   asset path with resType `104436933`) for Hebrew (U+05D0–05EA) coverage — gated on
   item 2 (need Oodle + the resType's internal atlas/glyph format, itself a Frostbite
   proprietary font format with no cracked precedent yet, akin to the dedicated
   font sub-projects other games in this repo needed).
6. **Reaching visible Hebrew in-game additionally needs**: a working write/repack path
   for whatever format item 1 produces (not started — everything so far is read-only),
   confirmation the repack survives item 4's signature check, then either the user
   launching the patched game themselves or a purpose-built capture pipeline (none
   exists for BF6 yet) — and BF6 runs EA AntiCheat, which warrants extra caution around
   any live-process interaction beyond what's needed for the other, purely
   single-player titles in this project.

## מסמכים קשורים
- באותה תיקייה: [[games/battlefield6/FEASIBILITY|FEASIBILITY]], [[games/battlefield6/PIPELINE|PIPELINE]], [[games/battlefield6/RESEARCH_LOC|RESEARCH_LOC]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#battlefield6|CLAUDE_INDEX_games]]
