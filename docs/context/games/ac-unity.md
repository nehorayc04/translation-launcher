## Assassin's Creed Unity Hebrew — 🔴 NO-GO (font gate CLOSED). Text pipeline fully solved + proven; NO reachable font (2026-07-01 → 2026-07-20)

> **FINAL VERDICT (2026-07-20): AC Unity is NOT a feasible Hebrew target.** The container + loc codec +
> repack + deploy are 100% solved and PROVEN in-game — Hebrew reaches **both** the menu and the
> subtitles (confirmed by exact glyph counts: a 5+5+8-letter proof string rendered as 5+5+8 boxes).
> **But the glyphs are unreachable: every font source in the game was found and ruled out.** Game
> reverted to pristine (md5 == `.he_backup`). Keep this section for the reusable AnvilNext v27
> knowledge and to stop anyone re-attempting it.

New game scaffolded at `games/acunity/` (RECON.md / FEASIBILITY.md / PIPELINE.md + `tools/` + `work/`).
Phase-1 groundwork complete; **verdict 🟢 GO — "prove the repack, then run"** (strongest-positioned AC in
the repo). No game file modified (read-only recon + a working pure-Python reader). Memory
[[acunity-groundwork-go]].

- **Install:** `E:\Games\Assassin's Creed Unity` (Ubisoft Montreal, 2014, **AnvilNext 2.0**, Uplay/VMProtect,
  **no Denuvo**). exe `ACU.exe`; `game_detector`/launcher key would be `acunity` (== future Supabase games.id).
