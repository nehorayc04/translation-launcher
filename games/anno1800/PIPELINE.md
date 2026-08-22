# Anno 1800 — Hebrew translation pipeline (HOW-TO)

End-to-end build/deploy recipe for the Anno 1800 Hebrew translation. Mirrors the
structure proven on CP2077 / SM2 / WD2 / GoW:R (see the **Universal Game-Translation
Playbook** in the root `CLAUDE.md`). Verdict lives in `FEASIBILITY.md`; the format
facts live in `RECON.md` — this file is the runnable recipe only.

## Why Anno 1800 is the easiest deploy in the project

- **Loose-file mod.** No `.rda` repack, no native packer, no DLL applier, no
  Overstrike. The game's mod loader reads a plain folder tree — drop files in, done.
- **No anti-cheat**, no special launch flag.
- **Keep the user's locale.** UI text is GUID-keyed XML. There is **no Arabic slot**,
  so we hijack the **English** (LTR) slot: ship Hebrew inside `texts_english.xml` and
  the user keeps in-game **Language = English**. `AudioLanguage` is a *separate*
  setting, so English voice-over is unaffected.
- Engine = Anno/RDA. We only need a *reader* (already built); repacking is unnecessary
  because the mod is loose files.

> ⚠️ Two facts are **unproven until the proof gate (stage 6)**: whether the native HUD
> does bidi (→ LOGICAL vs VISUAL storage) and whether font injection lands on the HUD
> font. Build the translator output **logical**; gate the `visual()` decision on the
> in-game test. Do the proof gate BEFORE the full translation run.

## Status

| Stage | State |
|---|---|
| 0 — read/extract the EN spine | ✅ reader built (`work/rda_reader.py`) |
| 1 — build the translation pool | ⏳ |
| 2 — translate EN→He (logical) | ⏳ |
| 3 — Hebrew font injection | ⏳ |
| 4 — build the loose-file mod | ⏳ |
| 5 — deploy | ⏳ |
| 6 — **proof gate** (1 string, BEFORE a full run) | ⏳ |
| 7 — publish (GitHub + Worker + Supabase) | ⏳ |

## Tools

| Tool | Role |
|---|---|
| `work/rda_reader.py` | pure-Python `.rda` reader — extract a named file from `data0.rda` (read-only; no repack needed) |
| `work/anno1800_translate.py` | EN→He translator (SM2 LM trio, adapted) — serial gemma, token-budget batching, `validate()` + 3-strike park + atomic flush |
| `work/anno1800_watchdog.py` | self-healing supervisor (RUN THIS) — owns LM + translator + progress + hourly QA |
| `work/anno1800_progress.py` | push progress to the hub site |
| `work/anno_font.py` | inject Hebrew glyphs into the Anno UI TTFs (fontTools) |
| `work/build_mod.py` | assemble the loose-file mod folder (ModOps XML + fonts + optional CSS) |

Scope: **~28,165 base GUIDs** (UI-dominant, thin subtitle tail). Grows ~1.5–2× with
the full DLC set (extra GUIDs layer in via the same file/ModOp).

---

## 0. Pre-reqs / read side — extract the EN spine (one time)

The reader (`work/rda_reader.py`) is already built. Pull the English text table out of
the base archive:

```bash
cd "games/anno1800"
.venv/Scripts/python.exe work/rda_reader.py extract \
  "C:/Program Files (x86)/Steam/steamapps/common/Anno 1800/maindata/data0.rda" \
  texts_english.xml \
  games/anno1800/extract
# -> games/anno1800/extract/data/config/gui/texts_english.xml
```

`texts_english.xml` holds **28,165** records of the shape:

```xml
<Text>
  <GUID>1234</GUID>
  <Text>Build a Marketplace.</Text>
</Text>
```

This is BOTH the translation source AND the id-mapping (the `<GUID>` is the stable key
used everywhere). For a fully-DLC'd corpus, also extract any DLC text tables — the
additional GUIDs layer in via the same file path / ModOp and just extend the pool.

> Read-only: `RDAConsole` / `RDAExplorer` are alternative readers if you ever need to
> browse the archive by hand. We never repack the `.rda` — the mod is loose files.

## 1. Build the translation pool

A small adapter parses `texts_english.xml` into the normalized `{guid, source_en}`
list the trio expects:

```bash
.venv/Scripts/python.exe work/anno1800_build_pool.py \
  extract/data/config/gui/texts_english.xml \
  work/anno1800_strings.json
# -> [{"string_key": "1234", "source_en": "Build a Marketplace."}, ...]   (string_key = the GUID)
```

Optionally seed the community `/translate` pool (same as the other games — `string_key`
is the GUID):

