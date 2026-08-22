# The Witcher 3 Hebrew — Known Issues

Status of the shipped build: `v1.0.0-beta.1` (download link only, NOT published to the site).
Shipped as a **declared BETA** (2026-07-18) — `קרא_אותי.txt` carries a "מצב הגרסה" section
listing the open items for the end user.

---

## ✅ TRACK A — fixed pre-launch (2026-07-18), `work/fix_glossary_a.py`

A pre-launch audit found systemic **glossary + spelling** defects on the most-visible UI.
All fixes are deterministic and **guarded by the ENGLISH source** (a word is only swapped
where the EN really uses that term), so look-alike words are never touched.
**1,038 strings changed** — backup `fleet/hebrew.json.bak.trackA.*`.

| kind | count | examples |
|---|---:|---|
| glossary | 159 | `Potions` תחליבים→**שיקויים** · `Oils` שומנים→**שמנים** · `Stamina` אינסטנט→**סיבולת** · `Vitality` חיוות→**חיוניות** · `Mutagens` מטוגנים→**מוטגנים** · `Toxicity` טוקסיציות→**רעילות** · `Meditation` השתקעות→**מדיטציה** (11 more, beyond the 9 fixed on 07-14) · `Inventory` מטען→**ציוד** · `Trophy` טרופי→**גביע** · `Decoctions` תססים→**מרקחות** |
| stray bidi controls | 138 | leftover `U+202A..U+202E` in HEBREW values — the engine ignores bidi controls for Hebrew, and an RLO makes the line render **MIRRORED**. Now 0 in Hebrew values (the 12 left in the live file are untouched vanilla **Arabic**/credits strings — correct). |
| `witcher` spelling | 799 | 53 of 106 variants normalised to the dominant canonical **ויטצ'ר** / **הוויטצ'ר** (word-initial vav doubles after a prefix). Ambiguous leading-`וו` tokens are deliberately left alone; `מכשף` is a valid alternative and is untouched. |

⚠️ **The witcher normaliser must NOT be a naive in-place regex** — `ו` is both a valid prefix
("and") and the stem's first letter, so a regex re-prefixes an already-correct token
(`ויטצ'ר` → `ווויטצ'ר`). It is built as an explicit, reviewable token→token map, plus a
`בומבו` blacklist (EN "bumbotcher" merely ends like the stem) and the EN guard.

---

## 🟠 OPEN — translation QUALITY (the real gap; tracks B/C)

The audit also showed the corpus was never systematically reviewed: **the "New Era"
verified pass covers only 1,554 of 94,167 strings (1.7 %)**. Measured defects that remain:

* **1,758 English labels have 2-9 different Hebrew renderings** → **6,366 strings** affected.
* Real mistranslations in dialogue, e.g. `The Witcher of Rivia` → **הכומר** מריביה (*the priest*),
  `Ah, witcher.` → **ינשוף** (*owl*), `silver sword` → **חנית** (*spear*), `monsters` → **ווחשים**,
  `defeat` → **הובידו** (typos).
* Mojibake leaking into values (`ג'רált`), broken entities (`מ;set`).

**Planned:**
* **Track B** — fleet review of the 30,480 short UI/label strings on VM1+VM2 (~10-16 h).
* **Track C** — full New-Era pass over all 94,167 strings (~3-5 days on 2 VMs; faster with
  vm4/vm5/laptop back in the fleet). The hard limit is NIM free-tier throttling.

---

Everything below is a KNOWN, DOCUMENTED defect — none of it is fixable by changing the translation.

---

## 🔴 BUG #1 — RTL placement of DYNAMIC VALUES (numbers) next to a Hebrew label

**Symptom (confirmed in-game, meditation clock):**
The game shows `12:00 מדיטציה עד` / `13:00 הזמן הנוכחי` — the number is read FIRST.
It should read `מדיטציה עד 12:00` / `הזמן הנוכחי 13:00` (number last).

**ROOT CAUSE (traced end-to-end, 2026-07-14):**
1. The value is **NOT translatable text.** The script pushes it to the Flash as a raw number:
   `meditationClockMenu.ws` → `m_flashValueStorage.SetFlashInt("meditation.clock.hours", timeHours)`.
2. The **Flash** (`gameplay\gui_new\swf\meditation\panel_meditation_clock.redswf`) composes the whole
   line inside ONE center-aligned htmlText field, in the ActionScript function
   **`updateCurrentTimeString`**: `label + ": " + HH + ":" + MM`
   (the default text in the SWF is literally `<p align="center"><font …>Current Time: 00:34</font></p>`).
   This is compiled **AS bytecode**, not a static template.
