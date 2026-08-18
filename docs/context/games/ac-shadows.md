## Assassin's Creed Shadows Hebrew — groundwork laid, GO-WITH-CAVEATS (2026-06-17)

Feasibility researched + the project skeleton built. Verdict **🟡 GO-WITH-CAVEATS,
"prove-before-invest"**: 4 of 5 pipeline pillars are SOLVED and locally verified;
the project is gated on ONE hard dependency — there is **no free/open/scriptable
forge REPACKER for the 2025 `scimitar` v42 generation**. A *manual* one-off Hebrew
mod is likely achievable; the *automated launcher pipeline* (usual end goal) is
blocked until an open repacker exists. Full writeups: `games/acshadows/FEASIBILITY.md`
/ `PIPELINE.md` / `RECON.md`; memory [[acs-feasibility-go-with-caveats]].

- **Install:** `C:\Games\Assassin's Creed Shadows`, Ubisoft **Anvil**, ~142 GB,
  **99 `.forge` archives ALL version `scimitar` v42** (`b"scimitar\x00"` + `uint32
  LE 0x2A` @ offset 9 — verified via `games/acshadows/tools/acs_forge_probe.py
  survey`). Forge inner blocks are **Oodle-Kraken** compressed (lead `0x8C`); the
  game ships **NO `oo2core` DLL** (a repacker must supply one from another title).
  `dstorage.dll` present (DirectStorage/GDeflate streaming).
- **🟢 SOLVED — FONT (the big de-risk):** `resources/AvenirNextWorld-Regular.ttf`
  already carries **52 Hebrew glyphs (real outlines, not `.notdef`)** + 104 Arabic +
  133 Arabic presentation forms. The shipped UI font renders Hebrew AND does Arabic
  shaping/RTL — **no font work at all** (unlike Heebo/SM2, atlas/WD2, CR2W/CP2077).
- **🟢 SOLVED — Oasis loc system:** `VoiceAnimDataByOasisID` + `Dialogue*` in the
  Anvil type table. Text = per-language binary **`LocalizationPackage_<Lang>.data`**
  INSIDE the forge, keyed by numeric Oasis hashes (one file per language) — WD2's
  oasisstrings family. Lives in `DataPC_boot.forge` (20.7 GB) + its patch forges, NOT
  the per-language SOUND forges (audio only: bra/eng/fre/ger/ita/jap/spa, no Arabic VO).
- **🟢 SOLVED — language select = trivial INI edit:** `Documents\…\ACShadows.ini`
  `[Language] Text=/Subtitles=` use plain codes (`en-US`); flip to `ar-AE`. The 23-byte
  root `localization.lang` (`b"LANG…"`) is just a pointer stamp.