```bash
.venv/Scripts/python.exe universal/community_translate.py import anno1800 work/anno1800_strings.json
```

**Preserve inline markup/placeholders verbatim** — ~4% of records carry formatting
tags and `[GUIDNAME]`-style cross-references; the translator must copy them byte-for-byte.

## 2. Translate EN→He (store LOGICAL)

Reuse the standard SM2 LM trio, adapted as `work/anno1800_translate.py` /
`anno1800_watchdog.py` / `anno1800_progress.py`:

```bash
# launch the supervisor under BASE python (not the venv stub), hidden, UTF-8 stdout
#   Start-Process "...\Python313\python.exe" -ArgumentList '-u','work\anno1800_watchdog.py' `
#       -WorkingDirectory "<games/anno1800>" -WindowStyle Hidden
.venv/Scripts/python.exe work/anno1800_translate.py --status   # resumable progress count
```

Translator rules (carry from the playbook §3):

- Local LM **serial** (`--parallel 1`), short strict system prompt (~400 tok).
- Hebrew+Latin only · NO niqqud · copy every formatting tag / `[GUIDNAME]` ref / `%`-spec
  / `\n` EXACTLY · character & place names keep their established Hebrew spelling
  (build a glossary).
- **Token-budget batching** — short UI labels batched; a long lore/quest blurb goes solo
  (`max_tokens` sized per batch).
- **Atomic writes**; `validate()` + 3-strike park; the resumable state = a
  `{guid: hebrew}` JSON.
- **Store Hebrew in LOGICAL order by default.** ⚠️ CRITICAL UNKNOWN — if the proof gate
  (stage 6) shows the native HUD does NOT do bidi (mirror text), switch the BUILD step
  (stage 4) to emit **VISUAL** order (pre-reversed per line, WD2-menu / AC2 style). Keep
  the translator output logical and apply `visual()` **only at build time**, exactly like
  WD2's `wd2_ui_merge.py:visual()`.

## 3. Hebrew font injection (`work/anno_font.py`)

NO shipped UI font carries Hebrew (cmap-verified: `metaoffcpro` / `metaserifoffcpro` /
`kelvinch` / `heuristica` / `roboto` = Latin + Cyrillic only). Inject Hebrew glyphs from
an OFL source into the Anno UI TTFs with `fontTools`:

- **Serif headers** → Frank Ruhl Libre; **body** → Heebo / David.
- **Preserve the Anno font's `name` table, metrics, and `unitsPerEm`** so the engine
  loads "the same font" — now with Hebrew glyphs.
- **Inject into ALL the Latin UI fonts** (the exact HUD-font binding is unconfirmed —
  cover every candidate).
- Ship the injected TTFs as loose-file overrides at `data/fonts/<name>.ttf`.

```bash
.venv/Scripts/python.exe work/anno_font.py \
  --anno-fonts "C:/Program Files (x86)/Steam/steamapps/common/Anno 1800/.../fonts" \
  --hebrew-serif "Frank Ruhl Libre" --hebrew-body Heebo \
  --out mod/data/fonts
```

This is a plain-TTF op (`fontTools` glyph copy) — far simpler than CR2W-embed (CP2077)
or DDS-atlas injection (SM2 / WD2 / GoW:R).

## 4. Build the loose-file mod (`work/build_mod.py`)

Assemble the mod folder. The `data/...` tree MUST mirror the in-archive paths exactly.

```
zzz_hebrew_translation/
├── modinfo.json                          # minimal schema below
├── data/config/gui/texts_english.xml     # <ModOps> patch (see below)
├── data/fonts/<injected TTFs>            # loose-file font overrides (stage 3)
└── data/config/http/ ... .css            # OPTIONAL scoped CSS (stage 4b), only if needed
```

`modinfo.json` (minimal):

```json
{
  "Version": "1.0.0",
  "ModID": "zzz_hebrew_translation",
  "ModName":     { "English": "Hebrew Translation" },
  "Category":    { "English": "Localization" },
  "Description": { "English": "Hebrew UI translation (English-slot hijack)." },
  "CreatorName": "nehorayc04"
}
```

`data/config/gui/texts_english.xml` is a **ModOps patch**, not a full file — one ModOp
that *adds* a `<Text>` per translated GUID into the existing English text table. Adding a
`<Text>` for an existing base GUID **overrides** it:

```xml
<ModOps>
  <ModOp Type="add" Path="/TextExport/Texts">
    <Text><GUID>1234</GUID><Text>בנה שוק.</Text></Text>
    <Text><GUID>1235</GUID><Text>אסוף עץ.</Text></Text>
    <!-- one <Text> per translated GUID -->
  </ModOp>
