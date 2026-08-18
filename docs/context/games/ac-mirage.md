## Assassin's Creed Mirage Hebrew — ✅✅ PHASE 1 COMPLETE, every gate closed in-game, 🟢 GO (2026-07-22)

**All four gates proven in-game in one session.** Hebrew renders clean in the real main menu.
Read → build → deploy → font → bidi are all solved and reproducible. Next = Phase 2 (translation).

- **✅ MOUNT + THE "ENCRYPTION" GATE — DISSOLVED, it was never a wall.** The proof deployed to the
  BASE forge changed nothing, so the patch forge shadows it (§8e). Then, inspecting the "encrypted"
  patch resource, **the marker `0xD28389B5` was still in the clear at offset 110** — and the payload
  decoded perfectly. **The `name_len & 0x40000000` flag encrypts ONLY THE NAME FIELD; the text
  payload is plaintext.** My own guard (`raise SystemExit` on the flag) is what hid this for hours.
  **🔴 UNIVERSAL: a safety guard that ABORTS on an unknown flag can hide that the data is fine —
  make it downgrade to "treat the field as opaque" and keep parsing.** We never need the key: the
  name bytes are copied through **verbatim** on rebuild (same principle as "copy the hash bytes,
  don't recompute them"). ⚠️ The encrypted name field is **padded to a 16-byte boundary** (51→64,
  56→64), so LENGTH #1's delta is 77 there vs `12+name_len+1` in the base — **derive the delta from
  the ORIGINAL (`len(content) - size_field`) instead of re-deriving the rule**, and it works for both.
- **✅ THE ENGINE ACCEPTS A PLAINTEXT RESOURCE INSIDE THE ENCRYPTED FORGE.** We wrote a flag-0
  package into `DataPC_patch_01.forge` and the marker `ZZ-P-C` rendered. So the bypass planned in
  Phase 1 works exactly as designed — no crypto attacked, no anti-tamper touched.
- **✅ ID LADDER named the live block in ONE screenshot** ([[measure-with-a-ladder]]). Every visible
  menu label maps to 3+ ids; patching them all with `א`/`ב`/`ג` variants showed **ג** everywhere ⇒
  the main menu reads the **2867xxx** block (+ `880591` Credits, `2034381` New Game). Without the
  ladder this would have been 3 wasted launches. **The first proof failed for exactly this reason:**
  I patched `Credits` at 456221 (the in-game options page) while the menu reads 880591.
- **✅ FONT = `FontFile` class (crc32 = 3295364632), 9 fonts, ALL in `DataPC.forge` only.** Found by
  decompressing every resource and validating the sfnt **table directory** (the magic alone matches
  huge amounts of binary — the AC Unity lesson). Shipped faces, all **0/27 Hebrew**: **DINPro
  Regular / DINPro-Bold (42/48 Arabic — these draw the menu)**, 2 big DINPro CJK fallbacks
  (5,567 / 16,111 glyphs), Portrait Cy Regular/Bold (display), ACK Younger Futhark (runic prop).
  Object layout is delta-13: `u32 cls · i32 size · i32 name_len(0) · NUL · 0x01 · u64 ClassID ·
  u32 Hash · **i32 ttf_len** · sfnt`. **Injected Heebo's 27 Hebrew glyphs into 7 of 9**
  (`tools/mirage_font.py`, reusing `anno_font._add_hebrew`) — Latin 26/26 and Arabic 42/48
  preserved, verified by reading the fonts back OUT of the live forge. The 2 skipped are the giant
  CJK fallbacks (fontTools rejects their cmap format 12) and they are not needed.
  ⚠️ **Fonts have NO patch override → deploy them to the BASE forge** (text goes to the patch).
- **✅ bidi = VISUAL, settled by an A/B CONTROL, not by judgement.** The shipped **Arabic renders
  correctly** while LOGICAL Hebrew came out mirrored ⇒ the engine runs its RTL pipeline for the
  **Arabic script only** and draws Hebrew in storage order — the same signature as Witcher 3 patch
  4.00 ([[bidi-is-version-dependent]]). Confirmed by storing the SAME word both ways on two visible
  rows: the VISUAL one read **שלום**, the LOGICAL one read **םולש**
  ([[hebrew-screenshot-transcription-trap]]). `tools/mirage_rtl.py` runs the **real UBA**
  (`python-bidi`, RTL base) with engine tokens (`<img…>`, `<style…>`, `{0}`, `[CT_*]`) stashed as
  atomic PUA placeholders and each `\n` line converted independently so line order is never flipped
  — 11/11 selftests, and in-game `יציאה לשולחן העבודה (בדיקה)` rendered with the parentheses on the
  correct side (the thing a hand-rolled run-reversal gets wrong on every real sentence, §8b).
