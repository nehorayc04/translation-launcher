# MSMR — CATALOG + LAUNCHER WIRING RECON (read-only)

**Agent:** catalog/launcher gate · **Date:** 2026-08-09
**Scope:** investigation only. **ZERO writes** to Supabase, to the game folder, or to any
launcher source file. Everything below is the *exact diff that WOULD be needed*, for a later gated step.

---

## 0. HEADLINE — nothing needs to be created; the id is `spiderman`

| Question | Answer |
|---|---|
| Does a live catalog row exist? | **YES** — `id = "spiderman"` |
| Would MSMR be detected today? | **YES** — all three detection paths already resolve to `spiderman` |
| Is it in the bundled offline fallback? | **YES** — both `games_catalog.py` and `games.json` |
| Is there an applier / mod wiring? | **NO** — correct, no mod exists yet |
| Artwork uploaded? | **YES** — cover + banner + logo all live (HTTP 206) |

🔴 **The proposed-id question is MOOT and proposing one would be a BUG.** The project's own
standing rule (AC Odyssey: real id was `acodyssey`, not the `ac-odyssey` that had been proposed)
applies in reverse here — the row already exists under `spiderman`, so **any new id
(`spiderman-remastered`, `msmr`, `spiderman1`) would ORPHAN the launcher from the live card,
the cover art, and the 2026-05-15 row history.** Use `spiderman`. Do not mint a new id.

⚠️ `spiderman2` is Marvel's Spider-Man 2 (a separate, already-shipping paid mod) — **not** a collision,
but note the detector/exe tables must keep them apart (they do; verified below).

---

## 1. LIVE CATALOG — evidence

Direct fetch (not the WebFetch summarizer), cache-busted:

```
GET https://hebrew-translation-hub.com/api/games?cb=<ts>
HTTP 200 | x-vercel-cache = MISS
TOTAL ROWS = 49          # <- authoritative
duplicate ids: none
```

> ⚠️ **Methodology note:** a WebFetch summarization of the same URL reported **47** rows (and in a
> second pass claimed "62 records"). The **direct `urllib` fetch + `json.loads` + `len()` = 49** is the
> number to trust. A summarizing fetch is not a counting instrument. The brief's "~47 existing rows"
> is stale by 2.

### The exact live row (verbatim)

```json
{
  "id": "spiderman",
  "titleEn": "Marvel's Spider-Man Remastered",
  "titleHe": "מארוול ספיידר-מן רימאסטרד",
  "version": "-",
  "versionLabel": "",
  "gameVersion": "",
  "status": "locked",
  "cover":     "https://mfudkftrluabqlrpkvtj.supabase.co/storage/v1/object/public/covers/spiderman.webp",
  "bannerUrl": "https://mfudkftrluabqlrpkvtj.supabase.co/storage/v1/object/public/covers/banners/spiderman.webp",
  "logoUrl":   "https://mfudkftrluabqlrpkvtj.supabase.co/storage/v1/object/public/covers/logos/spiderman.png",
  "theme_key": "default",
  "themeKey": "default",
  "availability": "planned",
  "progress": null,
  "downloadUrl": null,
  "tagline": "השכונה מעולם לא נראתה קרובה יותר",
  "description": "הצטרפו לפיטר פארקר בסיפור אקשן סוחף ברחובות ניו יורק.",
  "next": false,
  "featured": false,
  "sortOrder": 23,
  "createdAt": "2026-05-15T13:31:11.244966+00:00",
  "priceCents": 0,
  "showOnWebsite": true,
  "showOnLauncher": true,
  "releaseStage": "stable",
  "changelog": "",
  "lockedFields": {},
  "interfaceOnlyNotice": false,
  "paymentOnly": false,
  "isSoftware": false
}
```

### Requested fields, tabulated

| field | value |
|---|---|
| **id** | `spiderman` |
| availability | `planned` |
| status | `locked` |
| price_cents | `0` (free) |
| show_on_website | `true` |
| show_on_launcher | `true` |
| sort_order | `23` |
| release_stage | `stable` |
| is_software | `false` |
| version / download_url / changelog | `-` / `null` / `""` (nothing published yet — correct) |

### Artwork is ALREADY uploaded and live

Range-request probe (`Range: bytes=0-0`):

```
cover     -> 206  bytes 0-0/16676    image/webp
bannerUrl -> 206  bytes 0-0/103852   image/webp
logoUrl   -> 206  bytes 0-0/46160    image/png
```

⇒ **No `upload_images.py` step is needed for this game.** All three assets exist in the public
`covers` bucket under the `spiderman` id.

### Sibling rows (for disambiguation)

| id | title | availability | status | price | sort |
|---|---|---|---|---|---|
| `spiderman2` | Marvel's Spider-Man 2 | available | beta | 5300 | 1 |
| **`spiderman`** | **Marvel's Spider-Man Remastered** | **planned** | **locked** | **0** | **23** |
| `spidermanmm` | Marvel's Spider-Man: Miles Morales | planned | locked | 0 | 24 |

---

## 2. DETECTION — MSMR is detected **today**, with no change whatsoever

