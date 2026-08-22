# AC Origins — PIPELINE

**Run everything with the repo `.venv` python** — `fontTools` and `python-bidi` live there, and
a silently-missing codec turns every scan into a false "0 hits".
`"../../.venv/Scripts/python.exe"` from `games/acorigins/`.

## Tools (`tools/`) — all copied from `games/acodyssey/tools/` and retargeted

| file | role |
|---|---|
| `aor_forge.py` | scimitar **v28** reader (`info` / `list` / `extract`) |
| `aor_cfd.py` | CFD decode + encode, per-resource Oodle codec sniffing |
| `aor_scan.py` | locate resources by ScimitarClass hash (`hist` / `find` / `sweep`) |
| `aor_loc.py` | LocalizationPackage codec (`list` / `dump` / `stats`) + `rebuild()` |
| `aor_rtl.py` | `to_visual` (**the shipping transform, BOTH surfaces**) · `to_logical` (A/B only) · **`to_visual_wrapped`** = the Phase-2 subtitle path · `wrap_logical` · `text_em` · `BOX_EM_SUBTITLE = 23.66` · the Origins engine-token contract |
| `aor_font.py` | Hebrew injection into the 9 `FontFile` resources (`list` / `inject`) |
| `aor_deploy.py` | append-relocate `apply` / `inplace` / `verify` / `revert` |

## Work (`work/`)

| file | role |
|---|---|
| `scope_report.py` | the three counts, oracle parity, tokens, dedup safety → `extract/scope.txt` |
| `build_proof.py` | the Phase-1 proof: `--build` / `--deploy` / `--verify` / `--revert` |
| `validate_offline.py` | the whole deploy chain against a COPY, incl. byte-identical revert |
| `build_ct_strings.py` | the `/translate` pool upload — base + DLC, `ar/ru/pl` in `context` → `extract/ct_upload.json` |
| `_blobs/` | the 12 staged resource blobs (3 text + 9 fonts) |

## The order that worked

```bash
cd "games/acorigins"
P="../../.venv/Scripts/python.exe"

# 0. reuse check FIRST — the magic decides the whole workstream
head -c 16 "F:/Games/Assassin's Creed Origins/DataPC.forge" | xxd    # scimitar + v28

# 1. inventory + scope
$P tools/aor_loc.py "F:/Games/Assassin's Creed Origins/DataPC.forge" list
$P work/scope_report.py

# 2. fonts (writes 9 blobs into work/_blobs)
$P tools/aor_font.py "F:/Games/Assassin's Creed Origins/DataPC.forge" inject work/_blobs --all

# 3. build the text proof, then PROVE THE CHAIN ON A COPY before touching the game
$P work/build_proof.py --build
$P work/validate_offline.py            # -> VALIDATE PASS

# 4. deploy + read the LIVE forge back
$P work/build_proof.py --deploy
$P work/build_proof.py --verify        # -> VERIFY PASS

# revert
$P work/build_proof.py --revert
```

## Deploy contract

- Target **`DataPC.forge` only** for the base game. There is no `DataPC_patch_01.forge`, so
  nothing shadows the base loc. The DLC text lives in `DataPC_22_dlc_patch_01.forge`
  (`DLC22-30_*`, Arabic subs 62,884 B) and must be patched separately in Phase 2.
- **Append-relocate, never in-place** — the rebuilt payload is ~2× the shipped one.
- Two length fields must BOTH be re-derived on any content change: `obj_size` at `content[4]`
  and the payload `count` at `marker+4`. `aor_loc.Package.rebuild()` does both.
- The game must be CLOSED (it locks the forge). `upc.exe` / `UplayWebCore.exe` may keep a
  transient lock — retry.

## Traps this game hit (each cost a real run)

1. **🔴 `decode_payload` returns INT keys.** A str-keyed `update()` silently ADDS new ids and
   changes nothing; a str-keyed `get()` returns `None` and reads as a failed deploy. It bit
   three times here — the builder, the validator and `verify()` — exactly as
   [[json-roundtrip-hides-key-type]] warns. **Grep for the pattern; do not fix the first hit.**
   `_i()` in `build_proof.py` normalises.
2. **🔴 A verification predicate written against LOGICAL text fails on VISUAL data.** The
   `id%3==2` subtitle rows are stored pre-reversed, so the literal `אבגד` is not a substring —
   the validator reported 8,576/12,844 on a perfectly correct build. Match both forms.
3. **🔴 A menu id CARRIED ACROSS FROM A SIBLING GAME is usually wrong, and the failure looks
   like a dead deploy.** Round 1 patched Odyssey-shaped ids: `850446` is `STORE` (upper-case)
   while the menu draws `Store` = `1011737`; `1080069` is `Exit` while the menu draws
   `Quit to Desktop` = `1014351`; `456221` is `CREDITS`, **not a main-menu row at all**, so the
   mount marker never appeared. Five of six menu rows stayed English and only `Options` hit.
   **Resolve every id by looking its ENGLISH VALUE up in `extract/base_english.json`, and put
   the marker on a row you have CONFIRMED is on that screen.**
