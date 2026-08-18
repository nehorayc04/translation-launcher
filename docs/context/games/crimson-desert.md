## 🏜 Crimson Desert PHASE 2 — the "דור 3" translation fleet is LIVE on 18 streams (2026-08-10)

Spider-Man 2 finished, its 18 streams were released, and the same six machines were handed to
**Crimson Desert** — the project's first **pure TRANSLATE** run on the דור-3 engine (every prior
דור-3 corpus was a REVIEW over shipped Hebrew). Desktop stays on Skyrim's book drain.

| piece | what |
|---|---|
| `fleet/build_multilang.py` | the THIN דור-3 adapter — reads all 14 `.paloc` language slots via `tools/cd_container.py`, hands `panel`+`spine` to `universal/multilang_review.build` |
| `fleet/review_corpus/{ui,dialogue}.final.jsonl` | **185,370 rows** (ui 132,171 → dialogue 53,199), **100 % carry ≥6 reference languages** |
| `fleet/brain_glossary.json` | 14 terms, **every one validated to EXIST in the corpus** + 4 game rules |
| `fleet/build_corpus.py` | projection → `corpus.json` **184,993** lines in VISIBILITY order (ui→dialogue, short→long) |
| `fleet/cd_nim.py` | the worker — the PROVEN Corsair Cove translate worker retargeted (all hardening inherited) |
| `reslice_equal` / `prep_machines` / `push_shards_restart` / `pull_cd.sh` | SM2's newest-generation scripts, retargeted; all read `machines.json` |

- **🔑 THE WHOLE CONTAINER/TEXT WORKSTREAM WAS REUSE.** `parse_pamt` + `parse_paloc` already
  existed from Phase 1, so the adapter is ~150 lines and the corpus was built in one run. The
  panel is the richest yet: **ru+pl** (speaker AND addressee gender), **de** (register + the
  length budget), **fr/es/it/pt** (referent). tr/ko/ja/zh ship too but are deliberately NOT in
  the prompt — they add little for Hebrew and would inflate every payload.
- **🔴 CD stores ONE string per (id, language)**, so the engine's `fv != mv` gender split can
  never fire — it correctly reported **`gendered 0`** on all 185,370 rows. That is the Skyrim
  shape, not a bug. The adapter therefore attaches a deterministic **`gender_hint` from the
  Russian** via `gender_oracle.ru_addressee/ru_speaker` (a CLOSED set): **6,324 lines** get a
  hard fact, the rest carry the raw ru/pl for the model to read.
- **🔴🔴 THE `[...]` SYNTAX IS OVERLOADED HERE — and the game's own Russian settles each class**
  (the AC2 trap, measured not assumed: 5,329 occurrences / 175 distinct).
  **PROSE** `[Crafting Method]` → ru `[Способ изготовления]` = a translated section HEADER
  (also `[Recipe] [Effect] [How to Use] [Supply Contract]`) ⇒ deliberately **NOT** in `STRUCT`,
  because putting it there would make the guard reject every correct crafting tooltip.
  **TOKEN** `[EMPTY]` (2,639) and `%0#`/`%1#` (285) → ru keeps them **verbatim** ⇒ both ADDED to
  `STRUCT`. Note `%N#` is Pearl Abyss's own form — real printf (`%s`/`%d`) is **0** occurrences.
  Line breaks are `<br/>` (23,751) and there is **not one real newline**, so the newline guard is
  inert and the `<br/>` count is what the token multiset protects. Guard self-test **10/10** on
  exactly these classes.
- **🔴🔴 A LOOKUP ON CORPUS DATA MUST NEVER BE A BARE `[...]` — this killed all 18 streams within
  seconds while the deploy reported `RESTARTED` for every machine.** The inherited
  `_payload` had `{"m":…,"f":…}[v["sg"]]` with **no `pl` key**, and `gender_oracle` returns
  **`"pl"`** for plural on BOTH axes — so the first line with a plural SPEAKER (1,614 of them)
  raised `KeyError: 'pl'`. Fixed to a membership-tested map, then **proven over all 184,993 rows:
  0 crashes**. Same family as the documented `{"p": "רבים"}` mis-map.
  **UNIVERSAL: a "deploy succeeded" line says the process was LAUNCHED, never that it is alive —
  verify workers by counting them and reading their log, exactly as for a scheduled task.**
- **🔴 `schtasks /run` on a Disabled task does nothing and still exits 0.** `prep_machines`
  registers `CdMP`/`CdMPBoot` **Disabled** on purpose (so a staged game can never start while
  another owns the keys), so `push_shards_restart` now **Enables** before it runs them.
