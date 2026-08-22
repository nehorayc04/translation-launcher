# MSMR — DEPLOY GATE (Phase-1) — 🟢 **SOLVED, and it is the EASIEST tier**

**Verdict:** the SM2 index-redirect deploy **maps onto MSMR**, is **byte-exactly round-trippable
with the stock vendored `dat1lib` (no custom serializers needed, unlike RCRA)**, and was proven
**end-to-end offline** — patched toc → raw mod file → the asset reads back byte-identical, with a
**size change**, and **zero drift** across the other 771,669 entries. Revert is byte-identical.

**The game folder was never modified.** `toc` sha unchanged all session (`73447f293923ff59`,
10,707,684 B). Every write went to `%TEMP%\msmr_deploy_probe` / `%TEMP%\msmr_deploy_sim`.

Scripts (run with `./.venv/Scripts/python.exe`):
`05_toc_sections.py` · `06_toc_roundtrip.py` · `07_archive_format.py` ·
`08_raw_archive_and_exe.py` · `09_deploy_simulation.py` · `10_engine_evidence.py` ·
`11_final_checks.py` (raw outputs `_07_out.txt` … `_10_out.txt`).

---

## 1. The MSMR toc is NOT the RCRA TOC2 — exact on-disk layout

```
[u32 magic 0x77AF12AF][u32 uncompressed_len][ zlib-deflate stream ]
                                              └─> inner DAT1 '1TAD', 21,709,552 B
```
Inner `DAT1` header: `magic 0x44415431 · unk1 0x51B8E006 ("toc") · size 21,709,552 · sections=6 ·
unknowns=0`; header ends at 88, 24-byte string blob, first section at **112**.

| # | tag | engine name (from the exe) | offset | size | entries | **bytes/entry** |
|---|---|---|---|---|---|---|
| 0 | `0xEDE8ADA9` Spans | *Archive TOC Header* | 112 | 2,048 | **256** | 8 |
| 1 | `0x506D7B8A` AssetIds | `m_BatchAssetIds` | 2,160 | 6,173,360 | **771,670** | 8 |
| 2 | `0x6D921D7B` KeyAssets | *Key Asset IDs* | 6,175,520 | 97,304 | 12,163 | 8 |
| 3 | `0x65BCF461` Sizes | **`m_FileSizes`** | 6,272,832 | 9,260,040 | **771,670** | **12** |
| 4 | `0xDCD720B5` Offsets | **`m_FileOffsets`** | 15,532,880 | 6,173,360 | **771,670** | 8 |
| 5 | `0x398ABFF0` Archives | *Archive TOC File Metadata* | 21,706,240 | 3,312 | **46** | **72** |

Record layouts (widths **derived from section_bytes ÷ entry_count**, not assumed):

```python
SpanEntry        "<II"   asset_index, count                       # 8
AssetIds         "<Q"    crc64(path)                              # 8
SizeEntry        "<III"  always1(=1), value(=SIZE), index(=pos)    # 12   <-- MSMR, NOT RcraSizeEntry
OffsetEntry      "<II"   archive_index, offset                     # 8
ArchiveFileEntry "<II" + char[64]  install_bucket, chunkmap, filename  # 72
```

**⇒ On MSMR an asset's location is split across TWO sections** (`Sizes.value` = size,
`Offsets.{archive_index,offset}` = where), whereas RCRA packs all four fields into one 16-byte
`RcraSizeEntry`. That is the single structural difference the port has to handle.

**`SizeEntry.index` is a PARALLEL index, not a dedup pointer** — measured over **all 771,670**
entries: `always1 != 1` → **0**, `index != position` → **0**. So `assets[i] ↔ sizes[i] ↔ offsets[i]`
line up 1:1 and a redirect is a two-field edit at one index.

**Alignment/padding is exactly 16-byte** (`pad_before` = 0,0,0,**8**,**8**,0), which is precisely
what dat1lib's `PAD_TO=16` reproduces — and the section-header table on disk is already tag-sorted,
matching `DAT1.save()`'s `sorted(...)`. That is *why* the round-trip below is byte-perfect.

