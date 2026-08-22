# Corsair Cove — FEASIBILITY: ✅ ALL GATES CLOSED IN-GAME, 🟢 GO (easiest tier)

**Every Phase-1 gate is CLOSED, and the last four were closed by ONE in-game screenshot.**
Nothing was reverse-engineered from scratch — the container and the text codec are reuse
from Until Dawn / Hogwarts Legacy; only the DEPLOY mechanism was specific to this build.

| gate | verdict | evidence |
|---|---|---|
| **0. RTL slot** | 🔴 none → **LTR (`en`) slot hijack** | 12 cultures, all LTR/CJK; no `ar` |
| **1. Container** | 🟢 free | pak **v11, unencrypted**, read+written by the vendored `repak` |
| **2. Text codec** | 🟢 **byte-identical round-trip on all 12 cultures** | `tools/cc_locres.py` |
| **3. Deploy** | ✅ **hijack a shipped 339-B EMPTY pak stub**, zero user action | proven in-game |
| **4. Font** | ✅ **27/27 render, ZERO tofu** | proven in-game |
| **5. DRM** | 🟢 none | no Denuvo/VMP/EAC/BattlEye, unpacked PE |
| **6. bidi** | ✅ **LOGICAL + a leading RLM** | A/B pair + a 3-rung base-direction ladder, in-game |

**🔴 An ADDED pak is NEVER mounted on this build** — `~mods/`, the flat `Paks/` folder, an
invented `pakchunk999`, and a manifest-known `pakchunk0-WinGDK_P.pak` were all tried and all
ignored. This is a Microsoft-Store/GDK build whose `package.manifest` + `layout_*.xml`
enumerate every shipped pak by name. **The lever is to hijack one of the 24 shipped
339-byte ZERO-ENTRY stubs** (`pakchunk0_s1..s24-WinGDK.pak`): they are manifest-listed, so
the engine definitely mounts them, and they contain nothing, so overwriting one loses
nothing. Backup = 339 bytes; their `.ucas`/`.utoc` are never touched.

**Both text surfaces are live** (each proven from its own stub): the `en` locres
(`pakchunk0_s2`) AND the runtime StringTable CSV (`pakchunk0_s3`).

## Why this is the easiest tier

1. **`repak` reads and writes the paks with no key** — magic checked first, exactly as the
   playbook prescribes, and it collapsed the whole container workstream into reuse.
2. **The text format is PUBLIC** (UE `FTextLocalizationResource`). `cc_locres.py` rebuilds
   every shipped `.locres` **byte-identically**, so a build can never drift structurally.
3. **The fonts are bare TTFs in a legacy pak** — no atlas, no SDF, no IoStore repack.
4. **Deploy costs the user nothing**: `en` is the default culture, so a patched `en`
   locres is on the first screen with no setting to change.

## Scope

```
records                12,821          (172 namespaces)
GLOBAL unique          11,914          <- the translation workload
characters            742,852          median 35, p90 130, max 830
  UI / content         9,203 rec /  8,403 unique
  recorded VO/dialogue 3,598 rec /  3,506 unique
```
A **single pass — no fleet** (comparable to SignalRGB ×6, VirtualDJ ×3).

The UI/VO split comes from the engine's OWN metadata (a non-empty `Audio Filename`
column = a recorded VO line), never a length or filename heuristic.

## Tokens to preserve (measured over the 12,821 en entries)

| token | occ | distinct | examples |
|---|---:|---:|---|
| `{VAR}` | 1,561 | 151 | `{Target}` `{TargetName}` `{absAmount}` `{0}` |
| `<tag>` | 1,894 | 139 | `<hl>` `<b>` `</>` `<img id="Coin"/>` |
| real `\n` | 762 | — | on 278 lines |
| `[bracket]` | **0** | 0 | — |
| `&entity;` | **0** | 0 | — |
| printf | 0 real | — | the 11 `%`-hits are literal percent signs in prose |

An unusually clean token set: no overloaded bracket syntax, no entities.

## 🔑 The differentiator: the developers shipped a LOCALISATION KIT

The 172 CSVs are not just source strings — every row carries translator metadata:

| column | filled | value |
|---|---:|---|
| `Context` | **12,801 (99.8 %)** | e.g. *"Name of a game setting."*, *"VO during cutscene"* |
| `Speaker` | 3,632 (28.3 %) | `Rambullion`, `Amara`, … |
| `Addressee` | 2,483 (19.4 %) | `self`, a character, a group |
| `SpeakerGender` | 1,225 | male 718 · female 496 |
| `AddresseeGender` | 1,147 | variable 1,014 · male 46 · female 46 · plural 36 |
| `Order`/`Place of the Sequence` | 6,488 (50.6 %) | conversation ordering → sliding-window context |
| `Audio Filename` | 3,598 | the UI-vs-VO discriminator |

