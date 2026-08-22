# Attack on Titan 2 (A.O.T.2) — Recon

- **Install:** `F:\Games\Attack on Titan 2` — Koei Tecmo / Omega Force, 2018.
  FitGirl-class repack, **SteamEmu (SKIDROW) crack** — `steam_api.ini` present
  at the game root (banner ASCII art + `[GameSettings]` block), Steam appid
  `601050` emulated. Multiplayer/lobby stanzas present but irrelevant
  (single-player campaign is what's being translated).
- **Engine:** Koei Tecmo's proprietary in-house engine (internal codename
  "KTGL" per the community toolkit that documents it — the same engine family
  used across many Koei Tecmo 2016-2019 titles: Fire Emblem Warriors, Attack
  on Titan / Wings of Freedom (older sibling), Dynasty Warriors 9, etc.).
- **Top-level archives** (`LINKDATA\`):
  | file | size | role |
  |---|---:|---|
  | `LINKDATA_A.BIN` | 6.27 GB | main asset bundle |
  | `LINKDATA_B.BIN` | 7.76 GB | main asset bundle |
  | `LINKDATA_C.BIN` | 2.47 GB | main asset bundle |
  | `LINKDATA_D.BIN` | 4.3 KB | tiny — likely a manifest/index stub |
  | `LINKDATA_DLC.BIN` | 1.02 GB | DLC assets |
  | `LINKDATA_PLATFORM_DX11.BIN` | 442 MB | DX11 platform assets |
  | `LINKDATA_PLATFORM_EDEN_DX11.BIN` | 826 MB | DX11 assets for the "Eden"/Final-Battle content |
  | `REGION\LINKDATA_REGION_EU.BIN` | 291 MB | **text — European languages** (EN/FR/DE/ES-ES/ES-MX/IT tables) |
  | `REGION\LINKDATA_REGION_JP.BIN` | 49 MB | text — Japanese |
  | `REGION\LINKDATA_REGION_AS.BIN` | 97 MB | text — Asian languages (incl. Traditional/Simplified Chinese, likely Korean) |
  | `REGION\LINKDATA_REGION_EDEN_EU.BIN` | 199 MB | text for the Eden/Final-Battle expansion, EU languages |
  | `REGION\LINKDATA_REGION_EDEN_JP.BIN` | 33 MB | Eden expansion, Japanese |
  | `REGION\LINKDATA_REGION_EDEN_AS.BIN` | 67 MB | Eden expansion, Asian languages |
  | `PATCH\` | — | update/patch archives |
  | `EX\` | — | extra content |

- **Container = `LINKDATA_*.BIN`, magic `0x00077DF9`.** Cracked by REUSING two
  independent public tools (per `check-public-format-first` /
  `engine-family-reuse-check-magic`): the AoT2-specific
  `the-real-thunderlol/AOT2-MODDING-TOOLKIT` (`linkdata_extract.py`) for the
  concrete field layout, cross-validated against `neptuwunium/Cethleann`'s
  authoritative C# `LINKDATA.cs`/`Leonhart.cs` (the general Koei Tecmo
  engine-family archive reader — confirms this is the same family used by
  several other Koei Tecmo titles, not an AoT2-only format).
  - Header: `u32 magic · u32 entry_count · u32 offset_multiplier · u32 pad`.
  - Entry (16 B ×N): `u32 offset_sectors · u32 pad · u32 compressed_size ·
    u32 decompressed_size`. `byte_offset = offset_sectors * offset_multiplier`.
  - **`offset_multiplier` = 256 for every AoT2 archive** (NOT the 2048 used by
    the older sibling title's own `TitanUnpacker` tool for the same magic —
    confirmed empirically: `max(offset*256 + compressed_size) == filesize`
    exactly, on every archive checked, while the 2048 hypothesis overflows).
  - `decompressed_size == 0` → entry stored RAW. `decompressed_size != 0` →
    zlib-compressed, with an 8-byte custom header
    (`u32 decompressed_size` + `u32 informational_compressed_length`) before
    a standard zlib stream (`zlib.decompress(raw[8:])` alone is sufficient —
    the 2nd header field is not needed to decode).
- **Generic sub-format — "DataTable"** (Cethleann's own name for it; used
  engine-wide for both text tables AND arbitrary non-text data bundles):
  `u32 count` → `count × {u32 offset, u32 size}` (offset absolute from the
  table start; size = the string's UTF-8 byte length INCLUDING its NUL) →
  a packed, back-to-back, NUL-terminated blob region.
  `is_datatable()` heuristic (Cethleann `Extensions.cs IsDataTable`):
  `first_record.offset == 4 + count*8` (unaligned) or that value 16-byte-
  aligned. Every text table found in this game uses the UNALIGNED form.
- **No dedicated FourCC-tagged sub-containers were needed for text** — text
  tables are bare DataTables sitting directly as LINKDATA entries.
- **Language settings:** `F:\Games\Attack on Titan 2\steam_api.ini`
  → `[GameSettings] Language=english` is the SKIDROW/SteamEmu **default** —
  zero user action needed to land on the English text tables that the
  hijack targets. **No Arabic locale exists anywhere in this game**
  (confirmed across every `REGION_*.BIN` variant including the Eden ones) →
  this is an **LTR-slot (English) hijack**, per the `rtl-bidi` skill; the
  bidi storage mode (LOGICAL+RLM vs VISUAL vs force-RTL-base) is decided by
  the deployed in-game proof, not assumed.
- **Textures = G1T container** (magic `GT1G`), DDS payloads (BC1/BC3/BC4/
  BC7 seen), decoded via a ported/adapted `AOT2-G1T-EXTRACTOR` reader
  (`the-real-thunderlol/AOT2-G1T-EXTRACTOR`, cross-checked against
  `Raytwo/G1Tool`'s flag semantics) — used only for texture *inspection*
  during the font hunt, not for the deploy itself.
- **DRM/integrity — clean.** SteamEmu/SKIDROW crack, single-player, no
  Denuvo / EAC / BattlEye / VMProtect strings found anywhere. No content-hash
  integrity gate detected on the LINKDATA archives (the append-relocate test
  write below loaded/read back cleanly with zero collateral changes).
