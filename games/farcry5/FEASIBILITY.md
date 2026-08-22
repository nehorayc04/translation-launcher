# Far Cry 5 — FEASIBILITY

## Verdict: 🟢 **GO** — one open gate (font), and a deployed proof is waiting on the user

Far Cry 5 is the **same Dunia container family as Far Cry 6**, so the whole read/write chain was
reused rather than re-derived. Everything upstream of the font is solved and proven offline.

| # | Gate | Status |
|---|---|---|
| 0 | RTL locale offered to the user | 🟢 **Arabic is in the in-game language menu**; text/audio independent → English VO free |
| 1 | Container | 🟢 FAT2 **v10** cracked + validated to the byte (FC6 reader reused) |
| 2 | Text format | 🟢 OASIS, 12-byte record; **identity round-trip BYTE-IDENTICAL on all 9 languages** |
| 3 | RTL slot | 🟢 Arabic-slot hijack; engine has a real RTL pipeline (`IsArabicUILanguage`) |
| 4 | Deploy | 🟢 append-relocate + entry repoint; **offline-validated on a real archive copy, revert byte-identical** |
| 5 | **Font** | 🟡 **OPEN** — no raw TTF anywhere; proprietary `FontDescriptor`/`DynamicFontContent` |
| 6 | DRM / integrity | 🟢 no Denuvo, no anti-cheat, no archive checksum |

---

## Why this was cheap

The single highest-leverage move was checking the **container magic before scoping anything**:
`2TAF` + the FC6 header shape meant `games/farcry6/tools/fc6_fat.py` already had a correct
`ver == 10` branch and parsed FC5 unchanged. From there the oasis differed by exactly one field
(12-byte record instead of 16), which a hexdump of the first 64 bytes made obvious.

## Scope

**31,664 records · 25,095 unique English strings · 2.32 M characters**
(UI 18,889 + subtitles 12,775, zero key overlap).

This is a **single-pass, no-fleet** corpus — comparable to AC Mirage (15 k) and well under
Witcher 3 (94 k) or RDR2 (218 k). Subtitles have a median of 106 characters, i.e. real dialogue.

**8 oracle languages come free** (ar/fr/de/it/es/ru/br/ja) at **100 % key parity**, so the
New-Era method applies with no extra extraction work — and Arabic ≈ Hebrew gives the gender
axis directly.

⚠️ A content scan reports **more oasis blobs than the 18 named** (52 in `common.fat`, 172 in
`patch.fat`, 40 per story DLC). Fold those in before declaring the corpus complete — the number
above is the *named* UI + subtitle corpus, not necessarily the whole game.

## The bidi question — predicted, not assumed

The game's own Arabic is stored **LOGICAL**, with **zero presentation forms** and **zero bidi
control characters**, so the engine does its own shaping and reordering. But that pipeline is
very likely gated to the **Arabic script**: this is the exact signature that made
**Far Cry 6 store VISUAL** for Hebrew, and the same story played out on AC Mirage and Witcher 3
patch 4.00.

**Prediction: store VISUAL.** The deployed proof puts the same word in both modes on adjacent
menu rows, so one screenshot settles it instead of a guess.

## The one open gate — the font

Six archives, ~360 k entries, scanned for an sfnt magic anywhere in the first 4 KB with a
table-directory check and a real font load: **0 fonts**. The engine DLL embeds none and never
mentions `.ttf` / `.otf` / `.ffd` / `.fnt`. It does ship `FontDescriptor.cpp`,
`DynamicFontContent.cpp`, `CFont`, `CFontBank`, and 41 references to `.xbt` (the Dunia texture
container).

So the font is a proprietary descriptor + glyph atlas. The strongest lead is that **Watch Dogs 2
— same Ubisoft Dunia lineage — uses exactly that shape** (`.ffd` metrics + `.xbt` TBX/DXT5 SDF
atlas), and it is already solved in this repo (`games/watchdogs2/work/wd2_font.py`, which adds
Hebrew to an Arabic atlas while keeping every original glyph pixel- and metric-identical).

Arabic renders in-game today, so an Arabic-capable font definitely exists; the only unknown is
whether it also carries Hebrew. **The proof answers that directly** — and the Latin marker in the
same build separates "the file never loaded" from "the font has no glyphs", which otherwise look
identical.

## Risk register

| risk | assessment |
|---|---|
| Hebrew renders as tofu | Likely. Mitigation = the WD2 atlas path, a solved class. Not a blocker, a sub-project. |
| Bidi turns out VISUAL | Expected; `python-bidi` + the store-VISUAL rules are already standard here. |
| Extra un-named oases missed | Known and quantified; the content scan enumerates them. |
| Game update overwrites archives | Deploy keeps `.he_backup` + a journal; re-run after an update. Record the deployed hash so a revert can never downgrade. |
| Integrity check on archive content | None found: no Denuvo, no per-archive checksum, and a repointed appended entry re-read correctly. |

## Recommendation

Proceed. Phase 1 is complete pending the user's screenshot. If Hebrew renders, this is a
**medium-easy** target with an unusually rich oracle panel. If it tofus, the remaining work is a
scoped, previously-solved font sub-project.

## מסמכים קשורים
- באותה תיקייה: [[games/farcry5/PIPELINE|PIPELINE]], [[games/farcry5/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#farcry5|CLAUDE_INDEX_games]]
