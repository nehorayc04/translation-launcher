# FL Studio 2026 Hebrew — PIPELINE

## Phase 1 — DONE (2026-07-21)
- Format identified + cracked: `.moe` = fixed-keystream XOR over gettext `.mo` (`work/moe_crack.py`
  decrypts the metadata block byte-perfect).
- English = embedded source; LTR hijack; font likely free; activation = registry; deploy = loose file.
- FL Cloud Plugins ruled out (thin cloud app).

## Phase 1.5 — full keystream + menu-proof (NEXT)
1. **Recover the full keystream `KS`** (`work/moe_fullks.py`, to finish) via English-msgid crib-drag +
   table reconstruction, and/or the de+es two-file text constraint over the msgstr pool. Save
   `work/keystream.bin`.
   - Validate: decrypt `de.moe` end-to-end → a valid gettext `.mo` (`msgfmt -c` clean) whose msgids are
     the English UI + msgstrs are German. Extract `extract/en.json` (the source corpus) + the string
     count `N` (real scope).
2. **Codec** `work/moe_codec.py`: `decrypt(path)->mo_bytes`, `encrypt(mo_bytes)->moe_bytes`
   (`XOR KS` + 16-byte header), and an **identity round-trip** test (re-encrypt a decrypted file →
   byte-identical). Use `polib` for `.mo` read/write.
3. **Menu-proof** `work/build_menu_proof.py`: build a tiny Hebrew `.mo` overriding ~10 top-level menu
   strings + a Latin marker `ZZ-FL-OK-ZZ`, in BOTH LOGICAL and VISUAL variants (distinct markers), and
   BOTH deploy modes — (A) new `he.moe`+`he.svg` and (B) hijack `vi.moe`. Set the registry, launch FL,
   one screenshot closes: mount · bidi mode · font (tofu?) · which deploy FL accepts.
   - Backup every touched file (`*.he_backup`) + the registry value; `--revert` restores.

## Phase 2 — translate + build + ship (after the proof)
1. **Delegate** the ~N strings EN→Hebrew ([[delegate-all-translation]]; New-Era against the shipped
   de/es/fr/ja/ko/zh as the meaning/context oracle — FL already ships 7 pro translations to cross-check).
2. **Build** `he.moe` via `moe_codec.encrypt(msgfmt(hebrew_po))`, storing LOGICAL or VISUAL per the proof.
3. **QA gate** (token multiset: `%s`/`%d`/`&`-accelerators/`\n`; niqqud; foreign-script; keep-Latin
   brand list — "FL Studio", plugin names, units).
4. **Publish** like VirtualDJ/SignalRGB: GitHub release repo `fl-studio-hebrew-mods`; Worker slug
   `fl-studio-hebrew`; Supabase `games` row id=`fl-studio`, `is_software=true` + `mod_version_history`;
   price per the standing rule (⚖️ but first run the "can this be sold?" check — a `.moe` is a
   from-scratch corpus, NOT a derivative of Image-Line's own file, unlike VirtualDJ, so paid is more
   defensible than the VirtualDJ case; still Image-Line software + trademark → decide before pricing).
5. **Launcher applier** `translation_manager/fl_studio_mod.py` (native, cloud-first): download →
   SHA-verify → drop `he.moe`(+`he.svg`) into `System\Languages\` → set the registry → backup for a
   byte-exact revert. A `kind:"registry"` `game_language.py` entry for the Hebrew/English switch.
   ⚠️ FL install path: detect `Image-Line\FL Studio 2026\System\Languages\` (version folder changes
   yearly — resolve from the registry `HKCU\Software\Image-Line\FL Studio 26` install dir or a scan).

## Tool inventory (`games/fl_studio/`)
| file | role |
|---|---|
| `work/moe_crack.py` | proof-of-format — crib-drags the gettext metadata, decrypts it byte-perfect |
| `work/moe_fullks.py` | full-keystream recovery (2-file + anchors) — to finish in Phase 1.5 |
| `extract/*.moe`, `*.svg` | copies of the 7 shipped language files + selector icons |
| `notes/` | evidence dumps |

Run everything with the **repo `.venv` python** (`.venv/Scripts/python.exe`) — the base Python is a
WindowsApps stub that mis-resolves MSYS paths and lacks `fontTools`.

## מסמכים קשורים
- באותה תיקייה: [[games/fl_studio/FEASIBILITY|FEASIBILITY]], [[games/fl_studio/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#fl_studio|CLAUDE_INDEX_games]]