</ModOps>
```

```bash
.venv/Scripts/python.exe work/build_mod.py \
  --he work/anno1800_he.json \
  --fonts mod/data/fonts \
  --out "mod/zzz_hebrew_translation"
```

### 4b. Optional CSS mod (CEF panels only)

Some stat/chart panels render in CEF (web view). If those specifically come out
LTR/left-aligned after the proof gate, add a **scoped** CSS mod
(`data/config/http/.../<panel>.css`) with `direction: rtl; text-align: right;` —
**only** for those panels, never global. Skip this unless the proof shows it's needed.

## 5. Deploy

Copy the assembled mod folder into the user mods directory (**preferred**):

```
%USERPROFILE%\Documents\Anno 1800\mods\zzz_hebrew_translation\
```

`Documents\Anno 1800\mods\` takes precedence, stays out of Program Files (no admin),
and is **immune to Ubisoft Connect "Verify files"**. The install-folder `<install>\mods\`
also works but is reverted by Connect verification.

Activation: the user sets in-game **UI Language = English** and restarts — the mod
auto-loads. **Removal = delete the folder.** No repack, no DLL, no applier.

## 6. The PROOF gate — do this BEFORE a full run

Build a **1-string** proof mod that resolves both open gates in a single launch:

```
mods/zzz_hebrew_proof/
├── modinfo.json
├── data/config/gui/texts_english.xml   # ONE ModOp overriding a single visible menu GUID
│                                        #   to a known Hebrew word
└── data/fonts/<one injected TTF>        # the font-injection test
```

Launch, set **Language = English**, and observe:

1. **Loose mod loads?** — does the target string change at all?
2. **Font works?** — Hebrew glyphs render, or tofu/boxes?
3. **RTL correct, or mirror-reversed?** → **this decides LOGICAL vs VISUAL** for stage 2.
4. **CEF panels** — check a stat/chart panel separately (decides whether 4b is needed).

The user (Hebrew speaker) is the final judge. Only after this passes do you run the full
translation (stage 2) and build the real mod (stage 4) with the proven storage order.

## 7. Publish

Same pattern as SM2 / CP2077 / WD2:

1. **GitHub release repo** `hebrew-translation-hub/anno1800-hebrew-mods` — a FULL release (so
   `releases/latest` resolves) carrying `manifest.json` + the mod zip.
2. **Worker slug** `anno1800-hebrew` added to
   `games/steam/steam_mod_worker/src/index.js` (redeploy:
   `cd games/steam/steam_mod_worker && npx wrangler deploy` — needs the Cloudflare token).
3. **Supabase sync** — `games` row + `mod_version_history`:

```bash
.venv/Scripts/python.exe universal/publish_version.py anno1800 <ver> --stage beta \
  --sha <sha256> --size <bytes> --archive-url <github-release-zip-url> --apply
```

Keep the **4 surfaces in sync** (Worker manifest, Supabase `games`, `mod_version_history`,
the GitHub zip sha256) — see the root `CLAUDE.md` version-sync rules.

**Launcher integration (future):** a `translation_manager/anno1800_mod.py` lifecycle that
deploys by copying the mod folder into `%USERPROFILE%\Documents\Anno 1800\mods\`, with the
detection key **`anno1800`** == the Supabase `games.id`.

---

## Gotchas / rules (do not regress)

- **Hebrew goes in `texts_english.xml`** (the hijacked English slot). The user MUST keep
  **Language = English** or the Hebrew won't load. `AudioLanguage` is separate → English
  VO stays.
- **LOGICAL vs VISUAL storage is unproven** until the proof string (stage 6). Build the
  translator **logical**; gate the `visual()` decision on the in-game test.
- **Inject Hebrew into ALL Latin UI fonts** — the HUD font binding is unconfirmed.
- **Deploy to `Documents\Anno 1800\mods\`** to stay out of Program Files AND survive
  Ubisoft Connect "Verify files".
- **No anti-cheat; no repack needed.** We have a reader; `RDAConsole`/`RDAExplorer` are
  read-only browsing tools, never used to repack.
- **Scope** ~28,165 base GUIDs, ×1.5–2 with full DLC. UI-dominant with a thin subtitle
  tail.
- Carry the universal LM gotchas: **UTF-8 stdout** on every script
  (`sys.stdout.reconfigure(encoding="utf-8")` + `PYTHONIOENCODING=utf-8` on children);
  **never reload the LM while a client holds a hung request** (kill client → `unload --all`
  → load → probe).
```

## מסמכים קשורים
- באותה תיקייה: [[games/anno1800/FEASIBILITY|FEASIBILITY]], [[games/anno1800/RECON|RECON]], [[games/anno1800/RESEARCH_COLDBOOT|RESEARCH_COLDBOOT]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#anno1800|CLAUDE_INDEX_games]]