- **Engine/format — `.forge` scimitar v27** (between AC2 v25 and AC Shadows v42). **Container FULLY CRACKED +
  reader built** (`games/acunity/tools/acu_forge.py`, pure-Python, verified): header (magic + u32 ver@9 +
  i64 indexOff@13) → index@0x41a (u32 fileCount) → **20-byte record array** `[u64 dataOffset][u32 fileID]
  [u32 flags][u32 uncompressedSize]` at indexOff+0x70 → **fixed 192-byte descriptor table** (record-index @
  +0x20, plaintext 'T'-name @ +0x2b; `descriptor[k] → record[embedded_index]`). Resources = Anvil "DataFile"
  chunks (magic `0x57FBAA33` + `0x1004FA99`, same family as AC2/ACS). `acu_forge.py list|names|extract <Name>`
  extracts any resource by name (records carry names, unlike ACS's pure-hash TOC).
- **🟢 DECISIVE — AC Unity SHIPS AN ARABIC TEXT LOCALE** → the Arabic-slot hijack applies (unlike AC2).
  `DataPC.forge` name table has `TLocalizationPackage_Arabic` [rec 1593] + `_Arabic_Subtitles` [rec 1594,
  **204,002 B real**] + `_Arabic_EManual`, `Support/Readme/Arabic/` shipped, 24 text languages total. Arabic
  is a **text-only** MENA locale (no Arabic VO pack → English voice stays).
- **Text = `TLocalizationPackage_<Lang>` (+`_Subtitles`,`_EManual`), char-INDEX u16 serialization** (AC2-class:
  sorted unique-char dict + index strings; Arabic dict = the `U+0600–06FF` block), **STORED uncompressed**
  inside the DataFile chunks → **readable with no codec**. Extracted English UI (rec 1527, 345,123 B) +
  Arabic to `games/acunity/extract/`.
- **⚠️ WRINKLE — Arabic is subtitle-populated but UI-STUB** (`_Arabic` UI = 139-byte empty stub; Ubisoft
  shipped Arabic = subtitles + English menus). So: **subtitles → Hebrew in the Arabic subtitle slot; UI/menus
  → decide via the menu-proof**. ⚠️ **The menu-proof RESOLVED it (2026-07-20): menus are unreachable
  (`Menu Language` has no Arabic) — AC Unity is subtitles-only.** ⚠️ **bidi is PER-SURFACE, the old blanket
  "VISUAL for BOTH surfaces" is superseded:** the **LTR/English UI slot** gets no engine bidi → store
  **VISUAL** (`work/acu_rtl.py visual_line`); the **Arabic subtitle slot** is the game's real RTL locale →
  store **LOGICAL** (do not pre-reverse). Confirm with the pending in-game subtitle check.
- **~~Font = `.ffd` + FTX/DDS atlas (WD2 model)~~ — ❌ WRONG, SUPERSEDED (2026-07-20).** There is no
  `.ffd`/FireFontDescriptor in AC Unity and AnvilToolkit has no font code at all. The game's ONLY fonts are
  **7 embedded TTFs in rec109** (all now Hebrew-injected), and the MENU is rendered by a font path that is
  none of them. See "FONT GATE — EXHAUSTIVELY SETTLED" below for the definitive answer.
- **Codec = LZO** (mode byte 0/1→lzo1x, 2→lzo2a, 5→lzo1c; stored when src==dst; no Oodle) — loc STORED so READ
  needs no codec. **Repack tools EXIST: AnvilToolkit** (free, Nexus, Unity-supported, XML loc export/import) +
  ACExplorer/pyUbiForge (Python read ref that VALIDATED the container struct). **A 2025 community English-loc
  mod ships a modified `DataPC.forge` the game loads → the repack chain is PROVEN achievable.**
- **Deploy:** repack-and-replace a forge (backup first); DRM = Uplay/VMProtect, no Denuvo, asset forges load
  when modded. Activation = in-game **Options → Subtitle → Arabic (العربية)** (voice/text independent) /
  `localization.lang` (ACU.ini has no `[Language]` key).
- **WRITE PATH — PURE-PYTHON REPACK BUILT + OFFLINE-VERIFIED, DIAGNOSTIC BUILD DEPLOYED (2026-07-01, awaiting
  in-game).** Decompiled AnvilToolkit → `c:\tmp\anvil_src\` (authoritative). Three tools now form a COMPLETE
  read→edit→repack→deploy chain, all pure Python (no GUI, launcher-bundle-able):
  - `work/acu_loc.py` — loc codec. English `.data` → **8,999 UI strings** (`extract/english_ui.json`);
    encode→decode **0 mismatches**.
  - `work/acu_build.py` — `.data` WRITER: splice the new BE char-index payload into CFD2 content, re-wrap as
    **STORED** blocks (per-block CRC32 is **read-and-discarded** by the engine → never gates loading). Rebuilt
    loc is ~2× the shipped size (game used a multi-char/BPE fragment dict; we + AnvilToolkit use single-char)
    → resource grows → relocate. Identity rebuild round-trips 0 mismatches.
  - `work/acu_deploy.py` — forge write-back by **append-relocate** (NO 312 MB re-serialize): append blob at
    EOF + patch the 20-byte record (`off→EOF`, `size→len`) + the 192-byte descriptor's size copy at +0x00.
    **KEY proof:** record field-4 == on-disk size for 1619/1620 resources, records are offset-monotonic, and
    every resource is read by its OWN record (off+size) → relocating one to EOF leaves a harmless hole and
    breaks no neighbour. Auto-backup `<forge>.he_backup`; `--revert`. Patch order data→desc→record (record
    LAST) → an interrupted write always leaves the ORIGINAL loadable.
  - Layout: `.data` = CFD1(meta)+CFD2(content)+sig; content = [u32 id][i32 count][i32 namelen][name]
    [fileheader][skip1][ScimitarClass u64 ID + u32 Hash][i32 Type][u32 Language][12×0][u32 marker
    **0xD28389B5**][i32 count LE][BE payload]. Payload = u16 MaxIndexSize + u16 fragCount + frags[>HH char,0]
    + u16 tableCount + tables[>III firstID,headersOff,entriesOff] + entries + code stream.
  **DEPLOYED a diagnostic build to the LIVE `E:\Games\...\DataPC.forge`** (backed up + reversible): edited
  `TLocalizationPackage_English` (rec1527 — the slot English reads) with Latin markers ("HE-PIPELINE-OK",
  "PIPE-OK-123" = font-independent, prove repack+encode+load) + pure-Hebrew VISUAL ("אפשרויות/חזור/כתוביות")
  + mixed. Re-read the live forge: rec1527 → 8,999 strings + all 7 edits; French/German/Subtitles still decode.

- **✅✅ TEXT PIPELINE PROVEN IN-GAME (2026-07-01) — game boots to the main menu, edited text renders.** The two
  earlier boot-hangs were NOT relocation — a stale **`content[4]` = field2** (a size field = `len(content) - 40`,
  the data-region-after-the-container-header) that wasn't updated when the payload length changed. Fixed → game
  BOOTS. Gates 1/2/3 CLOSED. The WORKING build path: minimal-rebuild loc payload (reuse orig BPE codes + re-encode
  edits, `work/acu_minbuild.py`) → **patch content[4]=len(newcontent)-40** → LZO-compress the CFD → overwrite
  IN-PLACE (delta-0). Ubisoft Connect did NOT demand a key / block the swap on a normal launch (integrity gate
  cleared for a normal launch). **TWO `.data` size fields must both be updated on any edit: the loc payload count
  (at P) AND field2 (at content[4]).** For a resource that GROWS, use **`work/cfd_partial.py`** (keep every
  original compressed LZO block verbatim, recompress ONLY the blocks overlapping the change) so the result fits
  the on-disk slot — a full re-LZO with `lzallright` runs ~2% bigger than the game's liblzo2 and won't fit.
### 🔴🔴 AC Unity FONT GATE — EXHAUSTIVELY SETTLED (2026-07-20): menus are UNREACHABLE, subtitles are the target

A full session of adversarial investigation closed this. **The earlier "the menu font is a Scaleform
DefineFont — go find the GFx resource" note was WRONG and is superseded.** The real answer is
structural, not a missing artifact.

- **🔑 THE DECIDING FACT — AC Unity has TWO SEPARATE language settings, and only ONE offers Arabic**
  (seen in-game, user screenshots):
  - **`Menu Language`** (UI/menus) — **LTR locales ONLY, there is NO Arabic option.** So the menu is
    *always* rendered by the Latin font path ⇒ **Hebrew in menus can never render — it is not a font
    bug, it is a missing locale.** (`Menu Language` also warns "restart the game to fully apply".)
  - **`Subtitles language`** — **HAS Arabic.** Subtitles are rendered by the Arabic-capable font path.
  ⇒ **AC Unity is a SUBTITLES-ONLY Hebrew target**, exactly like WD2's english-locked frontend.
  **UNIVERSAL: when a game exposes separate UI-language and subtitle-language settings, check WHICH ONE
  offers an RTL locale BEFORE doing any font work — that one menu decides whether menus are reachable
  at all, and it can invalidate weeks of font reverse-engineering.**
- **✅ The whole game contains exactly SEVEN embedded fonts, and they are ALL now Hebrew-capable.**
  `rec109 "TGame Bootstrap Settings"` (113 MB decompressed) holds: **News Gothic / News Gothic Bold /
  News Gothic Cond, DFHeiMedium-B5, AbstergoSansJP, AbstergoSansKO, Shilia 330 Light** — cmap-verified
  0/27 Hebrew originally. `work/build_diag_allfonts.py` subsets each to Latin+punct, merges
  U+05D0–05EA via `anno_font._add_hebrew`, pads to its slot (delta-0), partial re-LZO → **all 7 at
  heb 27/27 + latin 26/26, with REAL outlines** (verified on the LIVE forge: `contours=1`, proper
  bbox + advance, not empty glyphs).
- **🔴 AND THE MENU STILL RENDERED 8 TOFU BOXES for the 8-letter "אפשרויות".** Text reaches the menu
  (8 chars → 8 boxes) and Latin renders fine ⇒ **the menu font is not any embedded TTF.**
  **UNIVERSAL: a font injection that verifies perfectly offline (cmap + real outlines + live re-read of
  the deployed archive) and still renders tofu is PROOF the renderer uses a different font — trust the
  in-game pixel over the file, and stop iterating on that font.**
- **⛔ There is NO Scaleform artifact to find — searched exhaustively, do NOT re-chase.** Scanned
  **all 50 non-GI forges** (incl. `DataPC_ACU_Paris.forge`, 24,677 resources) decompressing every
  resource: **0 additional embedded fonts, 0 FireData resources, 0 valid SWF/GFX** (`FWS/CWS/ZWS/GFX/
  CFX` and the FireData-obfuscated `UEF`). **All tools promoted to `games/acunity/work/`**:
  `scan_all_forge.py` (unified per-forge font/SWF scanner) · `carve_fonts.py` (fontTools-validated
  sfnt carver) · `scan_fd2.py` (fast FireData peek) · `find_scaleform.py` · `tally_types.py`
  (class histogram) · `classreg.json` (hash→class registry mined from the AnvilToolkit decompile) ·
  `build_diag_allfonts.py` (inject Hebrew into all 7 fonts, delta-0) · `build_arabic_ui.py` ·
  `build_arabic_subs.py` · `cfd_partial.py`. **Run them with the repo `.venv` python.**
  - **`FireData` = AnvilToolkit's SWF class, hash `2940455555`** — it stores an **uncompressed SWF whose
    `FWS` magic is obfuscated to `UEF`** on disk (`FireData.Read` flips U,E,F→F,W,S). Useful for other
    AC titles; **AC Unity ships ZERO FireData resources.**
    **UNIVERSAL: a tool's "SupportedGames" list is NOT evidence the artifact exists — AnvilToolkit lists
    Unity under FireData, yet the game has none.**
  - **AnvilToolkit has NO font classes at all** (no FireFont/FontDescriptor/`.ffd`/glyph code) — so both
    the old `.ffd`+DDS guess AND the Scaleform-DefineFont guess are dead ends.
  - **⛔ AC2's SOLVED mechanism does NOT transfer (checked 2026-07-20, on the user's suggestion).** AC2
    (same Anvil family, v25) renders its UI from a **named DDS atlas** `AC2Aaux_ProLight_Latin_1_MapDesc`
    in `DataPC_extra.forge` (see the AC2 section — solved + rendering in-game). **AC Unity has NO
    `Aaux` / `CharacterSet` / `_Latin_` resource in any forge**, and a sweep of ALL 50 forges for any
    resource with "font" in its name returns exactly TWO, neither of them the UI font:
    `TDBG_FontTexture_Map` (DataPC — the DEBUG font, a 144-byte *descriptor* for a 2048×2048 texture
    whose pixels live in a separate resource) and `TGEN_ALL_StreetName_Font` (in-world street signage).
    ⇒ AnvilNext 2.0 replaced AC2's atlas scheme, and **AC Unity's UI font is not reachable as a named
    resource**. **UNIVERSAL: "same engine family" does NOT mean "same font mechanism" — a 5-year gap
    (2009 v25 → 2014 v27) replaced it entirely; verify by name/format before assuming a solved sibling
    game's pipeline transfers.**
  - Resource class histogram (`tally_types.py`, via `content[0]` = ScimitarClass hash): DataPC = 1475
    TextureMap + 66 LocalizationPackage + 33 EntityBuilder…; TitleScreenFPP = 336 LODSelector…
- **⛔ THIRD AND FINAL ATTEMPT ALSO FAILED — the `Language` field does NOT drive font selection.**
  Hypothesis: since `Menu Language` offers no Arabic but the internal `Language` u32 (=20 for Arabic)
  might be what selects font+bidi, hijack a *menu-selectable* LTR language. Built
  `work/build_menu_hijack.py`: took `TLocalizationPackage_Czech`, wrote Hebrew into 6 main-menu ids in
  a **one-build multi-mode proof** (a pure-Latin marker + LOGICAL items + VISUAL items), patched
  `Language 0 → 20`, deployed. In-game with Menu Language = Čeština: the package **loaded**
  (`POKRAČOVAT` = Czech) and **my Hebrew edits reached the menu** — verified by exact glyph counts
  (8 boxes = the 8-char VISUAL string, 5 + 5 boxes = the two 5-char strings) — but they rendered as
  **boxes**, while the same font drew `Č` (Latin-Extended) fine. ⇒ **the menu font is fixed and has no
  Hebrew, regardless of the package's Language field.** Czech was then restored with a *targeted*
  re-deploy of the pristine resource (NOT `--revert`, which would have wiped the Hebrew fonts +
  subtitles). **⇒ AC Unity menus are CLOSED. Three independent approaches exhausted: (1) inject Hebrew
  into every embedded TTF, (2) find a Scaleform/atlas font, (3) trick the engine via the Language
  field.** Menus stay English/LTR by design; subtitles are the deliverable.
- **⚠️ FALSE LEADS that cost real time — do not repeat:** `TGFX_*` resources are **particle/effect
  TEXTURES**, not Scaleform GFx. `TACU`'s "BEP Rift Light" / "Acquire Sans" / "Reach Font" are
  **mission + lighting names** (`Rift_BEP_M010`, `BEP Ambiance Cloudy`, `Les_Fontaines`), NOT fonts.
  The `\x00\x01\x00\x00` sfnt magic matches enormous amounts of random binary — always validate the
  table directory and fontTools-load before believing a font hit. "Abstergo" strings inside rec109 live
  in the JP/KO fonts' own `name` tables ("Latin characters based on AbstergoSans"), not a font config.

### AC Unity loc-package + deploy facts learned this session (reusable)

- **Sub-file header:** `content[0]` = **ScimitarClass hash** (LocalizationPackage `1849465967`,
  FireData `2940455555`), `content[4]` = **field2** size, `content[8]` = namelen, then name,
  `fileheader`,`skip`,`ClassID u64`,`Hash u32`,`Type i32`,**`Language u32`**,12×0,
  **marker `0xD28389B5`**, `count i32`, BE payload.
- **🔑 The `Language` field is the u32 IMMEDIATELY BEFORE the `0xD28389B5` marker. Arabic = `20`,
  English = `0`.**
- **🔑 Locate the payload by the MARKER, never by a heuristic scan** — `acu_loc._payload_from_data`'s
  finder is fragile and mislocated the payload the moment the Language field changed (it locked onto a
  false `count`). Correct: `mk = content.find(pack("<I",0xD28389B5))`, `count = u32@mk+4`,
  `payload = content[mk+8 : mk+8+count]`.
- **Package inventory (DataPC.forge):** `_English` 345,123 B / **8,999** strings · `_Arabic` (UI) =
  **139-byte STUB** (count=0, empty — Ubisoft shipped Arabic as subtitles-only) · `_Arabic_Subtitles`
  204,002 B / **7,663 real Arabic strings**.
- **Embedded-font layout inside rec109:** `[u32 marker 0x70A6A7EC][u32 storedSize][sfnt…]` — **the
  authoritative slot size is the u32 at `off-4`**; a carve-computed sfnt end can be 1–2 bytes short.
- **🐛 `acu_minbuild.emit` had a real encoder bug (FIXED).** It used `elif e <= 4334` for the 2-byte
  high form, which overflows (`ValueError: byte must be in range(0,256)`) on a package with a large
  `maxIndex` — it only ever worked because the English package's maxIndex is small. Correct form:
  1 byte if `e < maxIndex`; else `v = e + indexMask`, `hi = v>>8`, use the 2-byte form **only when
  `maxIndex <= hi <= 254`**, otherwise the 255-escape 3-byte form (`pack(">h", e)`).
- **Deploy:** `acu_deploy.apply_inplace` (delta-0, blob ≤ slot, record+descriptor untouched) is the
  safest and is what the proven builds use; `acu_deploy.apply` (append-relocate) for anything that
  grows. **The game LOCKS `DataPC.forge` while running** → `PermissionError` on write; close it first
  (`taskkill /F /IM ACU.exe` — the user granted standing permission to auto-close the game).
- **State at handoff:** live `DataPC.forge` carries rec109 (7 Hebrew fonts), rec1527 (Hebrew VISUAL
  menu text), rec1593 (Hebrew Arabic-UI — **dead weight**, Menu Language can never be Arabic) and
  rec1594 (**all 7,663 Arabic subtitles replaced with the LOGICAL Hebrew proof string**, awaiting the
  user's in-game subtitle check). Pristine backup `DataPC.forge.he_backup`; revert:
  `python games/acunity/work/acu_deploy.py "<DataPC.forge>" --revert`.
- **🔴🔴 SUBTITLES FAILED TOO — the FINAL verdict is NO-GO.** Replaced all 7,663 Arabic subtitle strings
  with the LOGICAL Hebrew proof `עברית עובדת בכתוביות` (5+5+8 letters) and set Subtitles language =
  Arabic. In-game the subtitle rendered as **5 + 5 + 8 BOXES** — an exact structural match, so the
  Hebrew reached the subtitle renderer, but **the subtitle font has no Hebrew either**, even though
  Shilia (the game's only Arabic TTF) had been injected with Hebrew and verified live. ⇒ **AC Unity
  renders NO text through the embedded TTFs — not menus, not subtitles.**
- **⛔ EVERY font source ruled out (6 avenues, each with in-game or exhaustive-scan evidence):**
  (1) the 7 embedded TTFs — Hebrew injected + live-verified, no effect on EITHER surface;
  (2) Scaleform SWF/GFX/FireData — **0** across all 50 non-GI forges;
  (3) a named font atlas — a sweep of every forge for "font" yields only `TDBG_FontTexture_Map`
  (debug) and `TGEN_ALL_StreetName_Font` (world signage);
  (4) the `Language`-field hijack — loads, text arrives, still boxes;
  (5) loose font caches / user data — the game dir has only exe+DLLs+forges+audio `.pck`, and
  `Documents\Assassin's Creed Unity\` holds just `ACU.ini` + `GFXSettings.ACU.xml`;
  (6) **`ACU.exe` (30.9 MB) + all 8 DLLs — 0 embedded fonts** (the exe is VMProtect-packed, so the
  glyph source is either packed inside it or generated at runtime — unreachable statically).
- **STATE: game REVERTED to pristine** (`DataPC.forge` md5 == `.he_backup`). ⚠️ Set the in-game
  **Subtitles language back to English** (it was left on Arabic for the test).
- **What IS worth keeping:** the whole read→edit→repack→deploy chain for **AnvilNext v27** is solved
  and reusable for any future Anvil title — forge reader, char-index loc codec, the three size fields,
  LZO + `cfd_partial`, delta-0 in-place vs append-relocate, and the font/Scaleform scanners.
  **UNIVERSAL: a fully-proven text pipeline does NOT make a game translatable — the font is an
  independent gate, and a game can be ruled out by it after everything else works.**
  Memory [[acunity-groundwork-go]].

### ⚠️ Environment gotchas this session (cost real time — apply to EVERY game)

- **🔴 ALWAYS run the AC-Unity / forge tooling with the repo `.venv` python**
  (`Game translator/.venv/Scripts/python.exe`). The machine's base Python 3.13 has **no `lzallright`
  (LZO) and no `fontTools`** — and `acu_loc.cfd_decompress` swallows the failure inside the scanners'
  `try/except`, so **every scan silently returned "0 hits"**. That looked exactly like a real negative
  result and nearly produced a wrong conclusion.
  **UNIVERSAL: a silently-failing codec dependency turns every scan into a false negative — assert the
  decoder imports (and that a known-good resource decodes) BEFORE trusting any "nothing found".**
- **Windows paths in Bash: use FORWARD SLASHES.** `"$G\\$f"` mangles a backslash immediately followed
  by a variable (the var arrives literal, e.g. `…Unity$f`); `E:/Games/…` works everywhere.
- **Workflow `args` did not arrive as an array** → hardcode lists inside the workflow script.
- **🔴 Do NOT use a Workflow of LLM agents for pure Python/IO fan-out.** One agent per forge (50) got
  **server-side rate-limited: 40/50 failed** and burned ~2.5M subagent tokens for 10 scanned forges.
  The same sweep run as **parallel background Bash jobs** finished all forges with zero token cost.
  **UNIVERSAL: parallelize CPU/disk work with background shell jobs; reserve agents for work that
  genuinely needs reasoning.**


