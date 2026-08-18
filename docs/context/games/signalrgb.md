## SignalRGB Hebrew — PHASE 1 COMPLETE, menu proof PASSED in-app, 🟢 GO (easiest tier) (2026-07-20)

New target scaffolded at `games/signalrgb/` (RECON/FEASIBILITY/PIPELINE + `work/` + `extract/`).
Target `%LOCALAPPDATA%\VortxEngine\SignalRgbLauncher.exe` → the real app is
`app-2.5.74\Signal-x64\SignalRgb.exe` (114 MB, **Qt 6 + QML**, Authenticode-signed, Squirrel-updated).
**Software, not a game** (peer of VirtualDJ / Borderless Gaming). Proposed `games.id` = **`signalrgb`**,
`is_software=true`. Memory [[signalrgb-groundwork-go]] + [[qt-qm-inplace-patch]].

- **Text = 8 Qt `.qm` files embedded in the exe's qrc** (`:/i18n/SignalRgb_<locale>`), uncompressed +
  unencrypted. **There is NO disk override** — the only i18n string in the binary is that resource
  prefix and nothing registers an external `.rcc` → **the exe is the deploy target.**
- **🟢 Codec written and proven the strongest way possible: `work/qm.py` rebuilds ALL 8 shipped
  `.qm` BYTE-FOR-BYTE identically** (`python work/qm.py` → `byte-identical: 8/8`), including Qt's
  elfHash lookup table. Format facts that cost the time: block order is
  `Language, Hashes, Messages, Contexts, NumerusRules, Dependencies` (wrong order was the ONLY thing
  blocking byte-identity); message item tags 6/7/8 carry **u32** lengths, not u8; item order is
  `Translation*, [Comment], [SourceText], [Context], End`; **the Hashes block is REQUIRED** or
  QTranslator finds nothing.
- **🔑 Deploy = delta-0 in-place patch.** Every Qt resource is `{u32be length}{payload}` and the u32
  before each embedded `.qm` **equals its parsed size** (verified on all 8); Qt's reader stops at the
  first `tag == 0`, so a rebuilt `.qm` is **NUL-padded to exactly 226,603 bytes** and written over the
  Arabic one. No offset, no length prefix, no other resource in the 114 MB exe moves.
- **🔑 THE SIZE TRAP + ITS LEVER (the last real risk, closed).** The Arabic `.qm` fills its slot
  EXACTLY, so a naive Hebrew build overflows as soon as Hebrew ≥ ~0.9× English
  (ratio 0.95 → 235,059 > 226,603). Fix: Comment/SourceText/Context inside a message are only
  VERIFICATION — lookup is by `elfHash(source+comment)` alone, and lrelease itself emits the minimal
  set. Keeping only what disambiguates a collision (**1,126 messages need nothing, 687 need Context,
  0 need SourceText**) **frees 93,590 of 226,603 bytes (41%)** and re-parses to all 1,813 messages →
  a full Hebrew build fits at ratio 1.25 with 52 KB to spare. `work/size_budget.py`.
- **🔴 NO Hebrew locale, but a FULL official Arabic one** (`ar` / العربية among ~20 locales) →
  classic Arabic-slot hijack. Activation = Settings → Language → العربية, **or** the registry
  `HKCU\Software\WhirlwindFX\SignalRgb\UI` value `Locale` = `ar` (`patch_exe.py --lang ar`), read by
  `SignalTranslation::FetchCurrentLocaleFromRegistry` → an in-launcher Hebrew/English switch is a
  one-value registry write (a `kind:"registry"` `game_language.py` entry, same mechanism as SM2).
- **Scope = 1,838 unique strings / 55,571 EN chars**, median 15 (1,357 ≤25 chars, 75 >140, max 437),
  264 contexts, **no plurals, no subtitles**. Tokens: `%1..%9` ×42, literal `%` ×11, `\n` ×26,
  2 HTML tags, zero `{...}`. **A single pass — no fleet.**
- **New-Era reference panel is free**: the shipped `.qm` carry the **English source text** alongside
  every translation, so `extract/reference.json` gives ar/ko/zh_CN/zh_TW/sr/ja for ~1,790 of the
  1,838 keys. ⚠ They are MACHINE translations with real errors (`Sign Out → انقر فوق` = "click on",
  `Decline → انخفاض` = "a decrease", `Macros → ماكرون` = Macron the surname) → oracle for
  context/gender, never gospel. **No Russian and no European gendered language ships** (gender oracle
  = Arabic + Serbian; barely relevant for a UI-only corpus).
