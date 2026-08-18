## Battlefield 6 Hebrew — Phase-1 groundwork PARTIAL, 🟡 GO-WITH-CAVEATS (2026-07-08)

New game scaffolded at `games/battlefield6/` (RECON/FEASIBILITY/PIPELINE + `tools/` + `notes/`).
Install `Game Lab/Battlefield 6` (+ a separate standalone `SP/` campaign build with its own
`bf6.exe`), EA DICE **Frostbite engine** — the **first Frostbite title in this project**, and the
first time a container looked genuinely cryptographically blocked instead of just needing a
compression codec.

- **Container = `.toc` (index) + `cas_NN.cas` (CAS blobs).** Magic `00 D1 CE 01` ("D1CE"≈"DICE").
  **The "encryption" scare was WRONG — corrected this session.** Initial hex dump of `.toc` files
  looked AES-encrypted (high entropy, no readable structure — unlike every other game here, which
  only ever needed a compression codec). Decompiling the actively-maintained community tool **FMT**
  (Frostbite Modding Tool, FMTDev, added an "EARLY WIP" BF6 profile in release `FMT-26.10.9654.14105`,
  2026-06-07, `github.com/FMTDev/FMT.Releases`) proved otherwise: `FMT.Core.TOCFile.Read()` has
  **zero** decrypt/deobfuscate calls. The "encrypted-looking" bytes are a **256-byte tamper-detection
  signature** (`ToCSig`, likely RSA-2048) + a 292-byte reserved region (`ToCXor`) — both read and
  discarded unmodified; **real plain structured data starts at a fixed offset of 556**. Confirmed by
  a second independent signal: `BF6Profile.json` has **no** `RequiresKey`/`KeyFile`/`Deobfuscator`
  field (vs. `BFVProfile.json` `RequiresKey:true`, `BF2042Profile.json` `RequiresKey:true` +
  `KeyFile:"FIFA21.key"` — BF2042 literally reuses FIFA21's key).
- **🟢 Container READ cracked + validated in pure Python — `games/battlefield6/tools/bf6_toc.py`.**
  Big-endian 12×int32 `MetaData` header (+3 more fields if a `CompressedStrings` flag is set) at
  offset 556, with bundle/chunk/name/data offsets all relative to 556. Validated against 6 real
  local `.toc` files: `characters.toc`=314 bundles/5,322 chunks, `globals.toc`=126/2,645,
  `ui.toc`=248/7,349, `vehicles.toc`=82/1,561, `weapons.toc`=9,101/9,183 (all sane/monotonic/in-bounds
  offsets), `loc/en.toc`+`voen.toc`=0/0 (correct empty-stub decode). `layout.toc` uses a DIFFERENT
  older key-value format (same family as the unencrypted, human-readable `chunkmanifest`) — not yet
  needed.
- **Method — 100% static analysis of a downloaded PUBLIC tool, zero interaction with the live game
  process.** FMT was downloaded (sha256-verified against the GitHub release API) but **never
  executed** — the sandbox's auto-mode classifier correctly blocked running it ("third-party binary
  the user never named/authorized"), and that was respected rather than worked around. Instead:
  `BF6Plugin.dll`/`BF6SDK.dll` (small normal .NET DLLs) were decompiled directly with `ilspycmd`.
  `FMT.exe` itself (325 MB) is a **.NET single-file bundle** with no top-level managed metadata
  (ilspycmd fails on it directly) — recovered by scanning the whole file for valid embedded
  `MZ`→`e_lfanew`→`PE\0\0` triples (628 found, pure Python + `pefile`), matching known class-name
  string hits (`TOCFile`/`IDeobfuscator`/`KeyManager`/`FMT.Core.dll`/`FMT.FileTools.dll`) to the
  nearest containing assembly offset, slicing it out to its own `.dll`, and decompiling that.
  **`ilspycmd` gotcha:** the already-installed global version (8.2.0.7535) throws
  `System.ArgumentException: fieldCount` inside `DecompilerTypeSystem.InitializeAsync` on any
  assembly targeting **.NET 10** (a real ILSpy compat bug) — fixed by pinning
  `dotnet tool install -g ilspycmd --version 9.1.0.7988` (the newer 10.0.x/10.1.x releases on NuGet
  have a broken package — missing `DotnetToolSettings.xml` — and fail to install at all).
- **🟢 Official Arabic locale confirmed** — `Data/chunkmanifest` (unencrypted, human-readable TLV,
  no tool needed) lists **"ArabicSA"** alongside English/French/German/Italian/Polish/Japanese/
  Korean/Spanish/SpanishMex/BrazilianPortuguese/Simplified+TraditionalChinese — matches EA's public
  Battlefield Bulletin language list; an EA Forums thread about *missing Arabic screen-reader/icon
  accessibility* implies Arabic text/RTL already renders correctly in-game (the complaint is scoped
  to accessibility tooling, not garbled text). **Not installed locally in this repack** (only
  `en`+`voen` on disk) — acquiring the Arabic language pack is a Phase-2 prerequisite.
- **🟢 Bundle NAMES also cracked (same session, continuation pass).** Names aren't plain strings —
  they're packed into a custom binary **Huffman tree** (`FMT.Core.CompressedStringHandler`:
  `CompressedStringTable`=flattened tree, `CompressedStringNames`=packed bitstream,
  `BundleNameOffset`=starting bit index). Ported to Python (`read_huffman_string` in `bf6_toc.py`,
  zero external deps) and validated by decoding **all 248 real bundle names in `ui.toc`** + more
  across `characters.toc`/`globals.toc`/`vehicles.toc`. Found two independent, content-bearing
  confirmations of `ArabicSA`: a per-language `fontconfiguration_languageformat_arabicsa` bundle in
  `ui.toc` (idx 185, 321 B) and a `legaltexts_arabicsa_bundle` in `globals.toc`, both alongside the
  same English/German/French/Japanese/Korean/Spanish/Polish/Russian/Chinese/Portuguese set. A raw
  string-scan of the small English loc CAS blob (`installation/commonbase/en/cas_01.cas`) surfaced
  one plaintext debug line — `"Entry = 0x300d Char = '_' Frequency = ..."` — a Huffman-table-builder
  trace, strongly suggesting the **actual localized text is also Huffman-coded** (same general
  technique, likely a different/bigger tree). New tool: `games/battlefield6/tools/bf6_bundle_grep.py`
  (efficient multi-term bundle-name search across tocs).
