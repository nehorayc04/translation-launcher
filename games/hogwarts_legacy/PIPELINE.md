# Hogwarts Legacy — Hebrew — PIPELINE (how to build + deploy, once translated)

## Tools

| Tool | What | Where |
|---|---|---|
| `work/hl_bin.py` | Pure-Python codec for `MAIN/SUB-<locale>.bin` ("AVAFDICT 2.0") — `decode(bytes) -> dict`, `encode(dict) -> bytes` | this repo |
| `repak.exe` | Rust CLI to read/write the game's legacy `.pak` containers (v11, no AES) | downloaded from `github.com/trumank/repak` releases (v0.2.3, MIT/Apache, SHA-256-verified) — re-download and place under `work/tools/repak.exe` for a durable copy (currently only in the session scratchpad) |
| `work/build_menu_proof.py` | Builds + deploys/reverts a small test override pak | this repo |

## End-to-end build (once EN→HE translation exists)

1. **Extract fresh EN + AR** straight from the live game (never trust a stale export):
   ```
   repak.exe unpack "<game>\Phoenix\Content\Paks\pakchunk0-WindowsNoEditor.pak" -o extract\ -f ^
     -i "Phoenix/Content/Localization/WIN64/MAIN-enUS.bin" ^
     -i "Phoenix/Content/Localization/WIN64/SUB-enUS.bin" ^
     -i "Phoenix/Content/Localization/WIN64/MAIN-arAE.bin" ^
     -i "Phoenix/Content/Localization/WIN64/SUB-arAE.bin"
   ```
2. **Decode** both English files and the Arabic skeleton with `hl_bin.decode()`.
3. **Scope = EN ∩ AR** (per the universal playbook rule) — 18,889 MAIN keys + 34,955 SUB keys.
   The extra 4,729 AR-only SUB keys are NOT in scope (no English source to translate from).
4. **Translate EN → Hebrew** (delegated to a second agent/local LM per the
   `delegate-all-translation` standing rule — Claude only builds tooling), preserving verbatim:
   `{0}`/`{1}` brace tokens, `<img src="..."/>` tags, `[LT icon]`/`[...]` bracket tokens, and real
   embedded newlines in multi-paragraph notes. Store the Hebrew **LOGICAL** (natural reading
   order) — **CONFIRMED by the in-game menu proof 2026-07-04**: the engine's native ICU bidi
   reorders logical Hebrew correctly, so **no visual pre-reversal, no RLM anchors** (the opposite
   of the WD2-menu/Anno1800/AC2 class). This flag is settled; build LOGICAL.
