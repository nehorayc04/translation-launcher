# Integrity Audit — Truncation Findings
**Generated:** 2026-05-24 · **Scope:** base game + Phantom Liberty DLC

## 📊 Summary

| | base | dlc | **total** |
|---|---:|---:|---:|
| All truncation findings | 1,657 | 518 | **2,175** |
| CRITICAL (multi-signal, multi-sentence loss) | — | — | **73** (68 unique pks; 5 mirrors) |
| HIGH (single strong signal) | — | — | **1,577** |
| MEDIUM (missing terminal punct only) | — | — | **525** |

## 🚦 Severity rules

| severity | rule |
|---|---|
| **CRITICAL** | ≥2 strong signals: e.g. multi-sentence English + Hebrew lost ≥50 % of sentences + ratio < 0.30 |
| **HIGH** | exactly 1 strong signal — clear truncation but localized |
| **MEDIUM** | `MISSING_TERMINAL` only (source ended with `.`/`!`/`?`, Hebrew didn't) |
| **LOW** | unused after the heuristic tightening — empty bucket |

## 🔍 Signals detected

| signal | what it means | hits |
|---|---|---:|
| `CUT_MID_SENTENCE` | Hebrew ends in a connector word (`ו`/`ב`/`ל`/`מ`/`כ`/`ש`/`ה`/`של`/`את`) or an English fallback (`the`/`and`/`is`/…) — LM halted mid-stream | 1,259 |
| `MISSING_TERMINAL` | Source ends with `.`/`!`/`?` (and is ≥2 sentences, ≥30 chars), Hebrew doesn't | 545 |
| `LENGTH_TRUNCATION` | Hebrew < 30 % of source, source is multi-sentence | 354 |
| `SENTENCE_COUNT_LOSS` | Hebrew has ≤ half the source's sentence count AND <60 % length | 111 |

## 🔴 Top 5 CRITICAL findings (full samples)

### 1. pk=85412 — Dogtown lore page (worst case)
- **section:** `ep1/onscreens/onscreens.json` (+ mirror in `onscreens_final.json`)
- **scale:** 4,232 chars → 1,204 chars (28.4 %), 34 sentences → 16 sentences
- **status:** **HALF the lore narrative is missing** — players reading the Dogtown background page see only the first half of CD Projekt Red's worldbuilding text.
- **all signals:** `CUT_MID_SENTENCE` + `MISSING_TERMINAL` + `SENTENCE_COUNT_LOSS` + `LENGTH_TRUNCATION`
- **EN source (first 200 chars):**
  > "The combat zone known as Dogtown was meant to be Night City's proud calling card. Today, it's but a stain on its conscience, forgotten by NC and its residents, who consider it a mo[…]"
- **HE current (first 200 chars):**
  > "אזור הלחימה שנודע בשם דוגטאון נועד להיות כרטיס הביקור הגאה של נייט סיטי. כיום, הוא רק כתם על מצפונה, נשכח על-ידי תושביה, אשר רואים בו מ[…]"
  → truncated mid-narrative around char 1,204 of 4,232
- **suggested fix:** Re-translate in two halves (split on `\n\n` paragraph break, translate each, concat). Buffer guidance: target ≤ 5,500 chars in Hebrew (~30 % English-to-Hebrew expansion safety margin); the CR2W field is sized for the original 4,232-char English so a ~1.3× buffer fits.

### 2. pk=83000 — Engineering cluster prep list
- **section:** `ep1/onscreens/onscreens.json` (+ mirror)
- **scale:** 540 → 145 chars (26.9 %), 8 sentences → 2
- **status:** 6 of 8 numbered steps dropped
- **EN:** `"1. The clusters you prepped have adequate power, but we'll need older soft on one (Mt-313)…\n\n2. […]\n\n3. […]\n\n…"`
- **HE:** `"הקלאסטרים שערכת מוכנים עם הספק מספיק, אבל נצטרך תוכנה ישנה על אחד (Mt-313)…"` *(only item 1)*
- **suggested fix:** Re-translate each numbered item as its own LM call; rejoin with `\\n\\n`.

### 3. pk=83126 — Dynalar coprocessor shopping list
- **section:** `ep1/onscreens/onscreens.json` (+ mirror)
- **scale:** 519 → 56 chars (10.8 %), 9 sentences → 1
- **status:** **8 of 9 items dropped** — only the Dynalar coprocessor remains
- **EN:** `"1. Dynalar subdermal coprocessor (nb. only v.3.45222 and up)\n2. Drivers for nano-optics…\n3. Cannisters with CB-Net300 coolant…\n…"`
- **HE:** `"מעבד משנה דיינלר תת-עורי (שים לב: רק גרסה 3.45222 ומעלה)"`
- **suggested fix:** Same per-item-call strategy.

### 4. pk=93526 — Thermal breakers TODO list
- **section:** `ep1/onscreens/onscreens.json`
- **scale:** 481 → 29 chars (6 %), 8 sentences → 1
- **status:** **7 of 8 items dropped**
- **EN:** `"1. test thermal breakers (P4, no rush)\n2. program remote activation for night vison…\n3. order 50 hydraulic load sensors…\n…"`
- **HE:** `"בדוק מפרידי חום (P4, בלי לחץ)"`
- **suggested fix:** Per-item.

### 5. pk=87687 — Interrogation recordings list
- **section:** `ep1/onscreens/onscreens.json`
- **scale:** 385 → 55 chars (14.3 %), 4 sentences → 1
- **status:** 3 of 4 recordings dropped
- **EN:** `"1. Recording of the interrogation of Arasaka agent Okimoto Yasushi [DOWNLOAD FILE]\n2. Recording of the interrogation of Zetatech agent Elise Ribie [DOWNLOAD FILE]\n3. Recording of…"`
- **HE:** `"הקלטה של חקירת סוכן אראסאקה אוקימוטו יאסושי [קובץ הורדה]"`
- **suggested fix:** Per-item.

## 🟠 HIGH findings — pattern summary (1,577 total)

| signal | count | typical example |
|---|---:|---|
| `CUT_MID_SENTENCE` | 1,258 | `"…רוצים שתלך עם"` (ends in "עם") — Hebrew dangles on a binding preposition. |
| `LENGTH_TRUNCATION` | 281 | Multi-sentence English (≥80 chars, ≥2 sentences) translated to <30 % length. |
| `SENTENCE_COUNT_LOSS` | 38 | English has 3+ sentences, Hebrew has 1, ratio <0.6. |
| `MISSING_TERMINAL` (with another signal) | 8 | Edge cases — already covered by stronger signals. |

## 🟡 MEDIUM (525) — `MISSING_TERMINAL` only

These are Hebrew sentences that lack the trailing period/exclamation/question mark their English source carries. **Likely safe to fix deterministically** (no LM call) — just append the matching punct character. Sample size to verify pattern: random 5 entries — all are simply missing the closing punct, body is correct.

## ⚠️ CR2W / Buffer safety rules (per task spec)

If any of these fixes are applied via re-translation, gate every result through these checks before writing back to JSON:

1. **No new tags / no removed tags.** Source tag set must equal translated tag set (preserve `<Rich color="...">`, `<br>`, `{0}`, `%s`, `&nbsp;` etc. verbatim).
2. **Length cap:** Hebrew ≤ 1.3 × English source length. Most CR2W string fields are dynamically sized but go up to a known limit; staying under 1.3× of the English keeps us inside what the original archive's slot can hold.
3. **No control-byte injection.** Reject any result containing characters outside the Hebrew range, basic Latin, or the original tag/punctuation set.
4. **Atomic write.** Use the existing `tqf._atomic_write_json` (`.tmp` + `os.replace`) — never touch the file in place. The CR2W is regenerated by `rebuild_dlc_and_pack.py` from this JSON, so a corrupt JSON write = corrupt archive.
5. **NEVER fix entries whose source field is empty / pure code / pure markup.** The audit already filters these out, but the fixer must double-check before writing.

## 📋 Artifacts

| file | content |
|---|---|
| `integrity_audit.py` | The detector itself (re-runnable any time after future translations) |
| `integrity_audit_report.json` | All 2,175 findings, JSON, full source/translation strings |
| `integrity_audit_report.md` | Top 50 per severity, human-readable |
| `integrity_audit_CRITICAL.json` | 68 deduped CRITICAL pks with EN source, HE current, and per-finding fix recommendation |
| `INTEGRITY_AUDIT_FINDINGS.md` | This summary |

## ▶️ Recommended next action

Review the 68 CRITICAL entries in `integrity_audit_CRITICAL.json`. Authorize a focused re-translation pass that:
- Targets the 68 CRITICAL pks only
- Splits multi-section sources on `\n\n` paragraph boundaries before sending to the LM
- Enforces all five CR2W safety rules above
- Writes to the source JSONs but **does NOT re-bake** the archive (defer to next regular release)

Estimated runtime for that focused pass: ~30-45 min (with `--ctx 8192 --parallel 4`).
