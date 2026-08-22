# Battlefield 6 — Hebrew translation FEASIBILITY

**Verdict: 🟡 GO-WITH-CAVEATS ("the entire generic Frostbite asset-read chain —
container, catalog, per-bundle byte extraction, chunks, and the real internal
SuperBundle format — is cracked and validated end-to-end against real bytes with real
decoded content; but an exhaustive scan proves BF6's actual translatable TEXT is NOT
stored in that asset system at all — it lives in a separate, undocumented loc-package
format with zero reference code or community precedent anywhere, which is a genuinely
harder, open-ended RE problem than everything solved so far, and write/deploy hasn't
been attempted at all yet").**
This is the **first Frostbite-engine title** in this project. It looked like it might be
**🔴 BLOCKED** for most of this session (the `.toc` container appeared AES-encrypted —
every other game here only ever needed a compression codec, never a per-title crypto
key) — but a from-scratch decompile of the actively-updated community tool **FMT**
(Frostbite Modding Tool) proved that read is **not actually blocked**: what looked like
encryption is a 256-byte tamper-detection **signature**, not a cipher. The container
format is now fully mapped and validated against 6 real local files with a from-scratch
pure-Python reader (`tools/bf6_toc.py`). The remaining unknowns are all standard
"AC-family" gates already solved elsewhere in this project (repack/re-sign a modified
container, locate the exact EBX string resource, font/RTL confirmation) — not a new
category of blocker.

Official Arabic localization ("ArabicSA") is confirmed to exist, both locally (an
unencrypted `chunkmanifest` lists it as a shipped language) and externally (EA's own
Battlefield Bulletin language list + an EA Forums thread implying Arabic text/UI already
renders correctly in-game) — so the Arabic-slot-hijack shortcut applies here too.

---

## Why GO-with-caveats

| Pillar | Status | Evidence |
|---|---|---|
| **Engine identified** | ✅ | EA Frostbite. Container = `.toc` (index) + `cas_NN.cas` (Content-Addressable-Storage blobs). Magic `00 D1 CE 01` (the classic Frostbite-2-era `00D1CE00` magic, one version byte later — "D1CE" ≈ "DICE", the studio). |
| **Container format (read)** | ✅ solved this session | `tools/bf6_toc.py` — pure Python, no deps, reverse-engineered by **decompiling FMT** (see "How this was cracked" below). Validated against 6 real `.toc` files: `characters.toc` (314 bundles/5,322 chunks), `globals.toc` (126/2,645), `ui.toc` (248/7,349), `vehicles.toc` (82/1,561), `weapons.toc` (9,101/9,183) all decode to small, monotonic, in-file-bounds offsets; `en.toc`/`voen.toc` correctly decode as legitimate empty (0/0) stubs. `layout.toc` uses a DIFFERENT, older format (a generic key-value "DbObject" tree, same family as the readable `chunkmanifest` — not yet ported, not needed for text). |
| **"Encryption" — RESOLVED, it's a signature, not a cipher** | ✅ | `BF6Profile.json` (FMT) has **no** `RequiresKey`/`KeyFile`/`Deobfuscator` field (compare `BFVProfile.json`: `RequiresKey:true`; `BF2042Profile.json`: `RequiresKey:true, KeyFile:"FIFA21.key"` — BF2042 literally reuses FIFA21's key). Decompiling `FMT.Core.TOCFile.Read()` shows **zero** crypto/deobfuscate calls: it reads `ToCVersion`(8B) + `ToCSig`(256B, opaque — almost certainly an RSA signature used for tamper-detection) + `ToCXor`(292B, opaque reserved/build-stamp region) and then parses the **real header PLAINLY** starting at a fixed offset of 556 bytes. The high-entropy hex I first saw was `ToCSig`, not ciphertext. |
| **Arabic slot (RTL shortcut)** | ✅ present | Local `Data/chunkmanifest` (unencrypted, readable TLV) lists **"ArabicSA"** as a full shipped language alongside English/French/German/Italian/Polish/Japanese/Korean/Spanish/SpanishMex/BrazilianPortuguese/Simplified+TraditionalChinese. Matches EA's own public Battlefield Bulletin language list. An EA Forums accessibility thread (complaining only about *screen-reader/icon* support, not garbled text) implies Arabic UI/subtitles already render correctly RTL in-game. **Not locally installed** in this repack (only `en`/`voen` are on disk) — installing the Arabic language pack is step 1 of Phase 2. |
| **Localization resource format** | 🟡 not yet located | Not yet confirmed where `LocalizedStringResource`/StringId text physically sits inside a bundle's EBX/RES data. General Frostbite precedent (used by community mods for older titles) is a StringId-keyed table; BF6-specific confirmation needs one successful bundle decompress (see gates below). |
| **Compression codec** | ✅ known, unused so far | Game ships `oo2core_9_win64.dll`/`oo2ext_9_win64.dll` (Oodle) directly — no borrowing needed (unlike AC Shadows). `BF2042Profile.json` shows Frostbite titles of this era use `Oodle` for RES/Chunk and `Zstd` for EBX; BF6's exact per-stream codec is unconfirmed but both are already-solved problems in this project (Oodle via ctypes, zstd via the `zstandard` package). |
| **Write / repack** | 🔴 not solved | FMT's own `BF6Profile.json` declares **`"CanLaunchMods": false`** and **`"AssetCompiler": "NullAssetCompiler"`** — even the tool actively adding BF6 support cannot yet build or deploy a BF6 mod. The 256-byte `ToCSig` may be verified by the game at load (unconfirmed) — if so, a modified `.toc` needs either a signature bypass or the game simply not checking it for local assets (needs an in-game test, analogous to AC Unity's "does Ubisoft Connect demand a key after a forge edit"). |
| **Anti-cheat** | 🟡 caution | EA's own anti-cheat (`EAAntiCheat.GameServiceLauncher.exe`) ships with the game. This project never attaches a debugger or touches a live game process for any title — all RE work here was 100% static (decompiling a downloaded third-party tool, hex-dumping files on disk) — and that discipline should continue. Whether the anti-cheat inspects local asset files for single-player/campaign content is unknown; deploy should start with the standalone `SP` (singleplayer/campaign) build, which is a separate exe/data tree from the main `bf6.exe`. |