`translation_manager/game_detector.py` already ships both tables:

```python
# line 116
"spiderman":  ["marvelsspidermanremastered", "spidermanremastered", "spiderman"],
# line 203
"spiderman":  ["Spider-Man.exe", "MarvelsSpiderManRemastered.exe"],
```

### Live verification against the real install

```
install exists      : True
literal folder name : 'Spider-man Remastered'
parent              : 'D:\Games'

match_to_catalog('Spider-man Remastered')            -> spiderman
match_to_catalog('spidermanremastered')              -> spiderman
match_to_catalog("Marvel's Spider-Man Remastered")   -> spiderman
match_by_executable(D:\Games\Spider-man Remastered)  -> spiderman
find_exe('spiderman', <install>)  -> D:\Games\Spider-man Remastered\Spider-Man.exe
root_from_exe('spiderman', <exe>) -> D:\Games\Spider-man Remastered
root .exe files: ['Spider-Man.exe', 'crs-handler.exe', 'unins000.exe']
```

**Why the folder name resolves even though it contains an edition suffix:** `_norm()` strips
`remastered` (it is in `_EDITION_SUFFIXES`), giving `spidermanremastered` → `spiderman`; and
`match_to_catalog` tries **both** the stripped form *and* the raw form. The pattern list carries
`"spiderman"` **and** `"spidermanremastered"`, so both branches hit. This is exactly the case the
in-code comment at `match_to_catalog` was written for.

**Why `Spider-Man.exe` at the root is enough:** `_EXE_SUBDIRS` contains `""` (the root itself), and
`_EXE_PATTERNS` iterates in insertion order with `spiderman` **before** `spidermanmm` / `spiderman2`
— and only `Spider-Man.exe` is present, so there is no ambiguity.

### End-to-end deep scan (real, read-only)

```
gd.deep_scan_drives(want={'spiderman'})
   [scan] סורק - המקומות הנפוצים
   [scan] סורק - כוננים נוספים
elapsed 1.7s
RESULT: { ..., 'spiderman': 'D:\\Games\\Spider-man Remastered' }
```

Found in **tier 2** ("כוננים נוספים") in **1.7 s**, because `"Games"` is in `_HOT_ROOTS` and
`D:/Games` exists. No wide scan needed.

### ⇒ What a new entry *would* need — **N/A, nothing**

| table | needed? |
|---|---|
| `_PATTERNS` | ❌ already present (line 116) |
| `_EXE_PATTERNS` | ❌ already present (line 203) |
| `_EXE_SUBDIRS` | ❌ not needed — exe is at the install root, `""` already covered |

---

## 3. 🔴 THE ONE REAL FINDING: a STALE persisted path (self-healing, but worth knowing)

`~/.translation_manager/detected_games.json` (27 entries) currently records:

```
spiderman                F:\Game Lab\Spider-man Remastered
```

**That path DOES NOT EXIST** (`Path.exists() == False`) — the game was moved to `D:\Games`.
There is **no second install**; `D:\Games\Spider-man Remastered` is the only one
(`Spider-Man.exe` 121,325,496 B, `asset_archive/` with `toc` 10,707,684 B + 37 entries).

**It self-heals and needs no action:** `_load_persisted()` drops any entry whose path no longer
exists, so at import time:

```
cached() entries (stale paths dropped at load): 26
spiderman in cached(): False
would refresh_deep hunt spiderman? True
```

⇒ On the next quick/deep scan the launcher re-detects `D:\Games\Spider-man Remastered` (1.7 s) and
rewrites the file. **Implication for a later phase:** any applier must take its target from
`_install_path(gid)` at call time (custom override → `detected_cached()`), never from a stale
snapshot — which is what `main_eel._install_path` (line 620) already does.

---

## 4. BUNDLED OFFLINE FALLBACK — also already present

Both bundled surfaces already carry MSMR under the same id. Nothing to add.

**`translation_manager/games_catalog.py` line 73** (in `PLANNED`):

```python
CatalogGame("spiderman", "Marvel's Spider-Man Remastered", "מארוול ספיידר-מן רימאסטרד",
    "-", "default", "planned",
    "השכונה מעולם לא נראתה קרובה יותר",
    "הצטרפו לפיטר פארקר בסיפור אקשן סוחף ברחובות ניו יורק."),
```

**`games.json` (line 256)** — identical shape, `"version": "—"`, `"availability": "planned"`.

### Parity audit (live vs bundled)

```
live rows        : 49
games_catalog.py : 40
games.json       : 36

spiderman: catalog.py availability=planned price_cents=0
           games.json availability=planned
           live       availability=planned status=locked price=0 stage=stable sort=23
                      showLauncher=True showWebsite=True

ids in bundled catalog.py but NOT live : []            # no orphans
ids in live but NOT in bundled catalog.py :
  ['007-first-light','aot2','borderless-gaming','corsair-cove','crimson-desert',
   'forza-horizon6','signalrgb','skyrim','virtualdj']
```

