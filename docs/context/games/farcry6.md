## Far Cry 6 Hebrew — 🟢🟢 ALL GATES CLOSED, scheme-2 codec CRACKED, full read+write pipeline PROVEN, Hebrew menu-proof DEPLOYED (2026-07-24)

New game at `games/farcry6/` (RECON/FEASIBILITY/PIPELINE + `tools/`). Install `F:\Game Lab\Far Cry 6`,
Ubisoft **Dunia** engine (`FC_m64d3d12.dll` 518 MB), Denuvo. `games.id` = **`farcry6`**, detector exe
`FarCry6.exe`. **The exe is NEVER touched (Denuvo — user constraint); only the data archive
(common.dat/common.fat) is edited, the standard translation mechanism.**  Memory [[farcry6-groundwork-caveats]].

### 🔓 THE "one gate" from last session — scheme-2 — is SOLVED. It was NOT a custom bit-packed LZ.
The previous session concluded scheme-2 = "custom bit-packed LZ, community-unsolved". **That was WRONG,
caused by a decode bug that made us read the wrong bytes.** The real answer, from FCBConverter's own
`Program.cs` (`GetFatEntriesDeserialize` + the unpack dispatch, curled to `c:\tmp\fcbc\`):
- **scheme 2 = LZ4** (FatEntry.cs enum `None=0, LZO1x=1, LZ4=2`), and for **FAT v11 (`dwVersion>9`) it is
  ONE standard LZ4 block over the whole entry** (`LZ4Codec.Decode(whole, whole)`). The custom `Different=true`
  LZ4 is only for v9. `lz4.block.decompress(raw, uncompressed_size=unc)` decodes it perfectly.
- **🔴🔴 THE ROOT-CAUSE BUG: v11 FAT entry layout ≠ v9.** `fc6_fat.py` used the v9 packing → a WRONG offset
  → it extracted garbage bytes (`byte0=0x04`, an invalid LZ4 start), which is what made scheme-2 look
  "custom/unbreakable". The correct v11 decode (Program.cs:3762, "thx to miru"): offset is **16-byte
  aligned and split across two fields**, CompressedSize is only **29 bits**:
  `offset = ((e>>29) | (dd<<3)) << 4` · `comp = e & 0x1FFFFFFF` (dd=4th u32, e=5th). Fixed in `fc6_fat.py`.
  **UNIVERSAL: when a codec looks "custom/unbreakable", first re-verify you are reading the RIGHT bytes —
  a wrong container-offset decode is indistinguishable from a wrong codec, and cost a whole session here.**

### 🟢 FULL read+write pipeline built + validated byte-exact
- **`tools/fc6_fat.py`** (FIXED) — FAT2 v11 reader with the correct offset/comp decode + `read_data` LZ4.
- **`tools/fc6_oasis.py`** (NEW) — the OASIS codec, reversed from `OasisstringsCompressedFile.cs` +
  the real bytes. Layout: `u32 ver=1, u32 sectionCount, [Section]`; Section = `NameCRC, StringCount,
  [Id,SectionCRC,EnumCRC,Extra(=0xFFFFFFFF) ×N (16B each)], CompressedValuesSectionsCount, [CompressedValues]`;
  CompressedValues = `LastSortedCRC, s32 CompressedSize, s32 DecompressedSize, bytes` where the inner
  bytes are a **standard LZ4 block** (`LZ4Decompressor64` default) decoding to `s32 StringCount,
  [SortedEnums u32 ×N], [StringOffsets s32 ×N], [(id u32, utf-16le value, u16 0) ×N]`, ordered by EnumCRC.
  **`parse(data)` = byte-EXACT** on the live common.fat: **1117 sections, 26,793 strings, 0 leftover.**
- **`edit(data, {(sectionCRC,id): hebrew})`** rebuilds ONLY the sections owning an edited string (all
  others copied verbatim → tiny on-disk delta, safest vs integrity checks). Inner blocks re-emitted as
  **ALL-LITERAL LZ4** (any decoder accepts it; FCBConverter's own compressor is commented-out/null, so
  it can READ but not WRITE FC6 oasis — we can do both). Round-trip: 26,793 values, **0 mismatches**.
- **`tools/fc6_deploy.py`** (NEW) — deploy = **append the raw edited oasis to common.dat at a 16-aligned
  EOF offset (original bytes untouched) + rewrite the oasis FatEntry to scheme-0 stored** (v11 packing);
  backup `common.fat.he_backup` + journal the orig dat length. `--revert` restores fat + truncates dat.
  **No encoder needed** (scheme-0 stored). `--proof` / `--revert` / `--status`.

### ✅✅ HEBREW RENDERS IN-GAME — every gate CLOSED, USER-CONFIRMED (2026-07-25, "עכשיו זה מושלם")
The main menu shows **"המשך משחק"** (Continue) + **"שלום עברית"** in clean correct-RTL Hebrew.
- **🔴🔴 THE FONT KEY — the menu font is NOT in common.dat.** The first text-only proof MOUNTED (Continue
  changed) but rendered `????`: the menu font lacked Hebrew. FC6 has **22 per-script glyf fonts, and the
  SAME font (same name-hash) exists in BOTH `common.fat` AND `worlds/installpkg.fat`** — but the game loads
  the **frontend** font from **installpkg** (the install package). Injecting Hebrew into common's copy did
  NOTHING; injecting into **installpkg's `Noto Kufi Arabic`** → Hebrew renders. **UNIVERSAL: when a
  font-hash lives in several archives, NUKE-TEST each archive's copy to find which one actually renders
  before concluding the font is dll-packed** (nuking common's glyf fonts left the menu readable; nuking
  installpkg's Noto Kufi Arabic broke the menu Arabic — that pinned it). `tools/fc6_font.py`
  `_add_hebrew` (Heebo, keeps Arabic) / `_remap` (Latin→Hebrew hijack, unused — no CP1256 after all).
- **🔴 NO CP1256 conversion** — I chased a `WideCharToMultiByte`/Thai→`?` red herring for hours; the `?`
  was purely the wrong-archive font lacking Hebrew (Thai `?` = Noto Kufi's notdef). The Hebrew reaches
  the font intact; the UI is Scaleform GFx + HarfBuzz (the `<!DOCTYPE html>` perf-monitor overlay with
  inlined FC-Common/FC-Titling WOFF is a RED HERRING — NOT the menu).
- **🔴 bidi = VISUAL — store PRE-REVERSED** (`python-bidi get_display base_dir='R'`, like GTA/AC2/RDR2).
  Stored LOGICAL it rendered MIRRORED (user: "עברית ראי"; my screenshot read it as correct — the
  [[hebrew-screenshot-transcription-trap]], trust the user); VISUAL → perfect.
- **Deploy = scheme-0 to TWO archives:** oasis text → `common.fat`; font → `worlds/installpkg.fat`.
  `fc6_deploy.deploy_archive(fat_path, {hash:bytes})` / `revert_archive` are archive-generic (each keeps
  its own `.he_backup` + `.he_journal.json`). Denuvo did NOT block the archive edits.
- **`tools/fc6_autocheck.py`** — autonomous launch→wait-menu→screenshot→CLOSE (dxcam DXGI,
  `__COMPAT_LAYER=RUNASINVOKER`, foreground-pid + settle detect). `tools/fc6_ramfont.py` = read-only
  RAM font probe. These let the diagnosis run without the user (they only look at the saved PNG).
- **NEXT — Phase 2:** delegate the 26,793-string translation ([[delegate-all-translation]]) → build every
  menu/UI string via `fc6_oasis.edit` + VISUAL + inject Hebrew into installpkg's Noto Kufi Arabic (and
  nuke-test which archive owns the SUBTITLE/HUD font the same way) → `fc6_deploy` → publish on "פרסם".

### The rest (all confirmed earlier this project, still true)

- **🟢 BREAKTHROUGH (user set the game to Arabic + a live memory read):** Arabic **renders perfectly
  in-game** (user screenshot) → **font covers RTL (zero tofu)** and **bidi = LOGICAL + engine-native**
  (menu right-aligned correct) — two gates closed by one screenshot (store natural Hebrew, no VISUAL).
  Then a read-only **process-memory read** (`tools/fc6_memdump.py`, ctypes ReadProcessMemory, no admin/
  no write) found the parsed oasis strings in RAM and recovered **138 frontend (id, Arabic-text) pairs**
  → `extract/fc6_frontend_corpus.json`. Also found the file-path template **`LANGUAGES/%s/
  oasisstrings.oasis.bin`** in memory, which **VALIDATED CRC64** and located the exact oasis entry.
- **🟢 Arabic oasis LOCATED:** `languages/arabic/oasisstrings.oasis.bin` (CRC64 lowercase + `\`) →
  **`common.fat`, hash `14f790b7fb9610c2`, scheme-2, comp 1,986,860 → unc 2,520,692** (2.5 MB UI/
  system text; subtitles live in the world/`installpkg` oases). The "english"-named archives bundle
  ALL text languages (name = voice lang).
- **~~scheme-2 offline decoder~~ = SOLVED (see the top of this section).** scheme-2 = a single standard
  LZ4 block; the "custom/unbreakable" conclusion was a v9-vs-v11 FAT offset bug reading the wrong bytes.
  The memory-read Path B (`fc6_dump_corpus.py`, `extract/fc6_full_corpus.json`, 2,948 pairs) is now moot —
  the disk oasis reads exactly (26,793 strings). `fc6_memdump.py` stays only as the read-only RAM tool.
- **Corpus (measured from the real disk oasis):** `common.fat` Arabic oasis = **1117 sections, 26,793
  string records / ~22,331 unique values, 21,978 Arabic** (UI/system/HUD/pause/weapons/missions;
  main-menu Options/Store/New-Game live in a DIFFERENT oasis, so the menu-proof targets pause-menu +
  Continue). Subtitles live in the world/`installpkg` oases (Phase-2 fleet). Base + 4 DLCs. Gender
  oracle: the game's own gendered locales (ru/es/fr/it) + Arabic once those oases are read.
- Sources curled to `c:\tmp\fcbc\` (FCBConverter `Program.cs` unpack dispatch + `GetFatEntriesDeserialize`
  + `OasisstringsCompressedFile.cs`). Tools: `fc6_fat / fc6_oasis / fc6_deploy / fc6_crc64 / fc6_memdump`.

- **🟢 Container = Dunia FAT2 v11 — CRACKED + validated (`tools/fc6_fat.py`), NOT in any public
  tool.** FCBConverter (`JakubMarecek/FCBConverter`, ex-Gibbed.Dunia2) only handles FAT v2–9;
  FC6 is **v11** so I reversed the header from scratch: `magic FAT2 · u32 ver=11 · u32
  platform(1=PC) · TWO new v11 u32s(@12,@16=0) · u32 entryCount@20 · entries@24`. Entry = 20 B =
  Entry = 20 B (5×u32): hash halves high-word-first (`hash=(a<<32)|b`); `c=(unc<<2)|scheme`.
  **⚠️ v11 offset/comp packing ≠ v9 (this was the session-costing bug):** `offset = ((e>>29)|(dd<<3))<<4`
  (16-byte aligned) · `comp = e & 0x1FFFFFFF` (29 bits) — dd=4th u32, e=5th (Program.cs:3762).
  Scheme 0=stored, 1=LZO1x, 2=LZ4. Reader runs clean on all 39 archives (entries sorted by hash).
- **🟢 Arabic (`ar-SA`) is an OFFICIAL FC6 text language** — registered in `HKLM\SOFTWARE\
  Ubisoft\FarCry6\Language` alongside 15 langs (from `uplay_install.state`) → Arabic-slot hijack
  gives free engine RTL/bidi (like AC Black Flag/Mirage). **BUT this SKU downloaded only `en-US`;
  no `*_arabic.*` archive is on disk** — either download the ar-SA pack, or hijack the `en-US`
  slot (LTR + VISUAL, works with what's present).
- **🟢 Text format = OASIS (`oasisstrings_compressed.bin`)** — documented from FCBConverter
  `OasisNew.cs` (magic u32@4 ∈ {CRC32("oasisstrings")=0x56de5672, 0x9ba82025}; section/string
  table; internal values LZ4). **🟢 Name-hash = CRC64** (reflected, init 0; table lifted verbatim
  → `tools/fc6_crc64.py`; ⚠️ path-normalization unvalidated — candidate oasis paths didn't hit,
  need a real FC6 filelist to validate). A magic scan of **all 114,014 stored entries across all
  39 archives found 0 stored oasis** → the oasis is scheme-2 only ⇒ reading it needs the codec.
- **🟢 Deploy needs NO encoder** — redirect the oasis entry to **scheme-0 stored** + write raw
  bytes (engine reads stored), the WD2 `wd2_archive.py` pattern adapted to the v11 entry layout.
  So only the *reader* is required, and only for the ONE oasis file.
- **⚠️ Note on the earlier scheme-2 analysis:** the "every codec fails / entropy 6.38 mesh"
  observations were made on the WRONG bytes (v9-offset bug) and on a mesh entry, not the oasis. They
  are void — scheme-2 is plain LZ4 (proven on the real oasis). Kept only as the cautionary example.
- **NEXT — Phase 2 (all gates closed):** (1) user launches the deployed menu-proof and confirms Hebrew
  renders correctly (the last real-world check). (2) Read the subtitle/world oases (same FAT+oasis
  codec) to get the full corpus. (3) Delegate the translation ([[delegate-all-translation]], New-Era +
  the game's own ru/es/fr/it as gender oracle) → `fc6_oasis.edit` → `fc6_deploy` → publish like the
  other games, on an explicit "פרסם". Docs: `games/farcry6/{RECON,FEASIBILITY,PIPELINE}.md`; tools
  `games/farcry6/tools/fc6_{fat,oasis,deploy,crc64,memdump}.py`. Sources: `c:\tmp\fcbc\` (FCBConverter).

---


