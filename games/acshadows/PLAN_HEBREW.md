# Assassin's Creed Shadows — Hebrew Translation: FULL PLAN

**Status: 🟢 GO — TEXT 100% SOLVED + PROVEN IN-GAME. One gate left: the baked font atlas.**
Written 2026-07-17; **updated 2026-07-17 (this session) with the in-game truth** — several
claims below (§1 font, §1 text-format, §2 rules 5+6) were written on pre-in-game theory and
are WRONG. The corrected truth is here at the top; the stale lines are annotated inline.

## 0-A. ⚡ CURRENT TRUTH (supersedes any conflicting line below)

- **TEXT = DONE, Hebrew renders in the main menu (user-verified).** The store is a
  **`LocalizationPackage`** object (`crc32(b"LocalizationPackage") == 0x6E3C9C6F` in v42 —
  NOT AC2's `0x6E37B1AF`; anchoring on the AC2 value is what produced June's false
  "Shadows has no LocalizationPackage / text is literal UTF-16"). It nests a
  **`CompressedLocalizationData`** (`0xD28389B5`) whose payload is the **char-index /
  fragment** format (BIG-ENDIAN), **identical layout to Black Flag v50** — the v50
  `acbf_locpkg.decode_payload`/`build_payload` work on Shadows as-is. **2,127 packages,
  LangID 23 = Arabic = 52,343 strings, 1:1 with English by lineID.** bidi = **LOGICAL**
  (engine does full bidi + shaping at runtime; store natural Hebrew, zero bidi code).
- **THE CRASH ROOT CAUSE = the Oodle COMPRESSOR (see §2 rule 5, now corrected).** The game
  compresses every block with **Mermaid (OodleLZ_Compressor 9)**; we were writing **Kraken
  (8)**. `byte0 = 0x8C` is identical for BOTH — it only means "Oodle LZ" — and the real
  codec is **`byte1 & 0x7F` = decoder_type** (game = **10** Mermaid, our Kraken = 6). A
  Kraken stream this engine will not decode → every re-encoded package crashed the instant
  the menu read it. **Mermaid@7 reproduces the game's own blocks BYTE-IDENTICALLY.** Fixed
  in `tools/acs_cfd.py` (`MERMAID = 9`, `LEVEL = 7`). This ALSO dissolves rule 6: the
  "~5% smaller → re-pack the forge" was never real headroom — Kraken simply compresses
  harder than Mermaid; match the codec and a natural re-encode lands on the vanilla size.
- **DEPLOY that works = in-place, Mermaid, exact-fill (no forge re-pack needed).**
  `work/acs_loc_deploy.py` — surgical char-index payload edit, `rebuild_blob` enforces the
  §2-rule-1 law, `exact_fill`/`_natural` hit the slot with zero pad, all blocks Mermaid.
  Proven: patched patch_02, all 4 blocks decoder_type 10, law holds, 11/11 ids read back,
  forge contiguous. **A forge re-pack (rule 6 / `repack_patch.py`) is NOT required.**
- **🔴 THE ONE REMAINING GATE = the font (baked atlas).** The Arabic-slot UI renders in
  **DIN Pro**, which has 42/47 Arabic and **0/27 Hebrew** → Hebrew shows as **tofu boxes**
  (confirmed in-game: `משחק חדש` = 4+3 boxes, `טעינה` = 5 boxes — the boxes ARE our Hebrew).
  **The engine renders from a PRE-BAKED SDF/raster atlas, NOT the TTF** — proven in-game:
  injecting the 27 Hebrew letters into the DIN `FontFile` (boot idx 9/10, `acs_font_deploy.py`,
  in-place + contiguous + Mermaid, Hebrew 27/27 verified offline) changed **nothing** while
  the Arabic stayed perfect. The runtime font is **`PhoenixFontDescriptorData`** (`PHXFD`
  magic, ~10 MB/weight) / **`OfflineGlyphs`** (`GOFF` magic) — baked with Arabic+Latin only.
  The loose `resources/AvenirNextWorld-*.ttf` (which DO ship 27/27 Hebrew) are **not
  consulted at runtime for the UI** — that §1 "FONT = ZERO WORK" claim is FALSE.
  **Next: crack the PHXFD/GOFF atlas + inject 27 Hebrew glyph rasters** (the GoWR-fOnk /
  007-GFXF class of sub-project). Then delegate the 52,343-string translation.

