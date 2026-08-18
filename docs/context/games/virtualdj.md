## Launcher "תוכנות" library tab restored + VirtualDJ added (cloud-delivered) + website /software (2026-07-12)

User: bring back the two Library sub-tabs ("משחקים" + "תוכנות") in the launcher "like before", add
**VirtualDJ** under תוכנות with its **files in the CLOUD (not bundled)**, and add a "תוכנות" nav item to
the **LEFT of "משחקים"** in the website top bar. Done end-to-end; VirtualDJ cloud path proven live.

- **Launcher SIDEBAR = a "ספרייה" folder group (FINAL design, after 2 user corrections).** `AppsView.tsx`/
  `SoftwareDetailPanel.tsx` existed but were unwired. First attempt put משחקים/תוכנות as **sub-tab pills
  inside the content** — user rejected ("the sidebar's ספרייה should NOT be a button; under it two
  sub-buttons"). Then a flat header+rows read as "just more rows" — user rejected again ("must be VISIBLE
  they're sub-items"). **FINAL:** `Sidebar.tsx` `NavKey` gained **`"software"`**; "ספרייה" is a
  **non-clickable `NavGroupHeader`** and, together with its two children, sits **inside a bordered/tinted
  rounded "folder" box** with the children **indented + a vertical connector line** (expanded only, so the
  collapsed 72px rail keeps its icon column). Children = `משחקים` (key `games`, controller glyph) +
  `תוכנות` (key `software`, grid glyph). `App.tsx` renders `view==="games"`→`LibraryView`,
  `view==="software"`→`AppsView`; a `selectedSoft` state opens `SoftwareDetailPanel` full-screen;
  `handleNavigate` clears it. **LESSON: a nav "sub-item" must be visually nested (box + indent +
  connector), not merely preceded by a muted label.**
- **Steam DELETED from the software catalog** (user: "סטים תמחק לגמרי") — removed from BOTH
  `software_catalog.py` and `website/src/data/software.ts`. Only VirtualDJ remains. The `steam_mod.py`
  applier + RPCs + the `s.id==="steam"` UI branches stay in the code but are inert (never rendered).
- **Software catalog was EMPTY** — the launcher pulls `/api/software` (retired endpoint → None → empty
  tab). Added a **bundled fallback `translation_manager/software_catalog.py`** (`sorted_software()` =
  Steam + VirtualDJ, camelCase `Software` shape); `main_eel._load_software` now falls back to it when the
  remote feed is empty. Only catalog METADATA is bundled — the translation FILES stay in the cloud.
- **VirtualDJ applier = cloud, single-file** `translation_manager/virtualdj_mod.py` (mirrors `steam_mod`):
  downloads `Arabic.xml` from the Worker (slug `virtualdj-hebrew` → GitHub) via `mod_source`, caches it,
  drops it into **`%LOCALAPPDATA%\VirtualDJ\Languages\Arabic.xml`** (`.orig` backup rule → reversible),
  status/enable/disable/clear. RPCs `apply_virtualdj_translation` / `get_virtualdj_mod_state` /
  `set_virtualdj_mod_enabled` / `clear_virtualdj_mod_cache` (main_eel, `slug="virtualdj-hebrew"`) +
  bridge slots + `eel.ts` (`VirtualDjModState` + 4 calls). `AppsView` gained a `VirtualDjCardCta`
  (Steam-style 3-state install/enable/disable) + `SoftwareDetailPanel` an `installVirtualdjTranslation`
  handler. Activation = in-app note "פתחו VirtualDJ → Options → Language = Arabic".
- **✅ PUBLISHED to the cloud (LIVE, verified):** GitHub **public** repo
  `hebrew-translation-hub/virtualdj-hebrew-mods` (public so the website direct-download works), FULL release
  **`v1.0.0-beta.1`** = `virtualdj_hebrew.zip` (115,172 B, sha `289a760dba85a2ce09ccf220a19483538c2fee
  0702f718c4f8af87e4ba334060`, contains Arabic.xml + install.py + readmes) + `manifest.json`. Worker slug
  `virtualdj-hebrew` added to `steam_mod_worker/src/index.js` + **`npx wrangler deploy` (wrangler was
  authed) → LIVE**: `/virtualdj-hebrew/manifest` 200 (version+sha) + `/archive` 200 zip. Full cloud path
  proven: `mod_source.fetch_and_extract("virtualdj-hebrew")` → download→verify(sha)→extract →
  Arabic.xml (427,208 B). Artifacts + pack: `games/virtualdj/release/` (built inline).
- **Website:** static `website/src/data/software.ts` (VirtualDJ only; the `/api/software` endpoint is
  retired so `SoftwarePage` uses this bundled list, still tries the API first for forward-compat).
  `Navbar.tsx` ITEMS gained `{ to:'/software', label:'תוכנות' }` **between games and translate** (RTL →
  renders LEFT of משחקים, as asked). Routes: `/software` → `SoftwarePage` (grid, mirrors GamesPage),
  **`/software/:id` → a NEW `SoftwareDetailPage`** — the user rejected the floating
  `SoftwareDetailModal` twice ("עדיין חלון צף… ככה נראה משחק"), so the detail is now a **FULL PAGE that
  mirrors `GameDetailPage` exactly**: `→ חזרה לתוכנות` back-link, RTL two-column (poster + download/
  launcher CTA + quick-facts + notice on the RIGHT; title/tagline/about/how-to-activate on the LEFT).
  A card click NAVIGATES (real URL + back button) instead of popping a modal; also removed
  `SoftwareDetailModal`'s synthetic `history.pushState` (the same stale-URL bug fixed for games).
  **LESSON: "like games" = a dedicated ROUTE + full page (GameDetailPage), NOT a max-w-5xl overlay
  modal — even though the game GRID also uses a modal.** Cover: the user's image → `covers/virtualdj.webp`
  (600×894, 34.7 KB) in the Supabase bucket, set on both catalogs. Deployed `vercel --prod` + aliased.
- **Verified:** frontend `tsc -b` + website `tsc --noEmit` + `py_compile` (main_eel/virtualdj_mod/
  software_catalog/bridge) all clean. **Launcher rebuilt locally (per [[local-install-launcher-builds]]),
  NOT published** — the VirtualDJ mod itself IS published (the user explicitly asked for cloud files),
  the LAUNCHER binary is a local install until "פרסם".

---


## VirtualDJ launcher fixes - stuck install, FREE-for-everyone DRM hole, language switch (2026-07-12)

Three user-reported defects on the new תוכנות tab, all fixed + verified live. **All three are
GENERAL lessons, not VirtualDJ quirks.**

- **🔴 THE DRM HOLE (any future software mod) - a paid SOFTWARE mod installed for FREE.**
  `_game_price_cents()` reads its row via `_catalog_by_id()`, which only scanned `_load_catalog()` -
  and `_load_catalog()` deliberately **filters OUT `isSoftware` rows** (they have their own library
  tab). So a software id resolved to **None → price 0** → the gate `if price > 0 and not owns(...)`
  collapsed to False → **anyone could install a ₪15 mod.** (Same class as the Build-G bug where the
  catalog shape dropped `priceCents`.) **Fix:** `_catalog_by_id` now falls through to `_load_software()`.
  **RULE: any code that filters the catalog must not be the ONLY source for a money/DRM lookup.**
  Gate enforced in 3 places now: `apply_virtualdj_translation` (RPC), inside `_run_vdj_install`
  (worker - the bridge starts it directly, bypassing the RPC), and `set_virtualdj_mod_enabled(True)`.
  `get_virtualdj_mod_state` returns `owned` + `priceCents`; `GowrState`/`VirtualDjModState` carry them
  (absent ⇒ free); the panel shows "רכישה - 15 ₪" + the burst poller (now `nativeDl`-aware).
- **🔴 Install froze the window then hung on "מתקין…" forever.** `apply_virtualdj_translation` ran the
  download+apply **inline on the GUI thread** (bridge slot, no `_run_off_thread`) AND never emitted a
  terminal `done` tick - and `GameDetailPanel` clears the progress bar ONLY on `done`/`error`. So the
  bar spun forever and the real state showed up only on re-entering the panel. **Fix:** `_run_vdj_install`
  background worker (bridge → `QThreadPool`, eel → `gevent.spawn`) that ALWAYS ends on done/error, +
  a UI safety net: an applier that answers WITHOUT `started` is treated as already-finished and the
  panel closes the bar itself. **RULE: every applier = worker + terminal tick; a GUI-thread applier
  both freezes the app and strands the progress bar.**
- **Language switch (עברית/אנגלית/אוטומטי) now works for VirtualDJ** - new **`kind:"xmltag"`** mechanism
  in `game_language.py` (generic: flip ONE XML element's text in a settings file, attributes preserved,
  atomic temp+replace). Config: `%LOCALAPPDATA%\VirtualDJ\settings.xml` `<language modified="yes">Arabic
  </language>`, codes english=`English` / hebrew=`Arabic` (the Hebrew ships in the Arabic slot).
  Verified on a COPY of the real file: read `Arabic`, flip → `English` → back, attrs kept, size delta 0.
  Install now auto-sets `hebrew`. `_lang_mod_installed` resolves virtualdj from the applier.
- **Beta opt-in** opened to the native download appliers (`isGowr` ⇒ GoWR/HL/W3/PT/VirtualDJ) - they pull
  their version from the Worker manifest, so a per-title override is meaningful.
- **Software wording** in the shared panel via `game.isSoftware` (`Game.isSoftware` added to
  `frontend/src/lib/types.ts`): "פתח תיקיית תוכנה", "שפת התוכנה", "קבל גרסאות בטא לתוכנה זו", and the
  remove/cache confirms. Build `20260712205214` (dev_build 56), installed LOCALLY, NOT published.

---


## VirtualDJ 2026 (build 9482) Hebrew — Phase-1 COMPLETE, menu-proof PASSED in-game, 🟢 GO (easiest tier) (2026-07-12)

New target scaffolded at `games/virtualdj/` (RECON/FEASIBILITY/PIPELINE + `tools/vdj_lang.py` +
`work/build_menu_proof.py` + `extract/`). **NOT a game — Atomix DJ software**, same groundwork applies.
Install `C:\Program Files\VirtualDJ\` = just `virtualdj.exe` (**664 MB**, everything packed inside) +
the installer MSI in the project folder. User data `%LOCALAPPDATA%\VirtualDJ\` (`settings.xml`,
`Languages\`, `Skins\`, `Cache\` — Skins/Languages empty on fresh install; downloaded on demand).
**Verdict 🟢 GO — the easiest container class in the project** (loose plain-UTF-8 XML, no
offsets/checksums/compression → identity round-trip free, no repack, no anti-cheat).

- **🔑 Text = an embedded `languages.zip` inside the exe** (carved by `tools/vdj_lang.py carve` — find the
  EOCD whose central dir lists the 12 lang XMLs) → **12 language files**: `English.xml` (source) +
  French/Portuguese/Spanish/Dutch/Greek/German/Italian/Russian/Japanese/Chinese(simplified) +
  **`Arabic.xml`** (the RTL slot). Schema = `<language lang iso author version build><Section><Key>value
  </Key>…</Section>…</language>`; **18 sections, 3,894 keys, keys IDENTICAL across langs** → EN→HE by key.
  Placeholders `%i/%s/%d/%2F/%%` (131 entries) preserved. **Codec `tools/vdj_lang.py`** (carve/parse/
  `build_hebrew(arabic,he_map)`/round-trip) — **round-trip OK** on English(3,894)+Arabic(3,882). Corpus:
  `extract/langs_orig/*.xml` + `extract/{english,arabic}.json`.
- **🔴 Language dropdown is HARDCODED** in the exe (`"English, French, …, Arabic"` — NO "Hebrew", no
  folder-name enumeration) → activation = **Arabic-slot hijack**: ship Hebrew in `Languages\Arabic.xml`
  (overrides the embedded copy) + pick **Arabic** in Options. `settings.xml` already has
  `<language>Arabic</language>` (user set it). Plan B if a folder Arabic.xml doesn't override the embedded:
  write `Hebrew.xml` + set `settings.xml <language>Hebrew</language>` directly (bypasses the dropdown).
- **Arabic already ships as a near-complete PRO translation** (3,860/3,882 keys differ from EN) → excellent
  Hebrew quality/gender cross-reference. `iso="ar"` on the slot ⇒ VirtualDJ's RTL locale path.
- **Scope:** UI **3,081** (Config 1430 · Settings 438 · skin_deprecated 303 · ContextMenu 213 · tooltips
  178 · Skin 149 · Plugins 85 · Columns 72 · Messages 60 · Errors 54 · RootElements 33 · skintooltips 33 ·
  Colors 24 · Search 17 · AudioSource 10 · EffectRoot 9 · DragDrop 7) + **813 `Actions`** = VDJScript
  command help/tooltips (technical, translate last/optional) = **3,894 total** (~212K chars). **No
  subtitles, no gender variants, no repack, no DRM/anti-cheat** → none of the usual traps.
- **✅✅ Menu-proof PASSED IN-GAME (user-confirmed "עובד" 2026-07-12).** `work/build_menu_proof.py
  --deploy` wrote `%LOCALAPPDATA%\VirtualDJ\Languages\Arabic.xml` = the Arabic skeleton + 15 overrides:
  1 Latin marker (`RootElements/Sampler`→`ZZ-VDJ-OK-ZZ`) + 14 Hebrew (browser column headers + folders),
  stored LOGICAL. **In-app result (screenshot):** the marker `ZZ-VDJ-OK-ZZ` rendered in the left folder
  tree → **the folder file OVERRIDES the embedded Arabic**; all 14 Hebrew strings (מוזיקה מקומית /
  הרשימות שלי / שולחן העבודה / כותרת / אמן / שנה / אלבום / סגנון / הערה …) rendered **clean, correct
  RTL direction, ZERO tofu** among the surrounding Arabic UI. **ALL GATES CLOSED at once:** override
  works · **bidi = LOGICAL** (store natural Hebrew, ZERO bidi code — the app RTL-renders the Arabic
  locale and Hebrew inherits it) · **font covers Hebrew — ZERO font work** (the skin font is Unicode,
  no inject/replace). Revert: `--revert`.
- **✅ Phase 2 handoff BUILT — New-Era agent (all 12 shipped langs as the meaning/gender/context oracle)**
  `games/virtualdj/agent_handoff/` ([[delegate-all-translation]]): `build_handoff.py` →
  `to_translate.json` **3,894** {key:{en, refs:{de/fr/es/it/ru/pt/nl/el/ja/zh/ar}}} (avg 10.3 ref-langs/
  line, UI-first ordering, Actions last) + `hebrew.json` + `name_registry.json` (brands stay Latin +
  DJ glossary). Loop `get_batch.py [N] [slot nslots]` → agent fills `he` (LOGICAL) → `merge_batch.py`
  (anti-cheat `_tokens.validate`: reject copy-EN-on-prose / dropped `%`-token / niqqud / foreign script /
  SKIP) → `qa_scan.py`. **New-Era rationale proven in the data: Arabic alone is wrong on many keys**
  (Message→"عيسוי"/massage, Pitch→"ملعب"/playground, TIDAL/Traktor→translated the brand) → the agent
  cross-verifies meaning+gender against ALL langs, reliable-European consensus wins. `INSTRUCTIONS.md` =
  the full Hebrew agent prompt. Loop + anti-cheat end-to-end tested (copy-EN + niqqud correctly rejected).
- **After the agent finishes** (`hebrew.json` full): build via `vdj_lang.build_hebrew(arabic_bytes,
  hebrew_map)` (LOGICAL, Arabic fallback for any untranslated) → drop one `Languages\Arabic.xml` →
  publish only on explicit "פרסם" (free per-user config drop; optional GitHub `virtualdj-hebrew-mods` +
  tiny installer + launcher applier `translation_manager/virtualdj_mod.py`).
- **✅ TRANSLATION 100% COMPLETE + DEPLOYED LOCALLY, NOT published (2026-07-12).** All 3,894 lines
  translated (a Google/Antigravity agent ran the `agent_handoff/` loop for the bulk UI + `Actions` on
  vm4 `vdj_nim.py` + Claude by hand per the user's explicit "לא מקומי רק אתה עד הסוף" override) →
  `agent_handoff/hebrew.json` full. **QA CLEAN: `qa_scan.py` = 3,894/3,894, 0 defects; independent audit
  0 token/foreign/niqqud.** ⚠️ The agent wrote `apply_translations_*.py` auto-fill scripts and left ~36
  short Skin/skin_deprecated button labels in English (LINE INPUT/MASTER EFFECT/SAVE LOOP…) via the
  name-passthrough — NEVER trust the agent's "done": Claude caught + Hebraized them (backup
  `hebrew.json.bak.skinfix.*`); 7 stay Latin legitimately (shadertoy.com, VDJ PRO/LITE, VirtualDJ HOME,
  VJ'Pro, BABY/JET SCR scratch names). `[[Manual]]→[[מדריך]]` is CORRECT (all shipped langs translate
  inside the `[[...]]`). Also caught the agent leaving ~114 single-word Skin/skin_deprecated UI labels
  English via name-passthrough (SYNC/LOOP/USER/VINYL/MASTER EFFECT/SAVE LOOP…) → Claude Hebraized ~114
  (kept genuine abbrev/brands Latin: BPM/CPU/FX/QT/AUX/RW/PRO/VDJ-LITE/FLANGER/scratch names).
  Built via `vdj_lang.build_hebrew`. Publish only on "פרסם".
- **🔑 BIDI FIX — wrap every line in RLE (U+202B)…PDF (U+202C) (2026-07-12, PROVEN in-game "A מושלם").**
  Mixed Hebrew+Latin lines (dialogs, welcome splash, any sentence with an embedded brand like "תכונות של
  VirtualDJ אינן זמינות") first rendered mis-ordered. Root-caused by an in-game A/B/C isolation on one
  dialog key: **VirtualDJ's renderer bidi's ARABIC-script correctly but detects LTR base-direction for
  Hebrew-only lines** (the app UI is LTR) → a mixed line's Latin island + sentence-final punctuation land
  wrong. Rejected: logical (wrong); `python-bidi get_display`/visual-reverse (mirrored letters — the
  engine shapes Hebrew RTL WITHIN a word itself, so DON'T pre-reverse letters); RLM U+200F prefix
  (IGNORED). **RLE U+202B…PDF U+202C per line = PERFECT.** User's insight drove it: the shipped Arabic
  ALSO embeds English brands mid-sentence and renders fine → engine CAN do RTL, just needs base direction
  forced. **`work/build_final.py --deploy`** wraps each line of every value (`wrap_rtl`, split `\n`, skip
  empty) → 3,882-key `Arabic.xml` (427KB, all RLE-wrapped), backup `.he_backup`. Safe in every widget
  (proper-bidi widget already RTL → RLE no-op; naive/LTR-base widget → forced RTL). **UNIVERSAL lesson
  for any Arabic-slot RTL hijack where mixed Hebrew+Latin mis-renders but pure Hebrew + the shipped Arabic
  render fine: force RTL base per line with RLE(U+202B)…PDF(U+202C); RLM(U+200F) is often ignored, and
  visual/letter-reversal is WRONG when the engine shapes the RTL script within-word itself.** Deployed to
  `%LOCALAPPDATA%\VirtualDJ\Languages\Arabic.xml`; publish only on "פרסם".
- **🔑 THE A/B/C IN-GAME ISOLATION METHOD that cracked the bidi (reusable for ANY RTL engine).** Five
  blind guesses failed in a row; what finally worked was **putting several candidate encodings of the
  SAME sentence in ONE visible string, labeled `A:`/`B:`/`C:`, and asking the user which reads right.**
  Each round eliminated one hypothesis in a single game launch. **The decisive round was NOT a
  judgement question but a TRANSCRIPTION one** — I stored two known strings (`שלום ABC 123` and
  `123 ABC שלום`) and asked the user to *transcribe exactly what appears*, left to right. That removed
  my dependence on unreliable screenshot OCR and on the user's (understandably varying) sense of
  "correct", and pinned the engine's actual behaviour in one shot. **UNIVERSAL: when a rendering
  hypothesis can't be settled from screenshots, stop asking "is this right?" and ask the user to
  TRANSCRIBE a known-input control string — judgement answers are ambiguous, transcriptions are data.**
  ⚠️ Also: the multi-line dialog key `Config/ManyVirtualdjFeaturesAreNot` is an ideal test surface — the
  user can re-trigger it on demand (skip-connect) and it holds several lines at once.
- **🔴 "The language file is 100%" ≠ "the app is Hebrew" — the SECOND round of English (2026-07-12).**
  After a 100% build the user still saw English. Two distinct causes, both worth checking on any target:
  1. **Single-word labels silently left English by the name-passthrough.** The QA audit only flagged
     no-Hebrew values with **≥2 words**, so ~114 single-word `Skin/` + `skin_deprecated/` button captions
     (`SYNC`, `LOOP`, `USER`, `VINYL`, `MASTER EFFECT`, `SAVE LOOP`…) passed as "names" and shipped
     English. **Audit rule: scan for no-Hebrew values with ANY real word, not just multi-word ones**, and
     bucket by section — a section like `Skin` being 71/71 English is the tell.
  2. **Surfaces that are NOT in the language file at all.** Verified by looking each visible string up as
     a VALUE in `English.xml`: the pad-page mode menu (`hotcues`, `slicer`, `cueloop`, `beatjump`,
     `saved loops`, `remix points`, `scratchbank`, `custom`…), the effect-dropdown names (`REVERB`,
     `WAHWAH`), the stem-pad captions (`Vocal`/`Kick`/`HiHat` — a `Config/*` key EXISTS but the skin
     doesn't read it), the Settings **option ids** in the left column (`autoBPMMatch` — shown in English
     in EVERY language; only the *description* is localized), and all **enum values** (`no/smart/always`,
     `auto`, `skip silence`, `1 beat`, `None/Outer/Inner`, `play-pause`). These are hardcoded in the
     skin/plugins and are English in every VirtualDJ language. **UNIVERSAL: before promising a "fully
     translated" UI, look each visible English string up as a VALUE in the source language file — a
     `key=None` result is proof it is unreachable, and saying so early prevents an endless chase.**
- **🔴 The language DROPDOWN is hardcoded in the exe — and the entry text also builds the FILENAME.**
  The Options → language list lives in `virtualdj.exe` at `0x3f4b2d8` as one ASCII string
  `"English, French, …, Chinese (simplified), Arabic"`, immediately followed by `".xml"` and
  `"\Languages"` — i.e. the code builds `\Languages\<entry>.xml`. Consequences: (a) setting the XML's
  own `lang` attribute to `עברית` does **nothing** to the menu (tested in-game — still "Arabic");
  (b) renaming the entry would also change which file is loaded; (c) the byte budget is 10 bytes
  (`Arabic` + 4 NULs) and `.xml` must survive, so `"עברית"` in UTF-8 (10 B) **cannot fit with a
  terminator** — only `Hebrew` (6 B, exact) or a CP1255 encoding would. **Decision (user, 2026-07-12):
  leave the menu reading "Arabic"** — it is only the label; the content is fully Hebrew. Do NOT patch
  the 664 MB exe for a cosmetic label.
- **📦 Local user package (2026-07-12):** `games/virtualdj/VirtualDJ_עברית.zip` (113 KB) = `Arabic.xml`
  + `הוראות התקנה.txt` (4-step Hebrew instructions: close app → `%LOCALAPPDATA%\VirtualDJ\Languages` →
  copy the file → Options → language = العربية). Source staging in `release_files/` (also holds
  `install.py` with `--revert`). **Local only — nothing published.**
- **⚖️ MONETIZATION VERDICT: distribute FREE — do NOT charge for this mod, in any channel** (manual
  download or launcher). Unlike the game mods in this project, `Arabic.xml` is a **derivative work built
  on Atomix's own shipped language file** (we start from their `Arabic.xml` skeleton and keep untranslated
  values), VirtualDJ's EULA forbids commercial use/derivative distribution, and "VirtualDJ" is a live
  trademark of a company selling subscriptions. This is a materially weaker position than the game mods
  (where the paid thing is launcher *convenience*, not the content, and there are long-tolerated modding
  communities). Only a written licence/permission from Atomix would make paid distribution safe; a
  voluntary donation with the mod itself free is the grey-but-safer middle. **This is a deliberate
  exception to [[mod-price-53-default]].** (Not legal advice.)

---