- **📊 REAL SCOPE = 15,404 lines / 971,026 chars** (from the PATCH forge, the copy the engine reads —
  the base forge's 13,085 was an undercount): **UI 9,748** (median 24 ch, 5,134 ≤25, codex up to
  2,167) + **subtitles 5,656** (median 44, max 155, only 7 >140). **8 oracle languages at the same
  ids in the same forge** (ar/fr/ru/es/it/pl/de + en) → the New-Era panel is free.
  Corpus dumped to `extract/patch/*.json`.
- **NEXT — Phase 2:** delegate the 15,404 lines ([[delegate-all-translation]], single pass, no
  fleet) → build with `mirage_rtl.to_visual` → `mirage_build.py build` → `mirage_deploy.py apply`
  into `DataPC_patch_01.forge` → publish (id `ac-mirage`, price per [[mod-price-53-default]]) only
  on an explicit "פרסם". Deployed state right now = proof #4; revert both forges with
  `mirage_deploy.py <forge> revert` (backups `DataPC.forge.he_backup` +
  `DataPC_patch_01.forge.he_backup`).
- ⚠️ **Ubisoft Connect's "update" was a verification pass, not a content patch** — the exe, the
  manifest and every forge kept identical sizes/entry counts; only mtimes and `uplay_install.state`
  changed, and **our deployed patch survived it untouched**. It DOES take a transient file lock
  (a deploy failed with `PermissionError` and succeeded seconds later).

### ✅ TITLE LOGO — SOLVED: the asset is `UI_PressStart_Text_AR`, and the ship is "drop the Arabic line" (2026-07-22)

Goal was to replace the Arabic line under the logo (**السَّراب**) with Hebrew. **Final shipped
answer, at the user's direction: don't substitute anything — REMOVE the script line, so the
Arabic slot renders the same lockup the Latin locales get** (ASSASSIN'S CREED + MIRAGE, nothing
underneath). Deployed and verified.

**🔑 THE ASSET: `UI_PressStart_Text_AR` (1024×560) in `DataPC_extra.forge` — NOT `UI_TitleReveal_AR`.**
Two families exist with near-identical three-band artwork; only PressStart is drawn. The tell is
**colour, and it was visible in the user's screenshots the whole time**: TitleReveal ink is pure
**white (255,255,255)**, PressStart is a **gold gradient** (ink mean ≈ 222,187,164) — which is what
the screen shows. Structure alone could not separate them; one glance at the palette could.
**When two assets match the screen structurally, compare their COLOUR to the screenshot before
deciding which is real.**

**How it was found after TitleReveal proved dead:** `tools/find_logo.py` scores every texture on
the SHAPE of its artwork — wide canvas, 3 stacked full-width ink bands, line-art coverage — instead
of on the name (patch forges encrypt them) or the size (unknown). **The unlock was accepting
MIPMAPPED textures**: `find_dims` demanded `payload == w*h` exactly, which silently skipped every
mip chain (`w*h*4/3`); with `dims_any` the textures measured in `DataPC_extra.forge` went from ~25
to 3,079 and the PressStart family surfaced immediately. **A dimension probe that only accepts one
payload layout is a silent filter, and it reads exactly like "nothing is there".**

**⚠️ THE COST OF THE MISTAKE: ~5 game launches burned on TitleReveal before the decisive test ran.**
That test is cheap and should have been FIRST: overwrite the texture with **solid white**, and one
launch answers "does the engine read this at all". **When a data swap doesn't show up, prove the
engine reads the slot before improving the payload.** ⚠️ And the first white-out was *worthless*
because it was built from an already-white slot: the zero padding of the previous in-place write
was re-parsed into the blob, inflating it to 187,664 B (a clean white is ~44 KB) and handing the
game a malformed resource. **Always rebuild from the PRISTINE forge** — `TextureRes` keeps
everything after the CFD chain as `trailer`, so a deployed slot round-trips its own padding back in.