---

## 0. Why Shadows is GO (and Black Flag Resynced is NOT)

AC Black Flag Resynced (scimitar **v50**, 2026) was proven to have **SHA256 forge
integrity / anti-tamper**: a structurally *perfect* modified resource (buffer==object,
native block count, exact contiguity, verified byte-correct) still black-screens, with
BOTH Oodle 2.9.12 and 2.5 — while the clean forge boots fine. That is an anti-tamper wall
we do not cross.

**Shadows (scimitar v42, 2025) is a different game:**

| | Black Flag Resynced (v50, 2026) | **AC Shadows (v42, 2025)** |
|---|---:|---|
| `SHA256` strings in exe | **143** | **11** |
| `tamper` / `integrity` | 11 / 5 | 3 / 3 |
| Community forge mods | **none exist** (no v50 tool at all) | ✅ **live Nexus scene** (retexture/outfit forge mods load) |
| Forge integrity check | ✅ proven | ❌ almost certainly none (the mod scene is the proof) |
| Denuvo | yes (exe) | yes (exe) — **does not protect asset forges** |

The working Nexus forge-mod scene is empirical proof Shadows **accepts a modified forge**.
The integrity check is a **new 2026/v50 addition**.

---

## 1. Already PROVEN for Shadows (prior work, do not redo)

- **Install:** `C:\Games\Assassin's Creed Shadows` (99 forges). Exe `ACShadows.exe`
  (+ `ACShadows_Plus.exe`). Engine: Ubisoft **Anvil**, `.forge` **scimitar v42**.
  `games.id` = **`ac-shadows`** (already a catalog row; already in `game_detector.py`).
- **✅ Arabic slot CONFIRMED IN-GAME** (Stage 0 Part A, user-verified): setting
  `Documents\...\ACShadows.ini` `[Language] Text=/Subtitles=` → `ar-AE` renders the
  **full setup/settings screen in Arabic with correct engine-native RTL**. The RTL slot
  is real and selectable. Tool: `tools/acs_set_language.py --arabic` (ini flip + backup).
- **⛔ CORRECTED — FONT IS THE HARD GATE, not "zero work" (see §0-A).** The loose
  `resources/AvenirNextWorld-*.ttf` DO ship 27/27 Hebrew, but the engine does **not** render
  the UI from them — it renders from a pre-baked SDF/raster atlas (`PhoenixFontDescriptorData`
  `PHXFD` / `OfflineGlyphs` `GOFF`) baked Arabic+Latin only. Proven in-game: Hebrew shows as
  tofu, and injecting Hebrew into the DIN `FontFile` did nothing. **Requires cracking the
  atlas + injecting Hebrew glyph rasters** (GoWR-fOnk / 007-GFXF class).
- **✅ Container READ cracked** (pure Python, no community tool): `tools/acs_forge.py`
  (v42 TOC: index@`0x41a`-style descriptor → 20-byte records; validated), `tools/acs_oodle.py`
  (ctypes Oodle; borrows `C:\Games\Battlefield 6\oo2core_9_win64.dll` = 2.9.12; RDR2 has
  `oo2core_5_win64.dll` = 2.5 if ever needed).
- **✅ Container WRITE format cracked + codec round-trips.** From a decompile of the FREE
  public AnvilToolkit v1.3.4: `CompressedFileData` = `u64 Magic 0x1004FA9957FBAA33` +
  7-byte CompressionInfo + `i32 blockCount` + BlockInfo `{i32 uncomp, i32 comp}×N` +
  blocks `{u32 adler, data}`. **Checksum = `zlib.adler32(comp, 0)`** (LZO Adler-32) — a
  plain data checksum, NOT anti-tamper. `tools/acs_cfd.py` decode+encode:
  **round-trip on the 56.3 MB loc resource = 2/2 CFDs byte-identical.**
- **⛔ CORRECTED — text is char-index in `LocalizationPackage`, NOT literal UTF-16 (see
  §0-A).** The June "literal UTF-16 / no LocalizationPackage" conclusion came from anchoring
  on **AC2's** hash `0x6E37B1AF`; in v42 the class hashes to **`0x6E3C9C6F`** (a class hash
  is `crc32(ClassName)` and the name table is in the forge tail — see the memory
  `anvil-class-hash-crc32`). The real store: 2,127 `LocalizationPackage` objects, each with a
  nested `CompressedLocalizationData` (`0xD28389B5`), char-index/fragment payload (BIG-endian,
  == v50 layout). Codec: `tools/acs_locpkg.py` + the v50 `acbf_locpkg` which works as-is.
  (`tools/acs_oasis.py` for the literal-UTF-16 dialogue resources still exists but is NOT the
  menu/UI store.)
