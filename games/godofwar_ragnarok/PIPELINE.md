# God of War: Ragnarök Hebrew — pipeline recipe

End-to-end recipe for the GoW:R Hebrew translation. Mirrors the structure proven
on CP2077 / SM2 / WD2 (see the **Universal Game-Translation Playbook** in the
root `CLAUDE.md`). **Status 2026-06-17:** read-side proven (extract works, scope =
48,886). Open gates: re-pack round-trip + Hebrew font glyphs (see FEASIBILITY.md).

## Status

| Stage | State |
|---|---|
| 0 — read/extract/scope | ✅ done (`work/gowr_wad.py`, corpus JSONs dumped) |
| 1 — re-pack round-trip + in-game load | ⏳ next gate |
| 2 — font/RTL decision | ⏳ after gate 1 |
| 3 — full translation (48,886) | ⏳ |
| 4 — publish (GitHub + Worker + Supabase) | ⏳ |

## Tools

| Tool | Role | Status |
|---|---|---|
| `work/gowr_wad.py` | r_lang_*.wad LZ4-decompress + MSGS_TXT extract → `{id:str}` | ✅ built, read-only |
| `work/gowr_wad.py` (pack mode) | rebuild MSGS_TXT + WTOC offsets + re-LZ4 | ⏳ TODO (gate 1) |
| Delutto "God of War Localization Tool" | community `r_lang_*.wad` packer | ⏳ fetch as fallback |
| `work/gowr_translate.py` | EN→Hebrew via local LM (template laid) | ⏳ template |
| `work/gowr_watchdog.py` | self-healing supervisor (template laid) | ⏳ template |
| `work/gowr_progress.py` | push progress to the hub site (template laid) | ⏳ template |
| `work/gowr_font.py` | inject Hebrew glyphs into the Arabic font (if needed) | ⏳ TODO (gate 2) |

## Recipe (the proven shape — fill the ⏳ steps as gates clear)

```bash
cd "games/godofwar_ragnarok"

# 0. EXTRACT (done) — EN source + AR skeleton, keyed by numeric id
python work/gowr_wad.py extract extract/r_lang_en.wad work/english.json
python work/gowr_wad.py extract extract/r_lang_ar.wad work/arabic.json
python work/gowr_wad.py stats   extract/r_lang_en.wad      # scope = 48,886 shared ids

# 1. ROUND-TRIP GATE  (⏳ build pack mode, then:)
#    edit one test id in arabic.json -> repack -> deploy to Game Lab copy -> verify in-game
python work/gowr_wad.py pack work/arabic.json extract/r_lang_ar.wad  out/r_lang_ar.wad
#    (backup the live file as r_lang_ar.wad.he_backup BEFORE first deploy)

# 2. TRANSLATE  (⏳ gemma-4 serial, watchdog-supervised — see template)
python work/gowr_watchdog.py        # owns LM + translator + progress + hourly QA

# 3. BUILD + DEPLOY
python work/gowr_wad.py pack work/hebrew.json extract/r_lang_ar.wad out/r_lang_ar.wad
#    copy out/r_lang_ar.wad -> Game Lab/.../exec/wad/pc_le/r_lang_ar.wad
#    in-game: Settings -> Language -> Arabic (العربية)

# 4. PUBLISH  (like SM2/CP2077: GitHub release + Worker slug + Supabase games row)
```

## Format spec (see RECON.md for the full reverse)

- **Outer:** LZ4 frame (`lz4.frame`, magic `04 22 4D 18`). Decompress ≈2.3×.
- **Inner:** WAD, `WTOC` table-of-contents @0, then resource entries; the
  `MSGS_TXT` resource holds the strings.
- **String record:** `*<numeric_id>*\n<value>\n`, UTF-8, ids identical across
  locales. EN value = translation source; write Hebrew into the AR-slot id.
- **Preserve verbatim:** `[[S:CHAR:vo_…]]` voice cues, `\n`, `[style=Highlight]`/
  `[/style]`, `[i]`/`[/i]`, `%d`, `[Icons:…]`, `[<Button>]` glyph refs.

## Translator rules (carry from the playbook §3)

- Local LM **serial** (`--parallel 1`), short strict system prompt (~400 tok).
- Hebrew+Latin only · NO niqqud · copy every `[[S:…]]`/`[style]`/`%d`/`\n` EXACTLY
  · character & place names (Kratos, Atreus, Mimir, Freya, Týr, Svartalfheim…)
  stay in their established Hebrew spelling, build a glossary · `[sound cues]`
  inside `[[S:…]]` are refs, NOT translated.
- **Token-budget batching:** short UI lines batched; a 2,279-char lore letter
  goes solo (`max_tokens` sized per batch).
- Atomic writes; `validate()` accepts a no-Hebrew result only for name/code rows.

## Gotchas (already cost us elsewhere — do not regress)

1. **UTF-8 stdout** — every script `sys.stdout.reconfigure(encoding="utf-8")`;
   launch children with `PYTHONIOENCODING=utf-8`. (Already hit here: the console
   `charmap` error while printing Arabic was exactly this — the data was fine.)
2. **Reload-while-busy** — never `lms unload/load` while a client holds a hung
   request; kill client → `unload --all` → load → probe.
3. **Backup before any game-file write** — `r_lang_ar.wad.he_backup`, revertable.

## מסמכים קשורים
- באותה תיקייה: [[games/godofwar_ragnarok/FEASIBILITY|FEASIBILITY]], [[games/godofwar_ragnarok/FONT|FONT]], [[games/godofwar_ragnarok/GENDER_TASK|GENDER_TASK]], [[games/godofwar_ragnarok/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#godofwar_ragnarok|CLAUDE_INDEX_games]]