**COMPLETE INVENTORY — the whole game holds exactly 6 Arabic textures** (`tools/find_ar_textures.py`,
name scan over `DataPC_extra` + `DataPC` + `DataPC_TitleScreen`; **0 shadowed by any patch forge**):

| family | Map_PC | MapDesc | Map_Durango_Orbis | canvas |
|---|---|---|---|---|
| `UI_PressStart_Text_AR` (**drawn**) | 2181436741074 | 2181436741075 | 2181436742028 | 1024×560 / 512×280 |
| `UI_TitleReveal_AR` (dead data) | 2141045950540 | 2141045950541 | 2141045950553 | 1072×600 / 536×300 |

All six are single-mip, no trailer, W%4 = H%4 = 0. All six were patched — the answer should be
"no Arabic anywhere", not "no Arabic where I looked". `find_ar_textures.py` is fast because it
decompresses **only the first block of the last CFD** (the name sits at content offset 12), instead
of inflating a 600 KB texture just to read its name.

**🔑 THE GAME SHIPPED THE TARGET DESIGN — copy a sibling instead of inventing one.**
`UI_PressStart_Text_RU` is the same 1024×560 canvas with the same first two bands and **no third**:

    UI_PressStart_Text_AR   bands (6,201) (232,348) (375,540)   <- 3 lines
    UI_PressStart_Text_RU   bands (6,201) (233,345)             <- the target look

So "make Arabic look Latin" is not a design task at all — it is *clear everything below MIRAGE*.
**Before building a variant by hand, check whether the game already ships the variant you want in
another locale and measure it.**

**The strip (`work/logo/strip_arabic_band.py`) is exact by construction.** The cut is snapped UP to
a **4-row block boundary** (`cut = ceil((band2_end+1)/4)*4`), so no BC7 block containing MIRAGE ink
is ever re-encoded — only fully-cleared block rows are. Result on all 6: **kept rows max err 0
(byte-identical), leftover alpha 0, bands now exactly 2.** Payload length is unchanged, so each
resource goes back **in-place**: file 2,546,499,584 B before and after, records untouched,
**contiguity violations 0**. Blobs shrink a lot (46 KB into a 68 KB slot) because a transparent
region compresses hard — never a fit problem.

**🔴 The direction of the cut is the trap.** Store order is BOTTOM-UP, so the rows to re-encode are
the FIRST block rows of the payload, not the last. Getting it backwards keeps the Arabic and wipes
ASSASSIN'S CREED — **and a per-band error check still reads "clean", because both halves are
individually correct, just swapped.**

**Diagnostics that WERE worth building (keep):**
- **Last-access tracking is ENABLED on this machine** (`fsutil behavior query DisableLastAccess`
  = 2). That makes it possible to see WHICH forges a session actually opened: during the 07:34
  run the game opened `DataPC.forge`, `DataPC_extra_patch_01.forge`,
  `DataPC_SharedGroup_00_patch_01.forge` and `DataPC_TitleScreen.forge`. ⚠️ Your own scans
  clobber atime — snapshot it BEFORE reading anything.
- `Universe` (resource **2107** in `DataPC.forge`, 157 MB) holds the master tables. Its
  per-language logo table is a **9-byte record array** (`u64 resource_id` + `u8`): 17× LogoText,
  then RU, JP, KOR, TRAD_CH, SIMPLE_CH, **AR**, then LogoText ×2. It maps Arabic to the
  **TitleReveal** id — i.e. **the game's own lookup table points at the asset that is never
  drawn.** A manifest is not proof of what renders; only the screen is.
- `DataPC_TitleScreen.forge` is the 3D title scene (Basim, weapons, cells) — not the 2D logo.
- Ruled out and not worth re-checking: loose files (only `splashscreen.png` +
  `Installer_Resources/game_art*.png`, crest-only), video, `Documents\…\cache|file_cache`
  (Ubisoft Connect store art), AppData, a second install, and font-rendered text (no standalone
  "السراب" string exists in the loc corpus — every hit is a full product name inside prose).

