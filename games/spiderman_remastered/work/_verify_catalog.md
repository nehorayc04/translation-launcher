# ADVERSARIAL VERIFICATION — MSMR "CATALOG + LAUNCHER WIRING" gate

Independent re-check of the prior agent's report. Every load-bearing claim re-run
with my own commands + negative controls. **Verdict: the report SURVIVES** — the
core finding (id = `spiderman`, already detected, artwork live, no wiring needed)
is correct. Four corrections/additions below.

---

## 1. CONFIRMED — live catalog

```
GET /api/games?cb=<ts>  (browser UA, no-cache)  -> HTTP 200, x-vercel-cache=MISS
TYPE list  LEN 49  DUP ids: []
```
Row verbatim:
```json
{"id":"spiderman","titleEn":"Marvel's Spider-Man Remastered","titleHe":"מארוול ספיידר-מן רימאסטרד",
 "version":"-","status":"locked","availability":"planned","priceCents":0,"showOnWebsite":true,
 "showOnLauncher":true,"sortOrder":23,"releaseStage":"stable","downloadUrl":null,"changelog":"",
 "isSoftware":false,"createdAt":"2026-05-15T13:31:11.244966+00:00"}
```
49 rows confirmed (report's methodology correction about the 47 was right).
Siblings distinct: `spiderman2` (available/beta/₪5300/sort 1), `spidermanmm`
(planned/locked/sort 24).

## 2. CONFIRMED — detection works today, zero code changes

`game_detector.py:116` `_PATTERNS["spiderman"]` and `:203` `_EXE_PATTERNS["spiderman"]`
both present. Live against the REAL install `D:\Games\Spider-man Remastered`:

| path | result |
|---|---|
| `match_to_catalog("Spider-man Remastered")` | `spiderman` |
| `match_to_catalog("Marvel's Spider-Man Remastered")` | `spiderman` |
| `_norm(...)` | `spiderman` |
| `match_by_executable(<install>)` | `spiderman` |
| `find_exe("spiderman", <install>)` | `D:\Games\Spider-man Remastered\Spider-Man.exe` |
| `root_from_exe(...)` | `D:\Games\Spider-man Remastered` |

**Stronger than the report:** I read the implementation, not just the outcome.
`match_to_catalog` is `if target in patterns` — an **EXACT** list membership test,
not a substring search — so the "spiderman is a substring of marvelsspiderman2"
collision is structurally impossible, independent of dict ordering. Controls:
`"Marvel's Spider-Man 2" -> spiderman2`, `"Marvel's Spider-Man Miles Morales" -> spidermanmm`.
`match_by_executable` matches on an exact lowercased filename set, so
`MarvelsSpiderMan2.exe` can never resolve to `spiderman`.

`"Games" in _HOT_ROOTS = True`, `"" in _EXE_SUBDIRS = True`.

## 3. CONFIRMED — artwork live (with a negative control)

| asset | HTTP | bytes | dims |
|---|---|---|---|
| cover | 200 | 16,676 | **300×450** RGB WEBP |
| banner | 200 | 103,852 | 1600×517 RGB WEBP |
| logo | 200 | 46,160 | 360×201 RGBA PNG |
| CONTROL (nonexistent object) | **400** | — | — |

Byte counts match the report exactly. The control proves the probe can fail.

## 4. CONFIRMED — no applier wiring anywhere

⚠️ The report's own grep `grep -nE "spiderman(?![2m])"` uses a **PCRE lookahead
inside ERE**, which grep cannot honour — that command returns empty no matter
what, i.e. its negative was unfalsifiable. I re-ran with a real Python regex
`re.compile(r'spiderman(?![2m])', re.I)` and a `spiderman2` control per file:

| file | bare `spiderman` | control `spiderman2` |
|---|---:|---:|
| main_eel.py | 0 | 20 |
| translation_manager/config.py | 0 | 0 |
| translation_manager/game_language.py | 0 | 1 |
| translation_manager/games_catalog.py | 1 (line 73, catalog row) | 1 |
| games.json | 1 (line **257**) | 1 |
| translation_manager/qt_shell/bridge.py | 0 | 7 |
| frontend/src/lib/eel.ts | 0 | 13 |
| frontend/src/views/GameDetailPanel.tsx | 0 | 6 |

`ls translation_manager/ | grep -i spider` → only `spiderman2_mod.py`.
`main_eel.py:883` `has_mod = ... or gid in (_SM2_ID,_WD2_ID,_GTAV_ID,_GOWR_ID,_HL_ID,_W3_ID,_PT_ID,_VDJ_ID,_BG_ID,_SRGB_ID)`
→ `spiderman` absent ⇒ `has_mod=False`. **The negative holds.**

`_install_path()` (main_eel.py:620) = `user_paths.get(gid) or detected_cached().get(gid)`
— resolved at call time, as reported.

## 5. CONFIRMED — the stale cache self-heals

`~/.translation_manager/detected_games.json`: 27 entries,
`spiderman -> F:\Game Lab\Spider-man Remastered`, `Path.exists() = False`.
`F:\Game Lab` exists but contains **no** Spider-Man folder (7 other games) — so
there is genuinely no second install. After import: `cached()` = 26 entries,
`"spiderman" in cached()` = **False**. Self-heals exactly as reported.
(`Path.home()` and `FOLDERID_Profile` both = `C:\Users\Nehoray_Cohen` — home is
NOT redirected in this session, so the read is trustworthy.)

## 6. CONFIRMED — bundled parity

`games_catalog.sorted_games()` = **40** · `games.json` = **36** · live = **49**.
`bundled-not-live` = `[]`; `live-not-bundled` = the same 9 ids the report listed
(`007-first-light, aot2, borderless-gaming, corsair-cove, crimson-desert,
forza-horizon6, signalrgb, skyrim, virtualdj`) — `spiderman` is not among them.
Both fallbacks carry `spiderman` as `planned` / price 0.

---

# CORRECTIONS / ADDITIONS

## 🔴 A. The registry open-question was answerable and the answer CHANGES the plan

The report deferred the MSMR language key as an open question, saying it "did not
touch the registry (out of scope for this read-only gate)". Reading HKCU **is**
read-only and was in scope. Measured:

```
HKCU\Software\Insomniac Games            -> subkeys: "Marvel's Spider-Man 2",
                                                      "Marvel's Spider-Man Remastered",
                                                      "Ratchet & Clank - Rift Apart"
HKCU\...\Marvel's Spider-Man Remastered  -> TextLanguage = 19 (REG_DWORD), FirstRun = 0
                                            subkeys: Graphics, Input
                                            *** NO englishVO value ***
HKCU\...\Marvel's Spider-Man 2           -> englishVO = 1, TextLanguage = 18, FirstRun = 0, ...
HKCU\...\Marvel's Spider-Man             -> ABSENT
HKCU\...\Spider-Man                      -> ABSENT
```

Two facts the report could not state:
1. **The subkey name is confirmed**: `Software\Insomniac Games\Marvel's Spider-Man Remastered`.
2. **The enum is NOT SM2's.** SM2's `LANG_CONFIGS` says english=0 / hebrew=18.
   MSMR reads **19** on an English-only install (`flt.ini Language=English`, only
   `a00s034.us` voice archive present) — so 19 is almost certainly MSMR's ENGLISH,
   i.e. the ordering differs entirely. And MSMR has **no `englishVO` value at all**,
   so SM2's `extra={"englishVO":1}` has no counterpart here.
   ⇒ Copying SM2's `codes`/`extra` blind would be wrong on **both** fields. The
   Arabic index must be derived from the 23 loc variants / the toc's archive
   language order and then confirmed by a live write+read, not assumed.

## ⚠️ B. Unflagged IRON-RULE violation in `games.json`

`games.json` ships `"version": "—"` (U+2014 EM DASH) for `spiderman` — and for
**37 rows total**. `games_catalog.py` correctly uses `'-'`. The report quoted the
`"—"` verbatim without flagging it. This is a launcher-rendered string, so it is
in scope for [[iron-rule-plain-hyphen]]. Pre-existing, cosmetic, not MSMR-specific.

## ⚠️ C. Cover art is half the current resolution standard

The cover is **300×450** — the older standard. Recent titles ship 600×900
(Crimson Desert, Corsair Cove). Banner (1600×517) and logo (360×201 contain-fit)
are current-standard. "Artwork already live" is TRUE; a cover refresh is a
candidate at publish time, not now.

## ➕ D. `/translate` pool is empty for this game (not stated by the report)

`GET /api/translate?action=games` → 22 games, **zero** `spider*` entries. So the
community pool has never been seeded for `spiderman` (nor for `spiderman2`), and
the Phase-2 import is untouched. Consistent with the report; worth recording.

## ✏️ E. Trivial citation slip

`games.json` `"id": "spiderman"` is on line **257** (the object opens at 256), not
"line 256".

---

# BOTTOM LINE

Nothing in the report's verdict is refuted. `spiderman` is the correct, existing
id; detection, artwork and both offline fallbacks need **no** changes; the absence
of applier wiring is real (and I proved it with a regex the report's own grep
could not have proved). The one substantive gap is the registry, which was
measurable and now shows MSMR's language enum is **different from SM2's** — do not
copy `codes:{english:0,hebrew:18}` or `extra:{englishVO:1}` into a future
`LANG_CONFIGS["spiderman"]`.