---

## How this was cracked (read side) — method, for future reference

1. Hex-dumped `.toc` files directly → saw the magic `00 D1 CE 01`, then ~550 bytes of
   what looked like high-entropy data, then a plaintext hex-string tail. Initial (wrong)
   read: "this is AES-encrypted, like BFV/2042." This matches the *shape* of what the
   community reports for recent Frostbite titles, so it was a reasonable first hypothesis
   — not a wasted step, just incomplete.
2. Researched the public Frostbite modding ecosystem (`Frosty Toolsuite`, `FMT` /
   Frostbite Modding Tool). Frosty's mainline has no BF6 support. **FMT (FMTDev) shipped
   an "EARLY WIP" BF6 profile in release `FMT-26.10.9654.14105` (2026-06-07)** — very
   recent, actively maintained, free to download from
   `github.com/FMTDev/FMT.Releases`.
3. Downloaded FMT (261 MB zip, sha256 verified against the GitHub release API), **did
   NOT execute it** (running a third-party GUI tool against the game files needs the
   user's own hands/authorization — this was flagged and respected mid-session). Instead
   did 100% static analysis on the downloaded files, same method already used elsewhere
   in this project for AnvilToolkit/repak-style tools:
   - `FrostbiteProfiles/BF6Profile.json` — plain JSON, read directly.
   - `Plugins/BF6Plugin.dll` + `SDK/BF6SDK.dll` — small, normal .NET DLLs, decompiled
     directly with `ilspycmd`.
   - `FMT.exe` itself (325 MB) turned out to be a **.NET single-file bundle** with no
     top-level managed metadata (ilspycmd fails on it directly). Carved out the ~628
     individually-embedded PE assemblies by scanning the whole file for valid
     `MZ` → `e_lfanew` → `PE\0\0` triples (pure Python + `pefile`), matched class-name
     string hits (`TOCFile`, `IDeobfuscator`, `KeyManager`, `FMT.Core.dll`,
     `FMT.FileTools.dll`) to the nearest containing assembly offset, sliced those two
     assemblies out to their own `.dll` files, and decompiled *those* successfully.
   - This surfaced `FMT.Core.TOCFile.Read()` (the file-level header parser) and
     `FMT.FileTools.Readers.BinarySbReader`/`BinarySbReaderV2` (the per-bundle content
     parser) in full, readable C#.
4. Cross-referenced `RequiresKey`/`KeyFile` across every profile in FMT (`BFVProfile.json`
   has `RequiresKey:true`; `BF2042Profile.json` has `RequiresKey:true` + a *shared*
   `KeyFile:"FIFA21.key"`; `BF6Profile.json` has **neither field**) — a second,
   independent signal pointing the same direction as reading `TOCFile.Read()` directly.
5. Wrote `tools/bf6_toc.py` from the decompiled `ContainerMetaData.Read()` struct layout
   and validated it against 6 real local `.toc` files (see table above) — big-endian
   int32 fields, sane monotonic offsets, correct empty-stub detection.

All of the above is standard reverse-engineering of a **public, freely-distributed
community tool** (not the game's own protected binary/live process) — the same class of
work already done in this project for AnvilToolkit, repak, FFDConverter, etc.

## Progress since the initial pass: bundle NAMES are now readable too

A second round this session decompiled `FMT.Core.CompressedStringHandler` and ported it
to Python (`read_huffman_string` in `tools/bf6_toc.py`) — bundle names in a `.toc` are
packed into a small custom Huffman bit-tree (not a general compression codec, no
external dependency needed). Validated by decoding **all 248 real bundle names in
`ui.toc`** and more across `characters.toc`/`globals.toc`/`vehicles.toc`. This surfaced
two concrete, independent confirmations that `ArabicSA` is a real, content-bearing
locale (not just a language-selector stub): a dedicated 321-byte
`fontconfiguration_languageformat_arabicsa` bundle in `ui.toc`, and a
`legaltexts_arabicsa_bundle` in `globals.toc` — both sitting alongside the same set of
per-language bundles for English/German/French/Japanese/Korean/Spanish/Polish/Russian/
Chinese/Portuguese. A raw scan of the small per-package English loc CAS blob
(`installation/commonbase/en/cas_01.cas`) surfaced one plaintext debug string —
`"Entry = 0x300d Char = '_' Frequency = ..."` — a Huffman-table-builder trace, strongly
suggesting the **actual localized text is also Huffman-coded**, likely with the same
general technique just cracked for bundle names. See `RECON.md` for the full writeup.

## Progress, round 2: catalog resolution SOLVED; the last gap moved one layer deeper

Same session, continued: decompiled `FrostySdk.FileSystem`/`FMT.ServicesManagers.
FileSystemService` (found in `FMT.ServicesManagers.dll` — carved out exactly where
predicted) plus the generic `FMT.FileTools.Readers.DbReader` (the classic Frostbite
"DbObject" recursive key-value binary format, used across the whole engine — NOT
specific to BF6). Ported both to Python: `tools/bf6_dbobject.py` (a full DbObject
reader) and `tools/bf6_catalog.py` (the catalog-index resolver). Together they crack
**`Data/layout.toc`** completely: 135 real install chunks, 82 real superbundle names, 9
real install-package names+sizes (e.g. an 18.5 GB package — a plausible real BF6 size).
This is a **THIRD, independent confirmation of a real Arabic locale** — a full
`installation/commonbase/ar` install chunk with `language=ArabicSA`, alongside every
other language, `alwaysInstalled=True`. The catalog-index mapping itself (which
`installation/<package>/` folder a bundle's `Catalog` byte refers to) is now solved and
validated: index 26 = Arabic, index 30 = English, matching the real folders exactly.

**Round 3 (same session): the gap that "moved one layer deeper" is now CLOSED.** The
generic `FMT.Core.TOCFile.ReadCasBundles` used for the round-2 attempt turned out to be
the wrong class entirely — `BF6TOCFile` (a BF6-specific override, saved to `notes/` in
this project's very first pass but not re-examined for this method until now) uses a
genuinely different byte layout: 9 header fields (not 8, explaining `HeaderSize=36`), a
flag sentinel of `128` (not `1`), and an 8-byte prefix keyed by the catalog's
`persistentIndex` (not a small ordinal byte directly). Implemented correctly in
`tools/bf6_toc.py:read_cas_bundle()` + `tools/bf6_catalog.py:build_persistent_index_map()`
and **validated conclusively**: every resolved entry forms a clean contiguous byte chain,
resolves to a real file, and — decisively — the actual bytes decode to a genuine
`RIFF`+`EBX`/`EBXD` resource with a **plaintext, readable embedded asset path**:
`Common/UI/Assets/Fonts/FontBFText/BFText-Regular-AR` — the real Arabic font-face
reference inside the `fontconfiguration_languageformat_arabicsa` bundle, alongside its
Traditional-Chinese/Korean/Japanese/Simplified-Chinese/base counterparts. **The full
read chain — container → bundle names → catalog → per-bundle byte range → real decoded
content — is now proven end-to-end, for the first time this session.** See `RECON.md`
for the full byte-level writeup.

**Round 4 (same session, continued further): chunks + the real internal SuperBundle
format ALSO cracked — and an exhaustive search proves the text isn't in this system.**
Ported `BF6TOCFile.ReadChunkData` (chunks — validated clean on all 7,349 real chunks in
`ui.toc`; turned out to be cutscene video/audio via an FFmpeg muxer signature, not text)
and `FMT.Core.{SBHeaderInformation,BundleReader}` — the REAL internal Frostbite
"SuperBundle" structure (ebx/res/chunk lists with names, sizes, and a `resType` field),
discovering a genuine MIXED-endianness quirk (the outer container is big-endian, this
inner structure is little-endian) validated by exact structural byte-math agreement, not
guesswork. Found `FMT.FileTools.ResourceType.LocalizedStringResource = 1585851909u` (a
real, explicit-valued enum) and scanned **every single bundle's `res` list across all 5
gameplay `.toc` files — 9,871 bundles, 0 parse failures, 0 hits.** Combined with the
`loc/en.toc` files' already-confirmed empty (0 bundle/0 chunk) stub, this is a clean,
exhaustive, conclusive negative: **BF6's translatable text is not routed through the
generic asset/bundle system at all.** It must be loaded by a dedicated, undocumented
localization subsystem reading `en/cas_01.cas` directly, with an internal format that
has zero reference code anywhere in FMT and no community precedent found. See RECON.md's
"Finding the actual localization TEXT resource" for the full evidence trail.

## What's NOT yet done (the real remaining gates, Phase-1 continuation)

1. **Crack the loc-package's own internal binary format** — the genuine remaining wall,
   now precisely located (see Round 4 above + RECON.md). This needs from-scratch, blind
   byte-level analysis of the raw CAS file with NO reference code or prior art to lean
   on — a fundamentally harder, more open-ended class of problem than everything solved
   earlier this session (which always had *some* FMT code trail, even when initially
   misidentified). Not a quick continuation — needs dedicated, patient future work.
2. **Font/compression tooling for the bigger blobs** (font atlas textures, resType
   `104436933`, not yet named or decompressed) — wire up Oodle (`oo2core_9_win64.dll`
   ships with the game, no borrowing needed) once there's an actual reason to decompress
   one (i.e. once gate 1 or the font check below needs it).
3. **Install/obtain the Arabic ("ArabicSA") language pack locally** — not present on
   disk in this repack (only `en`/`voen` are). Needed to get the real Arabic skeleton
   (structure ground-truth) and to test the in-game Arabic menu/RTL claim directly.
4. **Signature/tamper question on write.** Does `bf6.exe` actually verify `ToCSig` at
   load for single-player content? Completely unexplored — no write attempt has been
   made at all yet (everything built this session is read-only).
5. **Font check** — has a concrete, resolved target (`BFText-Regular-AR`, resType
   `104436933`) but is gated on item 2 AND on cracking that resType's own internal
   atlas/glyph format (itself a proprietary Frostbite font format with no precedent
   cracked yet, comparable in scope to the dedicated font sub-projects other games in
   this repo needed).
6. **Write/repack + deployment + in-game verification** — NOT STARTED. Everything this
   session is read-only. Reaching visible Hebrew in-game additionally requires: a working
   write path for whatever format gate 1 produces, confirming gate 4 doesn't block a
   repack, and then either the user launching the patched game or a purpose-built
   capture pipeline (none exists for BF6). Note BF6 runs **EA AntiCheat** — warrants more
   caution around any live-process interaction than the purely single-player titles
   elsewhere in this project.
7. **Menu-proof** — blocked on all of the above; this is genuinely Phase-1, not Phase-2.

## Scope note

`bf6.exe` (main multiplayer/live-service build) and the standalone `SP` folder
(singleplayer campaign — its own `bf6.exe`, its own `Data/Win32` tree) are **two
separate builds** sharing the same container format. `SP` is the lower-risk target to
start with (no live-service/anti-cheat-relevant multiplayer state).

See `RECON.md` for the full byte-level format writeup and `notes/` for the saved
decompiled source + `BF6Profile.json` this feasibility call is based on.

## מסמכים קשורים
- באותה תיקייה: [[games/battlefield6/PIPELINE|PIPELINE]], [[games/battlefield6/RECON|RECON]], [[games/battlefield6/RESEARCH_LOC|RESEARCH_LOC]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#battlefield6|CLAUDE_INDEX_games]]
