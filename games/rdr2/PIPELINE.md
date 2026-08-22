# RDR2 — PIPELINE (build + deploy)

Prereqs (once): FFdec 26.2.1 (`ffdec.jar`, needs Java — Adoptium JDK present) for the font;
the repo `.venv` python for the codec. Deploy needs LML + RDR2 ASI Loader + ScriptHookRDR2 in
the game folder (user-installed).

## Tools (this project)
- `work/rdr2_text.py` — the LML text-override codec. `parse` / `serialise` / `to_map` /
  `build_hebrew(records, {key: logical_he})` (stores VISUAL via GTA's `visual_line`). Round-trip
  self-tested. **Import path:** it adds `../../gtav/work` to `sys.path` to reuse `visual_line`.
- `work/rdr2_font.py` — Hebrew glyph injection. Reuses GTA's `font_add_hebrew.add_to_face`;
  auto-detects a 27-glyph donor face. Input/output = FFdec font XML.
- `work/build_menu_proof.py` — assembles the ready LML menu-proof (text + font).
- `extract/key_universe.json` — the 231,993 keys (labels + hashes) from the Ko Games mod.

## Font build (one-time per game patch)
```
J=…/scratchpad/ffdec/ffdec.jar
# 1. decompile the (Arabic-modded, or vanilla) font to XML
java -jar $J -swf2xml font_lib_efigs.gfx  rdr2_font.xml          # ~35s, ~350 MB XML
# 2. inject 27 Hebrew glyphs into all 18 faces (donor = GTA V Hebrew set)
python work/rdr2_font.py  ../gtav/work/fontwork/gen_allheb.xml  rdr2_font.xml  rdr2_font_he.xml
# 3. recompile
java -Xmx8g -jar $J -xml2swf rdr2_font_he.xml  font_lib_efigs_HE.gfx   # ~15s
```
Result: valid GFX v8, +18×27 Hebrew glyphs (~+30 KB). Precedent (Ko Games Arabic) proves this
exact .gfx slot renders injected glyphs in-game. (Optional quality pass: match a Hebrew donor to
each face's style; for the proof the donor's shapes on all faces are fine.)

## Text build
```python
import rdr2_text as R
base = R.parse(open("Ko Games Studio.gxt2", encoding="utf-8").read())  # optional: as fallback
he   = {...}   # {key: LOGICAL hebrew}  (from the translated corpus)
recs = R.build_hebrew(base, he)          # stores VISUAL, keeps untranslated keys from base
open("RDR2 Hebrew.gxt2","w",encoding="utf-8").write("# RDR2 Hebrew\n\n"+R.serialise(recs)+"\n")
```

## Deploy (LML) — layout
```
<RDR2>/lml/mods.xml                    (register + load order)
<RDR2>/lml/<font>/install.xml          (<FileReplacement> -> font_lib_efigs.gfx)
<RDR2>/lml/<font>/asset_replace/font_lib_efigs.gfx
<RDR2>/lml/<text>/install.xml          (<DataFile>RDR2 Hebrew.gxt2</DataFile>)
<RDR2>/lml/<text>/RDR2 Hebrew.gxt2
```
`RDR2_Hebrew_menu_proof_lml.zip` is a ready example of this exact layout. Activation: none in
game — keep RDR2 in English; the DataFile override replaces the active strings, the font renders
them. Revert: delete the two mod folders (or disable in `mods.xml`).

## English corpus (Phase-2 input) — get `{key → EN}`
- **A (manual, reliable):** OpenIV → `update_3/x64/data/lang/*.yldb` → export "Save raw content"
  → `.full` → ModActivator → `.txt`. Reconcile keys against `extract/key_universe.json`.
- **B (automate):** pure-Python RPF8 reader (AES key from `RDR2.exe` + RPF8 TOC; ref
  `VIRUXE/rpf-rs`) + yldb parser. Only if zero manual steps are required.

## Phase 2 (haul) — same shape as the other games
Delegate ~232k EN→Hebrew (agent handoff template; **NEVER Claude**). Gender oracle = the Ko
Games Arabic per key (Arabic ≈ Hebrew) + a canonical **name registry** (web-verified, enforced
every line). QA (tokens/foreign/niqqud). Build VISUAL → LML package → publish (GitHub repo +
Supabase `games` id=`rdr2` + `mod_version_history`). VISUAL is confirmed by the menu-proof first.

## מסמכים קשורים
- באותה תיקייה: [[games/rdr2/FEASIBILITY|FEASIBILITY]], [[games/rdr2/INSTALL|INSTALL]], [[games/rdr2/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#rdr2|CLAUDE_INDEX_games]]
