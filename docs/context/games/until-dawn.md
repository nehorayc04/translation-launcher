## Until Dawn (2024 remake) Hebrew — Phase-1 COMPLETE, menu-proof PASSED in-game, GO (2026-07-08)

New game scaffolded at `games/until_dawn/` (RECON/FEASIBILITY/PIPELINE + `tools/` + `work/`).
Install `F:\Games\Until Dawn` (FitGirl repack, DRM-free), Ballistic Moon / Sony, internal
codename **"Bates"**, **Unreal Engine 5** (PS5/XSX targets, DLSS/FSR3, Sentry SDK). No Denuvo/
EAC/BattlEye. **Verdict 🟢 GO — the easiest container+codec combo in the whole project so far**:
no reverse-engineering was needed at all.

- **Container = stock Pak V11, NOT encrypted — identical format to Hogwarts Legacy.**
  `Bates/Content/Paks/Bates-Windows.pak` (8.46 GB) + IoStore `.ucas`/`.utoc` (41.4 GB) sit
  side by side, but **all loose files (Config, .uproject, every `.locres`, every `.ufont`)
  live in the legacy `.pak` only** — the 41 GB IoStore container never needs touching.
  `games/hogwarts_legacy/tools/repak.exe` (already in the repo, unchanged) reads/writes it
  directly: `repak info/list/get/pack` all verified working.
- **Text = Unreal's own PUBLIC, DOCUMENTED LocRes format** (`FTextLocalizationResource`) —
  a first for this project: every other game needed a proprietary format cracked from
  scratch; here the spec was fetched straight from the open-source reference implementation
  **`akintos/UnrealLocres`** (`LocresLib/LocresFile.cs`, via `curl`/WebFetch) and ported to
  pure Python as `games/until_dawn/tools/ud_locres.py` (`load`/`save`, version 3 =
  Optimized_CityHash64_UTF16). Since translation only ever changes VALUES for EXISTING keys,
  the writer reuses the read namespace/key hash bytes verbatim — no CityHash64/CRC32
  implementation needed. **Round-trip verified:** identical (key,value) sequence, identical
  file size, not byte-identical (string-table internal order differs — harmless, the reader
  discards refCount at load time; same "semantic-PASS not byte-identical" pattern as GoT/TLOU2).
