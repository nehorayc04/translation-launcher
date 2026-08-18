## Borderless Gaming Hebrew — Phase-1 COMPLETE, menu proof PASSED in-app, 🟢 GO (easiest tier in the project) (2026-07-19)

New target scaffolded at `games/borderless_gaming/` (RECON/FEASIBILITY/PIPELINE + `work/` +
`extract/`). Install `F:\SteamLibrary\steamapps\common\Borderless Gaming`, Steam appid **388080**.
**Software, not a game** (like VirtualDJ) — a .NET + **Avalonia** borderless-window/upscaler utility.
Verdict **🟢 GO, the easiest container class yet: none.** Memory [[borderless-gaming-groundwork-go]].

- **Text = loose `languages/<code>.json`** — plain UTF-8, 2-space indent, **CRLF**, no BOM, nested
  objects, leading `"$schema"`. 30 shipped languages + `schema.json`. **No archive, no compression,
  no encryption, no repack.** Codec `work/bg_lang.py` (`flatten`/`unflatten`/`build_hebrew`/`dump`,
  selftest) **identity-rebuilds ALL 30 shipped files BYTE-IDENTICAL.**
- **Scope = 343 strings / 10,284 EN chars** (239 ≤25 chars, 4 >140; UI only, no subtitles) — a
  single-pass translation, **no fleet, no NIM streams, no gender oracle**. Tokens to preserve:
  only **`{0}` ×23, `{1}` ×7, `\n` ×3**. ar-SA has the identical 343-key set (0 missing).
- **🔑 ADD a real `he-IL` — do NOT hijack the Arabic slot** (a first for this project). Evidence the
  picker is DISCOVERED, not hardcoded: `es-419` (a shipped file) is not a literal anywhere in the
  exe; every file carries its own `Language.Name`+`Code` (exactly what a scanner needs); the exe has
  `"Failed to create languages directory"` + a `*.json` filter; and the app **creates an empty
  `languages/` folder in `%APPDATA%` on first run** = a user-side override folder.
  **⚠️ FALSE POSITIVE that nearly misled the recon: `he-IL` occurs 16× in the exe — but so does
  `ar-SA`, and the surrounding bytes are the standard .NET/ICU culture table
  (`uz|tt|pa|…|ar-SA|bg-BG|…|he-IL|…`). A locale code appearing in a .NET binary proves NOTHING;
  check what its neighbours are.**
- **bidi = LOGICAL, zero bidi code — PROVEN in-app.** The exe carries Avalonia's full Unicode Bidi
  Algorithm (`LeftToRightEmbedding`/`RightToLeftIsolate`/`PopDirectionalFormat`/`FirstStrongIsolate`),
  same class as Hogwarts/UE, and the proof confirmed it (the trailing `...` of `חיפוש חלונות...`
  rendered on the LEFT). Never pre-reverse, never inject `&rlm;`/RLE.
- **Font = FREE, PROVEN in-app (zero tofu).** Only `Inter-{Thin..Bold}.ttf` + `Roboto-Light.ttf` are
  embedded as Avalonia resources and Inter has no Hebrew — **but it also has no Arabic/Thai/CJK, and
  the app ships ar/th/zh/ja/ko**, so system-font fallback was already load-bearing; `אפקטים` /
  `חיפוש חלונות...` rendered clean. **UNIVERSAL: when a UI toolkit bundles a Latin-only font yet
  ships non-Latin locales, font fallback is already proven by the shipped languages — no injection
  sub-project needed. That inference held exactly.**
- **⚠️ Cosmetic, not data-fixable: the app does NOT mirror its layout** (no per-culture
  `FlowDirection`) — text is correctly RTL but panels/labels stay LTR-aligned. Not a blocker; a
  language file cannot change it. Re-judge after a full Hebrew pass.
- **Deploy = ONE file, user-side, Steam-proof:** `%APPDATA%\coreutils\borderless-gaming\languages\
  he-IL.json`. The install folder is **never touched** → Steam "Verify integrity of game files"
  cannot revert the translation, and no admin rights are needed. Removal = delete the file.
- **Activation = a flat JSON key.** `%APPDATA%\coreutils\borderless-gaming\settings.json` holds
  `"language": ""` → an in-launcher Hebrew/English switch is a one-key edit (a new `kind:"json"` for
  `game_language.py`), the cleanest activation of any target so far.
