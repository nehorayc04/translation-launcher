# KCAP .xpps — VERIFIED format crack (2026-07-07)

Independent verification against the REAL `lang_english_text.xpps` (16,583,124 B) and
`lang_arabic_text.xpps` (17,064,240 B). Ran BOTH candidate readers + raw byte analysis.

## VERDICT: `tools/xpps_alt.py` is CORRECT. `tools/xpps.py` is REFUTED (misaligns).

### Record layout — PROVEN
Every index record is **16 bytes: `{ u64 key ; u32 off ; u32 pad(=0) }`** (little-endian).
String = UTF-8 at `file[BASE + off]`, NUL-terminated. `BASE` = u32 @0x28 (EN 484 / AR 472).
Proof (raw records located by their target string):
- "Continue"  rec `bfe655a46d40e3e0 a2c80200 00000000` → key=`e0e3406da455e6bf` off=0x2c8a2 ✓
- "New Game"  rec `67c47394036f42fe 5e960300 00000000` → key=`fe426f039473c467` off=0x3965e ✓
- "Watch out!" rec `0000300000000000 1d700b00 00000000` → key=`0x300000`          off=0xb701d ✓
- "I cannot be stopped!" rec `0000050000000000 d1371000 00000000` → key=`0x50000`  off=0x1037d1 ✓
`xpps.py` reads the SAME bytes shifted −4 (`{u32 z,A,GROUP,off}` with off@[12:16]) → its
GROUP/A keys are the u64 split and it dedups/aligns WRONG → dialogue misaligns across languages
(e.g. it paired "I cannot be stopped!" with "أنا أعتمد على ذلك"). Empirically refuted.

### TWO key kinds (critical)
- **large-hash keys (> 0xffffffff)** = UI / menus / content. GLOBAL, SHARED across languages →
  join EN↔AR by exact u64 key. RELIABLE. Anchors: Continue→متابعة, Options→الخيارات,
  Subtitles→الترجمة, New Game→لعبة جديدة, Load Game→تحميل اللعبة (all correct).
- **small structured ids (fileId<<16 | line, e.g. 0x50000, 0x300000)** = dialogue / subtitles.
  These are **per-block LOCAL, NOT globally unique — they COLLIDE** ("Watch out!" and "Nobu!"
  both = 0x300000). Do **NOT** join dialogue by key alone → join by block(table)+position in
  Phase 2. (xpps_alt's docstring already warns this.)

## SCOPE (real numbers, proven layout, whole-file scan)
| | EN | AR |
|---|---:|---:|
| TOTAL clean records | 47,258 | 42,226 |
| — large-hash (UI/content) | 18,280 | 13,723 |
| — small-id (dialogue/subs) records | 28,978 | 28,503 |
| — small-id UNIQUE keys | 14,926 | 14,686 |
| — small-id global collisions | 14,052 | 13,817 |

- **UI/content join (large-hash): 13,078 shared keys**; of 13,068 with latin EN → 11,856 (90.7%)
  are genuine Arabic translations, 824 are identical passthroughs (single letters 'y'/'S'/'P',
  codes 'HDR', short labels) — correct behavior.
- Dialogue = the bulk (~28,978 EN records) but joins by block+position, not key.

## Reader-count reconciliation
- `xpps_alt` reports EN=15,058 / AR=14,915 = only the strictly-ascending-key table subset
  (≈12,911 large-hash + ≈2,147 dialogue). It is CORRECT but **UNDERCOUNTS** (misses ~2,400
  large-hash UI + ~26k dialogue records). Its ascending-key + min_len=8 table scanner is too
  strict. A production reader should scan ALL `{u64,u32,u32:0}` records and handle small-id
  dialogue by block+position.
- `xpps.py` reports EN=47,332 ≈ the true TOTAL record count, but with WRONG keys/alignment.

## BIDI verdict
python-bidi available. A stored Arabic UI string `'لقد فعلنا هذا معًا'` (key 80065881cc417089)
→ `get_display()` = `'اًعم اذه انلعف دقل'` (reordered). Stored ≠ display ⇒ **the file stores
Arabic in LOGICAL reading order and the engine performs its own bidi at draw time** (consistent
with Sony shipping GoT's Arabic as a polished first-party locale, and the shipped Persian mod).
**Working hypothesis: store Hebrew LOGICAL.** NOT final — needs an in-game menu-proof (the
Witcher-3/GoWR risk: an Arabic-specific reshaper might not reorder the Hebrew block; and FONT
glyph coverage for U+0590–05FF in the Arabic-slot face is the more likely blocker). Proof should
store ~6 strings BOTH logical and pre-reversed and screenshot once.