4. **🔴 A long store-VISUAL line is WRAPPED BY THE ENGINE IN STORAGE ORDER, so its LINE ORDER
   COMES OUT INVERTED.** Round 2's paragraph rendered bottom-up: `סימני פיסוק:` (the logical
   start) on the last line, `סוף!` on the first. Every character inside each line was correct —
   only the line order was wrong, which is why it survives a short-label proof and breaks the
   real corpus (§8b rule 4). **Measured: 34.3 % of subtitle rows are >60 chars.** The shipped
   Arabic pre-wraps only 11 of 12,844 rows because it never needs to (Arabic gets engine bidi).
   ⇒ Phase 2 pre-wraps with a real `\n` (the break the corpus already uses, 30 rows), budgeted
   in **Heebo font units, never character count** — the ruler now deployed measures that budget.
5. **🔴🔴 THE ENGINE EATS AN UNRECOGNISED `[...]` — so it can never be a proof marker.**
   Round 3's width ruler tagged each rung `[N] ‹body› [N]`; **not one bracket or digit reached
   the screen.** Verified from both sides (4,268 rows carry a `[N]` in the LIVE forge and
   `--verify` matched on it) ⇒ render-side fact, not a build bug: Origins parses `[...]` as a
   control-name substitution and renders an unknown name as NOTHING. **The trap: I picked `[N]`
   BECAUSE `aor_rtl` protects an all-digit bracket as an atomic token — but "my transform must
   not touch it" and "the engine claims it" are the SAME property from two sides.** Use a string
   the ENGINE has no meaning for (`W44` — plain Latin+digits). Phase-2 corollary: a prose
   bracket left in a form the engine does not know is **deleted, not shown**, which is why the
   shipped Arabic is the per-bracket oracle.
6. **⚠️ The IDE analyser flags `aor_*` / `bidi.algorithm` as unresolved** — it is pointed at the
   base interpreter; the `sys.path.insert` resolves them at runtime under the `.venv`. Ignore.
7. **⚠️ Windows file locks** on the scratch copy after a `Forge` read — drop the readers and
   swallow the `OSError` in cleanup.
8. **⚠️ `apply()` journals with `setdefault`, so a RE-deploy is safe but WASTEFUL** — the
   pristine record values and `_filesize` survive (revert stays byte-identical), but each round
   appends another ~13.7 MB of now-dead blobs. **`--revert` first, then `--deploy`.**

## Phase 2 checklist

- [x] **UI surface locked (round 1): bidi = VISUAL, candidate A wins, font renders zero tofu**
- [x] **subtitle surface locked (round 2): bidi = VISUAL** — proven per surface by the A/B pair
- [x] **subtitle box MEASURED (round 4): 23.66 em** — W48 fit, W54 broke at 40 not 50 chars,
      so box ∈ [23.66, 24.35). Ship the lower bound; ≈ 46 Hebrew chars.
- [x] **pre-wrapper BUILT** — `aor_rtl.to_visual_wrapped` (+ `text_em`, `wrap_logical`,
      `BOX_EM_SUBTITLE`). Validated on all 14,782 rows: 0 words lost, 0 lines over budget,
      0 token changes. 40.4 % of rows wrap. **Use it for every subtitle in Phase 2.**
- [x] **candidate B TESTED + CLOSED** — the game reverts `Text=ar-AR` back to `en-US` on
      launch (its own validation writes a known-good value over an unsupported one; `Subtitles`
      is the only field with an Arabic option). Candidate A remains the sole, already-proven path.
- [x] **`/translate` pool LIVE, folding in the DLC — 28,537 rows** (`work/build_ct_strings.py`
      + `universal/community_translate.py import acorigins`). Ordered by VISIBILITY:
      **ממשק ותפריטים 11,094 → כתוביות עלילה 17,443**, `string_key` = `ui:<id>` / `subs:<id>`
      (0 id overlap between base and DLC — measured, no prefix needed), `context` = the
      game's own Arabic + Russian + Polish. Verified live via the public API (0 mismatch
      round-trip, both category chips with exact counts).
      **🔴 Found while building it: `DataPC_22_dlc_patch_01.forge`'s English package is named
      `DLC22-30_LocalizationPackage_English(US)` — the `(US)` suffix silently evaded
      `scope_report.py`'s `LANGS` lookup (keyed on the bare `"English"`), so the earlier
      "21,924 global-unique" headline was BASE-ONLY and undercounted the DLC's real
      ~2,868 UI + ~2,611 subtitle NEW lines by that much. Fixed by reading the exact
      package name instead of a language-suffix map.** True total = 28,537 (base 21,924 net
      of the 2 kinds' own dedup + dlc ~2,868/2,611 new, minus 114 token-only drops).
- [ ] delegate the 28,537 lines ([[delegate-all-translation]]); single pass, no fleet
- [ ] build → `validate_offline.py` → deploy → publish only on an explicit "פרסם"

## מסמכים קשורים
- באותה תיקייה: [[games/acorigins/FEASIBILITY|FEASIBILITY]], [[games/acorigins/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#acorigins|CLAUDE_INDEX_games]]