- **🟢 SOLVED — deploy/Denuvo:** Denuvo protects the EXE, not asset forges — many
  Nexus retexture/outfit forge mods load fine; no EAC. Deploy = repack-and-replace
  **`DataPC_boot_patch_01.forge`** (the slot the live modding scene + Mod Manager
  v1.0.4 use — NOT `patch_02`, which is the game's own TU forge) + back up vanilla;
  re-apply after each game update (Ubisoft Connect "verify" reverts it).
- **🔴 THE GATE:** the only v42 extract+REPACK tool is **AnvilToolkit's
  donation/Discord-gated AC Shadows BETA** (public release stops at Mirage 2023). Its
  ability to repack a v42 `LocalizationPackage` into a forge that LOADS is unproven by
  any artifact, **no AC Shadows text mod exists in ANY language** (only retextures),
  reimport must preserve the `.header` sidecar or the game crashes, and a Discord-gated
  closed binary **cannot be bundled into the launcher**.
- **✅ STAGE 0 PART A — PASSED in-game (2026-06-17, user-confirmed).** Set
  `Text/Subtitles=ar-AE` via `acs_set_language.py --arabic` + launched the VANILLA
  game → the first-run setup screen rendered **fully Arabic, correct engine-native
  RTL** (`لغة النص=العربية`, `لغة الصوت=English`). **The Arabic RTL text slot is REAL
  and selectable on this SKU** — the research dispute (Game8 omitted Arabic) is
  resolved GREEN. Font + Arabic-slot + locale + oasis + deploy are now ALL proven;
  **exactly one gate remains** (the v42 repacker).
- **NEXT — Part B (the only remaining gate, needs external tools):** acquire the
  ATK beta + an `oo2core` DLL, extract the Arabic `LocalizationPackage`, repack it
  UNCHANGED into `patch_01`, deploy → does it boot showing vanilla Arabic? This
  zero-translation identity round-trip proves the repack+Oodle+`.header`+integrity+load
  chain before any translation. `tools/acs_capture.py` (built) grabs the game window
  for in-game verification (works — not exclusive-fullscreen).
- **Skeleton built:** `games/acshadows/` — `tools/acs_forge_probe.py` (read-only
  inspector, working), `tools/acs_set_language.py` (ini flip + backup, working),
  `tools/acs_capture.py` (window grab), `work/acs_{translate,watchdog,progress}.py`
  (SM2 LM trio copied as TEMPLATES), `extract/` (empty).
- **✅ READ-SIDE TOOLING BUILT + format largely cracked (2026-06-17, pure-RE "way 1"):**
  - **Oodle SOLVED** — `tools/acs_oodle.py` wraps `oo2core_9_win64.dll` (borrowed from
    `C:\Games\Battlefield 6`; game ships none) via ctypes: compress+decompress
    round-trip identical, our Kraken output lead byte = `0x8C` = forge blocks. **The
    Oodle wall is gone — we can decode AND re-encode** (key for building our own
    repacker; only DLL *redistribution* is gated, not local calls).
  - **v42 forge TOC reader VERIFIED** — `tools/acs_forge.py` (list/raw/verify/extract/
    decode-stats). Index: `u64 ptr@off13` → `u32 count@idx+0x0C`, `u32 array@idx+0x28`;
    24-byte records `{u64 offset,u32 ts,u32 flags,u32 size,u32 nameHash}`. Cumulative
    invariant `off[n+1]==off[n]+size[n]` holds **100%** incl. **DataPC_boot.forge
    (129,843/129,843, 20 GB)** + shared_00 (35,076/35,076).
  - **Resource sub-container cracked for simple resources** — chunk header 0x1F bytes:
    `magic 0x57FBAA33 · 0x1004FA99 · … · u32 uncompSize@+0x13 · u32 compSize@+0x17 ·
    u32 cksum@+0x1B · payload@+0x1F` (Oodle or stored). **98/103 AnimusRoom resources
    decode.** READ proven end-to-end (TOC→chunk→Oodle→bytes).
  - **✅ READ PATH COMPLETE — real dialogue text read (pure RE "way 1", no gated tool).**
    LARGE multi-block resources (the loc package = boot.forge idx 36626, nameHash
    `0xa5b3bea0`, base+patch dup) use **256 KB blocks** preceded by a `{count,blockSize}`
    header + a comp-size table + small variable inter-block headers. A robust walk
    (binary-search each block's comp length + forward-scan past headers) decoded **all
    134 blocks → 35.1 MB, whole resource**. Translatable text is **UTF-16LE keyed by
    Oasis IDs** (`0xAC4BDB1D…`); recovered real lines verbatim ("Don't be mad.", "Can you
    play something, Naoe? Please?", etc.). So TOC→resource→multi-block Oodle→UTF-16
    dialogue all works in home-built Python.
  - **✅ WRITE FORMAT CRACKED + CODEC ROUND-TRIPS (2026-06-17).** Decompiled the FREE
    public **AnvilToolkit v1.3.4** with `ilspycmd` (same method as AC2; user downloaded
    the binary, no donation) → exact `CompressedFileData` spec (full writeup
    `games/acshadows/FORMAT.md`): `u64 Magic 0x1004FA9957FBAA33` + `CompressionInfo[7]`
    (i16 ver=3, u8 algo=8=Oodle, OodleVersions[Shadows]=9 → oo2core_9) + `i32 blockCount`
    + BlockInfoData `{i32 uncomp, i32 comp}×N` + CompressedData `{u32 adler, comp bytes}×N`.
    **THE CHECKSUM is LZO Adler-32 = `zlib.adler32(data, 0)`** (start value 0) — a plain
    data checksum, NOT anti-tamper — **verified byte-for-byte on multiple blocks**. So a
    home-built Python repacker is fully viable (this was the make-or-break unknown).
    `tools/acs_cfd.py` = decode+encode; **round-trip on the 56.3 MB loc resource = 2/2
    CFDs reproduce identically**. The entire read+write engineering is now proven offline.
    Decompiled ATK source kept at `c:\tmp\atk_src\`.
  - **REMAINING to in-game Hebrew:** (a) locate the Arabic-slot UI resource (the
    setup-screen strings — 36626 is English quest dialogue; the visible menu Arabic is a
    different, not-yet-located resource); (b) parse the Oasis id↔UTF-16 record layout to
    edit a string; (c) inject Hebrew → re-encode CFD → same-size in-place patch (delta-0,
    forge TOC unchanged) → deploy to `patch_01` (backup vanilla); (d) user launches +
    verifies Hebrew RTL. Denuvo protects the exe not asset forges (texture mods load), so
    the repack-loads risk is low. Then the standard translate→publish pipeline.

### Loc format RESOLVED + 15,997 English lines uploaded to /translate (2026-06-20)

The "fragment LocalizationPackage" theory (§4b of an earlier FORMAT.md) was **empirically
WRONG for Shadows**: the ATK `LocalizationPackage` class hash `0x6E37B1AF` (1849465967) is
**ABSENT** from every shipped forge (full-decompress scans: top-50 largest + all 25k of the
100KB–5MB band + the entire 129,844-resource boot.forge → zero hits). AC Shadows stores text
as **literal UTF-16LE**, two kinds:
- **Oasis line records (the translatable dialogue):**
  `[lineID u64][0xFADE9F44 u32][00][convID u64][0000][charLen u32][UTF-16LE]`. `0xFADE9F44`
  (`44 9F DE FA`) = the localized-string field tag; the u64 **before** it = the unique Oasis
  line-ID (cross-language key); `charLen` = UTF-16 unit count. Tool: **`tools/acs_oasis.py`**
  (`scan`/`dump`/`extract`). Distributed (no master table; densest resource = 84 lines).
- **Bare UI strings:** `[u32 charLen][UTF-16LE]`, no inline id (settings/menu, e.g. idx 40549
  — the proof-of-load path). Not yet pool-uploadable (needs a `resourceHash:index` key).

**Extracted + uploaded** (user request "upload all English lines like the other games"):
boot **14,084** + patch_01 **10,979** + patch_02 **7,921** = **16,725 unique lineIDs** →
merged/normalized (`tools/acs_build_ct.py`, drop 728 markup-only) → **15,997 rows** →
`universal/community_translate.py import ac-shadows` (game id is **`ac-shadows`** with a
hyphen; the games row already existed). Verified live on `/translate`: `untranslated_open =
15,997`. The per-language SOUND forges and the `*_dlc.forge` (Vault/Rift/CrystalCave/WhiteRoom)
have **0** oasis records. English is clean (no Arabic/JP leakage; markup like `[beat]`,
`[[grunts]]`, `[style=…]` preserved). Files: `c:/tmp/acs_en_{boot,patch01,patch02}.json` →
`c:/tmp/acs_ct_strings.json`.

**Still open (deploy-side gate, unchanged):** the dialogue resources carry the ENGLISH text
inline; whether the Arabic copy of each lineID sits in the SAME resource (so Hebrew can be
written keyed by lineID) or a separate package is **not yet confirmed** → the Hebrew
write-back path is unproven. The bare-UI same-size in-place repack (`acs_repack.py` on idx
40549) is still the only demonstrated write. Memory [[acs-feasibility-go-with-caveats]].

### ✅ TEXT SOLVED end-to-end + 🔬 the FONT gate, fully mapped (2026-07-18/20)

Everything below is from the deep font session. **TEXT is 100% solved and proven in-game**;
the remaining gate is getting the Hebrew *glyphs* to rasterize. Plan of record:
`games/acshadows/PLAN_HEBREW.md`. Memory [[acs-shadows-text-solved-font-gate]].

**🔴🔴 THE TEXT ROOT CAUSE — the same lineID lives in THREE LocalizationPackages, and only
the winning one matters.** The menu proof verified "green 11/11" while the menu stayed
Arabic. The 11 main-menu lineIDs are split across **boot res 18566 (10 strings) ·
patch_01 res 51444 (11) · patch_02 res 17388 (11)**, and an earlier deploy had run with
`ACS_FORGES` restricted to patch_02 — so the package the engine actually resolves stayed
vanilla. Two compounding traps:
- `acs_loc_deploy.verify(patched_only=True)` **only checks packages that already have a
  `.lpbak_` sidecar**, so it reports a perfect score while ignoring the package that is
  actually being displayed. **A verifier that only inspects what you patched can never
  tell you that you patched the wrong thing.**
- `--verify` alone raises (`heb is None`) — it must be `--proof --verify`.
**Fix: always deploy + verify across ALL THREE forges** (`ALL_FORGES` is the default; do
not narrow `ACS_FORGES` unless you re-verify globally afterwards). Now 11/11 live in all 3.
**UNIVERSAL: in a base+patch archive stack, a string can exist in several packages and the
engine picks by load order — patch every copy, and verify by reading back the resource the
engine WINS with, not the one you edited.**

**Font container — PHXFD, fully dissected (`class hash = zlib.crc32("PHXFD") = 0xcbd4939a`).**
Reference weight 20630 (pristine decoded = 3,575,045 B):
| Region | Bytes | Contents |
|---|---|---|
| header | `0..328` | wrapper + `"PHXFD"` + 144-byte header + `"GFOF"` @256 |
| page-1 records | `328..38,416` | 1058 glyph records |
| GAP | `38,416..52,888` | size-page headers (page-2 @38,432) |
| **stream A** | `52,888..2,861,186` | **THE ATLAS** — 8-bit SDF rasters |
| TAIL | `2,861,186..3,575,045` | 713,859 B, second raster region |

- **Glyph record = 36 bytes**: `f32[7] = [advance, xMin, yMin, xMax, yMax, W, H]` +
  `u32 tex_offset` @+28 (**ABSOLUTE** into the decoded object) + `u32 codepoint` @+32.
  Lookup is **LINEAR** (no hash/sorted table), so any record order works.
  Raster = `decoded[tex_offset : +W*H]`, 8-bit SDF with **edge ≈ 128** (inside ~168,
  outside ~40, far-outside 0).
- **Size-page header = 16 bytes**: `u32 em=1000 | u32 0 | f32 scale | u32 count`, then
  `count × 36` records. Page-2 (`scale=1, count=108`) rasters into the TAIL.
- **8 Arabic PHXFD weights** carry the menu font — patch_02 `20630/20631/20632`,
  patch_01 `24062/24063`, boot `82569/82570/82571` (each 1058 glyphs: 254 `arb` +
  725 Arabic-presentation-form). All 8 must be injected or some UI elements tofu.
- **Injection = REPURPOSE**: take the largest rare Arabic-presentation-form records
  (U+FB50–FEFF), rewrite `codepoint` → Hebrew, overwrite the raster in place.

**🔑 DIFFERENTIAL RENDERING is what cracked this — and it is the reusable method.** After
the injection produced "Arabic with noise" and static analysis had exhausted itself, the
answer came from *changing one candidate region and looking at the screen*
(`work/acs_stream_probe.py`): vertically flip the largest **non-Hebrew** rasters in stream A,
redeploy, screenshot. The menu drew those Arabic letters **upside-down** ⇒
**stream A IS the atlas and our write path is byte-correct.** One screenshot killed every
competing theory at once (second texture / VRAM-shader cache / wrong weight / the TAIL /
2-D atlas-UV misread). See §12 of the Universal Playbook.

**🔴 …and the SAME probe isolated the actual bug, by being a strict subset of the failing
change:**
| What the edit touched | Result on screen |
|---|---|
| **pixels only** (flip probe) | ✅ reached the screen — drew upside-down |
| **pixels + metrics** (`acs_atlas_inject.py` v1 rewrote advance/bbox/W/H) | ❌ kept drawing the slot's ORIGINAL Arabic shape |
⇒ **the metric rewrite is the single difference between the working and broken cases**
(most likely the engine builds its GPU atlas from a second copy of the glyph box and falls
back to the vanilla upload when the record's W/H disagrees). Hence
**`work/acs_atlas_inject2.py`: change ONLY `codepoint` + raster pixels, and rasterize the
Hebrew letter INTO the slot's exact original W×H canvas** — every metric left vanilla. The
price is that each Hebrew letter inherits its Arabic slot's advance/bearings, so spacing and
per-letter size are uneven; that is a cosmetic follow-up, tuned one variable at a time.
**UNIVERSAL: when a big change fails, do not debug it — build the SMALLEST edit you can
prove reaches the screen, then re-add one field at a time. The delta between the two IS the
bug, and you learn it in one launch instead of ten.**

**🔴🔴 TWO HARD DEPLOY LIMITS (both cost a black screen / a wasted launch):**
1. **`_encode_exact` spends ALL the slack.** A deployed object re-encodes to *exactly* its
   forge slot with **headroom 0**, so any later edit computed against the deployed state
   fails to fit. **Every subsequent build must start from the PRISTINE blob**
   (`_atlasbak_<idx>.bin`; `acs_stream_probe.pristine()` does this) — never from what is on
   disk. A flip probe built on the deployed object scored 0/8 purely for this reason.
2. **The decoded payload must not grow far past the object's internal size fields.** Exact-slot
   fill works by appending incompressible filler; ~15 KB is fine, but a zero-fill probe made
   the object so compressible it needed **488,670–562,327 B** of filler → **black screen
   after the logo**. Keep the filler in the low tens of KB.

**Measured cost of a raster transform** (compressed-size delta vs a zero-headroom baseline —
useful for designing any future probe): `zero` ≈ **−500 KB** (unusable) · `invert` ≈
−600…+1,500 B · `vshift` ≈ +3.5–9 KB · `vflip`/`hmirror` ≈ +50–62 KB · `hshift` ≈ +77–87 KB.
**Only `invert` and small `vshift` are compressibility-neutral enough for a zero-slack
object** — a flip needs a back-off ladder (`n → n/2 → n/4 → 12 → 6 → 3` glyphs) per weight.

**Exact-slot fill: the compressed size is NOT continuous in the filler length** (one extra
byte can move the output by three), so the target byte can land in a gap. Newton-step into
the neighbourhood, scan a window, and **if it still misses, RE-SEED the filler CONTENT** —
that reshuffles where the jumps fall. Tuning matters: `seeds=12, window=96` never finished
(193 encodes × 12 seeds × 8 weights, each a full Mermaid compress of a 3–13 MB object);
`seeds=4, window=30` lands 8/8. Encoding is **Oodle Mermaid (compressor 9) at LEVEL=7**,
which reproduces the game's own blocks byte-identically.
- ⚠️ **Measure "does it fit" separately from "did the search find the byte."** A 7/8 build
  looked like an overshoot; `c:\tmp\acs_fillfit.py` proved every weight fits with **4.8–7.5 KB
  to spare** — the failure was the search, not the size. Two different fixes.
- ⚠️ Rasterize margins as **0**, not a mid-grey — a long constant run is what buys the fill
  its headroom (the shipped rasters bottom out at 0 too).
- ⚠️ Random NOISE is *less* compressible than an SDF glyph: a noise probe scored 3/8.

**Status:** `acs_atlas_inject2.py --apply` deployed 8/8 weights across all 3 forges
(27/27 Hebrew codepoints each); forges re-verified contiguous (129,843 / 46,563 / 38,555);
the rasters were read back OUT of the live forges and ASCII-rendered — מ/ש clearly correct,
`bad=0`, 22,648 ink px. **Awaiting one cold launch.** Undo: `acs_atlas_inject2.py --revert`.
Diagnostics live in `c:\tmp\acs_*.py` (`verify_heb_glyphs` · `contig` · `classes` ·
`all_phxfd` · `tailmap` · `dualstream` · `gap` · `pages2` · `tailglyphs` · `filler` ·
`transform_fit` · `fillfit`).

**Phase 3 (gated on the font):** delegate the **52,343** strings to agents
([[delegate-all-translation]]); publish nothing without an explicit "פרסם".


