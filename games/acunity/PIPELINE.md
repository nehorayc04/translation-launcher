# Assassin's Creed Unity — Hebrew translation PIPELINE

The build recipe + the order gates must close. Mirrors the project's universal playbook
(`universal/NEW_GAME_GROUNDWORK_PLAYBOOK.md`) adapted to AC Unity's `scimitar` v27 / char-index loc /
`.ffd`/DDS-atlas font / Arabic-slot facts (see `RECON.md`, `FEASIBILITY.md`, `BRIEF.md`).

> ⛓️ **Golden rule (do NOT skip):** build the whole `read → repack → deploy` chain on **identity
> round-trips** before touching translation. Prove one Hebrew string appears in-game (RTL, readable
> font, no crash) BEFORE translating tens of thousands of lines.

---

## Verified toolchain (built this session)

- `tools/acu_forge.py` — pure-Python **read-side** v27 forge reader. `list` / `names` /
  `extract <Name> <out>` / `extract-index <i> <out>`. Verified: extracts any resource by name from
  DataPC.forge (loc packages, etc.). **Read-only — never writes a forge.**
- `extract/loc_english.bin`, `extract/loc_arabic.bin` — extracted loc packages (char-index payload).

## The install + key resources

- Game: `E:\Games\Assassin's Creed Unity` (neutral install — deploy here, back up first). exe `ACU.exe`.
- Text: `DataPC.forge` → `TLocalizationPackage_<Lang>` [+`_Subtitles`, `_EManual`]. Records (verified):
  - `TLocalizationPackage_Arabic_Subtitles` = record 1594, 204,002 B  ← **Hebrew subtitle target**
  - `TLocalizationPackage_Arabic` (UI) = record 1593, 139 B (empty stub) ← UI decision (below)
  - `TLocalizationPackage_English` (UI) = record 1527, 345,123 B ← LTR-hijack fallback / structure ref
- Fonts: **`.ffd` (Fire_Font_Descriptor) + FTX/DDS atlas** — the WD2 model (FFD markers confirmed x41 in
  DataPC.forge, x25 in DataPC_patch_01.forge), NOT Scaleform. Inject Hebrew via FFDConverter + atlas.
- Activation: Uplay/Ubisoft Connect account language and/or root `localization.lang`; Arabic is text-only
  (no Arabic VO) → English voice stays. (Exact "force Arabic text" path = confirm in-game.)

---

## Gate-closing order (each gate blocks the next)

### Gate 1 — DataFile chunk codec = **LZO** (✅ resolved by research; see `BRIEF.md`)
The loc packages are **stored** → translation READ is already unblocked. The font/atlas resources are
compressed with **LZO** (CONFIRMED from ACExplorer `pyUbiForge/misc/decompress_.py`): a per-block mode
byte selects the variant — `0`/`1`→`lzo1x`, `2`→`lzo2a`, `5`→`lzo1c`; when `len(src)==dst_len` the block
is STORED. **No Oodle** (Unity predates it). Read with `python-lzo`/`liblzo2`; re-compress via
`lzo1x_1_compress`. Only needed for the font path (loc needs no codec at all).

### Gate 2 — Forge v27 REPACK (identity round-trip) — THE deploy gate
> ✅ **A free repacker EXISTS: AnvilToolkit** (Kamzik123, Nexus) — supports AC Unity, repacks `.forge`,
> and **exports/imports the `LocalizationPackage` as XML** (bypasses hand-rolling the char-index encode
> for v1). Also `ACExplorer`/`pyUbiForge` (Python) reads v27 forges + LZO. **The real residual risk is
> deploy-integrity: Ubisoft Connect can demand an activation key after overwriting `DataPC.forge`** →
> prefer a runtime Asset-Overrides loader (leaves the on-disk forge vanilla) OR test that a plain
> forge overwrite survives Connect's verify. For a launcher-bundle-able path, a pure-Python v27 writer
> + `liblzo2` is still wanted (AnvilToolkit is GUI-only .NET).
1. Copy a forge. Read a resource, **repack it UNCHANGED**, and confirm the game still boots identically
   **and Ubisoft Connect does not demand a key** — this Stage-0 identity round-trip is the single
   afternoon that decides the project (do it BEFORE bidi/font work).
2. Simplest first move (proven on AC2, `ac2_forge.Forge.write_resource`): **append-relocate** — write
   the (modified) resource to a fresh aligned slot at EOF and patch only its 20-byte record
   (`data_offset` + `uncompressed_size`); the 192-byte descriptor carries no offset/size, so only the
   record changes. If the engine tolerates trailing data + record redirection, this avoids a full rewrite.
3. If append-relocate fails, do a full container rewrite (record array + descriptor table are understood).
4. **Deterministic** builds (no timestamps/random order) so version-tracking + deploy-verify hold.
5. `delta` discipline: prefer size-preserving edits; if a resource must grow, the record's
   `uncompressed_size` + `data_offset` update covers it (unlike GoWR's multi-stream WTOC, v27 records are
   self-contained per resource).

### Gate 3 — Char-index loc decode/encode
Decode the u16 char-index payload of a LocalizationPackage: sorted unique-char dictionary + strings as
index sequences (control `0x8000`). Build `work/acu_loc.py` (read verified, write new):
decode → edit strings → **rebuild the char dictionary to include Hebrew `U+05D0–05EA`** → re-encode →
re-wrap as a DataFile chunk (stored) → put back via Gate 2. Round-trip an UNCHANGED package byte-for-byte
first, then a one-string change.

