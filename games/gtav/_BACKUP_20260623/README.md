# GTA V Hebrew — backup snapshot (2026-06-23)

Everything valuable, preserved before a clean restore + fresh restart.

## Vanilla originals (to restore the game to English)
- `global_PATCH_vanilla_351entries.gxt2` — vanilla **patch** global.gxt2 (md5 `ebddedec5ced9aff678d871f8e549109`), from `update.rpf\x64\patch\data\lang\american_rel.rpf`. 351 strings.
- `font_lib_efigs_ORIGINAL.gfx` — vanilla Scaleform font (96,789 B) for `scaleform_generic.rpf`.
- ⚠️ **Missing:** vanilla `font_lib_efigs_pc.gfx` was never separately backed up. The perfect way to restore BOTH fonts is to **Uninstall `Menyoo_Hebrew_Font.oiv` in OpenIV** (OpenIV holds its own backup of both originals).
- The vanilla **base** american_rel global.gxt2 (1,141,267 B, 23,136 strings) lives in `../work/_rpf/global.gxt2`.

## The translation WORK (the valuable 23k-string effort — to rebuild fresh)
- `hebrew_translations.json` — {joaat_hex: Hebrew} for all UI strings (21,576 translated).
- `to_translate.json` — {joaat_hex: English} source (23,136).
- `skip.json` — keys left Latin (names/codes).
- `global_he_BUILT.gxt2` — the built Hebrew gxt2 (visual, no-dedup, 1,511,573 B).

## Hebrew fonts (current, atlas-injected by a prior session — INCOMPLETE coverage)
- `font_lib_efigs_HEBREW.gfx` / `font_lib_efigs_pc_HEBREW.gfx` — 711,440 B each, 27/27 Hebrew letters. Covers SOME Scaleform surfaces but NOT the pause menu (tofu) → needs proper multi-font work for a fresh attempt.

## OIV packages (history)
- `gtav_hebrew_FULL.oiv` — install Hebrew (gxt2 base slot + both fonts).
- `gtav_restore_FULL.oiv` — restore (gxt2 base+patch + _efigs font for both slots).
- older partials: `gtav_hebrew_ui.oiv`, `gtav_restore_original.oiv`, `gtav_restore_patch_vanilla.oiv`.

## Lessons for the fresh restart (key facts learned)
1. **GAME MUST BE CLOSED for every OpenIV install** — SYS_ERROR_00000020 (sharing violation) = the game/CodeWalker is holding the RPF; installs silently FAIL.
2. **gxt2 must NOT de-dup strings** — the RAGE loader uses offset[i+1]-offset[i] for length; dedup → ERR_MEM_EMBEDDEDALLOC_ALLOC. (Fixed in `gtav_gxt2.write_gxt2`.)
3. **Two american_rel/global.gxt2:** BASE = `x64b.rpf\data\lang\american_rel.rpf` (23,136 full UI); PATCH = `update.rpf\x64\patch\data\lang\american_rel.rpf` (351 DLC strings). The PATCH slot is what visibly overrode text in tests.
4. **Font coverage is the real gate:** the pause menu uses a Scaleform font WITHOUT Hebrew → tofu. `font_lib_efigs` alone is not enough; a fresh attempt must Hebraize the pause-menu font(s) too.
5. **bidi = VISUAL** (store pre-reversed), confirmed.
