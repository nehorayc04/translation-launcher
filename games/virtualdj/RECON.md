# VirtualDJ 2026 — RECON (Phase-0/1)

**Target:** VirtualDJ 2026, build **9482** (Atomix Productions). DJ software, not a game — same
translation groundwork applies.
**Install:** `C:\Program Files\VirtualDJ\` = just `virtualdj.exe` (**664 MB**, everything packed
inside) + `virtualdj.visualelementsmanifest.xml`. Also `games/virtualdj/install_virtualdj_2026_b9482_pc.msi`
(576 MB, OLE/MSI, the installer).
**User data:** `%LOCALAPPDATA%\VirtualDJ\` (= `C:\Users\Nehoray_Cohen\AppData\Local\VirtualDJ\`) —
`settings.xml`, `Languages\`, `Skins\`, `Cache\`, `Mappers\`, `Plugins64\`, … No admin needed.

## Where the text lives — SOLVED
- The exe embeds a **`languages.zip`** (carved by `tools/vdj_lang.py carve`) with **12 language XMLs**:
  `English.xml` (source) · French · Portuguese · Spanish · Dutch · Greek · German · Italian · Russian ·
  Japanese · Chinese (simplified) · **`Arabic.xml`** (the RTL slot).
- On disk these extract/override under `%LOCALAPPDATA%\VirtualDJ\Languages\`. That folder is empty on a
  fresh install (the app reads embedded by default) → it's the **user-override / custom-language location**.
- **Format = loose, plain UTF-8 XML** — NO offsets, NO checksums, NO compression. The easiest container
  class in the whole project (Plague Tale / Anno / Steam tier).

## Schema
```
<language lang="Arabic" iso="ar" author="Atomix Productions" version="8.2" build="9475">
  <Section><Key>value</Key> ...</Section>
  ...
</language>
```
- **18 sections**, **3,894 keys** total. Keys (`Section/Key`) are **IDENTICAL across languages** →
  map EN→HE by key, edit in place. Placeholders `%i %s %d %2F… %%` (131 entries) preserved verbatim.
- Section breakdown (EN): `Actions 813` (VDJScript command help/tooltips — technical) · `Config 1430` ·
  `Settings 438` · `skin_deprecated 303` · `ContextMenu 213` · `tooltips 178` · `Skin 149` · `Plugins 85` ·
  `Columns 72` · `Messages 60` · `Errors 54` · `RootElements 33` · `skintooltips 33` · `Colors 24` ·
  `Search 17` · `AudioSource 10` · `EffectRoot 9` · `DragDrop 7`.

## Language selection — HARDCODED dropdown
The Options→language dropdown is a **hardcoded string** in the exe:
`"English, French, Portuguese, Spanish, Dutch, Greek, German, Italian, Russian, Japanese,
Chinese (simplified), Arabic"` → **there is NO "Hebrew"** and no folder-enumeration of custom names.
⇒ activation = **Arabic-slot hijack**: ship Hebrew inside `Languages\Arabic.xml` and pick **Arabic** in
the dropdown. `settings.xml` already has `<language modified="yes">Arabic</language>` — the user set it.

## Arabic already ships as a near-complete pro translation
Arabic.xml: **3,882 keys, 3,860 differ from EN** (only 22 same) → an excellent Hebrew quality/gender
cross-reference. `iso="ar"` on the slot ⇒ VirtualDJ selects its RTL locale path.

## Tooling built (`tools/`, `work/`)
- `tools/vdj_lang.py` — carve embedded zip · parse/build the XML · `build_hebrew(arabic, he_map)` ·
  round-trip self-test. **Round-trip OK** on English.xml (3,894) + Arabic.xml (3,882).
- `extract/langs_orig/*.xml` (12 originals) · `extract/english.json` · `extract/arabic.json` (id→text).
- `work/build_menu_proof.py` (`--deploy`/`--revert`) — the Phase-1 menu proof (below).

## Open gate → the in-app proof
The ONE thing static analysis can't answer: **does VirtualDJ's skin engine render RTL (bidi) for the
Arabic locale, and does the skin font cover Hebrew?** → the deployed menu proof decides it.
See `FEASIBILITY.md` / `PIPELINE.md`.

## מסמכים קשורים
- באותה תיקייה: [[games/virtualdj/FEASIBILITY|FEASIBILITY]], [[games/virtualdj/PIPELINE|PIPELINE]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#virtualdj|CLAUDE_INDEX_games]]