**🔑 THE DEPLOY CHAIN IS PROVEN — by the TEXT, on screen.** The main menu renders
`שלום` / `טען משחק` / `אפשרויות` / `קרדיטים` + the Latin marker `ZZ-V4`, i.e. the
LocalizationPackage patches in `DataPC_patch_01.forge` are live.

- **`UI_TitleReveal_AR` matches the on-screen lockup pixel-for-pixel and is still DEAD DATA**
  (1072×600; bands 9..220 ASSASSIN'S CREED / 241..372 MIRAGE / 393..567 السَّراب) — which is exactly
  why it was so convincing. Siblings per script: `_JP _KOR _RU _SIMPLE_CH _TRAD_CH` (each a
  different height for its own subtitle) + `_LogoText` (1072×384, Latin only) / `_Crest` /
  `_UbisoftOriginal`. Whiting out **all 21** of them changed nothing on screen, not even the crest.
  **An asset matching the screen pixel-for-pixel is not proof the engine draws it.**
- **🔴🔴 THE SAME IMAGE EXISTS AS *TWO* RESOURCES AND BOTH MUST BE PATCHED.** Patching only
  the obvious one changed **nothing on screen**:
  | resource | id | class | header | payload |
  |---|---|---|---|---|
  | `UI_TitleReveal_AR_Map_PC_Ggp_Prospero_Scarlett` | **2141045950540** | `TextureMap` (2729961751) | 264 B | 643,200 B |
  | `UI_TitleReveal_AR_MapDesc` | **2141045950541** | `TextureMapSpec` (2560476850) | 325 B | 643,200 B |
  **"MapDesc" reads like a descriptor and is not — it carries the full pixel payload too**,
  and it is the copy the game rendered from. The tell was in the listing all along: its
  on-disk size (187,664) is within 34 bytes of the `_Map_PC_` one. **Whenever two resources
  of the same asset have suspiciously similar sizes, decode BOTH before deciding which is
  "the" texture.** `_Map_Durango_Orbis` (id 2141045950553) is the Xbox-One/PS4 quarter-res
  copy — content only 161,053 B, PC never reads it, correctly skipped.
- **Object layout is delta-0 friendly:** `u32 class · i32 size · i32 name_len · name · NUL ·
  …descriptor… · BC7 payload 643,200 B`. The replacement is the same length, so **the size
  field and every header byte carry over untouched.** The header LENGTH differs per class
  (264 vs 325), so `mirage_texture.py` derives it as `len(content) - len(payload)` rather
  than hardcoding it.
- **🔴🔴 THE PAYLOAD IS STORED BOTTOM-UP — and the naive splice fails SILENTLY.** Decoding
  the raw blocks and diffing against the reference PNG gives **472,994** alpha differences
  as-is and **0** after `flipud`. Splicing on the top-down row number would have kept the
  Arabic and overwritten ASSASSIN'S CREED — **and the per-band error check would still have
  read "clean", because both halves are individually correct, just swapped.** Always PROVE
  the orientation with a diff against a known reference before slicing a texture by row.
- **🔴 The near-black RGB under low alpha is a BAKED SHADOW, not encoder debris.** 298,715
  texels sit at alpha 1..199 with RGB mean 18. Flattening them to white (the obvious move to
  make blocks collinear for a single-axis BC7 mode) lights that shadow up as a **visible halo
  around ASSASSIN'S CREED**. Measure what low-alpha RGB is doing before "cleaning" it.
- **✅ THE FIX: splice at BLOCK level.** BC7 is a fixed 16-B-per-4×4-block format with no
  inter-block state, so Ubisoft's own blocks are carried over verbatim for the untouched bands
  and only the Hebrew band is re-encoded — **64% of bytes kept byte-identical**, the top bands
  come back at **max channel error 0**, the new line at **max 10/255**. Same "touch only what
  changed" discipline as the forge deploys, one level down. Split: displayed y≥384 ⇒ raw block
  rows 0..53.
- **`games/acmirage/tools/bc7_encode.py` (NEW) — a BC7 encoder, mode 6 only.** Nothing on this
  machine could WRITE BC7 (PIL decodes `bcn` but cannot encode; no texconv/nvcompress/
  imagecodecs), so it is written in-repo rather than adding a binary dep. Mode 6 is the one
  mode with a single subset + full RGBA endpoints, which is near-lossless for line art
  (selftest: max channel error **1**) and hopeless for noise — fine, the content is bimodal.
  Endpoints come from the block's dominant axis; the shared p-bit is chosen by measuring both
  options; the anchor index constraint is handled by swapping endpoints and mirroring indices.
- **Tools (all under `games/acmirage/`, run with the repo `.venv` python):**
  | file | role |
  |---|---|
  | `tools/bc7_encode.py` | the BC7 (mode 6) encoder — nothing on this machine could WRITE BC7 |
  | `tools/mirage_texture.py` | TextureMap/Spec payload swap + a re-decode check |
  | `tools/mirage_deploy.py` | `inplace` (preferred) / `apply` (relocate) / `verify` / `revert` |
  | **`tools/find_ar_textures.py`** | **name scan for Arabic variants; decompresses one block per resource** |
  | `tools/find_logo.py` | signature search (shape, not name/size); `dims_any` accepts mip chains |
  | `tools/mirage_texdump.py` · `slot_patch.py` · `atime_probe.py` | dims probe · slot-level backup · which-forge-did-the-session-open |
  | **`work/logo/strip_arabic_band.py`** | **THE SHIPPED BUILD — clears everything below MIRAGE on all 6** |
  | `work/logo/survey_logo_family.py` · `probe_ar.py` | family dump + patch-shadow check · per-resource measurement |
  | `work/logo/build_pressstart.py` | the Hebrew-calligraphy build (superseded; keeps the gradient-sampling technique) |
- **Revert:** `python games/acmirage/tools/mirage_deploy.py "<…>/DataPC_extra.forge" revert`
  (pristine `.he_backup`, 2.5 GB, + a `.he_journal.json` fallback).
- **The Hebrew-calligraphy route is SUPERSEDED but its technique is reusable.** `build_pressstart.py`
  sampled the shipped **gold gradient** row-by-row from the band it replaced (interpolating rows with
  no ink) and re-applied it to the new artwork, so the new line matched MIRAGE's colour ramp exactly.
  **When replacing part of a gradient-filled asset, measure the gradient from the pixels you are
  overwriting instead of picking a colour.** Artwork was the USER'S (`תמונה4.png`, 3782×626) — my own
  attempts (typeset Heebo over a kashida rail, then hand-drawn Bézier letterforms) were both rejected,
  correctly: *"לקח פונט רגיל של עברית ולהוסיף קו זה לא הדרך"*. Kept for reference:
  `work/logo/{build_hebrew_logo,draw_hebrew_calligraphy,font_sheet,fit_user_art,splice_bc7}.py`.
  Measured targets if a band is ever redrawn: pen **13 px** monoline, kashida baseline **y 507..519**,
  body ~69 px, ink span **x 12..1059**.

### Phase-1 detail (as first mapped)


## Assassin's Creed Mirage Hebrew — Phase-1 groundwork DONE, 🟡 GO-WITH-ONE-GATE (2026-07-22)

New game scaffolded at `games/acmirage/` (RECON/FEASIBILITY/PIPELINE + `tools/` + `extract/`).
Install `F:\Game Lab\Assassin's Creed Mirage`, Ubisoft Bordeaux 2023, **AnvilNext (Valhalla
lineage)**. Proposed `games.id` = **`ac-mirage`**, detector exe `ACMirage.exe`. **Read-only recon —
no game file modified.** Memory [[acmirage-groundwork-go]]. Six of seven gates closed offline in
one session; the whole read chain is pure Python and validated.

- **🟢 Container = scimitar **v29**, CRACKED + VALIDATED** (`tools/mirage_forge.py`). Fills the gap
  between Unity (27) and Shadows (42): header `"scimitar\0" + u32 ver@9 + i64 header_size@13
  (=1050)`, then at 1050 `i64 total_count, i64 0, i32 -1, i64 -1, i32 count+6, i32 fileset_count,
  i64 first_fileset (=1094)`; FileSet = `u32 count … i64 next@+0x10 … entries@+0x30`, each entry
  **20 B = `i64 offset, u64 id, i32 length_on_disk`**. `validate()==0` + exact counts on all 35 root
  + 15 DLC forges. **🔴 v29 has NO NAME TABLE** — AnvilToolkit does `Entry.Name =
  ID.GetOriginalFileName()` from an external hash→name DB, so resources are addressed by u64 ID
  and must be located by **CONTENT** (`tools/mirage_scan.py` scans the ScimitarClass hash).
- **🟢 Codec = the AC Shadows CFD, unchanged.** Every resource is `CFD0`(16-byte meta)+`CFD1`(object),
  magic `0x1004FA9957FBAA33`, algo 8 = Oodle, `{i32 uncomp,i32 comp}` blocks, `adler32(comp,0)`,
  STORED when equal — `games/acshadows/tools/acs_cfd.py` decodes it as-is (borrowed
  `oo2core_9_win64.dll`; Mirage ships none). Object header = `u32 class_hash (=crc32(ClassName)),
  i32 size, i32 name_len, name`.
- **🟢 Text = `LocalizationPackage` (class 1849465967), 14 languages, decoded.** `tools/mirage_loc.py`
  → `[i32 Type][u32 Language][12][u32 marker 0xD28389B5][i32 count][BE payload]` → the AC2/Unity
  **char-index fragment-tree** store (`acu_loc.decode_payload` reused verbatim).
  **Scope = 13,085 lines / ~800k EN chars: UI 7,612 (median 22 ch, codex up to 2,167) + subtitles
  5,473 (median 43, max 155).** Key sets identical across all 14 languages → map EN→HE by id.
  Tokens: `\n` ×2,414, `<img src='…'/>`, `<style name='…'>…</style>`, `{0}/{1}`, `[CT_*]` buttons,
  `[sigh]/[laugh]/[beat]`. Identity round-trip **semantic PASS 7,612/7,612 + 5,473/5,473** (not
  byte-identical: the game uses a multi-char BPE-ish fragment dict, ours single-char → payload
  ~1.7–2× bigger, exactly like AC Unity).
- **🟢 THE ARABIC SLOT IS FIRST-CLASS** — Mirage is set in 9th-century Baghdad and ships **Arabic UI
  + subtitles + full Arabic VO** (`sounddata\PC\sounds_ara.pck`, `ara=15`). All 14 languages live
  **inside the forge** (no language-pack download). **Activation = ONE registry string**
  `HKCU\SOFTWARE\Ubisoft\Assassins Creed Mirage\Language = ar-AA` (from `uplay_install.state`;
  key absent until first launch) → a `kind:"registry"` `game_language.py` entry, same lever as
  AC Black Flag Resynced. Text and audio language are independent → English VO preserved.
- **🟢 bidi = LOGICAL, zero bidi code.** Measured over the shipped Arabic (497,101 Arabic chars):
  **0 presentation forms**, **2** bidi controls in the entire corpus, 3,437 lines end with `.` vs 1
  that starts with one ⇒ the engine does its own shaping + reordering. Store natural Hebrew, never
  pre-reverse, no `&rlm;`.
- **🔴🔴 THE ONE GATE — the title-update forge is ENCRYPTED.** A full sweep of **all 50 forges**
  found LocalizationPackages in exactly three places: `DataPC.forge` **28 packages, 100 %
  PLAINTEXT**; `DataPC_patch_01.forge` **the same 28 resource IDs, ~+22 % bytes, ENCRYPTED**;
  `dlc_2\DataPC_2_dlc.forge` 28, encrypted. The flag is `name_len & 0x40000000` (base 0 % encrypted,
  patch ≈87 %, DLC loc 100 %). A known-plaintext XOR (patch ciphertext vs the base's plaintext
  resource name) recovers a "keystream" that is **identical for exactly the first 16 bytes** between
  two resources sharing a 16-byte plaintext prefix and then diverges ⇒ **a 16-byte BLOCK cipher
  (AES-class), not an XOR stream**; the key sits in the VMProtect-packed exe (`.vmp0`/`.vmp1` +
  `denuvo` strings). **We do NOT attack it** ([[acbf-resynced-v50-cracked]] policy). The bypass to
  TEST is that the flag is **per resource** and the base forge proves the engine reads flag-0
  objects natively → write a **plaintext (flag-cleared)** package into whichever slot the engine
  wins with, or drop the patch's loc entry so the base wins. Per §8e the patch normally shadows the
  base — **one screenshot decides which branch we are in.**
- **🟡 Font NOT located.** No `.ttf`/`.otf`/`.ffd` strings and no embedded sfnt in `ACMirage.exe`
  (VMProtect-packed, so static strings are unreliable — only `Noto` ×3 / `ICU` ×2 survive); no
  font-named resource in any forge (only `DebugFontTexture` + `SDR_UI_WorldMap_FogFont`).
  Same shape that ended AC Unity — **but with the decisive difference that Mirage's Arabic is a real
  UI locale rendering RTL in the actual menus**, so an Arabic-capable face is definitely loaded; only
  Hebrew coverage is unknown, and the menu proof answers it alongside the gate above.
- **🔑 A FREE PUBLIC TOOL COVERS THE WHOLE CONTAINER — this is what AC Shadows/Black Flag lacked.**
  Decompiling **AnvilToolkit v1.3.4** (no donation/Discord gate) shows `Game.Mirage` with **BOTH
  `ForgeFile.Deserialize29` AND `Serialize29`** (a real v29 repacker) and `Game.Mirage` inside
  `LocalizationPackage.SupportedGames`. We do not depend on it (everything above is pure Python) but
  it is a proven repack fallback. Decompile: `ilspycmd -t <FQTN> AnvilToolkit.dll` with
  `DOTNET_ROLL_FORWARD=LatestMajor`; source cached in `c:\tmp\anvil_src\` (+ `FileSet.cs`,
  `ForgeEntry.cs` added this session), binary in `c:\tmp\atk134\`.
- **🟢 WRITE PATH BUILT + VALIDATED OFFLINE (same session).** `tools/mirage_build.py` +
  `tools/mirage_deploy.py`. **Object layout mapped byte-for-byte, and there are exactly TWO length
  fields** — the object `size` at **+4** (`= len(content) - (12 + name_len + 1)`) and the payload
  `count` at **marker+4**; the payload runs to the END of the object (tail = 0 B). Field offsets
  around the marker: `Hash mk-24 · Type mk-20 · Language mk-16` (⚠️ my first pass was one field off —
  Type read as the Hash; the tell was `Type=1849465967`). `Type` 0=UI / 1=Subtitles;
  `Language` **1=English(US), 22=Arabic**. Re-encode via `acs_cfd.build_cfd` with **Mermaid @7**.
  Deploy = **append-relocate** (append at EOF → patch only that record's `offset` @rec_pos+0 and
  `length_on_disk` @rec_pos+16), `.he_backup` + a `.he_journal.json` so `--revert` works even
  without the backup.
- **✅ OFFLINE PROOF ON A COPY OF THE REAL FORGE — all green:** identity `selftest` PASS
  (7,612/7,612 and 5,473/5,473, both length fields correct); after deploying the menu-proof blob the
  patched resource re-reads with its 5 edits, **38,109/38,109 other resources are BYTE-IDENTICAL**,
  the header + FileSet table are byte-identical, **27/27 sibling loc packages still decode**, and the
  file grew by exactly the blob. Payload +1.68× (single-char fragment dict) yet the blob is SMALLER
  than vanilla (194,729 vs 214,689 B) — Mermaid compresses the simpler stream better.
  **The real game file was never touched** (validation ran on a scratchpad copy, since overwriting a
  game file is a user-OK gate).
- **NEXT = the menu proof (needs the user: game closed, then launch + screenshot).**
  `mirage_build.py … proof` patches the **Arabic** package with a pure-Latin marker
  `ZZ-MIRAGE-OK-ZZ` on `Options Page` (456215) + Hebrew on Controls/Interface-Language/Credits/Sound
  (456219/456233/456221/456223 — ids resolved from the ENGLISH package, ids are shared).
  Deploy → Options → **العربية** → one screenshot settles mount · patch-shadowing · font · bidi.
  Then Phase 2 = delegate 13,085 lines ([[delegate-all-translation]], single pass, no fleet) with a
  **free New-Era panel** (all 14 languages at the same ids in the same forge; `extract/` already has
  en/ar/fr/ru/es/it/pl) + name registry + `/translate` pool (`ui:<id>` / `subs:<id>` keys).

---


