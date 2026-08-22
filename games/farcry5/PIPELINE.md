# Far Cry 5 — PIPELINE

## Phase 1 (DONE) — the deployed menu proof

**Currently deployed to the live game.** Revert with:
```
cd games/farcry5/work
../../../.venv/Scripts/python.exe build_proof.py --revert
```

### What the user does
1. Launch Far Cry 5.
2. **Options → Language / Game language → Arabic (العربية)** (audio can stay English —
   the game keeps text and audio language separate).
3. Return to the **main menu** and screenshot it.

### How to read the screenshot — each row answers one gate

| menu row | shipped value | what it proves |
|---|---|---|
| **CONTINUE** | `ZZ-FC5-OK-ZZ` | **MOUNT.** Pure Latin, so it renders regardless of Hebrew coverage. If this is missing, the patched oasis never loaded and nothing else in the shot means anything. |
| **NEW GAME** | `שלום` stored **LOGICAL** | **BIDI A** |
| **LOAD GAME** | `םולש` stored **VISUAL** | **BIDI B** — exactly ONE of these two can read as `שלום`; that one is the mode. |
| **OPTIONS** | `אבגד` | **CONTROL** — 4 non-confusable letters, no final forms, so direction is readable even if a word looks ambiguous. |
| **QUIT** | all 27 letters | **FONT** — any box / `?` / blank marks the coverage gap. |
| **SETTINGS / RESUME** | the same sentence with punctuation, parens, digits and `Far Cry 5`, in both modes | **LAYOUT** — where neutrals and the Latin island land. |
| language menu → `Arabic` | `עברית` | the selector labels itself in Hebrew |

⚠️ Judge the Hebrew by **transcription, not by "does it look right"** — a screenshot's Hebrew
reads in *reading* order, which is exactly how earlier games produced contradictory readings.
The A/B pair plus the `אבגד` control is what makes one image decisive.

### Outcomes
* **Marker + readable Hebrew** → every gate closed; go straight to Phase 2.
* **Marker + tofu/`?`** → mount and bidi answered; the font is the only remaining work
  (see below).
* **No marker at all** → the engine is winning with a copy we did not patch. Both `common.fat`
  and `patch.fat` were patched; the next suspects are the extra un-named oasis blobs and
  `worlds/*.fat`.

---

## Phase 1.5 (only if the proof tofus) — the font

FC5 has **no raw TTF**. Route, in order of expected payoff:

1. **Treat it as the Watch Dogs 2 case.** Same Ubisoft Dunia lineage; WD2's font is `.ffd`
   metrics + `.xbt` (TBX + DXT5) **SDF** atlas, and `games/watchdogs2/work/wd2_font.py` already
   adds Hebrew to an Arabic atlas while keeping every original glyph pixel- and metric-identical.
   Locate FC5's atlas by scanning `.xbt` entries for a glyph sheet whose content is Arabic.
2. **Follow `FontDescriptor` / `DynamicFontContent`** in `FC_m64.dll` to the resource class hash,
   then pull every resource of that class out of the archives.
3. **NUKE-TEST to find which archive actually renders.** FC6's lesson: the same font can exist in
   several archives and only one is drawn. Blank a candidate and see whether the menu breaks —
   that pins the live copy in one launch.
4. Calibrate with the `hebrew-font-calibration` skill (measure from the user's own screenshot;
   never guess size/weight/alpha curve).

---

## Phase 2 — translation (delegated; Claude never translates the corpus)

**Corpus:** 25,095 unique English strings / 31,664 records / 2.32 M chars.
Single pass — **no fleet needed** at this size.

1. **Fold in the extra oases first.** `work/find_more_oasis.py` reports blobs beyond the 18 named
   files (52 in `common.fat`, 172 in `patch.fat`, 40 per story DLC). Extend
   `work/scope_full.py` to include them, then re-dump `extract/en_corpus.json`.
2. **Build the New-Era handoff.** All 8 other languages sit at **100 % key parity**, so each line
   ships with ar/fr/de/it/es/ru/br/ja beside the English — decide every line against the panel,
   never from the English alone. Arabic is the gender oracle (أنتَ/أنتِ ≈ אתה/את); attach the raw
   Arabic sentence per line rather than auto-deriving a hint from an open-class ending.
3. **Name registry first** (`name_registry.json`) — Hope County, Joseph Seed, the Deputy, Faith,
   John, Jacob, Dutch, Boomer… web-verify the canonical Hebrew spelling before translating, and
   enforce it at merge time so no variant can slip in.
4. **Order the community `/translate` pool by visibility**: ממשק ותפריטים (18,889) → כתוביות עלילה
   (12,775). `string_key` should be `ui:<sectionCRC>:<id>` / `subs:<sectionCRC>:<id>` so an
   approved line maps straight back onto the right oasis with no glue.
5. **Guard tokens**: `[STYLE_*]` / `[Quest_*]` (9,004 occurrences, 1,191 distinct), `{0}`,
   `{TX_PCButton_*}`, `%i/%d/%l/%u`, literal `\n`, `<br>`, `&#xA;` — multiset-validated on merge.

## Phase 3 — build & deploy

```python
from fc5_fat import Fat
from fc5_crc64 import name_hash
import fc5_oasis as O, fc5_deploy as D

# ALWAYS build from the pristine bytes, never from a deployed slot
raw = Fat(fat_path).read_data(entry)
new, applied = O.edit(raw, {(sectionCRC, id): hebrew, ...})
D.deploy_archive("patch.fat", {entry_hash: new})
```

Rules that must hold:
* **Patch every copy** — the oasis lives in `common.fat` *and* `patch.fat`, and patch wins.
* **Build from pristine** — a deployed slot must never be the input to the next build.
* **Store per the proof's verdict** (predicted VISUAL → `python-bidi get_display(base_dir="R")`
  with engine tokens stashed as atomic placeholders first, per the store-VISUAL rules).
* Deploy is append-relocate, scheme-0: original `.dat` bytes are never overwritten, only appended;
  the entry is repointed; `.he_backup` + `.he_journal.json` make revert exact.
* Record the deployed hash so a later game update cannot turn the backup into a downgrade.

## Phase 4 — publish (ONLY on an explicit "פרסם")

Standard 4-surface sync: GitHub release + Cloudflare Worker slug `farcry5-hebrew` + Supabase
`games` row `id=farcry5` + `mod_version_history`. Price per the ₪53 default. The launcher applier
is a native single-archive edit — the same shape as the GoWR applier.

---

## Quick reference

```bash
cd games/farcry5
../../.venv/Scripts/python.exe tools/fc5_oasis.py        # parse + identity round-trip, 9 langs
../../.venv/Scripts/python.exe tools/fc5_deploy.py --selftest
../../.venv/Scripts/python.exe tools/fc5_deploy.py --status
../../.venv/Scripts/python.exe work/scope_full.py        # corpus scope + oracle parity
../../.venv/Scripts/python.exe work/build_proof.py --deploy | --revert
```

Environment: repo `.venv` python (needs `lz4`, `fontTools`, `python-bidi`).
Override the install path with `FC5_GAME`.

## מסמכים קשורים
- באותה תיקייה: [[games/farcry5/FEASIBILITY|FEASIBILITY]], [[games/farcry5/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#farcry5|CLAUDE_INDEX_games]]