---

## 2. Does dat1lib round-trip? — **YES, byte-identical** (`06_toc_roundtrip.py`)

| test | ORIGINAL_ORDER | PRESERVE_PADDING | STRAIGHTFORWARD |
|---|---|---|---|
| parse → `dat1.save()` (no refresh) | **IDENTICAL** | **IDENTICAL** | ✗ 46.4 % of bytes differ |
| parse → `full_refresh()` → save | **IDENTICAL** | **IDENTICAL** | ✗ 46.4 % differ |

Per-section `save()` re-serialization, all six: **byte-identical**
(Archives 3312→3312, AssetIds 6173360→…, Sizes 9260040→…, Offsets, Spans, KeyAssets).

> 🔑 **This is the big MSMR win vs. RCRA.** `spiderman2_mod.py` had to monkey-patch
> `_serialize_sizes_rcra` / `_serialize_archives_rcra` because *"dat1lib's stock save() emits the
> older 12-byte MSMR layout"*. On MSMR the 12-byte layout **is** the correct one — so the stock
> serializers are right and **no overrides are needed**. Delete that machinery in the port.

`TOC.save()` (the zlib wrapper): inner DAT1 **byte-identical**; the outer file is
10,707,684 → 10,695,529 B because Python's zlib level differs from the shipping packer.
**That is expected and harmless** — the engine reads the decompressed stream, and the header's
`uncompressed_len` is recomputed correctly (21,709,552). **Always compare the INNER DAT1, never the
outer file bytes.**

---

## 3. Does the index-redirect map onto MSMR? — **YES, proven end-to-end**

`09_deploy_simulation.py` built a fake `asset_archive` in the scratchpad holding only a patched
`toc` + one raw mod file, then read the asset back through **dat1lib's archive reader — the same
offset/size/DSAR-magic logic the engine uses**:

```
payload: variant_00 6,033,201 B  ->  GROWN to 6,036,309 B (+3,108) + a marker at offset 64
target : asset_index 207368  BEFORE size=6,033,201 archive=19 offset=243,950,395
edit   : + archive[46] = 'tm_he_0'   sizes[207368].value=6,036,309
                                     offsets[207368].archive_index=46, .offset=0
read-back: archive=46 ('tm_he_0') offset=0 size=6,036,309
           read 6,036,309 bytes ... bytes match payload: True
           marker at offset 64: b'MSMR-HE-DEPLOY-MARKER'
[PASS] redirected asset resolves + reads byte-exact from a RAW mod file
22 other loc variants still on archive 19 — drifted: 0
global drift across 771,669 untouched entries: 0   -> CLEAN
inner DAT1 grew 21,709,552 -> 21,709,624 (+72 = exactly one archive record)
revert: restored toc byte-identical to the real one: True
```

Each of the three sections needs exactly one mutation:

| section | field | new value |
|---|---|---|
| Archives | *append* one 72-byte record | `bucket=0`, `chunkmap=10000+index`, `filename` = name padded to 64 B |
| Sizes | `entries[i].value` | `len(blob)` — **leave `always1` and `index` alone** |
| Offsets | `entries[i].archive_index`, `.offset` | new archive index, byte offset inside the mod file |

---

## 4. Will the **engine** accept it? — four independent pieces of evidence

**(a) The shipping game ALREADY reads a RAW (non-DSAR) archive.**
`a00s034.us` (1,221,464,064 B) starts with `b7 1b 4f 7e`, not `DSAR`, and serves **44,369 real
assets**. `max(offset+size)` over all of them = **1,221,464,009 ≤ 1,221,464,064** — a flat raw
concatenation, every asset at its plain declared offset. A mod archive is exactly this shape.

**(b) The DSAR-vs-raw branch is visible in machine code** — `Spider-Man.exe` @ `0x01CFAF45`:
`81 7C 24 30 44 53 41 52` = `cmp dword [rsp+30h], 'DSAR'` followed by `74 53` (`je`). The engine
reads 4 bytes, compares to `DSAR`, and branches — raw is the fall-through path, not an accident.