- **🔑 The brain is re-applied AT MERGE** (`pull_cd.sh`): every wrong Hebrew `variant` a glossary
  entry lists is rewritten to the canonical form on every pull, prefix-aware — so a term
  correction fixes the whole corpus **without re-translating a line**, and the step **prints how
  many rows it changed** (a transform that silently changes 0 is indistinguishable from a broken
  one). Inert today (no variants yet) and wired for the first promotion.
- **⚠️ `parked ~145` per shard at startup is CORRECT** — the worker's own token-only pre-park
  (a line that is 100 % engine tokens, e.g. a bare `[EMPTY]`, is unwinnable: translating breaks
  the multiset, echoing trips copy-EN). It is parked honestly, never fake-banked as English.
- **🔴🔴 12 OF 18 STREAMS PRODUCED NOTHING FOR HOURS — the SHIPPED provider models, not the
  fleet.** Overall rate fell to ~7 lines/min and the per-machine probe said "18/18 alive", which
  is exactly why the useful number is **the per-batch accept ratio in the worker's own log**, not
  liveness: `groq [33/1259] +31/31` (healthy) vs `sambanova +0/33` and `nim +0/43` on EVERY
  batch, each preceded by `step1 fail (The read operation timed out)` — a TRANSPORT failure, not
  a guard rejection. Diagnosed by probing candidate models **with a real 8-line batch of this
  corpus** on a worker box using its OWN keys (never `"hi"` — a trivial prompt succeeds on a
  model that returns an empty `content` for a JSON task):
  | provider | model | result |
  |---|---|---|
  | groq | `openai/gpt-oss-120b` | 3.5 s · 8/8 ✅ keep |
  | sambanova | **`DeepSeek-V3.2`** (shipped default) | **HTTP 429 "Rate limit exceeded"** |
  | sambanova | `DeepSeek-V3.1` | HTTP 429 "experiencing high demand" |
  | sambanova | **`Meta-Llama-3.3-70B-Instruct`** | 10.5 s · 8/8 ✅ switched |
  | nim | **`meta/llama-3.1-70b-instruct`** (shipped default) | 54.2 s — its batches blew the 150 s ceiling |
  | nim | **`meta/llama-3.3-70b-instruct`** | 37.2 s · 8/8 ✅ switched |
  ⇒ `PROVIDERS` retargeted **for this game only** (Skyrim keeps its own copy), and — because
  their limits differ in KIND — a per-provider line cap was added on top of the token budget:
  **`MAXLINES = {groq: 20, sambanova: 14, nim: 10}`** (groq is fast but TPM-capped so a huge
  batch 429s the key; nim is generous but slow per call, so a 43-line batch simply times out).
  Effect was immediate: sambanova `+0/33` → **`+14/14`**, nim `+0/43` → **`+10/10`**.
- **⚠️ AND THE FLEET PROBE ITSELF LIED FIRST — `LIVE CD STREAMS: 0/18` on a healthy fleet.** The
  worker's own startup line contains Hebrew ("דור-3"), so the remote log tail came back in the
  console codepage, `subprocess(text=True)` raised `UnicodeDecodeError`, `stdout` became `None`,
  and the filter printed a blank line that counted as zero. Fixed on both sides —
  `errors="replace"` in Python **and** an ASCII flatten (`-replace '[^\x20-\x7E]','.'`) in the
  PowerShell before it returns. Same family as [[powershell-json-output-corruption]] and
  [[verify-a-kill-by-recounting]]: **a filtered count of 0 is worthless — it is the value a
  broken filter returns.**
- **STATE: 18/18 streams live** (laptop · vm4 · vm5 · vm · vm2 · vm3 × groq/sambanova/nim,
  `C:\cdw`, task `CdMP` every 5 min), `CdFleetPull` every 5 min on the desktop + the
  `cd_progress` pusher (gameId `crimson-desert`). All three providers accepting after the fix.
  Nothing baked, nothing published — publish only on an explicit "פרסם".


## Crimson Desert Hebrew — ✅✅ PHASE 1 COMPLETE, every gate CLOSED + DEPLOYED in one build (2026-08-07)