- **⚠️⚠️ NEVER identify a `.qm` by its Language block — SignalRGB ships a MISLABELED one**: the file
  serving Traditional Chinese declares `ru_RU` and contains **zero Cyrillic**. Which file serves which
  locale is decided by its qrc FILENAME. `extract_corpus.py detect_label()` labels every `.qm` by the
  SCRIPT of its translations, and `patch_exe.py find_slot()` locates the Arabic slot by CONTENT — a
  language-tag lookup would have handed the translator a "Russian" column full of Chinese and could
  have pointed the patcher at the wrong slot. **UNIVERSAL for any Qt app.**
- **Font = free** (Qt system fonts; Arabic already renders). **bidi expected LOGICAL** (Qt always runs
  the UBA) but **the proof decides — do not pre-reverse.** The app has **no `LayoutMirroring`** and
  only 2 hardcoded `Qt.RightToLeft` in unrelated components → expect correct RTL text in an
  UNMIRRORED layout, exactly like Borderless Gaming, so **no direction word gets flipped until a
  screenshot shows whether it mirrors** ([[rtl-dont-flip-direction-words]]). Optional untested lever
  for a SECOND round: Qt derives `QGuiApplication::layoutDirection()` from a translation of
  `QT_LAYOUT_DIRECTION` = `"RTL"` (absent from the shipped Arabic) → `--deploy --rtl`.
- **✅✅ MENU PROOF PASSED IN-APP (2026-07-20, user screenshot of Settings) — every gate closed by
  ONE image.** `work/build_menu_proof.py --deploy` (15/15 strings, built 226,573 B padded to 226,603).
  Results: **`ZZ-SRGB-OK-ZZ`** rendered in place of the *About* nav header ⇒ the delta-0 patched `.qm`
  loads out of the qrc · **`שמע · ניטור · מאווררים · התראות · תוספים · שפה`** rendered clean at the
  same weight/size as the surrounding Arabic, **zero tofu** ⇒ the font gate never existed (Qt system
  fallback) · every Hebrew word in **correct letter order** ⇒ **bidi = LOGICAL, store natural Hebrew,
  never pre-reverse and never inject `&rlm;`** · untouched entries still render Arabic ⇒ a PARTIAL
  translation degrades gracefully (it can ship incrementally) · Arabic paragraphs auto-right-align
  with an embedded URL staying LTR ⇒ long Hebrew paragraphs will lay out fine.
  **The Latin marker is what makes one screenshot sufficient** — it separates "the file didn't load"
  from "the font has no glyphs", which otherwise look identical.
- **⚠️ PROVEN: the app does NOT mirror its layout.** The nav panel stays on the left and its labels
  stay left-aligned — for Hebrew *and* for the vendor's own Arabic. Text direction is right, box
  direction is not, and a translation file cannot change it. ⇒ **no direction word gets flipped**
  ("the left panel" stays "הפאנל השמאלי"), per [[rtl-dont-flip-direction-words]]. Untested lever for
  a later round: `--deploy --rtl` adds `QGuiApplication/QT_LAYOUT_DIRECTION = "RTL"` (absent from the
  shipped Arabic), which is where Qt reads `QGuiApplication::layoutDirection()` from.
- **🔴 A SAFETY GUARD THAT LOCKED OUT ITS OWN REVERT (found the moment the proof was deployed).**
  `find_slot` asserted `qrc_prefix == parsed_qm_size` — true on a pristine slot, but a DEPLOYED `.qm`
  is NUL-padded, so it parses SHORTER (226,593 vs 226,603) and the guard aborted `--status`,
  `--deploy` **and `--revert`**. Fixed: the qrc length prefix is the AUTHORITATIVE slot size and only
  `parsed > prefix` means the layout moved. **UNIVERSAL: a guard on a deploy path must be evaluated
  against the ALREADY-DEPLOYED state too — an assertion that only holds on pristine input turns the
  revert into a dead end exactly when you need it.** (The pristine backup was intact and SHA-verified
  throughout, so nothing was at risk.)