**(c) The engine's own field names match the sections we edit** (`0x03CA8048`):
`Archive TOC · ArchiveFileSystem · m_BatchAssetIds · m_FileSizes · m_FileHandlesSync ·
m_FileHandlesAsync · m_OnDemandHandles · m_FileBasePath · m_FileOffsets · Archive Asset IO ·
Archive Loose IO · %s\dag · %s\%s · Archive Block Streamer`.

**(d) A reference implementation for MSMR does exactly this** — ALERT's own
`server/state/suits_editor.py` (same author as **Overstrike**; the README states the scripts were
*"mostly written for MSMR"*):
```python
s.archives += [ArchiveFileEntry.make(0, 10000 + len(s.archives), fn)]   # bucket 0, chunkmap 10000+idx
...
sizes.entries[asset_index].value        = asset_size
offsets.entries[asset_index].archive_index = archive_index
offsets.entries[asset_index].offset        = archive_offset
...
os.makedirs(os.path.join(toc._archives_dir, "Suits"))       # subfolder under asset_archive
self._reroute_asset_via_new_archive(AID, blob, "Suits\\base1")   # BACKSLASH name
if not os.path.exists(toc_fn + ".BAK"): shutil.copyfile(toc_fn, toc_fn + ".BAK")
with open(toc_path, "wb") as f: toc.save(f)
```
This is community-proven on MSMR. **It also tells us `chunkmap = 10000 + archive_index`** — the
continuation of the shipped `g00s000..g00s033` = `10000..10033` series — instead of a guess.

**Not tested (out of scope for this read-only phase): an actual game launch.** Everything above is
static + offline evidence; the launch is the one remaining unknown.

---

## 5. 🔴 `m_FileBasePath` is `asset_archive/`, **not** the game root

This is the #1 way to port SM2's code and get a silently-broken deploy. On SM2/RCRA the toc sits at
`<game>/toc` so archive names resolve against the game root (`d\mods\tm_he_0`). On MSMR:

* the only asset-root string in the exe is **`asset_archive/toc`**;
* the engine builds paths as **`%s\%s`** and **`%s\dag`** from `m_FileBasePath`;
* **`dag` exists ONLY in `asset_archive/`** (there is no `<game>/dag`).