- **🟢 Catalog resolution CRACKED (same session, 2nd continuation pass).** Decompiled
  `FrostySdk.FileSystem`/`FMT.ServicesManagers.FileSystemService` (found in a newly-carved
  `FMT.ServicesManagers.dll` — exactly the assembly predicted last pass) + the generic
  `FMT.FileTools.Readers.DbReader` — the classic Frostbite **DbObject** recursive key-value binary
  format (type-tagged fields, 7-bit-varint length prefixes; used engine-wide, not BF6-specific).
  Ported both to Python: `games/battlefield6/tools/bf6_dbobject.py` (full DbObject reader) +
  `bf6_catalog.py` (catalog-index resolver). Together they crack **`Data/layout.toc`** completely —
  135 real install chunks, 82 superbundle names, 9 install-package names+sizes (one is 18.5 GB, a
  plausible real BF6 package). **THIRD independent confirmation of a real Arabic locale**: a whole
  `installation/commonbase/ar` install chunk, `language=ArabicSA`, `alwaysInstalled=True`, alongside
  every other language. The catalog-index mapping (`CASBundle.Catalog` byte → real
  `installation/<package>/` folder) is a plain 0-based ordinal position in `installChunks`
  (skip `testDLC` entries) — validated: index 26=Arabic, index 30=English, matching real folders.
- **🟢🔑 CASBundle per-bundle byte layout CRACKED (3rd continuation pass, same session) — the FULL
  read chain is now proven end-to-end.** The generic `FMT.Core.TOCFile.ReadCasBundles` tried in
  pass 2 was simply the WRONG class — `BF6Plugin.BF6TOCFile` (a BF6-specific override, saved to
  `notes/FMT_decompiled_BF6Plugin/` in this project's very FIRST BF6 pass but not re-examined for
  this specific method until now) has genuinely different logic: **9 header int32 fields** (not 8
  — explains why `HeaderSize` always read 36, never 32: 9×4=36), **flag sentinel `128`** (not `1`),
  and an **8-byte prefix** `{isInPatch:int16, catalogPersistentIndex:int32, cas:int16}` (not the
  generic 4-byte one) — the catalog value on disk is the chunk's large `persistentIndex` from
  `layout.toc`, looked up via `CatalogsIndexed`, NOT the small ordinal directly. Implemented in
  `bf6_toc.py:read_cas_bundle()` + `bf6_catalog.py:build_persistent_index_map()`. **Validated
  conclusively**: every entry across every bundle tried forms a clean contiguous byte chain,
  resolves to a real file, and the bytes decode to a genuine `RIFF`+`EBX`/`EBXD` resource with a
  **plaintext embedded asset path**: `Common/UI/Assets/Fonts/FontBFText/BFText-Regular-AR` — the
  real Arabic font-face reference inside `fontconfiguration_languageformat_arabicsa`, alongside its
  TC/KR/JP/SC/base counterparts. **This is the first real, human-meaningful content extracted from
  a BF6 bundle in this project** — container→bundle-names→catalog→byte-range→real-decoded-content
  is now a fully proven, working chain (verify: `python bf6_resolve.py <Win32-dir> <layout.toc>
  <file.toc> <bundle-name-substring>`).