5. **Merge into the Arabic skeleton by key**: `arabic_main[key] = hebrew_translation`,
   `arabic_sub[key] = hebrew_translation` — never invent new keys, never drop the AR-only extras
   (leave them as-is, untouched, since they're outside our EN∩AR scope).
6. **Encode**: `hl_bin.encode(patched_dict)` → new `MAIN-arAE.bin` / `SUB-arAE.bin` bytes. No
   size-matching needed — this format has no fixed-size sections or downstream offset streams to
   break (unlike GoWR/SM2/WD2/AC-family); a fresh encode is always safe.
7. **Pack** into an override chunk (pick an unused ID, e.g. keep using `111`, or check
   `Phoenix\Content\Paks\~mods\` for collisions with any other installed mod first — a
   "PakChunk Checker" utility exists on Nexus for exactly this):
   ```
   repak.exe pack <staged_dir> pakchunk111-WindowsNoEditor_P.pak --version V11
   ```
   `<staged_dir>` must contain `Phoenix/Content/Localization/WIN64/{MAIN,SUB}-arAE.bin` at the
   right relative path (mount point `../../../`).
8. **Deploy**: copy to `Phoenix\Content\Paks\~mods\pakchunk111-WindowsNoEditor_P.pak`. Never edit
   `pakchunk0-WindowsNoEditor.pak` directly — the additive `~mods` override is what survives
   Steam/Epic/GOG "Verify Integrity of Game Files".
9. **Font — NO WORK NEEDED (confirmed by the menu proof 2026-07-04):** the vanilla Arabic-locale
   font already renders Hebrew cleanly (no tofu). Skip this step entirely — no Composite-Font
   uasset editing, no glyph injection. (Kept here only as a historical note in case a future game
   patch ever swaps the Arabic font for one without Hebrew coverage.)
10. **Activation**: in-game Settings → Select Language → Arabic (العربية). Audio Language is a
    separate setting — leave it on English/original if desired.

## Known unknowns for Phase 2 (do not assume, verify each)

- **Is `MAIN-arAE.bin`/`SUB-arAE.bin` the ONLY place the Arabic slot's text is read from**, or do
  quest/dialogue systems (the 2025 Creator Kit's "Mod Dialogue Data" hints at a
  Blueprint/quest-editor dialogue layer) pull from elsewhere at runtime for some subset of lines?
  The menu-proof only touches `MAIN`; a small `SUB` patch should be tried next to confirm the
  in-mission dialogue/subtitle path uses the same file+font.
- **Chunk-ID collision**: if the user later installs other Nexus mods that also claim chunk `111`,
  switch to a different unused ID (999 is commonly free) — check with the "PakChunk Checker" mod
  or just `repak list`/`info` on whatever else is in `~mods`.
- **Composite Font location**: not yet found. Will need either a broader `repak list | grep -i
  font` sweep of `pakchunk0` + the IoStore chunks (fonts may be IoStore-only, requiring an IoStore
  reader — `retoc`, per the modding-community research, is the confirmed tool for that side) or a
  targeted search once we know the exact UI widget/StringTable driving the Settings screen.
- **`repak`'s own caveats** (from its README): index-write can be non-deterministic on very large
  paks, and it doesn't support writing frozen/compressed/encrypted indices — irrelevant here since
  our override pak is tiny (2 files) and uncompressed/unencrypted, but worth knowing if the plan
  ever grows to repacking something bigger.

## 🔑 Phase-2 gender protocol — build NO gender debt (per `universal/GENDER_ORACLE_ROLLOUT.md` #3)

English drops gender/number → a Hebrew translation made from English GUESSES it. Hogwarts ships an
**official Arabic locale** (`arAE`), and Arabic ≈ Hebrew (أنتَ/أنتِ = אתה/את, gendered verbs), so the
game's OWN Arabic value for each key IS the gender oracle — no playing, no screenshots. The gender
source is prepared and attached BEFORE translation so the Hebrew is right from line 1.

- **Gender source built** — `work/build_gender_source.py` → `extract/gender_source.json`:
  `{string_key: {"ar": "<arabic value>", "hint": "נמען=נקבה|רבים|זכר"|""}}`, keyed by the SAME
  `MAIN:`/`SUB:` string_key as the community pool. **Every line carries the raw Arabic** (the real
  gender source a translator/agent reads); `hint` is filled only where the STRICT Arabic oracle is
  unambiguous (**58,573 rows; 4,691 auto-hint**).
- **Oracle = `universal/gender_oracle.py:ar_addressee_strict`** — HIGH-PRECISION only: the fem/masc
  **pronouns** أنتِ/أنتَ, the **vocalized** possessive/object suffix ـكِ/ـكَ (Hogwarts' Arabic IS
  partially vocalized), the **plural** أنتم/أنتن/أنتما, and a **curated 2nd-fem verb whitelist**
  (تريدين/تعرفين/…). It deliberately DROPS the generic `ت…ين` heuristic, which false-fires on the
  form-II masdar (تحسين), broken/sound plurals (تنانين=dragons), and verb+object suffixes
  (تسامحني=forgive-ME) — a wrong hint would CREATE the exact debt we prevent. Verified on real
  Hogwarts data (masdar/plural/name FPs all eliminated).
- **The live `/translate` pool is already gender-hinted** — `work/enrich_pool_gender.py` appended
  the derived hint to the `context` field of the **1,717** high-confidence pool lines (1,605 fem +
  69 pl + 43 masc), so a community contributor sees `… · נמען=נקבה` and writes את/מוכנה, not
  אתה/מוכן. (Targeted PATCH of `context` only — never touches `current_he`/`status`.) Re-run after a
  re-extract; it reconciles against live state (strips stale/FP hints, adds new).
- **⚠️ Player-gender variants** — Hogwarts has `-female`/`-male` (and `playerfemale_`/`playermale_`)
  key variants (like CP2077's femaleVariant/maleVariant): the game already SPLIT dialogue by player
  gender, and each variant's Arabic uses the right gender. Most `-female`/`-male` AR keys are AR-only
  (no EN counterpart → not in the pool); the base key that IS in the pool gets the hint from its own
  arAE value. When the Phase-2 build wires the final `.bin`, keep the variant keys distinct.
- **For an AGENT handoff** (instead of/besides the pool): attach `gender_source.json[sk].ar` (+`hint`)
  beside the English on every line — the agent reads gender from the Arabic. Same as tlou1's
  `agent_handoff/gender_source.json`.
- **END-OF-PHASE-2 QA** — `work/gender_qa.py [hebrew.json]` runs the oracle scan over the translated
  Hebrew (auto-detects the pool export or `agent_handoff/hebrew.json`), comparing `he_addressee`
  vs `ar_addressee_strict` per key → `gender_suspects.jsonl` (ranked, fem-Arabic-but-masc-Hebrew
  first = the systematic default-to-masc debt). Run on the LOGICAL Hebrew (Hogwarts stores LOGICAL —
  no visual bake to undo). Deterministic, REPORTS only; fix a flagged line by re-inflecting ONLY the
  gender morpheme (`universal/dualgender_inflect.py`), meaning untouched. Safety: backup + qa.lock +
  atomic + per-line guard (never trust an agent "done" — the oracle IS the QA).

## Version-sync surfaces (once published, mirrors every other game here)

GitHub release repo (`hogwartslegacy-hebrew-mods` or similar) + Cloudflare Worker manifest slug +
Supabase `games` row (id should exactly equal the launcher's detector key — `hogwarts-legacy` or
`hogwartslegacy`, to be decided when adding the launcher entry) + `mod_version_history`. Not set up
yet — this is Phase-3/publish work, well past groundwork.

## מסמכים קשורים
- באותה תיקייה: [[games/hogwarts_legacy/FEASIBILITY|FEASIBILITY]], [[games/hogwarts_legacy/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#hogwarts_legacy|CLAUDE_INDEX_games]]
