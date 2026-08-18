## Corsair Cove Hebrew — ✅✅ PHASE 1 COMPLETE, every gate CLOSED in-game, 🟢 GO (easiest tier) (2026-08-02)

New game at `games/corsair_cove/` (RECON/FEASIBILITY/PIPELINE + `tools/` + `work/` + `extract/`).
Install `E:\Games\Corsair Cove` — **Limbic Entertainment / Hooded Horse, Unreal Engine 5,
`WinGDK` (Microsoft-Store/GDK) build v1.1.1.0**, RUNE-cracked (`ms_emu.json` + `winmm.dll`).
Proposed `games.id` = **`corsair-cove`** (checked the LIVE catalog: 47 rows, 0 Corsair hits —
no row exists yet, so nothing to match). Detector wired + verified on the real install
(folder-name / project-dir / exe-fingerprint all → `corsair-cove`).
**The proof is BUILT, SELF-VERIFIED and DEPLOYED; only a launch + screenshot is left.**

- **🔑 THE WHOLE CONTAINER + TEXT WORKSTREAM WAS REUSE — one `repak info` decided it**
  ([[engine-family-reuse-check-magic]]). Every pak is **v11 (Fnv64BugFix), UNENCRYPTED, no AES
  key, compression `None`**, so the vendored `games/hogwarts_legacy/tools/repak.exe` reads AND
  writes them, and the text is UE's **public LocRes v3** — the Until Dawn codec parsed it on the
  first try ([[check-public-format-first]]).
- **🟢 EVERY FILE WE TOUCH IS A LOOSE FILE IN A LEGACY PAK — the 27 GB IoStore side is never
  opened.** `pakchunk0-WinGDK.pak` (3.09 GB, 11,515 entries) holds the locres + the 172
  StringTable CSVs + Config; `pakchunk0_s25-WinGDK.pak` (101 MB) holds **18 `.ufont`** = the
  game's real UI fonts. The other 26 `_sN.pak` are 339-byte stubs beside their IoStore container.