- **⚠️ `schema.json` is `additionalProperties:false` with every section `required`** → the Hebrew
  file's key set must match `en-US.json` EXACTLY. `build_hebrew` clones the English tree and swaps
  only leaves (untranslated → English, never blank), so the key set can't drift.
- **⚠️ ENV-REDIRECTION, newly sharpened:** `%APPDATA%` **and**
  `SHGetKnownFolderPath(FOLDERID_RoamingAppData)` BOTH return the Antigravity sandbox profile —
  **only `FOLDERID_Profile` is real.** The first proof deploy silently wrote into the sandbox and
  the app would never have seen it. Build user paths as `FOLDERID_Profile / AppData / Roaming`
  (`work/build_menu_proof.py:real_appdata`). **The tool SHELL is redirected too** — `$env:USERPROFILE`
  inside the PowerShell tool resolves to `…\AntigravityProfiles\translation-profile3`, so even a
  one-liner that "just lists the folder" inspects the wrong tree; hardcode `C:\Users\Nehoray_Cohen`
  when eyeballing real user data. And setting `APPDATA=` for a Python call does NOT help either —
  these scripts resolve `FOLDERID_Profile` themselves (correctly) and ignore the env var.
  [[env-redirection-real-home]]
- **✅✅ MENU PROOF PASSED IN-APP (user screenshot, then reverted).**
  `work/build_menu_proof.py --deploy` wrote a `he-IL.json` with 10 Hebrew leaves + the Latin marker
  **`ZZ-BG-OK-ZZ`** in `App.Title`; ONE screenshot of Settings → Language + the title bar closed
  every gate at once: **עברית** appeared in the picker (discovery ⇒ add a real locale, no Arabic
  hijack) · the marker showed in the title (the added file really loads, proven independently of
  fonts) · `אפקטים` + `חיפוש חלונות...` rendered clean with **zero tofu** (font free) · the `...`
  landed on the LEFT (bidi LOGICAL) · everything untranslated stayed English (the fallback works).
  **The Latin-marker trick is what makes one screenshot sufficient — it separates "the file didn't
  load" from "the font has no glyphs", which otherwise look identical (blank/boxes).**
  `--revert` deletes the file AND resets `settings.json` `"language"` to `""` (the app persists the
  picked locale; if it is open it may rewrite that on exit — then pick English in the UI).
- **✅ PHASE 2 DONE — 343/343 translated + QA-clean + DEPLOYED (2026-07-19).** The user explicitly
  overrode [[delegate-all-translation]] ("תרגם אתה חד פעמית עם העידן החדש"), so Claude translated all
  343 strings **using the New-Era method**: `work/build_reference.py` builds
  `extract/reference.{json,txt}` = every key beside its EN **and the shipped ar/de/fr/ru/es/it**
  (coverage 334/327/332/334/326/328 of 343), and every line was decided against that panel rather
  than from the English alone. Output `hebrew.json`; gate `work/qa_scan.py`; build+deploy
  `work/build_hebrew.py --deploy` (refuses to build on a failing QA). **337 translated, 6 Latin on
  purpose** (brand ×2, `he-IL`, `X:`/`Y:` ×2 pairs). Awaiting the user's in-app look.
- **🔑 WHAT THE NEW-ERA PANEL ACTUALLY CAUGHT (why it beats translating from English):**
  (a) `Search windows...` — ar `البحث` (masdar) + ru `Поиск` (noun) ⇒ a NOUN `חיפוש חלונות...`, not
  an imperative; (b) `Make Borderless` — ar `إزالة الحدود` + ru `Убрать рамки` literally *remove the
  borders* ⇒ `הסר מסגרת`, a semantic choice the English never states; (c) `A-Z / Z-A` — ar ships
  `أ-ي` and ru `А-Я`, i.e. the alphabet itself is LOCALIZED ⇒ `א-ת / ת-א`; (d) `preset` is a
  loanword in ru/es/it ⇒ `פריסט` rather than a clumsy calque.
