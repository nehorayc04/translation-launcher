# The Witcher 3 — Hebrew — PIPELINE (build recipe)

The proven Arabic-slot hijack, adapted to REDengine 3 `.w3strings`. Codec: `work/w3strings.py`.

## 0. One-time prerequisites
- **TW3 ModKit** (`wcc_lite.exe`) or **WolvenKit 0.6.1** + **JPEXS** + **FontForge** — for the FONT only
  (Scaleform SWF in `r4gui.bundle`). Text needs no bundle tool.
- Back up before any game-file write: copy the touched `content\*\ar.w3strings` +
  `dlc\*\content\ar.w3strings` (and, if we ship a font, `r4gui.bundle`) to
  `~/.translation_manager/mod_backups/witcher3/<ts>/`.

## 1. Extract the source + skeleton  (`work/`)
```
# Decode every English source file (the translation source) and every Arabic file (the target skeleton):
py work/dump_corpus.py            # -> extract/en.json  {str_id: english}   (+ per-file map)
                                  #    extract/ar.json  {str_id: arabic}    (skeleton, for reference)
```
- Source = EN (decrypted by the codec). Target slot = AR (cleartext). Map is **by `str_id`** (shared).
- Preserve tokens verbatim in translation: in-string tags/markup TW3 uses — `<br>`, color/format tags,
  `%s`/`%d`, and any control chars. Keep the leading `U+202E` handling to the BUILD step (§3), not the
  translator — the agent/LM translates clean logical Hebrew.

## 2. Translate EN → Hebrew  (delegated — Phase 2)
Per the standing rule ([[delegate-all-translation]]): Claude builds the tooling + glossary + handoff;
a Google/Antigravity agent (or the local-LM trio) does the actual translation. Build an
`agent_handoff/` like WD2/Anno: `to_translate.json` ({str_id: en}), `skip.json` (ids that stay
Latin — proper nouns/codes), `hebrew.json` (output, LOGICAL Hebrew), and the `get_batch`/`merge_batch`
loop with a token-preservation + no-Hebrew-on-prose anti-cheat gate.
- **Witcher glossary** (lock early): Geralt=גe'ראלט, Ciri=סירי, Yennefer=ינפר, Triss=טריס,
  witcher=מכשף, Wild Hunt=הציד הפראי, Nilfgaard=נילפגארד, Novigrad=נוביגרד, Skellige=סקליגה,
  Roach=חוֹמְצָה/רוֹץ' … (finalize with the user).

## 3. Build the Hebrew `ar.w3strings`  (`work/build_ar.py`, uses `w3strings.py`)
For each content/DLC file:
```
he   = hebrew.json                              # {str_id: LOGICAL hebrew}
ar0  = decode(<file>/ar.w3strings)              # original skeleton (block2 key_hash map + id set)
entries = [ {str_id: id, text: visual_line(he[id] or fallback)} for e in ar0.entries ]
out  = encode(entries, ar0.block2, version=163) # cleartext, key1=key2=0
write out -> Mods\modHebrew\content\<mirror>\ar.w3strings   (+ per-DLC)
```
- **Store VISUAL** — apply `visual_line()` (reverse each Hebrew run, keep space/Latin/digit/symbol runs
  forward, flip run order, per line) at build time. **No RLO.** (Confirmed in-game: the menu is NON-BIDI
  for Hebrew; logical+RLO renders mirrored, VISUAL renders correct — see RECON.) `visual_line` is in
  `work/build_menu_proof.py` (promote it to a shared `work/rtl.py` for the full build).
- The translator/agent writes **LOGICAL** Hebrew; `visual_line` is applied ONLY at build.
- Keep `block2` (key_hash→str_id) verbatim from the original `ar` file.
- Fill any id present in `ar` but missing from `hebrew.json` with the English/Arabic fallback so no id
  is dropped (the game must find every id it references).
- Numbers/Latin inside a line: `visual_line` keeps them forward + flips run order; eyeball one such
  line in-game during Phase 2.

## 4. Font — ✅ NONE NEEDED
The vanilla Arabic-locale font already renders Hebrew (confirmed in the menu proof, zero tofu). Skip.

## 5. Deploy
- `Mods\modHebrew\content\...\ar.w3strings` (+ per-DLC), enable in the mod list (or overwrite base
  `content\*\ar.w3strings` directly; keep the backup for revert).
- **Activation:** Options → Text Language = **Arabic (العربية)**; Speech = **English**
  (or `user.settings [Localization] TextLanguage=AR`).

## 6. Publish (when in-game confirmed)
Same as SM2/WD2/Anno: GitHub release repo `hebrew-translation-hub/witcher3-hebrew-mods` (FULL release so
`releases/latest` resolves) + `manifest.json` + zip (the Mods folder + font) + `install.py`; Worker
slug `witcher3-hebrew`; Supabase `games` row (`id="witcher3"` — matches the launcher `gameId`) +
`mod_version_history`. Launcher: a native applier `translation_manager/witcher3_mod.py` (drop the
`.w3strings` into `<game>\Mods\`, reversible) + detection (exe `witcher3.exe`).

## Key facts to not re-discover
- Arabic slot is **cleartext** (keyID 0) → no encryption for Hebrew.
- `str_id` is shared across languages after `^encKey` → map EN→HE by id.
- Bidi = **VISUAL (pre-reversed, `visual_line`, no RLO)** — confirmed in-game; the engine has no Hebrew bidi.
- **Font already covers Hebrew** — no SWF/font work at all.
- No anti-cheat; text deploy needs no bundle repack.
- version byte = **163** (0xA3); `emit_bit6` proven for our count range.
- Menu proof lives in `work/build_menu_proof.py` (`--deploy`/`--revert`); backup = `content0/ar.w3strings.he_backup`.

## מסמכים קשורים
- באותה תיקייה: [[games/witcher3/FEASIBILITY|FEASIBILITY]], [[games/witcher3/KNOWN_ISSUES|KNOWN_ISSUES]], [[games/witcher3/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#witcher3|CLAUDE_INDEX_games]]
