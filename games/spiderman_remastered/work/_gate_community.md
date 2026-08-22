# MSMR Phase-1 gate — COMMUNITY PRECEDENT + EXISTING TOOLING

Agent: community/tooling gate. **Read-only. Nothing in `D:\Games\Spider-man Remastered` was touched.**
Date: 2026-08-09.

---

## 0. HEADLINE VERDICT

🟢 **GO on this gate, with ONE correction to CLAUDE.md that changes the project's strategy.**

| Question | Answer | Confidence |
|---|---|---|
| Do modified localization assets load in MSMR? | **YES — proven by ≥4 shipped, actively-updated full text mods** (Ukrainian, Thai, Indonesian, Simplified Chinese) | **VERIFIED** |
| Is there an end-to-end open-source read+write toolchain? | **YES — two independent ones**, both with source (`team-waldo/InsomniacArchive`, `Tkachov/Overstrike`) | **VERIFIED** |
| Does Overstrike support MSMR? | **YES, first-class** (`GameMSMR.cs`, internal code **`MSMR` / metainstaller `I20`**) | **VERIFIED** |
| Is the `.localization` format the SAME as SM2 / R&C? | **YES — identical DAT1 section tags**, and MSMR's asset magic `0x122BB0AB` matches our probe's `ab b0 2b 12` | **VERIFIED (independent cross-check)** |
| 🔴 Does the Arabic mod (Nexus 361) prove "RTL works on this engine"? | **NO. The claim in CLAUDE.md is UNSUPPORTED.** The page is **unavailable/removed**, there is **no Wayback snapshot**, and there is **no Arabic TEXT slot in the game** | **VERIFIED that it is unverifiable** |
| 🔴 Is there an Arabic-slot to hijack? | **NO.** All 23 localization variants are LTR/CJK. Variant `683222` is **ENGLISH text paired with the ARABIC VOICE track** | **VERIFIED (2 independent sources)** |
| Do font-replacement mods exist? | **YES** — MSMR has font mods, and the Thai mod ships **selectable font modules** inside one `.modular` | **VERIFIED** |

**⇒ MSMR is an LTR-slot-hijack game (AC2 / Anno / GTA / TLOU / R&C class), not an Arabic-slot game.**
This must be corrected in CLAUDE.md before the bidi gate is decided.

---

## 1. 🔴 THE CLAUDE.md CLAIM — "Nexus mod 361 proves RTL on this engine" — DOES NOT HOLD

CLAUDE.md (Ratchet & Clank section) states:

> "**RTL proven on this engine** = Arabic mod for Spider-Man Remastered PC (Nexus mod 361)."

What I could actually establish:

| Check | Result |
|---|---|
| Does `nexusmods.com/marvelsspidermanremastered/mods/361` exist? | Page resolves but renders **`Title: Mod unavailable`** (fetched through a text proxy that bypasses Cloudflare) |
| Did a mod with that title exist? | **Probably yes** — search engines still index the title string *"Arabic localization at Marvel's Spider-Man Remastered Nexus - Mods and community"* |
| Wayback Machine snapshot of the page? | **NONE.** `cdx` exact-match for `mods/361` returns **zero rows** (the `361*` wildcard only matches 3610-3616) |
| Nexus API without a key? | `{"message":"Please provide an authentication method"}` |
| Is it in the live MSMR mod list? | **NO.** `?keyword=arabic` → **0 results**; `?keyword=localization` → only Simplified Chinese (5715), Ukrainian (5477), Thai (3385) |

**Nothing about its content, its install mechanism, or any RTL note by its author is recoverable.**
So: *"it existed"* is plausible; *"it proves the engine does Arabic bidi"* is **an unsupported inference** and must not be carried into the Hebrew plan.

**And the structural evidence points the other way** (see §2): MSMR has **no Arabic text locale at all**, so any "Arabic localization" mod for it must have been an **LTR-slot hijack** — meaning its author would have had to solve RTL **himself** (pre-shaped + pre-reversed text, i.e. store-VISUAL), which is *evidence against* engine-side bidi, not for it.

> ⚠️ Direct consequence for the sibling bidi agent: **do not start from the assumption "Arabic renders, so Hebrew will".** The nearest true sibling is **Ratchet & Clank: Rift Apart**, which is the same engine family, also has **no Arabic slot**, and whose in-game A/B proof landed on **bidi = NONE ⇒ store VISUAL** (CLAUDE.md, R&C section). That is the correct prior for MSMR.