- **🔴🔴 THE TRAP ONLY THE PROOF SCREENSHOT COULD CATCH: "the left panel" must stay LEFT.**
  Two strings (`Profiles.Empty.Tip`, `EffectEditor.EmptyChain.Description`) point the user at the
  *left* panel. The reflexive RTL instinct is to flip it to "הימני" — **but the proof proved the app
  does NOT mirror its layout**, so the windows/effects list is still physically on the LEFT. Flipping
  it would have sent every user to the wrong side of the screen. **UNIVERSAL: never flip a
  directional word ("left panel", "on the right") for an RTL translation until you have SEEN whether
  the app mirrors its layout — the bidi answer and the layout answer are independent.**
- **Also worth keeping: `Frame` → `פריים`, deliberately NOT `מסגרת`** — in this app `מסגרת` is
  already taken by *border* (the whole point of the product), so the obvious word would collide with
  the core term. And a quoted option name inside a description (`'Flip processing order'`) must match
  that option's own Hebrew label verbatim — `qa_scan.py` has a `CROSS_REF` check for exactly that.
- **🔴🔴 A SECOND TEXT SURFACE existed and the language file could never reach it — the effect
  editor (2026-07-19). User: "עדיין יש אנגלית".** The categories / effect names / parameter labels
  and tooltips are authored as attributes INSIDE the 107 `.slang` shader sources
  (`[bgfx::EFFECT("CRT Easymode",2)] [bgfx::CATEGORY("CRT")] [bgfx::PARAM("Sharpness Horizontal",…)]`)
  — **720 unique strings / 26,909 chars, i.e. 2.6× the language file itself.** Proof they are not in
  the binary: `"Anti-Aliasing"`/`"Upscaling"` do not occur in `BorderlessGaming.exe`.
  **UNIVERSAL: "the language file is 100%" is not "the app is translated" — grep the install folder
  for text authored OUTSIDE the localization system before declaring a target done.**
- **🔑 THE MECHANISM: patch the compiled-effect CACHE, not the sources.** Settled by three in-app
  proof rounds, each answering a question the previous one exposed:
  (1) a user-side `.slang` **does override** the installed one (the CRT tree showed the markers in
  place of CRT Easymode/CRT Geom — still 5 entries, not 9 ⇒ override, not additive);
  (2) but Hebrew never survives Slang's reflection step — raw UTF-8 **with and without a BOM** is
  rejected with `'3' is an invalid escapable character within a JSON string. Path:
  $.parameters[0]…userAttribs[0].arguments[0]` (the reflection JSON escapes non-ASCII with **C-style
  OCTAL escapes** `\327`, which JSON forbids), and `\uXXXX` is swallowed undecoded (rendered as
  `05D705D3…`). All 107 shipped shaders are pure ASCII with no BOM, so upstream never exercised it;
  (3) `cache/effects/*.bin` is a **.NET `BinaryWriter` stream — every string length-prefixed UTF-8,
  so Hebrew is legal — and its validity key is the SHA-256 of the SOURCE, stored inside the cache.**
  We never touch the source ⇒ the patched cache stays valid, the app never recompiles, and the broken
  JSON stage never runs. Verified in-app (category `סרט`, `ZZ-CACHE-OK-ZZ`, Hebrew parameter labels).
  **UNIVERSAL: when a build/reflection stage rejects your script, look for a post-compile cache whose
  validity key is a hash of the SOURCE — patching it is invisible to the validator and skips the
  broken stage entirely.** [[patch-the-compiled-cache]]
- **⚠️ Patch by STRUCTURE, never by free-text search: 49 metadata strings occur more than once**
  (an effect name that equals a pass name, e.g. `CAS`). `work/bg_cache.py` reads the header fields at
  their exact spans and anchors every parameter on the Slang **variable name**.