- **20 LTR locales (da/de/en/es/fi/fr/it/ja/ko/nl/no/pl/pt/ru/sv/tr/zh…), ZERO Arabic/Hebrew**
  → AC2/Anno/GTA/TLOU-class **LTR-slot hijack**, not the Arabic-slot trick. `en` is the true
  superset (every other locale's key set is a strict subset, 0 extra keys anywhere) — clean
  EN→HE mapping by key. All text (UI + story dialogue + bonus-material captions) sits in
  **ONE StringTable namespace `ST_Localized`**, classified by **key-name prefix** (no `enum`
  field like WD2): `BATES_*`=UI/settings (764) · `SMG###_*`=story dialogue (11,632) ·
  `Bonus_Material_*`/`bts_video_*`=making-of captions (~266, optional/low-priority) ·
  `.HOWTO`=a literal dev-instructions row, skip. **Total 12,689 entries / 9,863 unique.**
  Game exposes **3 independent language settings** (Speech/Subtitle/Text Language) — English
  VO is preserved regardless of which Text/Subtitle locale is chosen (same as every other game
  here).
- **Font — the easiest case in the project: `.ufont` cooks with NO wrapper at all.**
  `repak get` returns each `.ufont` as a byte-identical bare TTF/OTF (sfnt magic at offset 0).
  Two families, 0/27 Hebrew on both (cmap-verified): **Univers** (6 weights, TrueType/`glyf`)
  → Anno-style glyph MERGE; **Cotford** (3 weights, CFF/PostScript) → glyf-merge is a no-op on
  CFF → TLOU1-style REPLACE (donor font + masqueraded `name` table). Both built +
  offline-verified 27/27 Hebrew / 26/26 Latin preserved (`games/until_dawn/tools/ud_font.py`).
  `FallbackFonts/` per-script folders exist (Cyrillic/JP/KR/Chinese) but none for Hebrew/Arabic.
- **✅ ALL THREE open questions closed by ONE screenshot (2026-07-08, user-confirmed
  "עובד").** `work/build_menu_proof.py` had patched BOTH `en/Game.locres` (Latin marker
  `ZZ-UD-EN-OK-ZZ`) and `tr/Game.locres` (marker `ZZ-UD-TR-OK-ZZ`, Turkish = "any non-native
  LTR locale" fallback candidate) with the SAME 8 Hebrew test strings in menu/settings keys
  (Load Game/Quit/Language/Text Language/Subtitle Language/Speech Language/chapter-select
  title/press-any-button splash) + Hebrew-injected fonts, deployed additively to
  `Bates/Content/Paks/~mods/pakchunk999-Windows_P.pak` (8.4 GB base pak untouched, exact
  `_P`-suffix naming convention proven on Hogwarts Legacy). **Result:** the main menu showed
  `BATES_MENU_QUIT` as clean **"יציאה"** with Text Language left at the DEFAULT (English,
  zero setting changed) — the best possible outcome: (1) **`en` slot loads** even though it
  equals the native culture (no Turkish fallback needed, simplest possible end-user
  activation — install and play, nothing to change in Settings), (2) **bidi = LOGICAL**
  confirmed correct (not mirrored), (3) **font renders cleanly** (no tofu, same visual weight
  as the surrounding Latin menu text). Revert = delete the one pak file
  (`python work/build_menu_proof.py revert`).
- **✅ PUBLISHED as "בקרוב" on the website + launcher (2026-07-08, DB-only, no deploy/rebuild).**
  User asked to list the game before starting Phase 2. Artwork (3 user-supplied PNGs) processed +
  uploaded to the public `covers` bucket: cover `until-dawn.webp` (600×900 → **300×450** webp q82),
  banner `banners/until-dawn.webp` (1920×620 → **1600×517** webp q82), logo `logos/until-dawn.png`
  (1334×588 RGBA → **360×138 "contain"**, aspect preserved + transparent pad — do NOT stretch a
  logo to the box). Supabase `games` row id=**`until-dawn`** (`availability=coming-soon`,
  `status=locked`, price 0, `show_on_website`+`show_on_launcher`=true, title_he "עד עלות השחר",
  sort_order 10003). **Verified live on BOTH surfaces with zero deploy** — `hebrew-translation-hub
  .com/api/games` (website) AND the anon-key REST read (the launcher's `_try_supabase_catalog`
  path, `select=*`) both return it. **Bundled/offline parity also updated** (only matters for a
  future launcher build / cold boot): `games_catalog.py` + `games.json` + **`game_detector.py`**
  (`_PATTERNS["until-dawn"]=["untildawn","untildawnremake","bates"]`,
  `_EXE_PATTERNS=["Bates.exe","Bates-Win64-Shipping.exe"]`, `_EXE_SUBDIRS` += `Windows`,
  `Windows/Bates/Binaries/Win64`) — all three detection paths verified against the REAL install
  (folder name, codename, exe fingerprint) → `until-dawn`. 2 news drafts pushed.
- **✅ Community `/translate` pool LIVE — 12,617 rows (2026-07-08).**
  `work/build_ct_strings.py` extracts the EN corpus from the LIVE pak (`repak get` → `ud_locres`)
  → `extract/{en.json,ct_upload.json,report.txt}` → `universal/community_translate.py import
  until-dawn`. Kept **12,617** of 12,689; dropped 72 (settings VALUES identical in every language
  — resolutions/FPS/Hz/aspect/bare numbers — plus pure-numeric timestamps and the `.HOWTO` dev
  note). Categorized by key prefix into 3 Hebrew visibility buckets, **UI first**
  ([[community-pool-by-category]]): **ממשק ותפריטים 780** → **כתוביות עלילה 11,570** →
  **חומרי רקע (מאחורי הקלעים) 267**. `string_key` = **the raw game key** (unique per row, so it
  maps back 1:1 at Phase-2 build — no md5-dedup indirection needed, unlike TLOU1/TLOU2 where many
  SIDs share one EN); `current_he=''` (fresh game); `source_en` and the future Hebrew both come
  from the SAME authoritative `en/Game.locres`, so the WD2 mis-pairing trap can't occur. Verified
  live: `/api/translate?action=games` → until-dawn total **12,617** / untranslated_open **12,617**.
- **Phase 1 COMPLETE + listed + pool live. Next = Phase 2** (delegate translation of the 12,617
  strings per [[delegate-all-translation]] → build via `ud_locres.save` + `ud_font.inject` →
  `repak pack V11` → `~mods` → publish) — **awaiting the user's go-ahead; NOT started.**

### 🌍 Universal lessons from the Until Dawn round (apply to every future game)

1. **🔑 CHECK WHETHER THE FORMAT IS PUBLIC BEFORE REVERSE-ENGINEERING IT.** Every prior game here
   needed a proprietary container/codec cracked from scratch (sometimes for days). Until Dawn's
   text format is Unreal's OWN documented `FTextLocalizationResource`, and a complete open-source
   reference implementation (`akintos/UnrealLocres`) gave the exact byte layout in ~2 minutes via
   `curl raw.githubusercontent.com`. **First move on any new game: identify the engine, then search
   for an existing open-source reader/writer for its text+container.** The container was likewise
   free (`repak`, already vendored for Hogwarts Legacy). Cost: minutes instead of days.
2. **🔑 A writer that only changes VALUES does not need the format's HASH function.** LocRes v3
   stores precomputed CityHash64-of-UTF16 hashes for namespace/key NAMES. Since translation only
   ever rewrites values for EXISTING keys (never adds/renames a key), the writer **reuses the hash
   bytes it read** — so no CityHash64/CRC32 had to be implemented in Python at all. Generalizes to
   any format with precomputed hashes/checksums over fields you aren't touching: **copy them, don't
   recompute them.**
3. **🔑 In a hybrid UE4/UE5 game (`.pak` + IoStore `.ucas`/`.utoc`), every LOOSE file lives in the
   legacy `.pak`.** Config `.ini`, `.uproject`, all `.locres`, all `.ufont` were in the 8.4 GB pak;
   the 41.4 GB IoStore container never had to be parsed or even opened. Check the pak's file list
   FIRST before assuming a modern UE title requires IoStore tooling.
4. **`.ufont` is a bare TTF/OTF — no uasset wrapper** (sfnt magic literally at offset 0). Always
   check the magic before writing wrapper-parsing code.
5. **Font injection technique is decided by the OUTLINE format, not the file extension:** `glyf`
   (TrueType) → glyph MERGE (keeps the original Latin/name/metrics); **`CFF ` (PostScript) → merge
   is a silent NO-OP** → must REPLACE the whole font with a donor + masquerade its `name` table.
   `tools/ud_font.py` now auto-detects and does the right one — reusable for any loose-font game.
6. **🔑 WHEN TWO MECHANISMS ARE BOTH PLAUSIBLE, TEST BOTH IN ONE PROOF — don't guess, don't do two
   round trips.** It was unknown whether UE loads a NATIVE-culture (`en`) locres override at all.
   Instead of picking one and risking a wasted launch, the proof shipped a **distinct Latin marker
   per candidate** (`ZZ-UD-EN-OK-ZZ` in `en`, `ZZ-UD-TR-OK-ZZ` in `tr`) in the same build; ONE
   screenshot identified the winner. This extends the Latin-marker trick from "did the file load?"
   to "**which** of my candidates loaded?".
7. **UE fact worth reusing: the native-culture locres IS loaded as an override.** Confirmed
   in-game — patching `en/Game.locres` works while the game sits at its default English. For an
   Unreal game with no Arabic slot this is the **best activation possible: zero user action**
   (no Settings change at all), better than every LTR-hijack game so far.
8. **Listing a game as "בקרוב" is a DB-only operation** — both the website and the launcher read
   the Supabase `games` row live, so no `vercel --prod` and no launcher rebuild are needed. Still
   update the bundled trio (`games_catalog.py`, `games.json`, `game_detector.py`) so a future build
   / cold boot / offline start matches, and keep the detector key **byte-identical to `games.id`**.
9. **Environment gotchas hit this session (cost real time):**
   - **Use the repo `.venv/Scripts/python`**, never the `python3` on PATH (a WindowsApps stub that
     also resolves MSYS paths differently — `open('/c/tmp/...')` fails).
   - **A bash `for` loop with `${var}` inside a Windows path breaks** (`C:/tmp/ud_extract${loc}_…`)
     — the `/` before the variable got eaten by MSYS path munging; use forward slashes end-to-end
     and quote carefully, then verify the file actually exists.
   - **`python -c "…r'F:\Games\…'…"` inside double quotes → `unicodeescape` error.** Use a heredoc
     (`.venv/Scripts/python - <<'PY'`) for anything containing Windows paths or Hebrew.
   - **Printing certain Unicode in a long loop raised `OSError: [Errno 22]`** on the captured
     stdout — cap the output or write results to a file instead of printing thousands of lines.
   - **`gh` CLI is NOT authenticated in this profile** → plain `curl` against `api.github.com` /
     `raw.githubusercontent.com` works fine unauthenticated for public repos (that's how the LocRes
     spec was fetched after `gh api` refused).
   - **`urllib`'s default User-Agent gets a 500/403 from the public API/Cloudflare** — set a real
     `User-Agent` header (same trap already documented for the Supabase Management API).

---