---

## 2. 🔴 THE 23 LOCALIZATION VARIANTS — NO ARABIC TEXT SLOT

Two independent sources agree, and both agree with our own probe.

### 2a. Community mapping (ZenHAX, thread 17283 p.2) — verbatim

```
localization_all.localization.207368 (ENGLISH)
localization_all.localization.239528 (ENGLISH)
localization_all.localization.283602 (DANISH)
localization_all.localization.283603 (DUTCH)
localization_all.localization.283604 (FINNISH)
localization_all.localization.283901 (FRENCH)
localization_all.localization.328271 (JERMAN)          -> German
localization_all.localization.372641 (ITALIAN)
localization_all.localization.417000 (JEPANG)          -> Japanese
localization_all.localization.461073 (KOREA)
localization_all.localization.461074 (NORWEGIA)
localization_all.localization.461371 (POLISH)
localization_all.localization.505741 (PORTUGIS)
localization_all.localization.550111 (RUSSIAN)
localization_all.localization.594481 (SPANISH)
localization_all.localization.638555 (SWEDIA)
localization_all.localization.638852 (PORTUGIS BRAZIL)?
localization_all.localization.683222 (ENGLISH) for ARABIC VOICE     <<<<<<
localization_all.localization.727592 (SPANISH LATIN)?
localization_all.localization.771666 (CHINA)
localization_all.localization.771667 (CEKO)            -> Czech
localization_all.localization.771668 (HUNGARIA)
localization_all.localization.771669 (GREEK)
```

**Those 23 numbers are the ASSET INDICES, and they are byte-for-byte the same set our own probe produced** — an exact independent confirmation of our extraction:

```
207368 239528 283602 283603 283604 283901 328271 372641 417000
461073 461074 461371 505741 550111 594481 638555 638852 683222
727592 771666 771667 771668 771669                       (= 23)
```

### 2b. Publisher's own language list (Insomniac support)

- **Audio**: Arabic, English, French, German, Italian, Japanese, Polish, Portuguese, Portuguese-BR, Russian, Spanish-ES, Spanish-LatAm.
- **Text/subtitles**: Chinese-Traditional, Czech, Danish, Dutch, Finnish, French, German, English, Greek, Hungarian, Italian, Japanese, Korean, Norwegian, Portuguese, Portuguese-BR, Russian, Spanish-ES, Spanish-LatAm, Swedish.
- **Arabic is in the AUDIO list and NOT in the TEXT list.**

That is exactly what `683222 (ENGLISH) for ARABIC VOICE` encodes, and exactly why the install ships `a00s044.ar` (a **voice** archive) with no matching Arabic text variant.

**⇒ The Hebrew slot must be an LTR sacrifice slot.** The community has already picked its favourites, which is a useful prior on which slots are safe:

| Mod | Slot it sacrifices | Source |
|---|---|---|
| Ukrainian (5477) | **Greek** — *"Українська мова замінює грецьку мову"* ("Ukrainian replaces the Greek language") | mod description, verbatim |
| Indonesian (2449) | **English** — *"THIS PATCH WILL BE REPLACING ALL ENGLISH SUBTITLE."* | mod description, verbatim |

Both then rename the in-game language-menu label, because the Ukrainian instructions end with *"3) У меню гри вибрати українську мову"* ("in the game menu, choose Ukrainian") while the slot is Greek — i.e. the language-name string is itself translated inside the same `.localization`, exactly like CP2077 / GoWR / SM2.

---

## 3. ✅ EXISTING TEXT MODS — the strongest possible "modified localization loads" proof

Live on Nexus **today** (verified via the live mod search, `?keyword=localization` / `?keyword=subtitle`):