- **✅ DONE + DEPLOYED: 535 strings across 106 effects** (`work/build_effects.py --deploy|--revert`,
  gated by `work/qa_effects.py`; translations in `effects_he/{categories,names,descriptions,labels,
  tooltips}.json`; scope report `work/scan_effects.py`). **Idempotent** — a pristine copy of every
  entry lives in `%APPDATA%\…\hebrew_backup\effects\` and the patch is always built from it; after a
  software update the cache recompiles in English, so **just run `--deploy` again** (it detects the
  new hash, refreshes the backup, re-applies). All 106 entries re-verified hash-valid after deploy.
  Deliberately skipped: the 176 `PASS` names (`Conv-4x3x3x16`, `Depth-to-Space`) — internal NN layer
  names, meaningless to translate.
- **🔑 THE QA GATE PAID FOR ITSELF — 9 real defects caught pre-deploy**, all of a kind that reads fine
  in Hebrew and is silently wrong: **numbers that evaporated in translation** (`3D`→"תלת-ממד",
  `2-lobe`→"דו-אונתי", `Set to 0 to disable`→"אפס מבטל" — the value the user needs, gone);
  **technical identifiers translated into words** (`INPUT`, a shader texture name; `OSD`); **two
  U+200F bidi marks I added by reflex**, against this target's own rule (Avalonia runs the UBA — store
  LOGICAL); and **a key I invented that does not exist in any shader** (would have translated nothing,
  silently). `qa_effects.py` therefore checks number multisets + ALL-CAPS/camelCase token survival +
  key existence, not just niqqud/foreign-script. **UNIVERSAL: for technical UI text, "every number and
  every identifier in the source must survive into the translation" catches more real damage than any
  linguistic check.**
- **Locked glossary — four collisions that would have confused users:** `Kernel → ליבה` vs
  `Grain → גרעיניות` (both are "גרעין"); `Strength → עוצמה` vs `Intensity → עצימות`;
  `Luminance → לומיננס` vs `Brightness → בהירות`; and the category **`Temporal → "בין-פריימים"`**,
  because "זמני" reads as *temporary* — the opposite of the meaning.
- **⛔ Untranslatable by design (do NOT chase):** every **dropdown value** (`Auto/Integer/Fit/Stretch/
  Fill`, Window Size Mode, Borderless Mode, Sync Mode) is a C# enum name — **all 343 language keys were
  checked and the app has NO `.Values`/`.Items`/`.Enum` convention anywhere**, so no dropdown value in
  the whole app is localizable; and `New Preset` (the default name of a new preset) is a hardcoded
  literal, while the *button* `EffectEditor.NewPreset` does have a key and IS translated. Patching the
  exe was rejected on purpose: a 71 MB single-file managed bundle, reverted by every update and by
  Steam file verification — the opposite of the property that made the user-side deploy worth choosing.
- **✅ PUBLISHED FREE, website + launcher (2026-07-19).** GitHub release `v1.0.0-beta.1` on
  `borderless-gaming-hebrew-mods` (`borderless_gaming_hebrew.zip`, 31,142 B, sha
  `42a90614b2b2b37cff1772a5879648e9ba3f70481ce8d20b00011444ba3b77fa`) · Worker slug
  `borderless-gaming-hebrew` deployed · Supabase `games` + `mod_version_history` with
  **`price_cents = 0`** (the user asked for חינם — a deliberate exception to
  [[mod-price-53-default]]) + `is_software=true` + both show-flags. Artwork uploaded to the `covers`
  bucket. The zip ships a self-contained `install.py` (finds the Steam library via
  `libraryfolders.vdf`, writes ONLY into `%APPDATA%`, `--revert` restores byte-identical) +
  `bg_cache.py` + `he-IL.json` + the 5 `effects_he` tables. Installer tested in an isolated
  `APPDATA`: install · hash-valid · idempotent · byte-identical revert · graceful on a machine
  where the app never ran (no cache yet).
- **Launcher applier `translation_manager/borderless_gaming_mod.py` DONE** (native, cloud-first via
  `_BG_SLUG`): download → SHA-verify → write the language file AND patch the effect cache, with a
  `hebrew_backup` for byte-identical removal. Wired through `main_eel` (4 RPCs) + `bridge.py` (the
  two heavy slots off-thread, 300 s — they rewrite ~106 cache files) + `eel.ts` + `NATIVE_DL_API` in
  `GameDetailPanel` (`gated:false`). Verified against the LIVE Worker end-to-end: 535 strings across
  106 effects, 106/106 Hebrew, 0 hash-invalid.
- **🔑 `software_detector.py` gained REAL Steam-library detection** (`_steam_libraries()` parses
  `libraryfolders.vdf` on every drive + registry `SteamPath`/`InstallPath`; new
  `SoftwareFingerprint.steam_dir` matched in a Pass-0 branch). It previously knew only fixed paths —
  a Steam app can live in ANY library folder, and this machine has it in TWO of them.
- **⚠️ The GitHub account is an ORG now: `hebrew-translation-hub`** (repos transferred from the
  `nehorayc04` USER; both accounts exist, and GitHub permanently redirects the old repo paths, so
  `nehorayc04/...` URLs still resolve to the same release assets). The API's `full_name` is the
  canonical truth. **Do NOT "fix" the org name back** — the source files and the Worker map are
  correct; all 10 slugs verified 200 after the rename.
- **🔑 UNINSTALL LESSON — for a hash-keyed cache patch, DELETE the entry, don't restore it
  (universal, [[patch-the-compiled-cache]]).** `build_effects.py --revert` copies each backup back
  and then **`unlink()`s it**, so the backup set is **single-use**: after one revert
  `hebrew_backup/effects/` is empty, a second revert prints "restored 0", and any entry that PREDATES
  the backup (here the 2 `Film_*` proof files) stays Hebrew **forever** — the source hash still
  matches, so the app never recompiles it. The clean fix is to **delete those `.bin` files**: the
  `.slang` sources were never touched, so the app rebuilds them in English on next start. **That is
  the whole point of a cache — a patched cache entry is always disposable, and "delete" is a safer,
  more idempotent uninstall than "restore" whenever the original is reproducible from an untouched
  source.** (A restore-based revert should also NOT consume its own backup, or it can only ever run
  once.)
- **✅ Community `/translate` pool LIVE — 791 rows in 4 Hebrew categories (2026-07-19).**
  `work/build_ct_strings.py` → `extract/ct_upload.json` → `universal/community_translate.py import
  borderless-gaming`. Ordered by VISIBILITY [[community-pool-by-category]]: **ממשק ותפריטים 342 →
  שמות אפקטים וקטגוריות 29 → הגדרות אפקטים 149 → תיאורים והסברים 271**. All 791 arrive with
  `current_he` filled (improve-mode, like Anno/GTA), seeded from the value the BUILD emits.
  Verified through the PUBLIC API, not the importer's message: 4 Hebrew category chips with exact
  counts, and the picker's "בחרו תוכנה" section now lists **virtualdj + borderless-gaming** (the
  page splits by the catalog's `isSoftware`, so a software row needs NO frontend change).
- **🔑 `string_key` carries its TARGET TABLE as a prefix — `ui:<dotted path>` · `fx.<table>:<english>`**
  (`fx.categories` / `names` / `labels` / `descriptions` / `tooltips`). This game has TWO build
  surfaces keyed differently (the language file by dotted path, the 5 effect tables by the ENGLISH
  string), so a bare key could not say where an approved line goes. **Verified before importing: all
  791 keys map back onto the real build files with 0 mismatches** — the round-trip check is what
  makes `community_translate.py export` droppable straight into the build.
- **⚠️ 96 rows deliberately NOT uploaded** — `Language.Code`, the 3 metadata placeholders
  (`Category`/`desc`/`...`), and **90 effect names that stay Latin on purpose** (Anime4K, AMD CAS,
  FSR, CRT Easymode…). **Uploading a brand with an empty `current_he` reads as "please translate
  me"** and invites a contributor to Hebraize a product name — so an entry with no Hebrew in the
  build tables is dropped, not seeded blank. (The 176 `PASS` names were never in the corpus.)
- **⚠️ `action=games` is edge-cached (`s-maxage=120, swr=600`), so a freshly-imported game is
  MISSING from the picker feed for a couple of minutes** even though the data is correct. Diagnose
  with a cache-buster (`&cb=<ts>` → `X-Vercel-Cache: MISS`) before suspecting the import; the normal
  feed catches up on the next revalidation (observed HIT → 19 games).
- **Full local reset** (what to run to demo the launcher install end-to-end on a machine that already
  has the mod): delete `languages/he-IL.json`, set `settings.json` `"language": ""`, delete any
  still-Hebrew `cache/effects/*.bin`, drop `hebrew_backup/`, and remove
  `~/.translation_manager/mod_cache/borderless-gaming` so the launcher card returns to "התקנה".
  ⚠️ **Close the app FIRST** — it rewrites `settings.json` on exit (so a reset done while it runs is
  undone), and it can run **ELEVATED**, in which case `taskkill /F` answers **Access denied** from
  this environment and the USER must exit it from the tray icon.
- **Remaining (optional):** a `kind:"json"` language switch on `settings.json` for
  `game_language.py`; publishing the launcher BINARY (the catalog card is already live for everyone,
  but the one-click install button needs a launcher release — the 1.1.0 build is local-only).

---