- **✅ Corpus extracted + community pool LIVE.** boot 14,084 + patch_01 10,979 +
  patch_02 7,921 → **16,725 unique lineIDs → 15,997 rows** uploaded to the `/translate`
  pool as **`ac-shadows`** (markup-only dropped). Tool: `tools/acs_build_ct.py`.
- **✅ Deploy slot known:** `DataPC_boot_patch_01.forge` — the slot the live Shadows
  modding scene uses. **NOT `patch_02`** (that's the game's own TU forge).
- **DRM:** Denuvo on the exe only; **no EAC/BattlEye**; single-player.

---

## 2. 🔑 THE ANVIL DEPLOY LAW (the new knowledge — this is what was missing)

Learned the hard way on v50; these are engine-level rules and almost certainly hold on
v42. **Every one of these was a black screen / hang until fixed:**

1. **`CFD0@10 == @4 + 51` — buffer MUST equal object.** A resource = `CFD0` (a 20-byte
   descriptor whose `u32 @10` = CFD1's decoded size) + `CFD1` (the object). The object's
   own header has **`u32 @4` = object size = `len(CFD1_decoded) - 51`**. If the
   decompressed CFD1 buffer is even one byte LARGER than the object (i.e. any trailing
   pad), the game hangs at menu load or black-screens. **Never pad the buffer.**
2. **The forge must stay FULLY CONTIGUOUS** — `off[n] + size[n] == off[n+1]` for every
   record. A gap (from shrinking a record's `size`) **black-screens at boot** (the loader
   streams the forge contiguously / DirectStorage). Verify with `acs_forge.invariant()`.
3. **Native block count** — no extra raw "pad" block. Blocks are `262144`-byte splits of
   the decoded data.
4. **On ANY content-length change, re-derive all three length fields:**
   `CFD0@10` (CFD1 decoded size) · `CFD1@4` (object size = decoded−51) · the payload's own
   length field. A stale one = "warning window + crash".
5. **⛔ CORRECTED (this was THE crash) — the Oodle COMPRESSOR is the suspect.** `byte0 =
   0x8C` is identical for EVERY Oodle LZ compressor — it only says "Oodle LZ" — so the
   "lead byte matches → not a suspect" reasoning was true but meaningless. **The real codec
   is `byte1 & 0x7F` = decoder_type. The game = 10 (Mermaid, `OodleLZ_Compressor 9`); we
   were writing Kraken (6).** A Kraken block this engine will not decode → crash at menu
   read. **Fix: compress with Mermaid (9); Mermaid@7 reproduces the game's blocks
   BYTE-IDENTICALLY.** (The 7-byte cinfo's byte[2] is the DECODER family field on read; on
   write, preserve cinfo verbatim and pass `compressor=9` to `OodleLZ_Compress`.) Done in
   `tools/acs_cfd.py`.
6. **⛔ CORRECTED — no forge re-pack is needed; there was never real headroom.** The
   "~5% smaller" was Kraken simply compressing harder than Mermaid — a symptom of the wrong
   compressor (rule 5), NOT a property to design around. With Mermaid, a natural re-encode
   lands on the vanilla size; `work/acs_loc_deploy.py` `exact_fill` closes any residual
   sub-byte gap with incompressible filler so the resource fills the slot EXACTLY (zero
   pad, forge stays contiguous) — an in-place ~KB write, no 20.7 GB rewrite. The
   `repack_patch.py` re-pack (below) is kept only as a fallback for a resource that GROWS
   past its slot (e.g. font-atlas injection may need it). Layout is
   `[header][resource data][TOC][footer of zeros]`; footer has no offsets, header has no
   file-size field. **Reference: `games/acblackflag-resynced/work/repack_patch.py`** (v50; v42 =
   20-byte records).
7. **TOC record fields:** `ts` = the resource's **fileID** (== `CFD0@2`), **not** a content
   hash. `nameHash` = the resource **type/class** hash (shared by all resources of a type),
   not a unique name. So there is **no content checksum in the TOC to update**.
8. **Patch forges OVERRIDE base forges** (by fileID). Always deploy to the forge the game
   **actually loads** — find the right record by decoding candidates and checking content.
9. **A game update rewrites the patch forges** → the mod must be re-applied after every
   update (and the correct record index may move).
10. **Always work game-CLOSED** (the forge is locked while it runs) and keep a backup.

---

## 3. THE PLAN

### Phase 0 — Baseline + IDENTITY PROOF (the decisive gate)  ⬅ START HERE

**Goal:** prove the game accepts a resource we re-encoded + re-packed. Nothing else
matters until this passes.

1. **Baseline:** `python tools/acs_set_language.py --arabic`, user launches → confirm the
   menu is Arabic + the game is healthy. (Already passed once; re-confirm post-any-update.)
2. **Find the loaded text resource.** Parse `DataPC_boot_patch_01.forge` (and boot.forge);
   locate the resource holding *visible menu* strings. Prior work: `acs_repack.py` targeted
   **idx 40549** (bare-UI strings) — re-locate it (indices move after updates) by decoding
   candidates and grepping for a known menu string.
3. **IDENTITY test:** decode that resource, re-encode it **naturally** (unchanged content,
   our Oodle, no pad, `CFD0@10==@4+51`), **re-pack the forge for contiguity** (port of
   `repack_patch.py`), deploy, user launches.
   - ✅ **Boots with Arabic** → the whole read→re-encode→re-pack→load chain is PROVEN. Go to Phase 1.
   - ❌ Black screen → run the Black Flag diagnostic ladder (§4). But the Nexus mod scene
     says this should pass.

### Phase 1 — MENU PROOF (closes bidi + font + mount in one screenshot)

4. Patch a handful of **visible menu strings** to Hebrew + one **Latin marker**
   (`ZZ-ACS-OK-ZZ`, proves mount independent of font/bidi). Deploy → user screenshots.
5. **Determine bidi mode from the shot.** Shadows renders shipped Arabic with correct
   engine-native RTL ⇒ the prior is **LOGICAL** (store natural Hebrew, zero bidi code).
   **But do not assume** — ship a MIX in the proof: some strings **LOGICAL**, some
   **VISUAL** (pre-reversed). Whichever reads correctly wins.
   (Reference: Hogwarts/Until Dawn landed LOGICAL; TLOU/GoT/007 landed VISUAL.)
   Reusable visual transform: `games/tlou1/work/tlou_rtl.py` `to_visual`.
6. Confirm: no tofu (font already has Hebrew → expected clean), correct order, numbers +
   Latin islands + tokens intact.

### Phase 2 — Locate the ARABIC text (the one real open question)

7. **The open gate:** the dialogue resources carry the **English** text inline. The game
   *does* render Arabic (Stage 0), so Arabic text exists — but **where** is unconfirmed:
   the same resource (a per-language variant) or a separate per-language resource/forge.
   Tools already written for this hunt: `tools/acs_find_ar.py`, `tools/acs_arscan.py`,
   `tools/acs_find.py`.
8. Decide the slot:
   - **If a per-language Arabic text resource exists** → write Hebrew into the **Arabic
     slot** (the clean hijack; user picks العربية; English VO preserved).
   - **If text is English-inline only with a runtime language switch** → hijack the slot the
     game reads for `ar-AE`.
9. Confirm the **lineID ↔ language** mapping so Hebrew can be keyed by `lineID`
   (cross-language stable, per the Oasis record format).

### Phase 3 — Translation (DELEGATE — Claude never translates)

10. **The corpus is already live**: `/translate` pool `ac-shadows` = **15,997 rows**.
11. Delegate per **[[delegate-all-translation]]** — Claude builds tooling + the agent
    handoff + verifies; the fleet/agents translate. Template:
    `universal/AGENT_TRANSLATION_HANDOFF_TEMPLATE.md`.
12. **Gender**: per **[[gender-oracle-from-game-langs]]** — Shadows ships Arabic; Arabic ≈
    Hebrew (أنتَ/أنتِ = אתה/את). Attach the game's own Arabic per lineID as the gender
    oracle (`universal/gender_oracle.py`, `ar_addressee_strict`). Cross-check with
    Russian (speaker) / Spanish-French-Italian (referent) if present.
13. **Names**: per **[[name-registry-and-internet-check]]** — build the canonical Hebrew
    name registry (Naoe, Yasuke, …), web-verify real Hebrew spellings, enforce in every
    line, verify with a consistency pass.
14. Preserve tokens verbatim (`[TOKEN]`, `{VALUE}`, `%d`, markup) — the auto-QA gate.

### Phase 4 — Build → Deploy → Publish

15. Build: write Hebrew (LOGICAL or VISUAL per Phase 1) into the located slot with
    `acs_loc_edit`/`acs_oasis` + `acs_cfd.build_cfd`, honoring **every rule in §2**.
16. Deploy: the v42 re-pack (contiguity preserved), backup first, game CLOSED.
17. User verifies in-game. Then **publish ONLY on an explicit "פרסם"** — GitHub release repo
    + Worker slug + Supabase `games` row (`ac-shadows`) + `mod_version_history`, exactly like
    SM2/WD2/Anno/GoWR. Re-apply after each Ubisoft update (rule 9).

---

## 4. If the identity proof fails — the diagnostic ladder (from Black Flag)

Run in this order; each isolates ONE variable (all learned empirically):
1. **Is the clean forge fine?** Restore + launch → Arabic. (Baseline; never skip.)
2. **Gap?** `acs_forge.invariant()` must be N/N. A gap → black screen at boot.
3. **Pad?** `CFD0@10` must == `@4+51`. Any trailing buffer → hang/black screen.
4. **Stale length field?** `CFD0@10` / `CFD1@4` / payload length all re-derived.
5. **Block count / cinfo** natural + verbatim.
6. **Oodle**: compare your block's lead byte to the game's (must be `0x8C`); try
   `oo2core_5` (2.5) as an older-stream cross-check.
7. **Only if a byte-perfect natural resource + full contiguity still fails** → suspect
   integrity (as in v50). Compare exe `SHA256`/`tamper` counts to Black Flag's 143/11 —
   Shadows' 11/3 says this should NOT happen here.

---

## 5. Tool inventory (`games/acshadows/tools/`)

| Tool | Role |
|---|---|
| `acs_forge.py` | v42 forge TOC reader (list/extract/verify + `invariant()`) |
| `acs_cfd.py` | CFD decode+encode (round-trip byte-identical; adler32(comp,0)) |
| `acs_oodle.py` | ctypes Oodle (BF6 `oo2core_9` 2.9.12; RDR2 `oo2core_5` 2.5) |
| `acs_oasis.py` | Oasis `0xFADE9F44` line records (scan/dump/extract) |
| `acs_locpkg.py` | (char-index decoder — **not used**, Shadows is literal UTF-16) |
| `acs_repack.py` | in-place same-size repack (idx 40549 bare-UI) — the only demonstrated write |
| `acs_identity.py` | identity round-trip helper |
| `acs_loc_edit.py` | loc edit helper |
| `acs_find*.py`, `acs_arscan.py` | Arabic/text hunting (Phase 2) |
| `acs_set_language.py` | `ACShadows.ini` `[Language]` flip (+ backup) — `--arabic` |
| `acs_capture.py` | game-window screenshot (works; not exclusive-fullscreen) |
| `acs_build_ct.py` | build the `/translate` upload |

**Port from Black Flag (`games/acblackflag-resynced/work/`):** `repack_patch.py` (the contiguity-
preserving re-pack — adapt v50's 24-byte records → v42's 20-byte records).

---

## 6. Standing rules

- **Claude never translates game text** ([[delegate-all-translation]]) — build tooling +
  handoff + verify only. **Never trust an agent's "done"** — always sweep independently.
- **Publish only on an explicit "פרסם"** — local build/deploy is fine, publishing is gated.
- **Never touch game files without a backup**; game must be CLOSED to write a forge.
- **Do NOT attempt to defeat anti-tamper / DRM.** (Not needed here — Shadows has no forge
  integrity check. If one ever appears, stop, exactly as with Black Flag Resynced.)
- Report in Hebrew; keep paths/identifiers Latin.

## מסמכים קשורים
- באותה תיקייה: [[games/acshadows/FEASIBILITY|FEASIBILITY]], [[games/acshadows/FORMAT|FORMAT]], [[games/acshadows/PIPELINE|PIPELINE]], [[games/acshadows/RECON|RECON]], [[games/acshadows/RESEARCH_FONT|RESEARCH_FONT]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#acshadows|CLAUDE_INDEX_games]]