This is the **gender oracle handed over as first-class data** — normally it has to be
reverse-engineered out of the game's Russian/Polish/Arabic. Emitted per key to
`extract/context_source.json` (12,821 rows) together with the reference languages.

⚠️ **The columns are REAL but DIRTY** — mixed case, a `Variable`/`various` bucket (the
addressee is the player, whose captain may be either gender), plural addressees written
as a group NAME (`Pirate Crew`), and a few rows where a `Comment` leaked one column left.
`scope_report.norm_gender()` maps them to a closed set and **refuses to guess** from free
text; a named character is kept as `named:<X>` rather than turned into a gender.

## New-Era reference panel — free and complete

All **11** other cultures are at **100.0 % key parity** with `en` (12,821/12,821):

* **ru, pl** — past tense marks SPEAKER *and* ADDRESSEE gender (what English drops)
* **fr, it, es, pt-BR** — referent gender
* **de** — register
* ja, ko, zh-Hans, zh-Hant — phrasing cross-check

## 🔴 Do NOT dedup by the English string — measured, not assumed

600 duplicate-English groups (1,507 keys). Against the game's own professional locales
they diverge at **fr 14.8 % · pl 11.5 % · es 6.3 % · de 6.2 % · ru 1.5 %** — so ~1 in 7
of those groups genuinely needs two different Hebrew renderings.
**Key the pool by `(namespace, key)`.**

## ✅ What the in-game proof settled (2026-08-02)

| row | stored | rendered | verdict |
|---|---|---|---|
| Resume | `ZZ-S2-LOCRES-ZZ` | shown | the stub mounts, the `en` locres wins |
| Story Mode | `שלום` LOGICAL | readable | **bidi = LOGICAL** |
| Uncharted Mode | `םולש` VISUAL | mirrored | VISUAL is wrong — do NOT pre-reverse |
| Load | `ZZ-S3-CSV-ZZ` | shown | the runtime CSV is a live SECOND surface |
| Settings | `אבגד` | correct | direction control agrees |
| Credits | all 27 letters | **zero tofu** | the Alegreya injection renders |
| Quit | `1 שלום` | correct | digit placement agrees |

### The LONG-paragraph gate (round 4, the description panel)

| gate | stored | result |
|---|---|---|
| WRAP | 330 chars, no newline | ✅ 4 lines, right-aligned, top-to-bottom order correct; `(anti-aliasing)` `1920x1080` `ב-30%` `"איכות" ל"ביצועים".` all placed correctly |
| LINE ORDER | an explicit `
` | ✅ line 1 ABOVE line 2 — the RDR2 store-VISUAL wrap bug does not exist here |
| BASE DIRECTION | opens with `AMD FSR 2.2` | 🔴 **left-aligned, neutrals on the wrong side** |

**🔴🔴 THE LAST RULE, and it is not "store natural Hebrew":** the UBA picks a paragraph's
base direction from its **FIRST STRONG character** (P2/P3). A Hebrew line that OPENS with a
Latin run — a brand, a version number, or a `{VAR}` the engine fills with Latin **at
runtime** — gets an **LTR base**: the whole paragraph left-aligns and its neutrals (`;`
`טווח:` `0-100%`) land on the wrong side. The engine is correct; the SOURCE is the problem.

Settled by a 3-rung ladder on three adjacent description panels:

| rung | fix | result |
|---|---|---|
| **A** | prepend **U+200F (RLM)** | ✅ right-aligned, punctuation correct, **no tofu** |
| **B** | reword the source to open in Hebrew | ✅ right-aligned |
| **C** | untouched control | ✗ still left-aligned — proves the comparison is real |

**A is the shipping rule** (`cc_rtl.to_logical`): it needs no discipline from the translator
and it is immune to runtime `{VAR}` substitution. ⚠️ **The fonts had NO glyph for U+200F**, so
a bare RLM would have rendered as a TOFU box (the Spider-Man 2 trap) — `cc_font` now maps the
whole bidi-control set to a zero-width, zero-contour glyph (verified in the live font:
`U+200F -> bidi_zero, contours=0, advance=0`).

Only cosmetic work is left: font size/weight calibration against the shipped Latin.