- **🟢 Chunk resolution + the REAL internal SuperBundle format ALSO cracked (4th continuation pass,
  same session).** Ported `BF6TOCFile.ReadChunkData` (chunks — a 2nd, simpler content-addressing
  mechanism, GUID-referenced whole resources; validated clean on all 7,349 real chunks in `ui.toc` —
  turned out to be cutscene video/audio via an FFmpeg `Lavf` muxer signature, not text) and
  `FMT.Core.{SBHeaderInformation,BundleReader}` — the classic Frostbite "SuperBundle" structure
  (ebx/res/chunk lists with names+sizes+a `resType` field). Found a genuine **mixed-endianness quirk**
  (outer container = big-endian, this INNER structure = little-endian, i.e. shipping-platform-native)
  — confirmed not by guessing but by exact structural byte-math agreement (`metaOffset` landed EXACTLY
  on the true cumulative size of everything before it). **Fully validated** on bundle 185: decodes to
  precisely 14 ebx + 14 res entries, every name/size/resType correct, matching the earlier raw-chain
  finding exactly. New tools: `bf6_chunk.py`, `bf6_bundle.py`.
- **🔴 Exhaustive search PROVES the actual text is NOT in this asset system at all.** Found
  `FMT.FileTools.ResourceType.LocalizedStringResource = 1585851909u` (a real explicit-valued enum —
  found as a literal name blob in a newly-carved assembly, confirmed via its full decompile) and
  built `bf6_find_loc.py` to scan every bundle's res list for it. **Result: 0 hits across all 9,871
  bundles in all 5 gameplay `.toc` files, 0 parse failures** — a clean, exhaustive, conclusive
  negative. Combined with the `loc/en.toc` files' already-known EMPTY (0 bundle/0 chunk) stub, this
  proves BF6's translatable text is loaded by a **dedicated, undocumented localization subsystem**
  reading `en/cas_01.cas` directly — NOT through the generic asset/bundle/chunk system this session
  cracked. Also checked: the earlier Huffman-debug-string lead is NOT from `CompressedStringHandler`
  (that class has zero debug-logging code) — it's a genuine EA/DICE build-tool leftover, not a pointer
  to any known-FMT format. **This specific format has zero reference code anywhere and no community
  precedent — cracking it needs from-scratch blind binary analysis**, a fundamentally harder/more
  open-ended task than everything else solved this session (which always had *some* code trail to
  follow, even when initially the wrong class).
- **Verdict: 🟡 GO-WITH-CAVEATS** — the ENTIRE generic Frostbite asset-read chain (container, bundle
  names, layout.toc/DbObject, catalog resolution, per-bundle byte extraction, chunks, and the real
  internal SuperBundle format) is now solved and validated end-to-end across four continuation passes
  this session, with real decoded content (a confirmed Arabic font-face reference). But the actual
  translatable TEXT lives entirely outside that system, in an undocumented format with no shortcut
  found — and write/repack/deploy/in-game verification have NOT been attempted at all (everything
  built this session is read-only; BF6 also runs EA AntiCheat, warranting extra caution around any
  live-process work beyond the single-player titles elsewhere in this project). Reaching visible
  Hebrew in-game realistically needs multiple more dedicated sessions: crack the loc format (blind
  RE), build a write path for it, confirm `ToCSig` doesn't block a repack, solve Hebrew coverage for
  the Arabic font face (its own dedicated proprietary-font sub-project, comparable in scope to what
  other games here needed), then get an in-game screenshot (the user launching the game, or a
  purpose-built capture pipeline — neither exists yet for BF6). Docs:
  `games/battlefield6/{RECON,FEASIBILITY,PIPELINE}.md`, tools:
  `games/battlefield6/tools/{bf6_toc,bf6_dbobject,bf6_catalog,bf6_resolve,bf6_chunk,bf6_bundle,
  bf6_find_loc,bf6_oodle,bf6_bundle_grep}.py`, evidence saved in `games/battlefield6/notes/`
  (`FMT_BF6Profile.json` + `FMT_decompiled_BF6Plugin/` — including `BF6TOCFile.cs`, the file that
  broke the CASBundle/chunk case open). Playbook appendix
  (`universal/NEW_GAME_GROUNDWORK_PLAYBOOK.md`) updated with a Battlefield 6 row.

---


