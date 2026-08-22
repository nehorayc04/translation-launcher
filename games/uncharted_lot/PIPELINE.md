# UNCHARTED: Legacy of Thieves Collection — PIPELINE

Everything below runs with the repo `.venv` python and the game's own Oodle DLL:

```bash
cd "C:/Users/Nehoray_Cohen/Projects/Game translator"
export TLOU_OODLE_DLL="F:/Game Lab/UNCHARTED - Legacy of Thieves Collection/oo2core_9_win64.dll"
```

Paths:

```
GAME = F:\Game Lab\UNCHARTED - Legacy of Thieves Collection
TEXT = $GAME\Uncharted4_data\build\pc\{uncharted4,thelostlegacy}\text2.psarc   # identical, patch BOTH
FONT = $GAME\Uncharted4_data\data\fonts.psarc
LANG = $GAME\steam_settings\force_language.txt
```

---

## Read / write chain (all working today)

```python
import sys; sys.path.insert(0, "games/tlou1/tools"); sys.path.insert(0, "games/uncharted_lot/tools")
from psarc import Psarc            # reader        — reused unchanged
from psarc_write import repack     # writer        — reused unchanged
from oodle import Oodle            # game's own DLL
import unc_loc                     # NEW: ND string-table codec (8 B vs 16 B auto-detect)

p    = Psarc(TEXT)
eng  = p.extract([e for e in p.files() if e.path.endswith("eng.common")][0])
m    = unc_loc.to_map(eng)                     # {sid_hex: "English"}
new  = unc_loc.encode(eng, {sid: "עברית"})     # SURGICAL — original blob kept verbatim
repack(TEXT, {"<path in archive>": new}, OUT, Oodle())     # 0.1 s
```

`unc_loc` CLI: `detect | decode | dump | stats | selftest`.
**Always re-run `selftest` after touching the codec** — it asserts a byte-identical identity
re-encode, which is what protects against the ND "rebuilt blob renders scrambled" trap.

---

## STEP 0 — deploy mechanism (do this first, it is cheap)

Unknown: whether the engine reads **loose files** next to the archive (some ND PC ports do) or only
the `.psarc`. Test in this order:

1. Drop a modified `eng.common` as a loose file mirroring the archive's internal path. Launch.
2. If ignored → **repack** `text2.psarc` (proven, 0.1 s) and overwrite, keeping `.he_backup`.

Repack is already proven offline and is the assumed path. Patch **both** `uncharted4/` and
`thelostlegacy/` copies (byte-identical today; keep them so).

Back up before any write:
`text2.psarc → text2.psarc.he_backup`, `fonts.psarc → fonts.psarc.he_backup`.

---

## STEP 1 — the font injector (`work/unc_font.py`, to build)

Target: `main.fnt` + `main_00.tga` (and later the per-language variants).

* **Descriptor** — plain text. Append one `char id=<cp> x= y= width= height= xoffset= yoffset=
  xadvance= page=0 chnl=<1|2|4|8>` line per Hebrew letter (U+05D0–05EA, 27 glyphs). Update the
  `chars count=` line. Optionally raise `scaleW`/`scaleH` in the `common` line **only if the engine
  honours it** — verify, do not assume.
* **Atlas** — 32-bit RGBA TGA, uncompressed, type 2, top-down, 18-byte header + 26-byte footer.
  Write glyph coverage into the channel named by `chnl`. **Measured free space: the alpha channel
  (`chnl=8`) is 47.9 % used and rows 69→128 are entirely empty.** Pack there first.
* **Donor font** — a Hebrew face whose weight matches Adelon-Serial DB (a serif). Follow the
  measure-don't-guess rule: match the shipped glyphs' **ink density** (weight) and **mid-tone
  fraction** (softness) rather than eyeballing blur/bold ([[bitmap-font-size-is-engine-side]]).
* **Padding** — keep ≥ the atlas's own inter-glyph gap so mip/bilinear sampling cannot drag a
  neighbour's ink into a glyph cell (the dots bug seen on GoWR / Plague Tale / AC Shadows).

---

## STEP 2 — PROOF A: mount · surface · font · bidi, in ONE launch — ✅ **BUILT + DEPLOYED**

```
python games/uncharted_lot/work/build_menu_proof.py --deploy   # done 2026-07-24
python games/uncharted_lot/work/build_menu_proof.py --revert   # restores the 3 .he_backup
python games/uncharted_lot/work/build_menu_proof.py --verify   # re-reads the DEPLOYED archives
```

Deployed state: `fonts.psarc` (Hebrew injected into `main.fnt`/`main_00.tga`, atlas grown
256x128 -> 256x256, 27/27 glyphs) + both `text2.psarc` (26 sid overrides on `eng.common`).
Backups `*.he_backup` sit next to each. Language stays **english** — zero user action.

Offline validation before it touched the game: only the 3 intended entries differ (47 + 16
others byte-identical), exactly 26 sids changed with the sid set unchanged, the deployed
atlas re-renders `שלום` with correct shapes, and Latin `A` is untouched at its original box.

Original design notes follow.

One build, several distinct signals ([[one-build-multimode-menu-proof]]):