### Gate 4 — Hebrew font glyphs
Fonts = **`.ffd` (Fire_Font_Descriptor) + FTX/DDS atlas** (the WD2 model — FFD markers confirmed on-disk),
NOT Scaleform/embedded-TTF. The Arabic-rendering font's dictionary ≠ Hebrew → inject `U+05D0–05EA`: draw
Hebrew glyphs into the atlas (DDS) + add metrics/codepoints to the `.ffd` (WD2/AC2 family, `wd2_font.py`
as reference; the repo's **FFDConverter** handles `.ffd`, but it stops at AC Rogue so v27 `.ffd` may need
a version flag/adapt). Pick a font that fits the Belle-Époque Paris aesthetic; confirm with the user
(playbook §4.5). Watch the off-by-one glyph-table + Arabic-Indic-digit traps (playbook §4.3–4.4).

### Gate 5 — Menu-proof (bidi decision) + activation
Translate ONLY the first menu/settings screen strings; build; deploy; user launches with the game set to
Arabic text and confirms in-game: Hebrew? RTL correct? font readable + period-appropriate? no tofu / mirror
/ crash? **Default = VISUAL** — peer-reviewed research (Al-Batineh 2024) shows Unity-era AnvilNext had
**no engine RTL** (added only in Valhalla/Mirage); Unity's shipped Arabic looks right because order is
**pre-baked into the data**. So `visual_line`-reverse Hebrew (`work/acu_rtl.py`, AC2/WD2 method) for BOTH
surfaces, and confirm with the one-line proof (VISUAL correct + LOGICAL mirrored = VISUAL). Pair the
menu-proof with a **vanilla Arabic-slot check** (set text=Arabic on the untouched game → observe RTL) —
that answers bidi with zero repack risk. Activation = in-game **Options → Subtitle → Arabic (العربية)**;
voice/text independent (English VO stays).

### Gate 6 — Count report → Phase 2
Separate UI vs subtitle counts (extract EN∩AR keys per surface). Report to the user (playbook §7 format).
Then hand translation to an agent via `universal/AGENT_TRANSLATION_HANDOFF_TEMPLATE.md` (per
[[delegate-all-translation]] — Claude builds tooling + glossary + instructions; the agent/LM translates).

---

## work/ trio (templates copied from SM2; adapt after gates 1–5)

- `work/acu_translate.py` — EN→He translator (serial LM or agent handoff; token-budget batches;
  `validate()` + strike/park; atomic flush; AC-period glossary). Adapt the read/write to `acu_loc.py`.
- `work/acu_watchdog.py` — self-healing supervisor (kill-client→`unload --all`→probe→relaunch; hourly QA).
- `work/acu_progress.py` — 60 s push to `/api/admin/progress` with `gameId="acunity"` (== Supabase games.id).

## After the run — publish (like SM2/CP2077)

GitHub release repo (`hebrew-translation-hub/acunity-hebrew-mods`) + Worker slug `acunity-hebrew` +
Supabase `games` row (`id="acunity"`, matching `game_detector` key) + `mod_version_history`. Keep the four
version surfaces in lockstep (playbook §10).

## Detection (launcher)

Add to `game_detector`: `_PATTERNS["acunity"] += ["assassinscreedunity"]`, `_EXE_PATTERNS["acunity"] =
["ACU.exe"]`. Key **must equal** the Supabase `games.id` (`acunity`).

---

## Verified toolchain — WRITE path (built + offline-proven 2026-07-01)

- `work/acu_loc.py` — LocalizationPackage codec (decode+encode). English `.data` → 8,999 UI strings;
  encode→decode 0 mismatches. Char-index BE payload; single-char fragment dictionary.
- `work/acu_build.py` — loc `.data` **writer**: splices a new payload into CFD2 content, re-wraps as STORED
  CFD blocks (engine reads+DISCARDS per-block CRC → never gates loading). `--edits <json>`. Rebuilt loc ~2×
  the shipped size (game used a multi-char/BPE fragment dict; we use single-char, like AnvilToolkit) → the
  resource grows → relocate.
- `work/acu_deploy.py` — forge **write-back by append-relocate**: append blob at EOF + patch the 20-byte record
  (`off→EOF`, `size→len`) + the 192-byte descriptor's size copy at +0x00. Auto-backup `<forge>.he_backup`;
  `--revert`. Safe: record field-4 == on-disk size for 1619/1620 resources, every resource is read by its own
  record (off+size), so relocating one leaves a harmless hole and breaks no neighbour.

A diagnostic build (Latin markers + VISUAL Hebrew in `TLocalizationPackage_English`, rec1527) was deployed to
the live `DataPC.forge` and re-read correctly (edited resource + untouched neighbours all decode). **Only the
in-game load (Ubisoft Connect integrity) + the Hebrew font remain.**

## Open gates checklist (Phase-1 exit → Phase-2 entry)
- [x] Gate 1 — compressed-chunk codec identified = **LZO** (loc is STORED; write path uses stored blocks).
- [~] Gate 2 — forge repack **offline-proven** (append-relocate; live forge re-reads); **in-game load pending**.
- [x] Gate 3 — char-index loc decode **and encode** round-trip (0 mismatches; `acu_loc.py` + `acu_build.py`).
- [ ] Gate 4 — Hebrew glyphs render (font injection) — the diagnostic build will tell us if the shipped UI font
      already has Hebrew; if tofu, inject via `.ffd`+DDS (in-repo FFDConverter).
- [~] Gate 5 — menu-proof **deployed** to the live game (English slot); awaiting the user's in-game observation.
- [ ] Gate 6 — UI vs subtitle counts reported.

## מסמכים קשורים
- באותה תיקייה: [[games/acunity/BRIEF|BRIEF]], [[games/acunity/FEASIBILITY|FEASIBILITY]], [[games/acunity/RECON|RECON]], [[games/acunity/RESEARCH_FONT|RESEARCH_FONT]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#acunity|CLAUDE_INDEX_games]]
