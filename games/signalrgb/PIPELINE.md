# SignalRGB Hebrew — Pipeline

`games.id` (proposed): **`signalrgb`** · `is_software = true` (like `virtualdj`,
`borderless-gaming`).

## Tools (`work/`)

| file | what it does |
|---|---|
| `qm.py` | Qt `.qm` reader/writer + `elfHash`. `python qm.py` = identity selftest (**8/8 byte-identical**). |
| `extract_corpus.py` | pulls every embedded `.qm` → `extract/{qm/,en.json,reference.json,index.json,report.txt}`. Labels each `.qm` by **script**, not by its (sometimes wrong) Language block. |
| `size_budget.py` | measures the delta-0 budget + the minimal-prefix lever. |
| `patch_exe.py` | `--status` / `--deploy <hebrew.json>` / `--revert` / `--lang <code>`. |
| `build_menu_proof.py` | builds + optionally deploys the Phase-1 proof. |

Key format everywhere: `key = context \x1f source \x1f comment` — exactly what
Qt looks a message up by, so a translation can never land on the wrong string.

## Phase 1 — proof ✅ PASSED in-app 2026-07-20

Marker shown, Hebrew clean with zero tofu, letter order correct (**bidi =
LOGICAL**), untouched entries still Arabic, and the layout confirmed
**unmirrored**. Details in FEASIBILITY.md. Re-run it any time with:

```bat
:: quit SignalRGB from the tray first (the exe is locked while running)
python work/build_menu_proof.py --deploy
:: -> patches the Arabic slot, sets HKCU ... UI\Locale = ar
:: start SignalRGB, open Settings
```

What to read off the screenshot:

* `ZZ-SRGB-OK-ZZ` in place of **About** → the patched `.qm` loads.
  (Latin-only on purpose: it separates "the file didn't load" from "the font
  has no glyphs", which otherwise look identical.)
* `הגדרות / שפה / שמע / התראות …` render with no boxes → font is free.
* **`מתקין...`** — if the `...` is on the **LEFT**, bidi is LOGICAL (store
  natural Hebrew). On the right → VISUAL. **Do not pre-reverse before this.**
* `הגדרות Add-on` → the Latin island keeps its direction and position.
* Everything else stays Arabic → untouched entries fall through cleanly, i.e.
  a partial translation degrades gracefully.
* Whether panels/alignment mirror (they probably do **not** — see FEASIBILITY).

Revert: `python work/build_menu_proof.py --revert` (byte-exact + clears the
locale).

Optional round 2 (only after round 1 passes): `--deploy --rtl` adds
`QGuiApplication/QT_LAYOUT_DIRECTION = RTL` to test Qt's automatic mirroring.

## Phase 2 — translation (handoff BUILT, ready to run)

`python work/build_handoff.py` → `agent_handoff/`:

| file | |
|---|---|
| `to_translate.json` | 1,838 rows `{key: {context, en, refs}}`, **avg 5.9 reference languages per line**, ordered by VISIBILITY (nav/settings/onboarding 146 → feature pages 936 → other 666 → dev/diagnostic panels 90) so a partial pass still covers what users see |
| `hebrew.json` | the output, `{key: hebrew}` |
| `name_registry.json` | 50 brands/protocols that stay Latin + the locked glossary |
| `INSTRUCTIONS.md` | the full Hebrew brief |

Then `python work/qa_scan.py` (the gate) and `python work/build_hebrew.py`.

Scope is a **single pass — no fleet, no gender-oracle infrastructure.** Follow
the New-Era method: decide each line against the panel of shipped languages,
not from the English alone — but treat the vendor's translations as **machine
output to cross-check**, not as truth.

Rules for this target:

* Store **LOGICAL** — proven in-app. No `&rlm;`, no RLE/PDF, no pre-reversal.
* Preserve `%1..%9`, literal `%`, `\n` exactly (multiset check).
* Do **not** translate: brand names (SignalRGB, Corsair, Razer, iCUE, Govee,
  ASUS Aura…), protocol/tech identifiers (SMBus, I2C, RGB, DPI, MCP, ARGB,
  OpenRGB), file/format tokens.
* Do **not** flip direction words — the proof showed the app does NOT mirror,
  so "the left panel" stays "הפאנל השמאלי".
* Keep a name/term registry so one English term maps to one Hebrew term
  everywhere (Effect/Layout/Canvas/Device/Component/Layer/Macro/Addon).

**`work/qa_scan.py` is the gate** (adversarially tested — every class below was
injected and caught, exit code 1): invented key · empty · `%1..%9`/literal-%/`\n`
multiset · every digit-run survives · ALL-CAPS & camelCase identifiers survive ·
niqqud · foreign script · bidi controls · still-English · locked-glossary drift.

## Phase 3 — build & deploy

```bat
python work/build_hebrew.py            :: build + report, no write
python work/build_hebrew.py --deploy   :: patch the exe + set the locale
python work/build_hebrew.py --revert   :: byte-exact restore
```

`build_hebrew.py` runs the QA gate first and refuses to build on a defect; it
always builds from the **pristine backup** (never from what is deployed), and
falls back to `minimize_prefixes` automatically if the naive build overflows.

`patch_exe.py` guarantees:

* the pristine Arabic slot is copied to
  `%LOCALAPPDATA%\WhirlwindFX\SignalRgb\hebrew_backup\` with its offset +
  SHA-256 **before the first write**;
* the patch is always built **from that pristine copy** → idempotent, and a
  re-run after a SignalRGB update re-detects the new install and refreshes the
  backup;
* the slot is located **by content** (Arabic/Hebrew script), never by the
  Language block;
* it refuses to write unless the built `.qm` is exactly the slot size;
* the exe is patched in a temp copy and `os.replace`d in (never a half-written
  114 MB exe);
* `--revert` restores byte-exact vanilla.

If a full Hebrew build ever exceeds the slot, apply
`size_budget.minimize_prefixes` before `qm.build` — it frees 93,590 bytes.

## Phase 4 — publish (only on an explicit "פרסם")

Same shape as `borderless-gaming` / `virtualdj`:

1. GitHub release on `hebrew-translation-hub/signalrgb-hebrew-mods` with a
   self-contained `install.py` (finds the newest `app-*/Signal-x64/SignalRgb.exe`,
   backs up, patches, `--revert`) + `qm.py` + `hebrew.json`.
2. Worker slug `signalrgb-hebrew` in `games/steam/steam_mod_worker/src/index.js`
   + `npx wrangler deploy`; verify `/manifest` **and** `/archive` with a real
   request, and make sure the manifest carries **`archive_name`**.
3. Supabase `games` row `signalrgb` + `mod_version_history`, `is_software=true`,
   `price_cents` per the standing rule (₪53 unless the user says free).
4. Optional launcher applier `translation_manager/signalrgb_mod.py` (native,
   cloud-first) + a `kind:"registry"` entry in `game_language.py` for the
   Hebrew/English switch (`HKCU\Software\WhirlwindFX\SignalRgb\UI` → `Locale`,
   `ar` ↔ `en_US`) — the registry mechanism already exists for Spider-Man 2.

## Known limitations to state on the product page

* Effect/store content comes from the server and stays English.
* A SignalRGB update reverts the translation → re-run the installer.
* Patching modifies a code-signed executable.

## מסמכים קשורים
- באותה תיקייה: [[games/signalrgb/FEASIBILITY|FEASIBILITY]], [[games/signalrgb/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#signalrgb|CLAUDE_INDEX_games]]