⚠️ The bundled fallbacks are behind the live catalog by 9 rows — **a pre-existing, unrelated drift**
(offline cold-boot only; the live/SWR path is authoritative). **`spiderman` is NOT one of the drifted
ids** and is perfectly in sync across all three surfaces. Cosmetic nit only: `games.json` uses the
em-dash `"—"` for version while `games_catalog.py` uses `"-"` — the IRON RULE (plain hyphen) would
prefer `"-"`, but this is a display placeholder in an offline fallback, not a translation string.

---

## 5. Mod / applier wiring — correctly ABSENT

Negative claims below are each paired with a positive control.

| check | result | control |
|---|---|---|
| `translation_manager/*spider*` | only `spiderman2_mod.py` | — |
| `grep -c "spiderman2_mod" main_eel.py` | **9** (control passes) | — |
| `grep -c "spiderman_mod\b" main_eel.py` | **0** → no MSMR applier | control above proves grep works |
| `config.py` `GAMES` | 8 entries, **no** `spiderman` (`'spiderman' in source == False`) | GAMES keys listed OK |
| `game_language.py` `LANG_CONFIGS` | has `spiderman2` (registry, `Software\Insomniac Games\Marvel's Spider-Man 2`, `TextLanguage` 0/18 + `englishVO`), **no** `spiderman` | — |

Consequence in `main_eel._enrich_game_row` (line 883): `has_mod` is
`(cfg is not None and cfg.mod_files) or gid in (_SM2_ID, _WD2_ID, …)` → for `spiderman` this is
**False**, so the card renders as a plain "planned" entry with no install button. **Correct today.**

---

## 6. THE EXACT DIFF THAT WOULD BE NEEDED LATER (gated — nothing applied)

### 6a. Catalog / detection — **NO CHANGES AT ALL**
`spiderman` id, patterns, exe fingerprints, artwork, and both bundled fallbacks are already correct.

### 6b. Only when a mod actually ships (all gated on an explicit "פרסם")

**Supabase `games` row `id=eq.spiderman`** — PATCH only (the row exists; never INSERT):
```
version        : "-"      -> "1.0.0-beta.1"
status         : "locked" -> "beta"
availability   : "planned"-> "available"
release_stage  : "stable" -> "beta"
price_cents    : 0        -> 5300      # [[mod-price-53-default]] unless the user states an exception
download_url   : null     -> https://github.com/hebrew-translation-hub/<repo>/releases/download/v1.0.0-beta.1/<zip>
changelog      : ""       -> "<Hebrew what's-new>"
show_on_launcher: true    -> keep true ONLY if an applier ships in the SAME launcher build,
                            else set false (a card with a dead install button is worse than none)
```
Plus a `mod_version_history` row with `is_current=true` and a sha/size matching the live asset.

**Bundled fallback parity** (offline cold boot only) — mirror `version` / `availability` /
`price_cents` into `games_catalog.py:73` and `games.json:256`.

**Launcher applier**, mirroring the SM2 index-redirect pattern (`translation_manager/spiderman2_mod.py`):
1. new `translation_manager/spiderman_mod.py`
2. `main_eel.py`: `_MSMR_ID = "spiderman"`, `_MSMR_SLUG = "<slug>"`, RPCs
   `get/install/remove_spiderman_mod` + `_run_msmr_install`, and add `_MSMR_ID` to the native-id
   tuples at the `has_mod` site (line 883) and the remove/state dispatch dicts (lines 3426/3432)
3. `qt_shell/bridge.py`: 3 off-thread slots
4. `frontend/src/lib/eel.ts`: 3 calls + a state type
5. `frontend/src/views/GameDetailPanel.tsx`: one `NATIVE_DL_API["spiderman"]` entry
   (`{get, install, remove, gated: true, note: "<activation text>"}`)
6. Cloudflare Worker `games/steam/steam_mod_worker/src/index.js`: add the slug, then `wrangler deploy`
7. Optional `game_language.py` `LANG_CONFIGS["spiderman"]` — MSMR is the same Insomniac engine as
   SM2, so a `kind:"registry"` entry under `Software\Insomniac Games\Marvel's Spider-Man Remastered`
   is the likely analogue. **Unverified — the key name and the language enum must be read from the
   real registry before writing anything.**

---

## 7. Verification commands used (all read-only, reproducible)

```bash
cd "c:/Users/Nehoray_Cohen/Projects/Game translator"
# live catalog (cache-busted, browser UA)
./.venv/Scripts/python.exe -c "import urllib.request,json,time; ..."   # -> 49 rows, HTTP 200 MISS
# detection
./.venv/Scripts/python.exe -c "from translation_manager import game_detector as gd; \
    print(gd.match_to_catalog('Spider-man Remastered'), gd.match_by_executable(...))"
# end-to-end scan (deep_scan_drives does NOT write; refresh_deep WOULD - not called)
./.venv/Scripts/python.exe -c "... gd.deep_scan_drives(want={'spiderman'}) ..."
```

**Environment note:** the Bash/PowerShell classifier was unavailable for part of this session; the
live-API query was first obtained via `WebFetch` and then **re-verified with a direct `urllib`
fetch**, which is what corrected the row count 47 → **49**.