3. **The Witcher 3's text engine runs bidi + shaping ONLY for ARABIC script.** Hebrew (which we ship
   inside the Arabic locale slot) is rendered **LTR / non-bidi** — that is exactly why the whole mod
   must store Hebrew **VISUAL** (pre-reversed). Because there is no bidi for Hebrew, the value that the
   AS appends *after* the label lands on the read-first side.

**PROOF that this is an engine limitation, not our data** (the decisive test — user reverted the mod):
* **Vanilla ARABIC renders it CORRECTLY** (`13:00 تأمّل حتى` — number after the label). The game DOES
  know how to place it; it only does so for Arabic script.
* Every possible loc-string encoding was tried on our Hebrew and **all failed**, because the number is
  not in the string at all:
  | stored form | result |
  |---|---|
  | VISUAL (`דע היצטידמ`) | text readable, number on the wrong side |
  | LOGICAL + RLO `U+202E` (matching the vanilla Arabic byte-for-byte) | **text turned mirror-reversed**, number did not move → the engine **ignores bidi controls for Hebrew** |
  | VISUAL + RLO | text readable, number still did not move |

**SCOPE — this is almost certainly NOT limited to the meditation clock.**
Scan of all 1,486 game scripts (2026-07-14) for dynamic values pushed to Flash:

| kind | call sites |
|---|---|
| `SetFlashInt` | 24 |
| `SetFlashNumber` | 6 |
| **numeric total (the bug-prone class)** | **30** |
| `SetFlashString` | 60 |

The 30 numeric call sites span **12 menus** — meditation clock is only **4 of 30**:

```
  4  inventoryMenu.ws          4  mapMenu.ws
  4  meditationClockMenu.ws    4  uirescaleMenu.ws
  2  characterSkillsMenu.ws    2  preparationMenu.ws
  2  preparationBombsAndPotionsMenu.ws   2  preparationMainMenu.ws
  2  preparationMutagensMenu.ws          2  preparationOilsMenu.ws
  1  characterMenu.ws          1  characterPerksMenu.ws
```

⚠️ Not every call site is a defect — the bug only appears where the Flash composes a **translated label
+ the number in the SAME text field**. A per-screen audit is required (open each menu in Hebrew and look
for a number sitting on the wrong side of its label).

**FIX OPTIONS (next version):**
* **(a) Per-screen Flash edit** — reverse-engineer and patch the AS bytecode of each affected `.redswf`
  so it composes `value + " :" + label` (RTL order). Since our mod ships Hebrew only (nobody plays the
  real Arabic with it), reordering there is safe for us. **HIGH RISK** — these are core menus
  (inventory / character / map); a broken Flash breaks the menu. Needs backup + in-game test per screen.
* **(b) Engine-level bidi for Hebrew** — not possible from a mod.
* **(c) Accept** — current decision for `v1.0.0-beta.1`. Cosmetic; label and value are both readable.

---

## 🟡 BUG #2 — keybind icon shows `*E*` instead of `[E]`

English shows `[E] Meditate` / `[ESCAPE] Back`; the Hebrew (Arabic slot) shows `*E* מדיטציה` /
`*ESC* חזרה` (asterisks + abbreviated key names). This is the **game's own keybind style for the Arabic
locale**, rendered by the GUI/Flash layer — it is not a translatable string. Changing it means editing
the Flash. Cosmetic; the key letter is readable. **Left as-is.**

---

## 🟡 Deferred — wording/phrasing pass

Per the user (2026-07-14): phrasing/wording corrections are deferred to the next version.
Fixed in this build (a real mistranslation, not phrasing): `Meditation` was rendered as the
nonsense word **"התרסה"** and as the clumsy **"השתקעות"**, while `Meditate` was correctly **"מדיטציה"** —
all 9 ids unified to **מדיטציה** / **מדיטציה עד**.

A broader **UI-terminology QA pass** (agent-driven, per `[[delegate-all-translation]]`) is recommended
before the next release — the `Meditation` inconsistency suggests other UI terms may be wrong too.

## מסמכים קשורים
- באותה תיקייה: [[games/witcher3/FEASIBILITY|FEASIBILITY]], [[games/witcher3/PIPELINE|PIPELINE]], [[games/witcher3/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#witcher3|CLAUDE_INDEX_games]]