New game at `games/crimson_desert/` (`tools/cd_container.py` + `work/cd_font.py` +
`work/build_menu_proof.py` + `extract/fonts`, `extract/fonts_he`). Install `C:\Games\Crimson
Desert` (Pearl Abyss, proprietary **"BlackSpace"** engine, action-RPG, ~30GB of `0000-0035`
numbered package-group folders). **Nothing here was guessed — the whole container/crypto/
compression stack was reverse-engineered from THREE public community repos found via
unauthenticated GitHub API/raw fetches** (no `gh auth` in this env — plain `curl -H
"User-Agent: Mozilla/5.0"` works fine for public repos): `MrIkso/CrimsonDesertTools` (C#),
`lazorr410/crimson-desert-unpacker`, `hzeemr/crimsonforge` (Python, actively-maintained
v1.11.0, real published Nexus mods). Per [[check-public-format-first]] this collapsed what
the ResHax modding thread itself called "static analysis not possible" (Denuvo-packed exe) into
a few hours of porting — because the DATA format's crypto key is **filename-derived, not
extracted from the exe**.

- **Container = PAMT (index) + PAZ (numbered blob files) + PAPGT (root group table).**
  `meta/0.papgt` maps each numbered folder (`0000`…`0035`) to a language bitmask + an expected
  PAMT checksum; each folder's `0.pamt` is a dir-trie/filename-trie/file-record index into its
  own `N.paz` blobs. **`games/crimson_desert/tools/cd_container.py`** — pure Python, zero deps
  beyond `cryptography`+`lz4`, fully self-contained (no downloaded GUI tool needed at runtime):
  `parse_pamt`/`parse_papgt`/`read_file`/`parse_paloc` (read side, proven against the real
  187,521-entry English `.paloc`) + a full WRITE side (`patch_paloc_values`, `patch_raw_file`)
  implementing the complete checksum chain **PAZ file CRC → PAMT's per-PAZ CRC/size fields →
  PAMT self-CRC → PAPGT's per-group CRC pointer → PAPGT self-CRC**, re-derived and verified
  fresh from disk after every write.
- **🔑 Crypto = ChaCha20 with a DETERMINISTIC, filename-only key** — no key database, no
  extraction from the packed exe needed. `derive_key_iv(filename)`: lowercase the basename →
  Bob-Jenkins `lookup3` hash (`HASH_INITVAL=0x000C5EDE`) → seed → IV = seed repeated ×4 (LE) →
  key = 8×u32 built by XORing `seed^0x60616263` against 8 fixed deltas. Symmetric (ChaCha20
  encrypt==decrypt with the same key/iv). Only files with certain extensions are encrypted
  (`.xml .paloc .css .html .thtml .pami .uianiminit .spline2d .spline .mi .txt .app_xml
  .pac_xml .prefabdata_xml`) — most binary assets (incl. the UI `.ttf` fonts) are NOT encrypted.
- **Compression = LZ4 block-mode (no frame header)** for most text/loc files (zlib for type 4).
  Integrity = a SEPARATE Pearl-Abyss lookup3 variant (`pa_checksum`, magic `0x2145E233`,
  distinct algorithm from the key-derivation hash) used only for the CRC chain above — a
  content-integrity mechanism, verified this session to be a genuine no-op wall-check (not a
  live-loaded-content gate): see the DRM bullet below.
- **🔴 PAPGT has NO folder-id field in its group-CRC table — indexed POSITIONALLY.** Sort every
  package-group directory name alphabetically; that sorted index gives the byte offset of the
  group's expected-PAMT-CRC field (`crc_offset = 12 + index*12 + 8`). Get this wrong and you
  silently write a checksum into the WRONG group's slot.
- **Text = `.paloc`** (one per language per group; English lives at `gamedata/
  localizationstring_eng.paloc` inside group `0020`, 7.46 MB compressed → 16.8 MB decoded).
  Format = length-prefixed UTF-8 string records, either numeric-id triplets
  `[empty, numeric_id, text]` or symbolic pairs `[symbolic_key, text]`. **187,521 records / global
  unique VALUES not yet separately deduped this session** (records==unique keys since every key
  is a distinct id); **185,352 non-empty · GLOBAL unique non-empty VALUES 100,635**; total chars
  9.66M (median 26, p90 138, max 1,774). Split by key SHAPE (the engine's own convention, not file
  layout): **132,734 purely-numeric keys** (item/currency/skill/tooltip/system text — a MIX of UI
  and lore, e.g. `4294967409`→a currency description) vs **54,787 symbolic keys** following
  `questdialog_*` / `textdialog_*` / `aidialogstringinfogroup_*` / `<npc>_<zone>_<id>` patterns
  (clearly quest/NPC DIALOGUE). Symbolic-prefix split: **dialogue/story 47,635 records / 44,345
  unique values · UI/content 137,717 records / 56,650 unique values**.
- **🔴 NO Arabic/Hebrew locale ships — confirmed 3 independent ways**: my own scan of all 14
  language-slot `.pamt` folders (`0019`–`0032`, kor/eng/jpn/rus/tur/spa-es/spa-mx/fre/ger/ita/
  pol/por-br/zho-tw/zho-cn), MrIkso's C# `PackGroupLanguageType` enum, and crimsonforge's own
  `data/languages.json` `game_languages` list — all three agree, zero Arabic/Hebrew entry. ⇒
  **LTR-slot hijack** (English, group `0020`), per §0/§3 of the groundwork playbook.
  ⚠️ **`ui/basefont_ara.ttf` DOES exist** (in the font group, `0012`, no matching `cdcommon_
  font_ara.css` sibling) — almost certainly a leftover/unused asset for a SKU that never shipped
  retail, not a real activatable locale; not chased further since it changes nothing (no group
  folder feeds it Arabic string content).
- **🟢 Deploy = index-redirect append-or-in-place** (the project's standard §8f pattern):
  `write_entry_payload` overwrites a PAZ entry IN PLACE if the new (16-byte-padded) payload fits
  in the gap to the next entry, else appends 16-byte-aligned at EOF and zeroes the vacated
  region — never a full re-pack, offsets of every OTHER entry in the archive are untouched by
  construction (relocating one entry only ever creates a hole + grows the file, never moves a
  neighbour). Verified LIVE this session: the 21-key localization edit relocated (7.46MB →
  14.9MB, doubled — the loc payload had essentially zero free gap), while 3 of the 4 font
  patches (`basefont.ttf`/`basefont_eng.ttf`/`creditfont.ttf`, all in the SAME 940MB `2.paz`)
  fit IN PLACE (file size unchanged) and only `minigamefont.ttf` (in the separate 655MB `5.paz`)
  needed relocation.
- **🟢 Font gate — `games/anno1800/work/anno_font.py::_add_hebrew` REUSED UNCHANGED.** The 4
  UI-relevant TTFs (`basefont.ttf` "Yoon Gokulyeo Light" pre-language-select default,
  `basefont_eng.ttf`/`creditfont.ttf`/`minigamefont.ttf` "Vollkorn Medium") are plain loose
  glyf TTFs with no vhea/vmtx — exactly Anno 1800's Meta-font shape — so the existing glyph-merge
  helper (donor `FrankRuhlLibre-Medium.ttf`, already vendored for Corsair Cove) worked with zero
  new code (`games/crimson_desert/work/cd_font.py`, a thin wrapper). **All 4 confirmed
  Hebrew=27/27, Latin=26/26, Cyrillic kept** before deploy.
- **🟢 DRM screen — clean.** `CrimsonDesert.exe` (376 MB): **0** Denuvo / VMProtect / `.vmp` /
  BattlEye / EasyAntiCheat strings; only 2 `integrity` / 1 `tamper` / 23 generic `SHA256` hits
  (a low count, consistent with a crypto library, not a content-hash gate — contrast AC Black
  Flag Resynced's blocking ×143/×5/×11). **No EAC/BattlEye DLLs anywhere in `bin64/`**
  (single-player/co-op title). `voices38.dll` + a `steam_settings/` folder alongside
  `steam_api64.dll` = this project's standard cracked/Steam-emu install pattern. Plus the
  strongest empirical signal per the playbook: **crimsonforge is an ACTIVE, versioned (1.11.0)
  tool with real published Nexus mods patching these exact archives** — a live third-party mod
  scene is the strongest "modified archives load" proof there is.
- **✅✅ THE PROOF — ONE build, closes every gate at once, DEPLOYED + verified 21/21 byte-
  identical on disk + both checksum chains valid (`games/crimson_desert/work/
  build_menu_proof.py --deploy`).** Since every candidate label (`Continue`/`New Game`/
  `Settings`/`Save`/…) has SEVERAL duplicate key instances (different UI contexts reusing the
  same English source string) and there's no way to know a priori which specific key the title
  screen reads, every duplicate got its OWN distinct proof content — redundant coverage across
  whichever screen the user's screenshot lands on:
  - **Mount marker** (`ZZ-CD-OK-ZZ`, pure Latin) on a "Continue" key AND a "Main Menu" key.
  - **LOGICAL vs VISUAL A/B + a 4-letter direction control** on the 4 "New Game" keys: `שלום` /
    `bidi.get_display('שלום', base_dir='R')` / `אבגד` / its VISUAL form.
  - **Full 27-letter Hebrew alphabet** (`אבגדהוזחטיכלמנסעפצקרשתךםןףץ`) on a "Save" key.
  - **Punctuation/parens/digit/Latin-island paragraph, both modes**, on the 3 "Settings" keys:
    `בדיקה: (משפט עם NVIDIA ו-12345) — האם זה עובד? כן!` LOGICAL + its VISUAL form + a `שלום`
    redundancy in case only the Settings screen gets captured.
  - **Semantic real translations** on common dialog buttons for extra legible-Hebrew coverage
    across pause/confirm dialogs: Resume→המשך, Options→אפשרויות, Confirm→אישור, Cancel→ביטול,
    Back→חזרה, Apply→החל, Yes→כן.
  - All 4 Hebrew-injected fonts deployed alongside (group `0012`).
  **Post-deploy structural sweep** (re-parse fresh from disk, not the writer's own state):
  187,521 paloc entries still parse cleanly (0 lost), all 20,432 files in the font group still
  enumerate, **all 19 TTF files — not just the 4 patched — read back at their exact expected
  size with zero exceptions** (proving the other 15 untouched font files are byte-perfect), both
  PAMT checksums valid, PAPGT checksum valid.
- **Backups**: `C:\Games\Crimson Desert\_HE_BACKUP\{0020,0012,meta}\` (pristine `0.pamt`/`0.paz`
  for group 0020, `0.pamt`+`2.paz`+`5.paz` for group 0012, `meta/0.papgt`). Revert:
  `python games/crimson_desert/work/build_menu_proof.py --revert`.
- **✅✅ ALL GATES CLOSED — user's screenshot confirmed 2026-08-07.** Font renders CLEAN (zero
  tofu, well-formed Hebrew letterforms next to untouched English `Play`/`Load`/`Exit`). Mount
  confirmed (any patched string rendering proves the whole paloc write landed).
  **🔴 bidi = VISUAL — determined via the LATIN/DIGIT-ANCHOR method (not by "does it look
  right"), per [[hebrew-screenshot-transcription-trap]]: never trust your own read of Hebrew
  glyphs off a screenshot.** `PARAGRAPH_LOGICAL` (raw, un-reversed) was shown; in the RAW
  STORED ARRAY, `NVIDIA` sits at ~char-index 16 of 52 (early/first-third) and `כן!` is the LAST
  3 chars. On screen, `NVIDIA` renders in the LEFT portion of the line and `כן!` renders at the
  FAR RIGHT (line end) — i.e. screen-left-to-right position == raw-array-index order, exactly.
  **⇒ the engine performs ZERO bidi reordering — it draws the stored codepoint array in raw
  index order, left to right, with no exceptions.** Same class as RDR2/GTA/AC2/Anno/TLOU/GoT/007
  (§8b "store-VISUAL" engines). Phase 2 MUST run every value through a REAL Unicode Bidi
  Algorithm (`python-bidi get_display(text, base_dir='R')`) before storing — protect engine
  tokens as atomic placeholders, strip each segment's edge whitespace, pre-wrap for anything the
  engine would word-wrap (measured via real glyph advances, not char count), justify like the
  other store-VISUAL games — never ship natural/logical Hebrew again for this game.
- **PHASE 1 COMPLETE. NEXT = Phase 2**: delegate the ~100.6k unique-value corpus
  ([[delegate-all-translation]], split dialogue-first vs UI by the key-shape convention above)
  → build via `patch_paloc_values`, running every value through `bidi.get_display(v,
  base_dir='R')` (with the §8b token-protection rules) before writing → publish only on an
  explicit "פרסם".
- **✅ Catalog card LISTED on the website (2026-08-07, DB-only, no deploy).** `games/
  crimson_desert/work/{upload_images,publish_catalog}.py` (mirrors Corsair Cove's scripts) —
  processed the user's 3 supplied images (600×900 cover, 3840×1240 banner, 444×138 RGBA logo,
  contain-fitted to 360×112) → the public `covers` bucket, all 3 HEAD 200. Supabase `games` row
  id=**`crimson-desert`** (title_he "מדבר ארגמן", `availability=planned`, `status=locked`,
  free, `show_on_website=true`, `show_on_launcher=false` — no mod yet, `sort_order=10012` right
  after corsair-cove). Verified LIVE on the public `/api/games` (cache-busted, `X-Vercel-Cache:
  MISS`) — full shaped row present with correct `cover`/`bannerUrl`/`logoUrl`.