⇒ `m_FileBasePath == <game>\asset_archive`, and a toc archive name `Hebrew\tm_he_0` resolves to
`<game>\asset_archive\Hebrew\tm_he_0`. Using SM2's `d\mods\…` would look for
`<game>\asset_archive\d\mods\…` — which is fine *if you create it there*, but writing it to
`<game>\d\mods\` (the SM2 location) makes the engine find nothing.

---

## 6. Ranking the four options

### 🥇 (d) **Added archive + index redirect** — RECOMMENDED
Nothing shipped is modified except the ~10 MB `toc`. Any payload size. One file to delete on
revert. Proven offline end-to-end (§3) and matched by the reference implementation (§4d).
**Cost:** one 72-byte archive record + two field writes per asset.

### 🥈 (a) In-place, same-size edit inside the DSAR archive — *possible, strictly worse*
Measured on `g00s019` (2,204,712,915 B): DSAR = 32-byte header + a **head-located block table**
(`blocks_header_end = 392,640` → **12,269 blocks**), blocks are **262,144 B real** / LZ4-compressed.
Every localization variant spans **23–25 blocks** and **shares its first AND last block with a
neighbouring asset** (`block_aligned=False` on all 23). So an in-place edit must:
keep the uncompressed size **exactly** identical (a translation never does), re-LZ4 23–25 blocks,
preserve the neighbours' bytes inside the two shared blocks, **and** have every re-compressed block
fit its original compressed byte budget — otherwise the whole 2.2 GB tail shifts.
👉 Use only if the added-archive route is ever refused in-game.

### 🥉 (b) Append-relocate at archive EOF — **not viable for a DSAR archive**
The block map lives at the **file head** and is bounded by `blocks_header_end`; bytes appended at
EOF are not addressable through it, and inserting block records shifts all 2.2 GB of data. It would
only work against the raw `a00s034.us`, which is language-bucketed (`0x01000002`) and 1.2 GB.
(This is the opposite of RDR2/FC5, where flat archives make append-relocate the default.)

### ❌ (c) Loose-file override — **not demonstrated, do not plan on it**
No `-mods` / loose-override switch among the 542 switch-like strings (only `-archive`,
`-archivetrace`, `-asset(s)`, `-path`, `-lang`, `-language`); the only asset-root string is
`asset_archive/toc`; the 3 `loose` hits are gameplay text + Havok. The `Archive Loose IO` string is
an **IO-channel name** next to `Archive Asset IO`, **not** evidence of an asset-id override path.

---

## 7. THE RECIPE (minimal, reversible)

```
toc        : <game>\asset_archive\toc
base path  : <game>\asset_archive\            (= m_FileBasePath)
mod dir    : <game>\asset_archive\Hebrew\     (mirrors the community's "Suits\")
mod file   : <game>\asset_archive\Hebrew\tm_he_0        (raw blob, no header)
toc name   : "Hebrew\tm_he_0"                 (BACKSLASH, ≤64 bytes, NUL-padded)
backup     : <game>\asset_archive\toc.he_backup   +  toc.he_manifest.json
```
> Fallback rung if a subfolder is ever refused: a **flat** name (`tm_he_0` directly in
> `asset_archive\`) — that matches the shipped `g00s###` / `a00s###.xx` convention exactly.

**Build**
1. `dat1lib.read(open(toc,'rb'))`; **`set_recalculation_strategy(RECALCULATE_ORIGINAL_ORDER)`**.
2. Concatenate every patched asset into **ONE** mod file, recording each one's byte offset
   (the reference impl does this; one file per asset also works).
3. Append **one** hand-built `ArchiveFileEntry`: deepcopy `archives[0]`, then
   `filename = name.encode('ascii').ljust(64, b'\x00')`, `install_bucket = 0`,
   `chunkmap = 10000 + len(archives)`.
4. Per asset — resolve `i` by **scanning `assets.ids` inside the intended span** (never by
   arithmetic, see §8.6), then
   `sizes.entries[i].value = len(blob)` · `offsets.entries[i].archive_index = new_ai` ·
   `offsets.entries[i].offset = off_in_file`. **Do not touch `always1` / `index`.**
5. `refresh_section_data()` for `0x398ABFF0`, `0x65BCF461`, `0xDCD720B5` **only**.
6. `toc.save(f)` into a temp file, then `os.replace()` onto `toc` (never a partial 10 MB write).
7. Record in the manifest: `original_sha256`, `deployed_sha256`, `size`, `mtime_ns`, the list of
   mod files, and every `(asset_index, old_size, old_archive, old_offset)` we changed.

**Revert**
1. **Release dat1lib's cached archive handles first** (`toc.set_archives_dir(dir)`) — see §8.3.
2. If `sha256(live toc) != deployed_sha256` → **a game update or another tool rewrote it**: delete
   our mod files + manifest + backup and **do NOT restore** (restoring a pre-update toc over updated
   archives is a downgrade). Otherwise `copy2(toc.he_backup, toc)` (proven byte-identical), then
   delete the mod file(s), the backup and the manifest.
3. Game must be **closed** (it holds `toc` open).

---

## 8. Traps — every one of these was hit or measured this session

1. **Never `RECALCULATE_STRAIGHTFORWARD_ORDER`** — it re-sorts sections by tag and rewrites 46 % of
   the inner DAT1. `ORIGINAL_ORDER` (or `PRESERVE_PADDING`) is byte-perfect.
2. **`dat1lib.types.sections.toc.archives.ArchiveFileEntry.make()` IS BROKEN** — verified:
   `NameError: name 'self' is not defined` (it references `self._version` inside a `@classmethod`,
   and calls `cls(data)` without the required `version`). **Build the entry by hand.** Hand-built:
   72.0 B/entry, `chunkmap=10046`, `bucket=0` → re-reads correctly.
3. **`TOC._get_archive()` caches an OPEN file handle per archive** → deleting/overwriting a mod file
   afterwards fails with `PermissionError WinError 32`. Confirmed live. Call `set_archives_dir()`
   (which closes them) before any cleanup.
4. **Do NOT clobber `toc.BAK`** — that is ALERT/Overstrike's own pristine baseline for MSMR. If the
   user ever installed a suit mod, `toc.BAK` is *their* vanilla and overwriting it destroys their
   ability to revert other mods. Use a distinct `toc.he_backup`
   ([[two-appliers-one-backup]]). Conversely, if `toc.BAK` exists our "vanilla" may already contain
   someone else's mod — back up whatever is live, and say so.
5. **Never ADD an asset id.** Asset ids are **sorted ascending within every span** (checked: 0 of 28
   non-empty spans out of order) — the engine binary-searches them. Inserting requires re-sorting the
   span, bumping every later span's `asset_index`, and rewriting `size.index` for all 771,670 entries
   (`sort_assets()` in the reference impl). A pure **reroute needs none of that**.
6. **The variant→span map is NOT arithmetic.** The 23 localization variants sit in spans
   `0, 8, 24, 32, 40, 48, 56, 64, 72, 80, 88, 96, 104, 112, 120, 128, 144, 152, 168, 184, 200, 208,
   216` — R&C's "variant N → span N×8" **breaks** here (16, 136, 160, 176, 192 are skipped).
   Resolve by scanning ([[resolve-ids-by-value-not-by-sibling]]).
7. **`m_FileBasePath` is `asset_archive\`, not the game root** (§5) — the top porting hazard.
8. **The outer file will not be byte-identical** after a save (different zlib level). Compare the
   inner DAT1. A no-op rewrite is *smaller* (10,695,529 vs 10,707,684) — that is fine.
9. **Never re-pack a shipped DSAR archive** — head-located block map, 2.2 GB, neighbours share
   blocks. (Project rule: an archive read-modify-write must be in-place/append, never a full re-pack.)
10. The engine has a **`>>> Error: file size is wrong!`** string — `sizes.entries[i].value` must equal
    the real byte length available at that offset. Our simulation matched it exactly.
11. The **`MOD0` section (`0x30444F4D`) is a modding-tool marker, not an engine feature** — `MOD0`
    occurs **0 times** in the exe, and the live toc has no MOD0 section. Don't add one; don't need one.

---

## 9. DRM / integrity — 🟢 clean, no wall

`Spider-Man.exe` (121,325,496 B): **Denuvo 0 · VMProtect 0 · `.vmp` 0 · BattlEye 0 · EasyAntiCheat 0**;
`SHA256` ×2, `integrity`/`Integrity` ×4 total, `tamper` **0**, `checksum` **0**.
PE is ordinary and unpacked (`.text` 58.3 MB with matching raw size, `.reloc` 2.2 MB, no odd RWX
section, entry in `.text`). This is the **"asset mods load"** profile — nothing like AC Black Flag
Resynced (SHA256 ×143 / integrity ×5 / tamper ×11 = blocked). Corroborated by a live MSMR modding
scene (Overstrike / ALERT suit mods) editing this exact toc.

---

## 10. What is still unknown

* **An actual in-game launch with a modified toc.** All evidence here is static/offline.
* Whether `install_bucket`/`chunkmap` are consulted at all on PC (no such strings in the exe; they
  look like PlayGo streaming-install metadata). Mitigated by using the community's proven values
  (`bucket=0`, `chunkmap=10000+index`) rather than zeros.
* Whether a **subfolder** name is accepted as readily as a flat one. The reference impl uses
  `Suits\…`, and `%s\%s` + `m_FileBasePath` say it should be — the flat name is the zero-risk rung.