- **✅ TEXT CODEC BYTE-IDENTICAL ON ALL 12 CULTURES** (`tools/cc_locres.py`). Two fixes got it
  from "semantic PASS" to byte-exact, and **both are latent in every copy of this codec**:
  **(a) an EMPTY LocRes string is length `0` with NO payload**, not a lone NUL (writing `\x00`
  at length 1 round-trips semantically and is never byte-identical); **(b) the string table's
  refCount is the REAL number of entries pointing at that string**, not `1`. Also verified from
  the shipped bytes that the table's order IS first-appearance order. **Ported back to
  `games/until_dawn/tools/ud_locres.py` → 12/12 byte-identical there too**
  ([[json-roundtrip-hides-key-type]]-style rule: grep the tree, don't fix the first hit).
- **🔴 `.ufont` IS NOT A BARE TTF HERE.** Until Dawn's `.ufont` starts with the sfnt magic at
  offset 0; Corsair Cove's is **`[u32 sfntSize][sfnt][4×00]`** — verified exactly (the prefix
  equals the sfnt's own 4-aligned table-directory end on 18/18) and `tools/cc_ufont.py`
  round-trips **18/18 byte-identical**. **Dump the first bytes before reusing a sibling game's
  container assumption, even inside the same engine.**
- **🟢 FONT = the easiest class in the project: loose bare TTFs, 4/4 injected 27/27.** The UI
  faces are **Alegreya Regular/SemiBold** (serif display) + **AlegreyaSans Regular/Bold-
  FixedNumbers** (sans UI), all `glyf`, all **0/27 Hebrew**; the 14 Noto CJK faces are
  per-culture fallbacks (most CFF, where a glyf merge is a silent no-op) and are deliberately
  skipped. Donors are **vendored** in `tools/donors/` so a build is reproducible off-machine:
  **Frank Ruhl Libre** → Alegreya (both calligraphic humanist serifs), **Assistant** → Alegreya
  Sans (both humanist sans). Original font NAMES kept, Latin 26/26 preserved.
- **🔴 NO Arabic/Hebrew locale — 12 LTR/CJK cultures** (`+CulturesToStage` = de en es fr it ja ko
  pl pt-BR ru zh-Hans zh-Hant) ⇒ **English-slot hijack**, which costs the user **ZERO actions**
  (`en` is the default culture, so the proof is on the first screen). ⚠️ `ST_Languages.csv` DOES
  carry an `Arabic` row — a planned-then-dropped locale, NOT a shipped slot; don't be fooled.
- **Deploy = an additive `_P.pak` in a folder the game doesn't even ship**:
  `Content\Paks\~mods\pakchunk999-WinGDK_P.pak` (`repak pack --version V11 --mount-point
  ../../../`). **No shipped file is modified**, so a store "verify files" cannot revert it and
  the revert is deleting one file.
- **Scope = 12,821 records / 11,914 GLOBAL unique / 742,852 chars** across 172 namespaces
  (median 35, p90 130, max 830) — a **single pass, no fleet**. Split by the engine's OWN metadata
  (a non-empty `Audio Filename` column = a recorded VO line): **UI/content 9,203 rec / 8,403
  unique · VO dialogue 3,598 rec / 3,506 unique**. Tokens are unusually clean: `{VAR}` 1,561 occ /
  151 distinct · `<tag>` 1,894 / 139 (`<hl>` `<b>` `</>` `<img id="Coin"/>`) · 762 real `\n` ·
  **0 `[brackets]`, 0 `&entities;`, 0 real printf**.
- **🔑🔑 THE DEVELOPERS SHIPPED A LOCALISATION KIT — the richest translation source in the whole
  project.** All 171 StringTable CSVs are registered as RUNTIME tables (`+StringTableCSVs=`), and
  every row carries translator metadata: **`Context` on 99.8 %** (12,801 rows — *"Name of a game
  setting."*, *"VO during cutscene"*), `Speaker` 3,632, `Addressee` 2,483, **`SpeakerGender`
  1,225 · `AddresseeGender` 1,147**, and `Order`/`Place of the Sequence` on 6,488 (= ready-made
  sliding-window conversation context). That is the gender oracle handed over as first-class
  data instead of being reverse-engineered from ru/pl/ar ([[gender-oracle-from-game-langs]]).
  Emitted per key to `extract/context_source.json` (12,821 rows, with the reference languages).
  **⚠️ The columns are REAL but DIRTY** — mixed case, a `Variable`/`various` bucket (1,014 rows =
  the addressee is the PLAYER, whose captain may be either gender), plural addressees written as
  a group NAME (`Pirate Crew`), and a few rows where a `Comment` leaked one column left.
  `scope_report.norm_gender()` maps them to a closed set and **refuses to guess from free text**
  ([[gender-hint-needs-closed-set]]); a specific character is kept as `named:<X>`.
- **🔑 New-Era panel is FREE and complete: all 11 other cultures at 100.0 % key parity**
  (12,821/12,821 each) — ru+pl give speaker AND addressee gender, fr/it/es/pt-BR referent,
  de register.
- **🔴 DO NOT DEDUP BY THE ENGLISH STRING — measured, not assumed.** 600 duplicate-English groups
  (1,507 keys); against the game's OWN professional locales they diverge at **fr 14.8 % ·
  pl 11.5 % · es 6.3 % · de 6.2 % · ru 1.5 %** ⇒ key the pool by **`<namespace>|<key>`**
  ([[dedup-safety-from-game-langs]]).
- **🟢 DRM: none.** 0 hits for Denuvo / VMProtect / `.vmp` / EAC / BattlEye / `tamper` in the
  173 MB shipping exe; `SHA256` ×136 + `integrity` ×4 are stock UE crypto strings; the PE is
  ordinary and unpacked; no `.sig` pak-signature files.
- **✅ bidi = LOGICAL + ONE LEADING RLM, both proven in-game.** `tools/cc_rtl.to_logical` is the
  SHIPPING transform (strip stray controls, keep natural order, prepend U+200F); `to_visual` is
  the A/B counterpart only. Selftest 10/10.
- **🔴🔴 "STORE NATURAL HEBREW" IS NOT THE WHOLE RULE — the PARAGRAPH BASE is decided by the
  FIRST STRONG CHARACTER (UBA P2/P3), and a Hebrew line that OPENS with Latin gets an LTR base.**
  Found on a 330-char description that began `AMD FSR 2.2 …`: the whole paragraph left-aligned
  and its neutrals (`;` `טווח:` `0-100%`) landed on the wrong side. The engine is correct; the
  SOURCE is the problem — and it hits any line opening with a brand, a number, or a **`{VAR}` the
  engine fills with Latin AT RUNTIME** (170 corpus lines start with `{`/`<`). Settled by a 3-rung
  ladder on three adjacent description panels: **A** prepend **U+200F** ✅ right-aligned, correct
  punctuation, **no tofu** · **B** reword the source to open in Hebrew ✅ · **C** untouched control
  ✗ still left-aligned (proving the comparison is real). **A ships** — it needs no discipline from
  the translator and is immune to runtime substitution.
  ⚠️ **The fonts had NO glyph for U+200F**, so a bare RLM would have rendered as a TOFU BOX (the
  Spider-Man 2 trap). `cc_font._add_empty_controls` now maps U+200E/200F/202A-202E/061C to a
  zero-width zero-contour glyph — verified in the LIVE font: `U+200F → bidi_zero, contours=0,
  advance=0`. **Never inject a bidi control without first checking the font has a glyph for it.**
- **⚠️ A STALE DOCSTRING IS HOW A WRONG RULE SHIPS.** `cc_rtl` said "never inject bidi controls"
  — true of letter ORDER, wrong about the paragraph BASE. Same class as the AC-Origins
  `to_logical`-vs-`to_visual` docstring trap: **when a proof overturns a prediction, grep the
  TOOLING for the old claim, not just the notes.**
- **✅ LONG-PARAGRAPH gate PASSED (round 4, the Graphics description panel — the widest/tallest
  text area in the game).** A one-line label can never exercise these: **WRAP** — 330 chars over
  4 lines, right-aligned, top-to-bottom order correct, with `(anti-aliasing)` `1920x1080`
  `2560x1440` `ב-30%` `DLSS, AMD FSR ו-XeSS` `"איכות" ל"ביצועים".` all correctly placed even
  across a line break; **LINE ORDER** — an explicit `
` keeps line 1 ABOVE line 2, so the RDR2
  store-VISUAL inverted-wrap bug does not exist here. Exposure that made this worth a launch:
  **1,075 corpus strings are >140 chars and 762 carry a real newline.**
- **✅ THE PROOF IS DEPLOYED** (`work/build_menu_proof.py --deploy`; 2.65 MB, 6 entries, verified
  by unpacking the pak it just wrote AND by re-reading it out of the game folder). One screenshot
  closes everything: a pure-Latin **`ZZ-CC-OK-ZZ`** on *New Game* (MOUNT, font-independent) ·
  the SAME word stored LOGICAL (*Settings*) vs VISUAL (*Credits*) + an `אבגד` control (bidi) ·
  all 27 letters on *Exit to Desktop* (glyph coverage) · `1 שלום` / `9 עברית` (**the digit side
  answers bidi even through total tofu** — [[tofu-still-answers-bidi]]) · a punctuation/parens/
  quotes/digits/Latin-island paragraph in BOTH modes on two Options descriptions (layout).
  **🔑 Plus a SURFACE LADDER that costs nothing** ([[measure-with-a-ladder]]): `Menu_Load` is
  left ENGLISH in the locres and patched to **`ZZ-CSV-OK-ZZ`** in the runtime CSV — since this
  game reads 171 CSVs from file at runtime, that marker appears **only if the native-culture
  locres override does NOT win**, naming the winning surface without a second deploy.
- **🔴 ROUND 1 CAME BACK NEGATIVE — "אנגלית, אין שינוי": not even the pure-Latin marker.** That
  is exactly what the marker exists for: it rules OUT font and bidi in one word and says
  **the pak never mounted** (had it mounted with the locres losing, the CSV marker would have
  shown — the two were in the same pak, which is the one design flaw of round 1: a single pak
  cannot separate "didn't mount" from "mounted, wrong surface"; put each candidate in its OWN
  pak over its OWN file, because **a pak override is per-FILE — the highest-priority pak that
  contains a path wins the WHOLE file**, so two candidates patching the same locres can never
  both be visible).
- **🔎 THE SUSPECT, from the game's own packaging data: this is a Microsoft-Store/GDK build with
  STREAMING INSTALL, and `pakchunk999` is a chunk index it has never heard of.**
  `package.manifest` (JSON, `"chunks":[{"id":0,"IsInitial":true,"files":[...]}]`) and
  `layout_*.xml` **enumerate every shipped pak BY NAME** (96 refs), and the shipping exe carries
  `ChunkInstall`. On such platforms Unreal gates pak mounting on the chunk being known/installed,
  so a directory scan can FIND a pak and the engine still skip it.
  **UNIVERSAL: on a Store/GDK/streaming-install title, read `package.manifest` / the layout XML
  before choosing a mod-pak NAME — an invented `pakchunk<N>` can be silently ignored, and it
  looks identical to "the folder isn't scanned".**
- **⚠️ No log route on this build**: the 173 MB shipping exe has `LogPakFile` ×0, `Mounted Pak
  file` ×0, `~mods` ×0 — logging is compiled out (`USE_LOGGING_IN_SHIPPING=0`), so `-log`
  produces nothing. The ladder IS the instrument.
- **🔴🔴 ROUND 2 ALSO CAME BACK NEGATIVE — an ADDED pak is never mounted on this build, however
  it is named or placed.** The 3-candidate ladder (`Paks\pakchunk0-WinGDK_P.pak` with a KNOWN
  chunk index · `Paks\~mods\pakchunk0_s2-WinGDK_P.pak` · `Paks\pakchunk0_s25-WinGDK_P.pak`)
  changed nothing. **The user's screenshot is what made it conclusive**: the menu reads
  *Resume / Story Mode / Uncharted Mode / Load / Settings / Credits / Quit* — **five of those
  rows are keys the build had patched** (`Menu_Resume`, `Menu_Load`, `Menu_Settings`, `Credits`,
  `ST_HUD/Quit`) and every one still rendered English.
- **🔴 MY OWN PROOF-DESIGN BUG, caught by that screenshot: the MOUNT MARKER SAT ON A KEY THAT IS
  NOT ON THE SCREEN.** `NewGame` was the marker row, and this game's main menu has no "New Game"
  item at all (it offers *Story Mode* / *Uncharted Mode*). Had the pak mounted, the marker would
  STILL have been invisible and I would have mis-read it as a mount failure.
  **UNIVERSAL: pin every proof string to a row you have SEEN on the target screen — read the
  menu first (or ladder several keys), never pick the key that merely sounds like a main-menu
  item.** ([[proof-marker-must-be-meaningless-to-engine]] covers the marker's CONTENT; this is
  the complementary rule about its LOCATION.)
- **🔑🔑 THE LEVER THAT REPLACES "add a pak": 24 of the SHIPPED paks are 339-byte EMPTY STUBS.**
  `pakchunk0_s1..s24-WinGDK.pak` all report **`0 file entries`** — their real content went to the
  IoStore `.ucas`/`.utoc` half, so the `.pak` carries nothing. They are **listed in
  `package.manifest`**, so the engine definitely mounts them, and **overwriting one loses
  NOTHING**. Backup is 339 bytes; the chunk's `.ucas`/`.utoc` are never touched.
  **UNIVERSAL: on an IoStore-era UE title that refuses added paks, look for the shipped
  ZERO-ENTRY pak stubs — hijacking a manifest-listed empty container sidesteps the whole
  "is my new pak allowed to mount" question at a 339-byte cost.**
  `build_menu_proof.deploy()` REFUSES to overwrite any pak whose entry count is not 0, so it can
  never destroy real content.
- **✅✅ ROUND 3 PASSED — the stub hijack works and closed EVERY remaining gate in one screenshot**
  (user: "עובד"). Payload split across three shipped stubs so the surfaces cannot compete:
  **`pakchunk0_s2`** = the full Hebrew `en` locres · **`pakchunk0_s3`** = the runtime CSV ·
  **`pakchunk0_s4`** = the 4 Hebrew fonts. The whole main menu WAS the proof:
  | menu row | stored | rendered | gate |
  |---|---|---|---|
  | Resume | `ZZ-S2-LOCRES-ZZ` | ✅ shown | MOUNT + the `en` locres surface wins |
  | Story Mode | `שלום` LOGICAL | ✅ readable | **bidi = LOGICAL** |
  | Uncharted Mode | `םולש` VISUAL | mirrored | VISUAL is wrong — never pre-reverse |
  | Load | `ZZ-S3-CSV-ZZ` (CSV pak only) | ✅ shown | **the runtime CSV is a live SECOND surface** |
  | Settings | `אבגד` | ✅ correct | direction control agrees |
  | Credits | all 27 letters | ✅ **ZERO tofu** | the Alegreya injection renders |
  | Quit | `1 שלום` | ✅ correct | digit placement agrees |
  ⇒ **`cc_rtl.to_logical` is the SHIPPING transform** (store natural Hebrew, no bidi controls),
  the font gate is closed, and there are TWO independent build targets (locres AND CSV).
  Left: font size/weight calibration + an eyeball of the Options punctuation paragraph.
  Revert (restores the three 339-byte stubs + removes rounds 1-2):
  `python games/corsair_cove/work/build_menu_proof.py --revert`.
- **⚠️ (superseded) ROUND 2 — a 3-candidate MOUNT LADDER** ([[measure-with-a-ladder]]).
  Each candidate is its OWN pak over its OWN file, so they cannot compete:
  **A** `Paks\pakchunk0-WinGDK_P.pak` (KNOWN chunk 0, flat, classic UE patch naming) → the full
  Hebrew locres, marker **`ZZ-A-CHUNK0-ZZ`** on *New Game* ·
  **B** `Paks\~mods\pakchunk0_s2-WinGDK_P.pak` (the `~mods` FOLDER, but a chunk index the
  manifest DOES list) → the runtime CSV, marker **`ZZ-B-MODSCSV-ZZ`** on *Load* ·
  **C** `Paks\pakchunk0_s25-WinGDK_P.pak` → the 4 Hebrew fonts.
  Reading it: **A** ⇒ the chunk index was the gate and the locres surface wins (and every other
  gate is answered on the same screen) · **B** ⇒ `~mods` works AND the runtime CSV is live ·
  **neither** ⇒ this build ignores added paks entirely and the only route left is editing the
  SHIPPED pak in place (repak can, with a backup).
- **✅✅ EVERYTHING UP TO THE TRANSLATION IS BUILT (2026-08-02) — the only thing left is the
  Hebrew itself.** Five artifacts, each verified, none of them a placeholder:
  | artifact | state |
  |---|---|
  | `work/name_registry.json` | **65 terms**, every one validated to EXIST in the corpus, each carrying its `oracle` evidence |
  | `extract/ct_upload.json` + the LIVE pool | **12,778 rows**, 0 unresolvable / 0 `source_en` mismatches |
  | `work/build_hebrew.py` | full build + QA gate + read-back verify + `--deploy`/`--revert` |
  | `work/publish_catalog.py` | the `games` row (`corsair-cove`, planned/locked/free, sort 10011) |
  | `work/upload_images.py` | cover 600×900 · banner 1600w · logo 360w contain-fit, all HTTP 200 |
- **🔑 THE NAME REGISTRY IS DECIDED BY THE GAME'S OWN LOCALES, AND THAT CAUGHT THREE REAL BUGS.**
  Corsair Cove ships `Speaker`/`Addressee` columns, so the cast is a genuine **CLOSED SET (20
  names)** — no regex guessing. Then Russian (Cyrillic makes a transliteration visible at a
  glance) decides translate-vs-transliterate per term. **The rule it established: place/faction/
  ship names are TRANSLATED (ru+de agree on every single one), personal names TRANSLITERATED.**
  Three that the English alone would have got WRONG: **`Raven` → ru Ворон / pl Kruk = TRANSLATED**
  (an epithet, so `עורב`, not `רייבן`); **`Reaper` → Жнец / Żniwiarz = TRANSLATED** (`הקוצר`);
  and **`Jonah` → ru Иона / pl Jonasz = each language's own BIBLICAL form**, so Hebrew must be
  **`יונה`**, never a transliteration `ג'ונה`. Plus **`Kanja` → ru Канья is /kanya/**, so `קאניה` —
  a Hebrew translator would reflexively write `קאנג'ה`. Web-verified separately against
  he.wikipedia: **`Teach` = `טיץ'`** (the historical Edward Teach/Blackbeard) and **`al-Hurra` =
  `אל-חורה`** (א-סיידה אל-חורה, the real Moroccan pirate queen).
- **🔴 VALIDATE THE REGISTRY AGAINST THE CORPUS — two of my own entries were fiction.**
  `Sea Witch` does not exist (the real term is **`Witch of the Waves`**, 28 hits) and `Doubloon`
  appears **zero** times in this game. A registry written from imagination damages as much as it
  fixes; the check is one line (`term not in corpus`) and it now runs on every build.
- **`/translate` pool LIVE — 12,778 rows** in 2 visibility-ordered categories (**ממשק ותפריטים
  9,180 → כתוביות עלילה 3,598**), split by the engine's OWN `Audio Filename` column, never a
  length heuristic. `string_key` = **`<namespace>|<key>`** — byte-identical to what `cc_locres`
  returns and `build_hebrew.py` consumes, so an approved export drops onto the build with no
  remapping. **Every row carries the dev kit's real `Context` + speaker/addressee + normalised
  gender + the game's own 7-language panel.** Verified through the PUBLIC API (both category
  chips exact, first served batch is UI), not the importer's message.
  ⚠️ Only **43 rows dropped**, and only with evidence: 42 token-only, plus the single
  `DummyTable|DummyKey` whose English is an instruction to a developer *and* whose shipped German
  is byte-identical to the English. **Deliberately NOT dropped: `ST_ECPrincipleCompassNodeType|*`**
  — they look like code identifiers and German leaves them, but the professional **Russian
  translates all four**, so they may be displayed; uploading them with that Russian in the context
  lets a human decide instead of guessing.
- **⚠️ The picker feed returns `game_id`, not `gameId`/`id`.** My first verification looked for the
  wrong field and reported the game MISSING while the data was perfect — check the field name
  before believing a negative.
- **🚁 FLEET RUNNING on streams #13-21 since 2026-08-03** (`games/corsair_cove/fleet/`). The user
  chose the fleet over a single pass; at 12,778 lines it is a short run, and the fleet buys the
  enforced New-Era panel + the gender guard. **Streams 13-21 = vm / vm2 / vm3, the LOCAL
  VirtualBox guests on 127.0.0.1:2222-4** — Spider-Man 2 finished on them and RDR2 was pulled
  back off at the user's request, so they were idle. **RDR2 keeps #1-12** (desktop, laptop, vm4,
  vm5); nothing was taken from it. The stream registry was repointed `spiderman2:*` →
  `corsair-cove:*` (a retired game's slots go to the same physical machines).
  | piece | what |
  |---|---|
  | `build_corpus.py` → `corpus.json` | **12,778 lines** (identical filter to the /translate pool), **UI 9,180 → subs 3,598 in VISIBILITY order**, full **6-language panel (ru pl de fr es it) on 100.0 %** |
  | `cc_nim.py` | the worker — RDR2's hardened one retargeted (strike/park, omit ceiling, fail-fast, PID+cmdline singleton, atomic per-PID writes) |
  | `split_corpus.py` → `shards/` | 9 DISJOINT per-provider shards, 1,419-1,420 each, identical UI/subs mix, 0 duplicates |
  | `deploy_cc.sh` | scp worker+adapter+registry+shards+per-machine `keys.json` → `C:\ccw`, register SYSTEM tasks `CcMP` (5 min) + `CcMPBoot` |
  | `pull_cc.sh` + `CcFleetPull` (3 min) | validate-before-replace banks → `hebrew.json`, name-canon at MERGE, keeps the pusher singular |
  | `cc_progress.py` | dashboard pusher, gameId `corsair-cove`, sentences |
- **🔴🔴 THE BUG THAT WOULD HAVE PARKED REAL CONTENT: a reasoning model's THINKING counts against
  `max_tokens`.** Groq's `openai/gpt-oss-120b` truncated a 6-line batch at `max_tokens=720` after
  **173 characters / 2.5 lines** — and the missing keys are simply ABSENT from the JSON, so the
  omit counter reads them as *model dropout* and `MAX_OMITS` would eventually **park ordinary
  lines as unfixable**, behind a reassuring `+2/6` in the log. Budget for the reasoning preamble,
  the long ids the model must echo verbatim, and Hebrew at ~1 token/char:
  `mx = min(4000, 1000 + sum(len(k))//2 + sum(len(en))*2)`. **Diagnose by printing the RAW
  response beside the parsed count** — `raw 173 chars, parsed 2/6` names it instantly;
  `answered 2/6` does not. [[reasoning-model-max-tokens-truncation]]
- **⚠️ On a free tier, latency is QUEUE VARIANCE, not prompt size** — NIM answered the same batch
  in **99.5 s / 18.6 s / 93.1 s** at panel widths 6 / 4 / 2, parsing **6/6 every time**. So the
  full 6-language panel was KEPT; do not trim the New-Era panel to chase speed before measuring
  that the panel is the cost.
- **✅ SPOT-CHECKED AT 176 LINES (1.4 %) AND RESTARTED CLEAN — two systematic defects the
  structural guard cannot see, both decided by the game's OWN locales:**
  (a) **imperative NUMBER drift** — `בנו 100 מבנים באי שלך` mixed a PLURAL verb with a SINGULAR
  possessive in one line, and sibling achievements varied `גייס`/`גייסו`. German uses `du`/`deine`
  (`Errichte`, `Heuere`) and Polish the singular imperative (`Ukończ`, `Wznieś`) ⇒ **masculine
  singular throughout**, now a directive in the prompt quoting that evidence.
  (b) **a hyphen glued between a Hebrew prefix and a Hebrew word** (`ב-שבעת הימים`) — deterministic,
  so a REPAIR in `normalize()`, never a rejection: `(?<![א-ת])([ובלמהשכ])-(?=[א-ת])` → `\1`. The
  lookbehind keeps a real compound safe (`האל-מלך`) and leaves the correct `ל-NPC` / `ב-2024`
  alone. Verified 7/7 offline, then **0 and 0 across the re-run bank**.
  [[spot-check-the-fleet-at-1-percent]]
- **⚠️ The homepage tab stays HIDDEN** — `ProgressDashboard` filters `availability !== 'planned'`
  and Corsair Cove is deliberately still `planned`. Snapshots are recorded but invisible; that
  flag is admin-owned ([[operating-doctrine]]), flip it only on the user's word.
- **🔴🔴 FLEETDASH SHOWED THE WRONG GAMES — fixed, and the cause generalises.** The board read
  `rdr2 #1-12`, `ratchet-rift-apart #22-25` and a DEAD `spiderman2 #36-44`, with Corsair Cove
  absent. Three separate faults, all now closed:
  1. **A game only appears if it is in `tools/fleet_dashboard/fleet_config.json`** — the fleet dir
     alone does nothing. Added `corsair-cove` (vm/vm2/vm3, `C:/ccw`, task `CcMP`, worker `cc_nim`),
     and the shard filenames were renamed to the collector's convention
     **`corpus_{machine}_{provider}.json`**.
  2. **The community-compute game was HARDCODED** (`_CC_GAME = "ratchet-rift-apart"`) while
     `cc_stats` returns the AGGREGATE — so the FINISHED R&C run (17,624/17,624) was being merged
     into the live Hogwarts run (45,7xx/53,810) and shown under the wrong name, reporting
     `63,331/71,434`. **`cc_lines` keeps every seed until its results are collected**, so an
     aggregate is never safe. Added the RPC **`cc_games(p_secret)`** (one row per seeded game,
     `SECURITY DEFINER`, same `_cc_gate`, granted to anon) and `collect_cc` now returns a LIST,
     emitting only games with `remaining > 0` — a finished seed drops off by itself and a new one
     appears with no code change. `_CC_TITLES` maps ids to Hebrew names with an id fallback.
     ⚠️ `_cc_rpc` now RETRIES ×3: PostgREST 500s while its schema cache reloads, and one failure
     made every community row VANISH — which reads as "the fleet died".
  3. **Stream numbers must be RENAMED in the registry, never re-allocated.** `stream_ids.json`
     hands an unknown key the next free number, so the earlier `spiderman2:*` → `corsair-cove:*`
     rename left the RUNNING dashboard to re-add `spiderman2:*` at #36-44. Renamed
     `ratchet-rift-apart:community:devN` → `hogwarts:community:devN` (keeping #22-26) and DELETED
     the retired `spiderman2:*` + `rdr2:vm/vm2/vm3:*` keys. **Clean the registry AND restart the
     app**, or the running instance writes the stale keys straight back.
  Verified in isolation (`collect(cfg, remote=None, hist={})` — `dash.py --once` blocks on the ssh
  probes), stable over 3 runs: **rdr2 #1-12 · corsair-cove #13-21 · hogwarts #22-25**.
  `dist/FleetDash.exe` rebuilt (50.4 MB) + `dist/fleet_config.json` synced.
  [[dashboard-game-must-be-discovered]]
- **NEXT:** let the fleet drain → re-run the 1 %-style consistency grep on the full bank →
  `build_hebrew.py --check` (the QA gate) → `--deploy` → calibrate the font size/weight against
  the shipped Latin → publish only on an explicit "פרסם".