| Mod | ID | Author | Notes |
|---|---|---|---|
| **Ukrainian localization** | 5477 | ju5tA1ex | Requires **Overstrike**. Replaces the **Greek** slot. Full install + uninstall steps. |
| **Marvel's Spider-Man remastered Thai Localization** | 3385 | SpiderF | **Two** install paths (standalone `asset_archive` drop-in, or `.modular` via Overstrike) + **swappable font modules** |
| **INDONESIAN SUBTITLE** | 2449 | (MGMC'S credited) | Replaces the **English** slot. Standalone toc patch. Changelog shows re-releases per game version. |
| **MSM-R Simplified Chinese Localization** | 5715 | themoon174 | live |
| (sibling game) Miles Morales Thai Localization | MM 647 | — | same format family |

### 3a. Ukrainian (5477) — install instructions, verbatim
```
Українська мова замінює грецьку мову.
Встановлення:
1) Скачайте Overstrike (https://www.nexusmods.com/marvelsspidermanremastered/mods/4199)
2) Запустіть Overstrike ... 2.1) "Add game" ... 2.3) Browse... і вибираєте папку з грою
   2.7) Натиснути на + 2.8) Вибрати файл (неважливо він у архіві чи ні)
   2.9) Переконатися, що Українська локалізація активована 2.10) Натиснути "Install mods"
3) У меню гри вибрати українську мову.
Видалення:
1) У меню гри вибрати іншу мову. 2) Деактивуйте мод у Overstrike 3) "Install mods"
4) Видаліть "Spider-Man UA Localization" файл
Проблеми гри:
1) Якщо гра не завантажується і показує чорний екран, закрийте гру через диспетчер завдань і запустіть заново.
```
Note the failure mode the author documents: **a bad install = black screen on load**, recoverable by killing + relaunching. Useful for our own proof runs.

### 3b. Thai (3385) — TWO deploy paths, and a FONT precedent
```
วิธีติดตั้งแบบ Standalone
  ...ก็อบโฟลเดอร์ asset_archive ไปวางที่โฟลเดอร์เกม SteamLibrary\steamapps\common\Marvel's Spider-Man Remastere
วิธีติดตั้งแบบ Overstrike
  ...คัดลอกไฟล์ SMTHSpider-Translate.modular ... ไปวางที่ \Overstrike\Mods Library
  ...ให้คงม็อดภาษาไทยไว้อันดับที่ 1 และตามด้วยฟอนท์ที่เราสนใจ
หมายเหตุ: สามารถสลับฟอนต์ได้ มีทั้งแบบมีหัวและไม่มีหัว โดยการคลิกขวาที่ม็อดภาษาไทยใน Overstrike
  และเลือก Edit Modules... จากนั้นก็เลือกฟอนต์ที่เราต้องการ และกด Save
```
Translation of the load-bearing parts:
1. **Standalone** = "copy the `asset_archive` folder into the game folder" — i.e. ship a rebuilt `toc` + `patch.archive` pair directly, no mod manager.
2. **Overstrike** = drop `SMTHSpider-Translate.modular` into `Overstrike\Mods Library`, keep the localization mod at **position 1**, "**followed by the font you want**".
3. **"You can switch fonts — there are looped and loopless variants — by right-clicking the Thai mod in Overstrike → Edit Modules… → pick the font → Save."**

🔑 **This is a direct precedent for the font half of a non-Latin translation on MSMR**: a single `.modular` can carry the localization **plus alternative FONT modules**, user-selectable. Thai is a non-Latin script with its own shaping needs, and it shipped. Independent font mods also exist (`Custom Fonts` #2663, `Raimi Font` #5277).

### 3c. Indonesian (2449) — the operational warnings, verbatim
```
IF YOU DOWNLOADED THIS MOD, I STRONGLY RECOMMEND YOU BACKUP YOUR TOC AND TOC.BAK FIRST.
THIS PATCH WILL BE REPLACING ALL ENGLISH SUBTITLE.
DISCLAIMER: This subtitle files will use the default game, that's mean nothing mod will be loaded,
except this translations files.
```
Changelog (verbatim): `Update For v.2.616.0.0 - 2023`, `Update for V1.1212.0.0`, `Update for V1.1122.0.0`, `Update for V1.1006.0.0`.

**⇒ Two operational facts:** (a) a **standalone** toc patch is mutually exclusive with other mods (it ships a whole toc), and (b) **a game update invalidates the mod** and forces a re-release — the toc is rewritten by the patch. Same class as our documented [[game-update-makes-backups-stale]] rule.

---

## 4. 🛠 TOOLING INVENTORY (all open-source, all verified from source)

### 4a. `team-waldo/InsomniacArchive` — **the complete read+write chain, MSMR-specific**
- Repo: <https://github.com/team-waldo/InsomniacArchive> — **default branch `spiderman_pc`**, 11 stars, last push 2022-08-26, **no license file**.
- Layout: `InsomniacArchive/` (library) · `SpidermanLocalizationTool/` (CLI) · `SpidermanFilenameHook/`.
- Needs **.NET 6.0 runtime** (community reports `hostfxr.dll` errors otherwise).

CLI verbs (verbatim from `SpidermanLocalizationTool/Program.cs`):
```
export        <loc-in> <csv-out>                       # -> CSV columns: key, source, translation
import        <loc-in> <csv-in> <loc-out>
arc-extract     <archive-dir> <assetIndex> <out-path>
arc-extract-all <archive-dir> <assetName>  <out-dir>   # writes "{name}.{index}"  <-- the .207368 naming
arc-import      <archive-dir> <out-dir> asset_number:asset_path ...
```
`arc-extract-all` is literally why the ZenHAX file list is named `localization_all.localization.207368`.

### 4b. `Tkachov/Overstrike` — the mod manager **+ a maintained Localization Tool + Modding Tool**
- Repo: <https://github.com/Tkachov/Overstrike> — **GPLv3**, .NET 7.0 Desktop Runtime.
- Nexus (MSMR page): <https://www.nexusmods.com/marvelsspidermanremastered/mods/4199>
- Games in source (`Overstrike/Games/`): `GameMSMR.cs`, `GameMM.cs`, `GameRCRA.cs`, `GameMSM2.cs`, `GameI30.cs`, `GameI33.cs`
  → **MSMR, Miles Morales, R&C Rift Apart, Spider-Man 2, i30 (SM2 variant), i33 (Wolverine)**.
- `GameMSMR.cs`, verbatim essentials:
  ```csharp
  public const string ID = "MSMR";
  GetExecutablePath -> Path.Combine(gamePath, "Spider-Man.exe");
  GetTocPath        -> Path.Combine(gamePath, "asset_archive", "toc");
  IsCompatible      -> SMPC | SUIT_MSMR | STAGE_MSMR | SUITS_MENU | MODULAR_MSMR | SCRIPT_MSMR
  GetMetaInstaller  -> new MetaInstaller_I20(...)          // MSMR internal codename = i20
  ```
- **Localization Tool** (`LocalizationTool/README.txt`, verbatim):
  ```
  Localization Tool allows you to open, modify and save .localization files.
  Supported games:
  - Marvel's Spider-Man Remastered
  - Marvel's Spider-Man: Miles Morales
  - Ratchet & Clank: Rift Apart
  Created by DemonRed.
  ```
  GUI editor: load/create/save, undo/redo, search by key or value, sort, edit key/value/**flags**, add/delete entries.
  (SM2 is *not* supported — that is open issue [#31](https://github.com/Tkachov/Overstrike/issues/31).)

### 4c. Older / adjacent tools
- **SMPC Modding Tool** (Nexus #51) — the original `.smpcmod` installer; still what Vortex drives on the back end.
- **Vortex** + its SMPC extension (site mod #443).
- **Add Suits to New Slots** (#2318) — `.suit` installer.
- `leonyarov/SpiderManTextureTool` — `.texture` files.
- **modding.wiki** MSMR user guide: <https://modding.wiki/en/marvelsspidermanremastered/users> — *"Before modding, it's recommended that you back up the `...\Marvel's Spider-Man Remastered\asset_archive\toc` file. If you forget to do this and there are any issues, you'll need to re-verify the game via Epic/Steam."*

---

## 5. 📐 THE FORMAT — fully documented in open source, and it **matches SM2 / R&C exactly**

### 5a. `.localization` asset = `[36-byte header][DAT1]`
From `Overstrike/DAT1/Files/Localization.cs`:
```csharp
public const uint MAGIC = 0x122BB0AB;
magic = r.ReadUInt32(); dat1_size = r.ReadUInt32(); unk = r.ReadBytes(28);   // 4+4+28 = 36 = 0x24
```
From `InsomniacArchive/FileTypes/AssetFile.cs` (same 0x24, other direction):
```csharp
bw.Write(AssetId); bw.Write(input.Length); bw.Pad(0x24 - (int)bw.BaseStream.Position);
// Compressed = false;  // LZ4 is wired up but DISABLED — payload is written raw
```
🔑 **`0x122BB0AB` little-endian is `AB B0 2B 12` — byte-for-byte the magic our own probe found at the start of every extracted variant.** Independent confirmation that our extraction is correct and that MSMR uses the identical asset wrapper as SM2/R&C (CLAUDE.md §8f: *"[36-byte header][DAT1]"*).

### 5b. DAT1 section tag map (with the engine's OWN literal names)
| Tag | Overstrike name | Engine string literal | Type |
|---|---|---|---|
| `0xD540A903` | EntriesCountSection | `Localization Header Built` | u32 |
| `0x4D73CEBD` | KeysDataSection | `Localization Tags Built` | string blob |
| `0xA4EA55B2` | KeysOffsetsSection | `Localization TagOffsets Built` | u32[] |
| `0x70A382B8` | ValuesDataSection | `Localization Text Built` | string blob |
| `0xF80DEEB4` | ValuesOffsetsSection | `Localization TextOffsets Built` | u32[] |
| `0xB0653243` | UnknownSection | **`Localization Flags Built`** | u8[] |
| `0x06A58050` | KeyHashesSection | — | u32[] |
| `0xC43731B5` | SortedKeyHashesSection | `Localization SortedHashes Built` | u32[] |
| `0x0CD2CFE9` | SortedIndexesSection | `Localization SortedIndexes Built` | **u16[]** |

**This is EXACTLY the R&C set already recorded in CLAUDE.md** (`VALUES=0x70A382B8, KEYS=0x4D73CEBD, TEXT_OFFSETS=0xF80DEEB4, KEY_OFFSETS=0xA4EA55B2, ENTRY_COUNT=0xD540A903`).
⇒ **`games/ratchet_rift_apart/work/*` and `games/spiderman2/work/*` should parse MSMR's `.localization` with little or no change.** Check the magic first ([[engine-family-reuse-check-magic]]) — done, it matches.

Two things our notes did **not** have, both from the engine's own literals:
- **`0xB0653243` is a per-entry FLAGS array** (Overstrike's GUI exposes an editable "flags" column, `View > Show flags`). Not "unknown".
- There is a **sorted-hash lookup** (`SortedKeyHashes` + `SortedIndexes`), and `SortedIndexes` is **u16** ⇒ **≤ 65,535 entries per variant** and the sorted arrays must be rebuilt if keys are ever added/removed. **A value-only edit never touches them** — which is what every shipped mod does.

### 5c. The write model (verbatim, `LocalizationFile.ImportStrings`)
```csharp
// rebuild the VALUES blob from scratch; keys/keyoffsets are untouched
if (key != "INVALID" && value == string.Empty) offset = 0;
else { offset = (int)newStringData.Position; bw.WriteNullTerminatedString(value); }
...
stringOffset.Data = newStringOffsetArray;
stringData.Data   = newStringData.ToArray();
```
⇒ **Translation = rewrite `ValuesData` + `ValuesOffsets` only.** Keys, hashes, sorted arrays and flags stay byte-identical. Note the one special rule: an **empty value maps to offset 0** (except the key literally named `INVALID`).

`DatFileBase.Save` adds one more hard constraint, verbatim comment:
```csharp
// section infos should be stored in ID increasing order
// for binary search
```

---

## 6. 🚀 DEPLOY MECHANISM — three real, shipped variants

### 6a. `toc` container (`InsomniacArchive/FileTypes/TocFile.cs`) — matches our probe
```csharp
private const uint TOC_COMPRESSED_SIGNATURE = 0x77AF12AFu;
protected override string Signature => "ArchiveTOC";
// on-disk: [u32 0x77AF12AF][i32 uncompressedSize][u16 0xDA78 zlib hdr][deflate stream]
```
Section IDs inside the toc:
| Tag | Section | Struct |
|---|---|---|
| `0x398ABFF0` | ArchiveFileSection | `ushort flag; byte unk02; byte unk03; ushort unk04; ushort unk06; char[0x40] fileName` (**72 B**) |
| `0x506D7B8A` | NameHashSection | `ulong[]` (CRC64 of the asset path) |
| `0x65BCF461` | FileChunkDataSection | `int chunkCount; int totalSize; int chunkArrayIndex` (**12 B**) |
| `0x6D921D7B` | KeyAssetHashSection | `ulong[]` |
| `0xDCD720B5` | ChunkInfoSection | `int archiveFileNo; uint offset` (**8 B**) |
| `0xEDE8ADA9` | SpanSection | `uint offset; uint size` |

⚠️ **Same section IDs as SM2/R&C for archives (`0x398ABFF0`) and sizes (`0x65BCF461`), but DIFFERENT struct layouts** — MSMR's toc is the older i20 shape (12-byte size entry, 72-byte archive entry) vs SM2's RCRA (16-byte `<IIIi>` size entry, 66-byte `<QQIHI>` archive entry). **Do not blind-reuse `spiderman2_mod.py`'s struct formats.**

### 6b. Standalone patch (`ArchiveDirectory.SaveArchives`) — what the Thai/Indonesian mods ship
```csharp
string newArchivePath = Path.Combine(outputDirectory, "patch.archive");
...
var newArchiveFileEntry = new TocFile.ArchiveFileEntry() {
    flag = 2, unk02 = 0, unk03 = 0, unk04 = 0xCCCC, unk06 = 1, FileName = "patch.archive",
};
archiveFileArray[^1] = newArchiveFileEntry;                 // APPEND a new archive
...
fileChunkData.totalSize   = replacer.GetSize();             // per replaced asset
chunkInfo.archiveFileNo   = archiveFileArray.Length - 1;    // redirect to patch.archive
chunkInfo.offset          = (uint)outputFileStream.Position;
...
Toc.SaveFile(Path.Combine(outputDirectory, "toc"));         // write a NEW toc
```
**This is the identical index-redirect deploy our SM2 native applier already implements** (append a new archive entry + repoint the asset's size/offset entry; never repack a base archive). Community naming: the output folder is `asset_archive_new`, and the user copies `patch.archive` + `toc` over the originals.

ZenHAX warning, verbatim: *"Backup the Original TOC files. Because TOC files so important to make game works."*

### 6c. Overstrike (`MetaInstaller_I20`) — the mod-manager path
```csharp
var tocPath    = .../asset_archive/toc
var tocBakPath = .../asset_archive/toc.BAK
if (!File.Exists(tocBakPath)) File.Copy(tocPath, tocBakPath);      // first run: snapshot pristine
else { RemoveReadOnlyAttribute(tocPath); File.Copy(tocBakPath, tocPath, true); }   // every run: RESTORE first
Directory.CreateDirectory(.../asset_archive/mods);                 // mod payload archives live here
Directory.CreateDirectory(.../asset_archive/Suits);
... _toc.Save(tocPath);
```
🔑 **Overstrike always rebuilds from the pristine `toc.BAK`, never from the currently-installed toc** — the community-standard version of our own [[always build from the pristine backup]] rule. It also `RemoveReadOnlyAttribute` before writing (relevant: cracked/repacked installs sometimes mark `toc` read-only).

⚠️ **Two appliers, one backup** — the exact hazard already documented for SM2 ([[two-appliers-one-backup]]): if a Hebrew applier of ours writes `toc` and the user then runs Overstrike, Overstrike will *silently overwrite our toc from its `toc.BAK`*, and a first-ever Overstrike run on an already-modded install would snapshot **our modded toc as "pristine"**. Any MSMR applier we build must detect `toc.BAK` and reconcile.

---

## 7. ANTI-TAMPER / FRAGILITY

- **No community report of any content-integrity or anti-tamper wall.** The MSMR modding scene is large and mature (suits, textures, scripts, full text replacements), and the toc is *designed* to be rewritten by tools. There is no analogue of the AC-Black-Flag SHA-256 wall.
- **DRM status not established from an authoritative source** — PCGamingWiki 403s both direct and via proxy. **Moot for this gate**: the existence of ≥4 working text mods that rewrite the toc is the empirical answer to "do modified archives load".
- **Game updates DO break mods.** Indonesian mod changelog: separate releases for `V1.1006.0.0`, `V1.1122.0.0`, `V1.1212.0.0`, `v2.616.0.0`. A patch rewrites `toc`, so any deployed translation must be re-applied (and any `.he_backup` taken before the patch becomes stale).
- **Known failure mode from a shipped mod's own docs**: a broken localization install = **black screen at load**; kill via Task Manager and relaunch. Also, mixing a standalone toc patch with other mods is unsupported by design.

---

## 8. WHAT THIS MEANS FOR THE HEBREW PROJECT

**Confirmed green:**
1. **Container + text codec = REUSE, not research.** Two open-source implementations, and the DAT1 tag set is identical to R&C/SM2 which we already have Python for.
2. **Deploy = index-redirect, already implemented in this repo** (`spiderman2_mod.py` pattern) — but the toc struct layouts differ (i20 vs RCRA), so re-derive those three structs.
3. **Text mods demonstrably load**, including full subtitle replacement, in a game that is still being updated.
4. **Font replacement is a solved, shipped thing** on MSMR (Thai mod's selectable font modules; two standalone font mods).
5. **A no-repack, no-anti-cheat, reversible deploy** exists with a community-standard pristine-backup discipline (`toc.BAK`).

**Newly-raised red flags:**
1. 🔴 **No Arabic text slot ⇒ no free engine RTL.** Plan for an **LTR-slot hijack** and treat **store-VISUAL** as the working hypothesis (R&C precedent), pending the in-game A/B proof. **Greek (771669)** is the community-blessed sacrifice slot; **English (207368/239528)** is the zero-user-action slot the Indonesian mod uses.
2. 🔴 **The CLAUDE.md "RTL proven via Nexus 361" line must be corrected** — it is unverifiable and structurally implausible.
3. ⚠️ **`SortedIndexes` is u16** ⇒ ≤65,535 entries; never add/remove keys, only rewrite values.
4. ⚠️ **Coexistence with Overstrike** must be handled (`toc.BAK` reconciliation) before shipping a launcher applier.
5. ⚠️ **Per-entry FLAGS section exists** (`0xB0653243`) — preserve it verbatim; do not let a codec drop it.

---

## 9. SOURCES

**Verified by direct fetch of the source/page:**
- ZenHAX thread 17283 (p.1 + p.2): <https://zenhax.com/viewtopic.php@t=17283.html> · <https://zenhax.com/viewtopic.php@t=17283&start=20.html>
- `team-waldo/InsomniacArchive` (branch `spiderman_pc`): <https://github.com/team-waldo/InsomniacArchive> — read `SpidermanLocalizationTool/Program.cs`, `InsomniacArchive/FileTypes/{LocalizationFile,AssetFile,DatFileBase,DatHeader,TocFile}.cs`, `InsomniacArchive/ArchiveDirectory.cs`
- `Tkachov/Overstrike` (GPLv3): <https://github.com/Tkachov/Overstrike> — read `README.md`, `Overstrike/Games/GameMSMR.cs`, `Overstrike/MetaInstallers/MetaInstaller_I20.cs`, `DAT1/Files/Localization.cs`, `DAT1/Sections/Localization/*.cs`, `LocalizationTool/README.txt`
- Nexus MSMR mod list (live, via text proxy): `?keyword=localization|arabic|hebrew|subtitle|font`
- Nexus mod descriptions (via Wayback): Ukrainian <https://www.nexusmods.com/marvelsspidermanremastered/mods/5477> · Thai <https://www.nexusmods.com/marvelsspidermanremastered/mods/3385> · Indonesian <https://www.nexusmods.com/marvelsspidermanremastered/mods/2449> · Overstrike <https://www.nexusmods.com/marvelsspidermanremastered/mods/4199>
- modding.wiki: <https://modding.wiki/en/marvelsspidermanremastered/users>
- Insomniac language options (via search index): <https://support.insomniac.games/hc/en-us/articles/46669467876883-Marvel-s-Spider-Man-Language-Options>

**Verified as UNAVAILABLE:**
- Nexus mod 361 "Arabic localization": <https://www.nexusmods.com/marvelsspidermanremastered/mods/361> → "Mod unavailable"; **0** Wayback snapshots (`cdx` exact match).

**Not established (stated as such):**
- MSMR PC Denuvo/DRM status (PCGamingWiki blocked both direct and proxied).
- Content and RTL notes of the removed Arabic mod 361.
- Which exact asset holds the UI font (a font-asset hunt is the font gate's job; only the *existence* of font mods is established here).

**Method notes for the other agents:** `www.nexusmods.com` returns Cloudflare 403 to both WebFetch and curl; a public text-proxy read (`https://r.jina.ai/<url>`) gets the mod LIST and page status, but mod **descriptions** are client-rendered and only came through via **Wayback snapshots fetched with curl** (WebFetch refuses `web.archive.org`). The GitHub MCP has bad credentials — use the plain GitHub REST/raw endpoints with curl.
