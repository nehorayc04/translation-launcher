# Watch Dogs 2 — Hebrew translation pipeline (TOOLING COMPLETE)

Status (2026-06-17): **GO, end-to-end proven in-game.** Every tool needed to ship a
Hebrew translation is built and validated. The only thing NOT done is the actual
EN→Hebrew translation of the text (by request). Hebrew text + Hebrew font glyphs render
correctly RTL in-game (proven with test markers).

## UI translation — ✅ COMPLETE + DEPLOYED (100%, 2026-06-19)

Full WD2 interface is Hebrew and live in-game: **19,419 strings translated + 96
left Latin (handles/codes/place names) = 19,515/19,515**, 0 missing, QA-clean.
The local-LM run reached ~95%; the **final tail (~338) was finished by an external
Google/Antigravity agent** via the self-contained handoff in
`games/watchdogs2/agent_handoff/` (`INSTRUCTIONS.md` + `to_translate.json` +
`hebrew.json` + `get_batch`/`loop_split`/`loop_merge`/`qa_scan` + `skip.json`).
The agent translated itself (no model), looped until `get_batch`="All done!",
parked untranslatables to `skip.json`. Deployed: `wd2_ui_merge.py
agent_handoff/hebrew.json` (visual) → `wd2_loc.py encode` → `wd2_archive.py deploy`
(3 archives, backups `F:\WD2_lang_backup`). The resumable history below is kept
for reference. **Remaining future task: the spoken subtitle lines (excluded by
request) + publish like SM2/CP2077.**

## UI translation — local-LM run history (2026-06-17→18)
Translating the game **interface** (NOT the audio subtitle lines, by request) on the
local LM, in parallel with the SM2 run.

- **Where the UI text lives — the key discovery.** The full string table is
  `main_english.loc` (48,138). The oasis XML
  (`extract/en_oasis/.../oasisstrings_converted.xml`) keys every string by `LineId`
  and tags it with an **`enum`**: audio subtitle = `enum="soundbinary\N.bnk"` (16,537);
  everything else has a **symbolic name** (`enum="Brightness"`, `"Quality Main Menu"`,
  `"InventoryWheel_ammo"`, `"actNavigate"`) = the 27,573 NAMED entries. **The UI is the
  NAMED set, NOT the "4,032 not-in-oasis" pool** an earlier pass used (that pool was
  mostly leaked cutscene dialogue). The section names (`CinemaSubtitles`/`BarkSubtitles`)
  are USELESS — the `enum` is the only discriminator.
- **The UI queue (17,917)** = NAMED entries minus: person names (`name_\d`, Surname,
  Occupation), media metadata (Song/Artist/Album/Manufacturer), car-paint codes,
  dev-junk, and comms text (Message/email/phone/TOR — closest to "lines", excluded).
  Kept: settings, HUD, objectives, prompts, fail msgs, item/vehicle/clothing
  names+descriptions, ctOS profiler jobs/novelty facts. Built into `C:/tmp/wd2_ui_queue.json`,
  ordered SHORTEST-FIRST (most-visible labels translate first).
- **Renderer is NON-BIDI** (frontend + settings + HUD all draw glyphs in storage order):
  Hebrew MUST be stored **VISUAL (pre-reversed) per line** — `wd2_ui_merge.py:visual()`
  reverses each Hebrew run + run order, keeping Latin/`[TOKEN]`/`{VALUE}`/`%spec`/`[CR]`
  intact. Logical storage → mirror text in-game (the bug seen 2026-06-17). Latin proof:
  the main menu (visual) renders correct; a logical-stored settings string rendered mirror.
- **Tools (`work/`):** `wd2_ui_translate.py` (translator — same model `gemma-4-31b-it@q2_k_xl`
  at `localhost:1234`, serial, BATCH=14, strict short prompt, placeholder-multiset validate,
  atomic resumable `C:/tmp/wd2_ui_he.json`); `wd2_ui_watchdog.py` (**RUN THIS** — supervises
  the translator + **auto-deploys every 400 new strings when WatchDogs2.exe is closed**:
  combine `wd2_ui_all.json`+`wd2_ui_he.json` → `wd2_ui_merge.py` (visual) → `wd2_loc.py encode`
  → `wd2_archive.py deploy`). Launch under BASE python, hidden, `PYTHONIOENCODING=utf-8`.
- **Throughput** ≈ 9 str/min shared with SM2 → ~2-3 days for 17,917. Resumable; on a
  reboot just relaunch the watchdog (same command).
- **`wd2_ui_all.json` (1,602)** = an earlier, separate UI batch from the not-in-oasis pool;
  combined with the new translations at every deploy. Memory: [[wd2-ui-translation]].

## What works (proven)
- **RTL rendering** — the engine renders the Arabic locale slot RTL correctly (the user
  sets Settings → Written Language → **Arabic**; `WD2_GamerProfile.xml TextLanguage2=22`).
- **Text channel** = `languages\main_arabic.loc` (format `SL`, a per-language Huffman string
  blob). The `oasisstrings.rml` is NOT read at runtime. The **main menu / frontend is
  english-locked** (not via .loc/.rml) — a known, minor limitation.
- **Font** = `ui\fonts\helveticaneuelt_w1g_65_md_arabic.ffd` + its atlas `..._1.xbt`
  (TBX header + DXT5 DDS, 1024×2048). Hebrew glyphs must be injected or text shows tofu.
