# Assassin's Creed Shadows — Hebrew translation PIPELINE

Status (2026-06-17): **Groundwork laid; gated on a scimitar-v42 repacker.**
Read [FEASIBILITY.md](FEASIBILITY.md) first — the verdict is GO-WITH-CAVEATS and
the order below is deliberately *prove-before-invest*. This maps the AC Shadows
work onto the proven 5-stage shape from the Universal Game-Translation Playbook
(root `CLAUDE.md` → "🌍 UNIVERSAL Game-Translation Playbook").

```
C:\Games\Assassin's Creed Shadows         <- the install (~142 GB, 99 .forge, scimitar v42)
games/acshadows/
  RECON.md            verified on-disk facts
  FEASIBILITY.md      GO-WITH-CAVEATS verdict + the cheap decisive experiment
  PIPELINE.md         this file
  tools/
    acs_forge_probe.py   read-only forge inspector (header/strings/survey) — BUILT
    acs_set_language.py  back up + flip ACShadows.ini language (the 10-min test) — BUILT
  work/
    acs_translate.py     LM translator  (TEMPLATE from SM2 — adapt I/O to Oasis)
    acs_watchdog.py      self-healing supervisor (TEMPLATE from SM2)
    acs_progress.py      site progress pusher (TEMPLATE from SM2)
  extract/            (empty) destination for the extracted LocalizationPackages
```

## Stage 0 — PROVE IT (do this before acquiring any tool)
The single cheapest gate. See FEASIBILITY.md "decisive cheap experiment".
```
# PART A — is Arabic a real selectable text slot on THIS install? (~10 min, no tooling)
python games/acshadows/tools/acs_set_language.py --arabic     # backs up ACShadows.ini, sets Text/Subtitles=ar-AE
# -> launch the game, look: Arabic RTL menu/HUD?  yes = slot proven; no = gated SKU, stop here
python games/acshadows/tools/acs_set_language.py --restore    # revert when done
```
Only if Part A passes, do **Part B** (identity round-trip with the repacker —
extract Arabic package → repack UNCHANGED into `patch_01` → boots showing vanilla
Arabic). That proves the repacker gate with zero translation effort.

## Stage 1 — EXTRACT (text)
Needs a scimitar-**v42** extractor (AnvilToolkit AC Shadows beta; the public
release stops at Mirage). Also pull the already-decompressed Shadows loc samples
from ResHax topic 1779 to inspect layout without the beta.
1. Open `DataPC_boot.forge` (20.7 GB) + `DataPC_boot_patch_01.forge` /
   `_patch_02.forge`. Use `tools/acs_forge_probe.py survey "<game_dir>"` and
   `... strings` to narrow where the `LocalizationPackage` resources sit.
2. Export **two** packages:
   - `LocalizationPackage_English.data` → the **EN source** you translate.
   - `LocalizationPackage_Arabic.data` → the **RTL skeleton** you fill (key-by-key
     by numeric Oasis ID).
3. **Preserve every `.header` sidecar** that the export drops — reimport without
   it crashes the game.
4. Decode the `.data` to a flat `id <TAB> string` (or XML) editable form
   (`aclocalizationpackagetool` / the ATK export). Land both under `extract/`.

## Stage 2 — TRANSLATE (EN → Hebrew into the Arabic slot)
Reuse the scaffolded `work/acs_translate.py` (copied from the proven SM2/WD2 LM
trio). Adapt only the I/O + tag rules:
- **Input:** the extracted EN Oasis source; **fill target:** the Arabic package
  structure (so Hebrew rides the engine's tested Arabic RTL/bidi pipeline).
- **LM:** serve a **VRAM-fitting quant** on LM Studio (Vulkan, `--parallel 1` —
  the RX 9070 reality from the playbook). Short strict system prompt: Hebrew+Latin
  only · NO niqqud · copy every Oasis ID / placeholder / format-spec / markup tag
  EXACTLY · proper nouns stay English. The loc JSON IS the resumable checkpoint.
- Run under `work/acs_watchdog.py` (self-healing, hourly structural QA, UTF-8
  child stdout, kill-client-first recovery — all carried over verbatim).
- `work/acs_progress.py` → live site progress (`gameId='acshadows'`).
- **RTL caveat to verify in-game:** confirm the engine's Arabic shaper passes
  Hebrew through with correct bidi only (Hebrew is non-joining) and does NOT apply
  Arabic joining. The font has real Hebrew glyphs, so this should be clean.

## Stage 3 — REPACK
Re-import the Hebrew-filled Arabic `LocalizationPackage` (`.data` + its preserved
`.header`) into a forge with the v42 repacker, supplying `oo2core` for Oodle-Kraken
re-compression. Produce one modded **`DataPC_boot_patch_01.forge`**.

## Stage 4 — DEPLOY
1. **Back up** the vanilla `DataPC_boot_patch_01.forge`.
2. Replace it with the modded forge (or use AC Shadows Mod Manager v1.0.4 to
   toggle it). **Target `patch_01`** — the slot the live modding scene uses;
   `patch_02` is the game's own TU forge.
3. `acs_set_language.py --arabic`, launch, verify Hebrew renders RTL.
4. **Re-apply after every game update** — Ubisoft Connect / Steam "verify files"
   and title updates overwrite the modded forge back to vanilla.

## Stage 5 — PUBLISH (only if an OPEN/scriptable repacker exists)
Same shape as CP2077/SM2: GitHub release + `manifest.json` (sha256) + Cloudflare
Worker slug + Supabase `games` row + `mod_version_history`, then launcher wiring
(card + `acshadows_mod.py` lifecycle + RPCs). **If the only repacker stays a
Discord-gated closed binary, the launcher CANNOT bundle it** — fall back to a
manual-download website mod + the `acs_set_language.py` language step.

## Tools — acquire
| Tool | Role | Note |
|---|---|---|
| **AnvilToolkit (AC Shadows beta)** | extract + **repack** forge/LocalizationPackage | only confirmed v42 repacker; ATK Discord, donation-gated; needs external `oo2core` |
| `oo2core_*_win64.dll` | Oodle-Kraken codec | not shipped by the game — copy from another Oodle title on this machine |
| **AC Shadows Mod Manager v1.0.4** | deploy/toggle | Nexus `assassinscreedshadows/mods/88`; swaps the prebuilt forge into `patch_01` |
| **ResHax topic 1779** | extracted+decompressed Shadows loc samples | inspect LocalizationPackage + `.header` layout without the beta |
| `aclocalizationpackagetool` | LocalizationPackage `.data` ↔ txt/XML | Mirage/Valhalla-era; Shadows unverified; preserve `.header` |
| `tools/acs_forge_probe.py` | read-only inspector (local) | locate package offsets; validate a repacked header pre-deploy |

## The two hard, unproven dependencies (re-state on every revisit)
1. A **drivable v42 repacker** that round-trips a `LocalizationPackage` and
   produces a forge that BOOTS (currently only a gated beta; repack of v42
   text unproven by any artifact).
2. The **Arabic slot is selectable on this SKU** (disputed across sources;
   prove with Stage 0 Part A).
Everything else (font, oasis model, locale config, deploy/Denuvo, the LM
translate stage) is green.

## מסמכים קשורים
- באותה תיקייה: [[games/acshadows/FEASIBILITY|FEASIBILITY]], [[games/acshadows/FORMAT|FORMAT]], [[games/acshadows/PLAN_HEBREW|PLAN_HEBREW]], [[games/acshadows/RECON|RECON]], [[games/acshadows/RESEARCH_FONT|RESEARCH_FONT]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#acshadows|CLAUDE_INDEX_games]]