- **✅ PHASE 2 TOOLING BUILT + adversarially tested.** `work/build_handoff.py` → `agent_handoff/`:
  `to_translate.json` (1,838 rows `{key:{context,en,refs}}`, **avg 5.9 reference languages per line**,
  ordered by VISIBILITY — nav/settings/onboarding 146 → feature pages 936 → other 666 → dev/diagnostic
  90, so a partial pass covers what users actually see) + `hebrew.json` + `name_registry.json`
  (50 brands/protocols that stay Latin + a locked glossary) + a full Hebrew `INSTRUCTIONS.md`.
  **`work/qa_scan.py` is the gate** — each defect class was INJECTED and confirmed caught (invented
  key · niqqud · token multiset · dropped number · missing ALL-CAPS identifier · glossary drift ·
  still-English), exit 1. `work/build_hebrew.py` runs the gate first, refuses on a defect, always
  builds from the PRISTINE backup (never from what is deployed — otherwise a dry build silently
  inherits the previous one), and auto-applies `minimize_prefixes` if the naive build overflows.
- **Safety in `patch_exe.py`**: pristine slot + offset + SHA-256 backed up to
  `%LOCALAPPDATA%\WhirlwindFX\SignalRgb\hebrew_backup\` before the first write; the patch is always
  built FROM that pristine copy (idempotent, and a re-run after a SignalRGB update re-detects the new
  `app-<ver>` and refreshes the backup); refuses to write unless the built `.qm` is exactly the slot
  size; patches a temp copy then `os.replace`s (never a half-written 114 MB exe).
- **Risks stated**: patching breaks the Authenticode signature (SignalRGB does not self-verify);
  a Squirrel update installs a new `app-<ver>` and reverts it → re-run `--deploy`; the store/effect
  catalog (`catalog_en.json`, 367 effects) is fetched from the server already localized and stays
  English.
- **✅✅ PHASE 2 COMPLETE — 1,838/1,838 translated, QA-clean, BUILT + DEPLOYED locally (2026-07-20).**
  The user explicitly overrode [[delegate-all-translation]] ("תתחיל לתרגם + עידן חדש"), so Claude
  translated all 1,838 strings by the **New-Era method** — every line decided against the panel of
  the vendor's own shipped languages (ar/sr/ja/ko/zh_CN/zh_TW, avg 5.9 per line), never from the
  English alone. Loop tooling: `work/batch.py get|put|stat` (index→key mapping so a malformed key is
  impossible) in 13 batches of 110-160.
- **The New-Era panel repeatedly beat the English**, and the vendor's MT was repeatedly WRONG:
  `Accept` vs `Agree` are one word in Arabic but split in Serbian (Прихвати / Прихватам) ⇒ `קבל` /
  `מסכים`; `Decline → انخفاض` ("a decrease") and `Sign Out → انقر فوق` ("click on") and
  `Macros → ماكرون` (Macron the surname) are pure MT garbage that a single-language check would
  have copied. **Rule that held: when one reference language diverges from the rest, it is the one
  that is wrong.**
- **Final audit (independent of the QA gate): 0 defects · 0 term inconsistencies** (every English
  term maps to exactly ONE Hebrew term across all 1,838 lines) · 53 lines intentionally Latin
  (brands/units/identifiers: SignalRGB, Pro, LED, FPS, ms, X/Y, uid, crc, N/A …) · HE/EN char ratio
  median **0.79**.
- **🔑 THE BUILD FIT WITH ROOM TO SPARE — the size trap never fired.** Hebrew came out **more
  compact than the vendor's Arabic**: the full build is **220,787 of the 226,603-byte slot (5,816 B
  headroom)**, so `minimize_prefixes` was never needed (it stays as the automatic fallback). The
  predicted overflow assumed Hebrew ≈ English length; measured, it is 0.79×.
- **⚠️ THE DEFECT I KEPT RE-INTRODUCING — a reflex U+200F before a line-initial Latin brand.** The QA
  gate caught it in batch 1 and it recurred in EVERY later batch (36 lines total). Fixing it per
  batch was the wrong response: `batch.py put` now **strips bidi controls on merge**, so the reflex
  cannot reach the file. **UNIVERSAL: when the same defect class recurs across batches, move the fix
  into the pipeline — a human/model reflex will not stop just because a gate reports it.**
- **QA-gate refinements the pass forced** (each from a real false positive): the keep-Latin
  whitelist must be matched on the **stripped** English (` FPS` has a leading space); a **fully
  upper-case source string is a styled HEADER, not a set of identifiers** (`CONFIGURE CLAUDE
  DESKTOP` demanded CONFIGURE/CLAUDE/DESKTOP all survive); and plain English words that merely
  happen to be capitalised (`PC`, `EXPERIMENTAL`, `NEW`, `ALL`) are not technical identifiers.
- **STATE**: the FULL Hebrew build is deployed in the exe (**33,364 Hebrew chars, 0 Arabic left in
  the slot**) with `UI/Locale = ar`; the pristine Arabic slot is backed up + SHA-verified at
  `%LOCALAPPDATA%\WhirlwindFX\SignalRgb\hebrew_backup\`. Revert byte-exact with
  `python work/build_hebrew.py --revert`.
- **🔴🔴 PHASE 3 — THE .qm IS NOT THE WHOLE APP (2026-07-20, user: "יש עדיין באנגלית").** With the
  .qm at 100% the user still found English on the **Macros page**, the **Fan-Curve dialog**, and the
  language picker still offered **"العربية"**. Three DIFFERENT surfaces, none reachable by the .qm —
  the same lesson as [[borderless-gaming-groundwork-go]]: *"the language file is 100%" is not
  "the app is translated"*, and the audit must be **grep the install folder + the exe**, not the corpus.
- **✅ SURFACE 2 = `Signal-x64\Macroscripts\{Inputs,Actions}\*.js` (47 loose files) — TRANSLATED.**
  The Macros page is DATA-DRIVEN: every trigger/action declares its own `this.Name`,
  `this.Description` and `Options[].label` in plain JS. Nothing goes through `qsTr()`, so none of it
  is in ANY `.qm` (proof: `Discard Original Keypress` occurs **only** in those .js — not in the exe,
  raw or compressed). Codec `work/macro_scripts.py` (structural anchors, never free-text search),
  deploy `work/build_macros.py --deploy|--revert` → **142 strings across 47 files**, backup in
  `hebrew_backup/macroscripts`, patch always built FROM the backup (idempotent + update-safe).
- **🔴 THE TRAP THAT WOULD HAVE BROKEN EVERY MACRO: a combobox `values` entry is a CODE KEY.**
  `this.actions = {"Toggle":…}` + `"values": Object.keys(this.actions)` + `this.actions[this.TargetMode]()`,
  and `if (this.terminalType === "Windows Terminal")`, and `Target Page` ships internal page ids
  (`dashboard`/`customize`/`devices`). Translating any of them yields `this.actions["החלף"]` =
  undefined at runtime. `patch()` therefore rewrites **Name/Description/label ONLY** — the 25 dropdown
  values are never touched (verified: value list byte-identical before/after). Same class as
  Borderless Gaming's C# enum dropdowns. **UNIVERSAL: in a data-driven plugin/script UI the visible
  dropdown choice is usually ALSO the lookup key — translate labels, never values.**
- **A `verify` step that re-reads from DISK caught a bug the build reported as success**: two labels
  containing an escape (`C:\\Games`) were never patched, because `extract()` returned the UNESCAPED
  string while `patch()` looked up the ESCAPED one. **UNIVERSAL: when a codec unescapes on read it
  must unescape on write-lookup too — and only a read-back check finds it, since the patcher happily
  reports "142 patched".** Also `node --check`ed all 47 files after patching (0 syntax errors).
- **✅ SURFACE 3 = a plain C string literal in the exe — the language picker's own name.** The locale
  menu is built from a table of NUL-terminated UTF-8 native names (`…Español·中文(简体)·العربية·Bahasa
  Melayu…`, 16-byte slots), so the Hebrew build still offered **العربية**. `patch_exe.LITERALS` +
  `apply_literals()` patch it **delta-0**: Qt reads it with `QString::fromUtf8(ptr)` = up to the first
  NUL, so a SHORTER replacement (`עברית` 10 B into a 14+2 B slot) simply ends earlier and the leftover
  padding is never read. Original bytes + offset saved to `hebrew_backup/literals.json`, restored by
  `--revert`. ⚠️ Hebrew is 2 B/char in UTF-8, so this lever only works where the source string is long
  enough — every entry is measured against its slot and skipped rather than truncated.
- **✅ SURFACE 4 = the 444 DEVICE PLUGINS (found PROACTIVELY, before the user hit it) — TRANSLATED.**
  Every supported device ships a `.js` plugin declaring its settings UI as `ControllableParameters`
  (`{"property":"dpi1","group":"dpi","label":"DPI 1",...}`), and those labels are what the per-device
  Settings page renders — again never through `qsTr()`. **132 unique labels → 2,312 occurrences
  patched across 776 files** (`work/build_plugins.py` + `plugins_he.json`, reusing
  `macro_scripts.patch_labels_only`). Verified: 0 unpatched, 0 combobox-value drift, 0 product-name
  drift, `node --check` clean on a 120-file sample.
  **🔑 Two carry-over rules, plus one NEW one:** `values` never (code keys, as above); **and here
  `this.Name`/`this.Description` must ALSO be left alone — for a device plugin that is the PRODUCT
  name ("Corsair K95"), which stays Latin.** That is why the plugins get a label-only patcher instead
  of reusing the Macroscripts one. `group` is likewise untouched: the four ids (`dpi`/`lighting`/
  `mouse`/`settings`) are already mapped through the app's OWN .qm (`ThirdpartySettings|lighting` →
  תאורה) — a good reminder to check whether a "raw-looking" id is already localized before patching it.
  **⚠️ Unlike the Macroscripts, plugins are refreshed from a CDN** (`cache\plugin_cdn`, patched too);
  a server refresh restores English for the refreshed files → re-run `--deploy`.
- **⚠️ RTL AUTO-ALIGNMENT CLIPS THE SETTINGS NAV HEADERS (mitigated, needs the user's eye).** With the
  whole UI in Hebrew the settings side-panel section headers render RIGHT-aligned (QQuickText
  right-aligns an RTL string when no alignment is set) and lose a fixed band at the right edge —
  `משתמש` renders as `נשתמש`, `חיוב` as `ויוב`. **The diagnostic: the loss is CONSTANT regardless of
  string length ⇒ a margin/position problem, not "the text is too long" (an overflow clips
  proportionally to the string).** A translation file cannot move the box, but a **leading NBSP
  occupies the visual RIGHTMOST slot under RTL** and pushes the letters back into view →
  `build_hebrew.LAYOUT_PAD` (applied at BUILD time so `hebrew.json` stays clean prose). NBSP and not
  a plain space, because a leading normal space collapses if the label is rendered as RichText.
  **The amount was MEASURED with a RULER, not guessed** (the RDR2 trick): the 5 headers were deployed
  with **2/3/4/5/6** NBSPs and ONE screenshot answered it — *2 → still clipped; 3,4,5,6 → intact AND
  all at the same position*, i.e. **3 is the threshold and past it the text stops moving** (the
  surplus is absorbed), so over-padding is free → shipped at **4** (answer + margin) for all five
  (User / Billing / Application / System Info / About). **UNIVERSAL: when a UI constant cannot be
  measured from outside the app, deploy a LADDER of different values in one build — the first value
  that renders correctly IS the measurement, and if every rung looks identical that is equally
  decisive (it proves the lever does nothing).** ⚠️ This also **corrects the earlier "the app does NOT
  mirror" note**: the MAIN nav does not mirror, but the SETTINGS nav auto-right-aligns its RTL text.
- **🔑 A RUNNING APP NO LONGER BLOCKS DEPLOY.** The exe is locked while SignalRGB runs, but **Windows
  lets you RENAME a running executable** (the process keeps its handle to the file whatever its name).
  `write_slot` now falls back to: move the locked image to `SignalRgb.exe.hebrew-old` → drop the
  patched copy in its place → restore the original on any failure (so a failed patch changes nothing).
  Costs the user nothing, because the `.qm` is read at STARTUP — a restart was required either way.
  The leftover `.hebrew-old` is deleted by the next deploy, once the old process has exited.
- **⛔ OUT OF REACH — the Fan-Curve dialog and the Macros page CHROME (evidence, not a guess).**
  `Curve Type`, `Stepped`, `Apply to This Fan`, `+ Create Macro`, `New Profile`, `WHEN`/`THEN` occur
  **NOWHERE**: not in the exe (UTF-8 **and** UTF-16), not zlib/zstd/gzip/brotli-compressed inside it
  (0 zstd frames at all), not in any loose file, not in the 216 runtime `.qmlc`, not in the
  QtWebEngine cache, not in the addons. The exe DOES embed QML source as plain text (`import QtQuick`
  ×889) and does hold the C++ backend (`MacrosProxy`, `macrosEnabledChanged`), so these labels are
  produced by code at runtime (auto-generated / composed), not stored anywhere a file can reach.
  Note the signature that dates them: the .qm has `Apply to all Fans` and `Create New Macro` while the
  screen shows `Apply to All Fans` and `+ Create Macro` — **rewritten pages whose new strings were
  never re-run through lupdate**. Nothing short of patching code reaches them; not attempted.
- **✅ PUBLISHED (2026-08-01, user said "תעלה ותוסיף לאתר … + מתאים להתקנה … ב 15 ש"ח + לעלות
  את התרגומים").** All live:
  - **Images** — the user supplied a portrait poster (cover) + a wide desk shot (banner) + a logo.
    Processed via `game-art-assets` (cover 600×900 webp, banner 1600×517 webp, logo contain 360×138
    png) → `covers/signalrgb.webp` · `covers/banners/signalrgb.webp` · `covers/logos/signalrgb.png`.
  - **The mod package** — `games/signalrgb/release_files/` (self-contained `install.py` +
    `qm.py`/`patch_exe.py`/`macro_scripts.py`/`build_macros.py`/`build_plugins.py` +
    `hebrew.json` **padded** + `macros_he.json` + `plugins_he.json` + Hebrew readme); packer
    `pack_and_release.py`. GitHub **`hebrew-translation-hub/signalrgb-hebrew-mods` v1.0.0-beta.1**
    (77,051 B, sha `785f8886…`), Worker slug **`signalrgb-hebrew`** deployed (`/manifest` + `/archive`
    verified), Supabase `games` row (**price ₪15 = 1500**, is_software, available/beta) +
    `mod_version_history` (id 23, is_current).
  - **/translate pool** — `work/build_ct_strings.py` → **2,095 rows** in 5 visibility categories
    (ממשק ותפריטים 1082 · מאקרו 134 · הגדרות התקנים 123 · תיאורים והודעות 666 · כלי פיתוח 90).
    `string_key` carries its surface: **`ui:<ctx\x1fsrc\x1fcomment>` · `macro:<en>` · `plugin:<en>`**.
  - **Launcher install (₪15)** — native applier `translation_manager/signalrgb_mod.py`
    (cloud-first: downloads the package, runs its bundled `install.py` deploy/revert in-process;
    backups live in the app's own `hebrew_backup`, game-update-aware). Wired end-to-end:
    `software_catalog.py` + a `software_detector.py` **glob branch** (SignalRGB lives in a versioned
    `%LOCALAPPDATA%\VortxEngine\app-*\Signal-x64\`, so it can't be a fixed path — pick the newest),
    `main_eel` RPC block + `_SRGB_ID` in the `has_mod`/`_mod_state`/`_lang_mod_installed` sites,
    bridge slots (worker + terminal tick, DRM-gated in the worker), `eel.ts` + `GameDetailPanel`
    `NATIVE_DL_API` entry. **A new `kind:"regsz"` in `game_language.py`** (a REG_SZ registry value,
    unlike the existing DWORD `registry`) drives the Hebrew/English switch — `HKCU\…\SignalRgb\UI`
    `Locale`. **🔑 The app CANONICALISES `ar` → `ar_EG`** (its Arabic-slot locale id = the `.qm`
    slot), so the switch's `hebrew` code must be **`ar_EG`** (what is actually stored) even though
    the installer writes `ar` — otherwise the switch reports "other" instead of "hebrew". Built +
    installed LOCALLY (per the standing rule); reaching other users needs a launcher **publish**.
  - **THE MONETIZATION NOTE:** the user set ₪15 directly (like VirtualDJ). SignalRGB's `.qm` is a
    from-scratch corpus (more defensible than a derivative-of-vendor-file), but it IS a patch of
    Image-Line-class commercial software + trademark — the ₪15 is the user's call, recorded, not
    re-litigated ([[can-this-mod-be-sold]]).
  ⚠️ The release ships THREE payloads via one `install.py`: the exe slot patch, the Macroscripts,
  AND the device plugins — a package that only covered the .qm would leave 2,300+ strings English.

---