- **Deploy** = fat-redirect: append the new (stored) file to a `.dat` and rewrite its
  20-byte `.fat` entry (v11 stored ⇒ UncompressedSize=0). Fully reversible; the game reads
  `common`/`patch`/`patch2` (handle-probe confirmed). EAC off: `WatchDogs2.exe -eac_launcher`.

## Tools (all in this folder)
| Tool | Role |
|---|---|
| `work/wd2_loc.py` | **.loc encoder/repacker** (`encode <orig.loc> <strings.txt> <out.loc>`). 100% round-trip incl. Hebrew. Also a (table-correct) Python decoder. |
| `tools/loctool/loctool.exe` | **.loc decoder** (C#, ahmet-celik port). `loctool.exe <main_xx.loc>` → `<…>.txt` (id=text, UTF-16). Ground-truth decode. |
| `work/wd2_archive.py` | **extract / deploy / revert** a stored file across the archives (fat-redirect, tagged backups in `F:\WD2_lang_backup`). |
| `work/wd2_font.py` | **font atlas generator** — keeps every original glyph + metrics, adds Hebrew (px=40) into a taller 1024×2304 atlas; emits `.fnt` + `.xbt` (correct DDS header). |
| `tools/ffdconverter/FFDConverter.dll` | **.ffd ↔ .fnt** (eprilx, `-v WD2`). `DOTNET_ROLL_FORWARD=LatestMajor dotnet FFDConverter.dll …`. |

## End-to-end recipe
```bash
# 0. one-time: extract the live skeleton + EN source + font
python work/wd2_archive.py extract "languages\main_arabic.loc"  ar.loc
python work/wd2_archive.py extract "languages\main_english.loc" en.loc
python work/wd2_archive.py extract "ui\fonts\helveticaneuelt_w1g_65_md_arabic.ffd"   font.ffd
python work/wd2_archive.py extract "ui\fonts\helveticaneuelt_w1g_65_md_arabic_1.xbt" font.xbt
tools/loctool/loctool.exe en.loc      # -> en.loc.txt  (48,138 EN strings, the source)
tools/loctool/loctool.exe ar.loc      # -> ar.loc.txt  (48,138 AR skeleton, same ids)

# 1. TRANSLATE en.loc.txt EN->Hebrew  (the only NOT-done step; use the SM2 LM trio pattern)
#    -> he.txt  (lines "id=<hebrew>", [CR]/[LF] preserved, same ids)

# 2. encode Hebrew into a new main_arabic.loc
python work/wd2_loc.py encode ar.loc he.txt main_arabic_he.loc

# 3. build the Hebrew font (.ffd + .xbt)
#    (need orig_real.fnt = ffd2fnt of font.ffd WITH dims 1024 2048)
printf '1024\n2048\n\n' | DOTNET_ROLL_FORWARD=LatestMajor dotnet tools/ffdconverter/FFDConverter.dll \
   --ffd2fnt -v WD2 -f font.ffd -o orig_real.fnt
python work/wd2_font.py orig_real.fnt font.xbt heb_font
printf '1024\n2304\n\n' | DOTNET_ROLL_FORWARD=LatestMajor dotnet tools/ffdconverter/FFDConverter.dll \
   --fnt2ffd -v WD2 -f font.ffd -b heb_font.fnt -o heb_font.ffd

# 4. deploy (game CLOSED) + launch with EAC off
python work/wd2_archive.py deploy "languages\main_arabic.loc" main_arabic_he.loc
python work/wd2_archive.py deploy "ui\fonts\helveticaneuelt_w1g_65_md_arabic.ffd"   heb_font.ffd
python work/wd2_archive.py deploy "ui\fonts\helveticaneuelt_w1g_65_md_arabic_1.xbt" heb_font.xbt
#   & "F:\Games\WATCH_DOGS2\bin\WatchDogs2.exe" -eac_launcher   (Written Language = Arabic)
# revert anytime:  python work/wd2_archive.py revert "languages\main_arabic.loc"   (etc.)
```

## .loc format (for `wd2_loc.py`)
`SL`(2) ver=1(2) lang(2) table_length(2) tree_offset(4) · `table_length` Tables
(first_id u32 + offset_length: 28b offset|4b subtable-count) → SubTableMeta/SubTableIds
(delta-ids, 64-id blocks with u16 offsets **relative to subtable start**, pseudo-id gaps,
per-id `lo/hi` bit ranges) → 12 `tree_meta` thresholds (stored reversed) → 4-byte Huffman
tree nodes. `wd2_loc.py` re-encodes with a trivial fixed-width (8-bit when the alphabet
≤255) code: `tree_meta` forces one width, `node[code]=char`, splitting any subtable that
would exceed the u16 offset / max_id limits and regrouping into ≤15-subtable tables.

## Notes / gotchas
- The font atlas DDS must keep the **original DDS header** (Pillow writes a wrong
  `dwPitchOrLinearSize`/mipcount) — `wd2_font.py` splices header + our DXT5 body and patches
  height+linearsize for the taller atlas.
- Glyphs are stored **white RGB + alpha=coverage**; keep that.
- Per the SM2/CP2077 LM playbook (root `CLAUDE.md` §"UNIVERSAL Game-Translation Playbook"):
  translate with the local LM serial, UTF-8 stdout, atomic writes, structural QA.

## מסמכים קשורים
- באותה תיקייה: [[games/watchdogs2/FEASIBILITY|FEASIBILITY]], [[games/watchdogs2/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#watchdogs2|CLAUDE_INDEX_games]]