| what to patch | with | what it proves |
|---|---|---|
| a main-menu `eng.common` string | pure-Latin **`ZZ-UNC-OK-ZZ`** | the repack **mounts** — independent of fonts and bidi |
| 2 more menu strings | Hebrew **LOGICAL** / Hebrew **VISUAL** | which bidi mode the engine uses |
| 1–2 `eng.subtitles` lines | the same A/B pair | whether subtitles come from the same loc file |
| — inject Hebrew into **`main.fnt` only**, leave Iggy untouched — | | **which renderer draws what**: Hebrew in subtitles + tofu in menus ⇒ menus are Iggy; Hebrew in both ⇒ the atlas serves both |

**Read the result with a control string, never by judgement** — store the *same* word both ways on
two adjacent rows plus a 4-distinct-letter control (`אבגד`), and ask for a **transcription**, not an
opinion ([[hebrew-screenshot-transcription-trap]]). Avoid final-form letters in the control (`ם`
reads as `ס` at menu size).

Revert: restore `text2.psarc.he_backup` + `fonts.psarc.he_backup`.

---

## STEP 3 — PROOF B: is the dormant `ara` slot alive?

The high-value gamble (FEASIBILITY §"the decisive question"). Separate launch, because it changes
the selected language.

1. Add **`ara.common` + `ara.subtitles`** to `text2.psarc` — copies of the `eng.*` files with the
   same probe strings. (`psarc_write.repack` must be extended to ADD entries, not only replace;
   PSARC TOC is md5(path)-ordered, so insert in hash order.)
2. Add **`arabic.fnt` + `arabic_00.tga`** to `fonts.psarc` — clone `main.*`, renamed, Hebrew injected.
3. Append `arabic` to `steam_settings/supported_languages.txt`; set `force_language.txt` = `arabic`.
4. Launch.

| outcome | meaning | next |
|---|---|---|
| loads **and reorders** RTL | the PS4 Arabic path is alive | 🏆 store **LOGICAL**, no VISUAL bake |
| loads, no reordering | clean dedicated slot, no bidi | store **VISUAL** in `ara` |
| does not load / falls back | PC build has the enum but not the data path | drop it, hijack `eng` (or `rus`) |

---

## STEP 4 — translation (delegated)

Per [[delegate-all-translation]] — Claude builds tooling, never translates.

* Corpus: `extract/lang/eng.{common,subtitles,subtitles-systemic}` → **36,610 unique strings**.
* **New-Era panel is free**: 100 % sid parity across 23 languages, so every line ships with up to 22
  reference translations. Read them by strength ([[new-era-doctrine]]).
* **Gender oracle** (no Arabic to read, so use the game's own gendered locales,
  `universal/GENDER_ORACLE_ROLLOUT.md`): **rus / pol / cze** for speaker *and* addressee (past-tense
  agreement), **fre / ita / spa / sas / por / bra / gre** for referent gender. Attach the reference
  **sentence** per line; only auto-derive a hint from a **closed set**
  ([[gender-hint-needs-closed-set]]).
* **Name registry first** ([[name-registry-and-internet-check]]): Nathan Drake, Sully, Elena, Sam,
  Rafe, Chloe, Nadine, Asav, Hoysala — web-verify the canonical Hebrew spelling **before** the pass,
  enforce it at merge time.
* **Order by visibility** for the community pool and the agent handoff
  ([[community-pool-by-category]]): **ממשק ותפריטים** (5,261) → **כתוביות עלילה** (30,415) →
  **דיבורי רקע** (11,687).
* Tokens to preserve verbatim: `[A]` `[B]` `[TEXT]` `[TEXT2]` `[GAME]` and the other 57 brackets,
  the 8 printf specs, `\n`, `$H`, and the literal `\` line separator inside the long UI blocks.

---

## STEP 5 — build, deploy, publish

```
build  ->  unc_loc.encode (per file)  +  unc_font inject  ->  psarc_write.repack
deploy ->  overwrite text2.psarc (BOTH game folders) + fonts.psarc, keep .he_backup
verify ->  re-READ the deployed archives and assert the Hebrew is there  (never trust the builder)
```

Publish only on an explicit **"פרסם"** ([[local-install-launcher-builds]]):
GitHub release repo `uncharted-hebrew-mods` → Worker slug `uncharted-hebrew`
(`games/steam/steam_mod_worker/src/index.js` + `npx wrangler deploy`) → Supabase `games` row
`id=uncharted` + `mod_version_history`, price per [[mod-price-53-default]].
Manifest **must** use `archive_name` ([[mod-manifest-archive-name-contract]]).

A launcher applier would be a native single-archive swap (the GoWR pattern) with the backup held
**outside** the game folder, plus a `kind:"textfile"` language switch on `force_language.txt`.

---

## Open items entering Phase 2

1. **Which renderer draws subtitles vs menus** — Proof A answers it.
2. **bidi mode** — Proof A (LTR slot) and Proof B (`ara` slot).
3. **Is `ara` alive** — Proof B. Highest-value unknown in the project right now.
4. **Iggy font editing**, only if Proof A shows the menus need it.
5. `psarc_write` needs an **add-entry** path for Proof B (today it replaces existing entries only).
6. `sid-lookup` (3.8 MB) is not yet decoded — not needed for translation, but worth a look before
   the final build in case it gates anything.

## מסמכים קשורים
- באותה תיקייה: [[games/uncharted_lot/FEASIBILITY|FEASIBILITY]], [[games/uncharted_lot/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#uncharted_lot|CLAUDE_INDEX_games]]
