# Until Dawn (2024 remake) — FEASIBILITY

## Verdict: 🟢 **GO — ALL GATES CLOSED, menu-proof PASSED in-game (2026-07-08)**

**User-confirmed in-game**: the main menu rendered `BATES_MENU_QUIT` as **"יציאה"**
(clean, correctly-oriented Hebrew, same visual style as the surrounding Latin menu
items — no tofu) with **Text Language left at the default (English)** — i.e. the
**best-case outcome**: the `en/Game.locres` slot IS loaded by the engine even
though it equals the native culture, so activation needs **zero user action**.
This single confirmation closes all three open questions at once: (1) the `en`
slot loads, (2) bidi = LOGICAL works correctly (not mirrored), (3) the
Univers-family Hebrew-injected font renders cleanly. Ready for Phase 2.

Unlike almost every other game here, the container needs **no reverse
engineering at all** — it's a stock, unencrypted Unreal PakFile V11 (same as
Hogwarts Legacy) readable/writable with the existing `repak.exe`, and the
text format is Unreal's own **documented, publicly-implemented LocRes**
format (not a proprietary one) — so `tools/ud_locres.py` is a straight port
of a public reference implementation, not a reverse-engineering exercise.

| Playbook gate | Status |
|---|---|
| Format mapped | ✅ Pak V11 (repak-compatible) → loose `.locres` (Unreal LocRes v3) + loose `.ufont` |
| Arabic slot exists | ❌ none (20 LTR cultures) → LTR-slot hijack (AC2/Anno/GTA/TLOU class) |
| bidi mode determined | ✅ **CONFIRMED IN-GAME 2026-07-08** — LOGICAL, zero custom bidi code (Unreal/Slate ICU, same as Hogwarts Legacy) |
| font has Hebrew? | ✅ was 0/27 → injected (Univers merge / Cotford replace) → **CONFIRMED rendering cleanly in-game**, no tofu |
| identity round-trip | ✅ `ud_locres.py roundtrip` — same (key,value) sequence, same file SIZE, semantic-PASS (string-table order differs, harmless — reader ignores refCount) |
| container round-trip | ✅ `repak pack` V11 rebuild verified: correct mount point, correct file list, `repak get` back out matches what we wrote |
| **menu proof in-game** | ✅ **PASSED 2026-07-08** — `BATES_MENU_QUIT` rendered "יציאה" with Text Language left at English (best case: `en` slot loads with zero user action) |
| count report | ✅ see below — 12,689 entries / 9,863 unique in one StringTable |
| deploy target | ✅ additive override pak in `Content/Paks/~mods/` (Hogwarts Legacy convention — never touches the 8.4 GB base pak) |
| anti-cheat / DRM | ✅ none — FitGirl repack, no Denuvo/EAC/BattlEye |

## ✅ RESOLVED — the `en` slot loads, no fallback needed

## (historical) The one open question — which locale slot actually loads

Every other UE game handled in this project (Hogwarts Legacy) hijacked an
**official Arabic locale** that's unambiguously loaded as a non-native
override. Until Dawn has no Arabic locale at all, so the natural fallback
(per the AC2/Anno/GTA/TLOU "LTR-slot hijack" class) is to just overwrite the
**English** locale's own locres — the simplest possible activation for an
end user (nothing to change in Settings at all). The only uncertainty: some
Unreal projects skip loading a NATIVE-culture locres at runtime (relying on
the string baked directly into the StringTable asset instead), which would
make an `en/Game.locres` edit silently do nothing.

**Resolved by testing both at once**, rather than guessing: the menu-proof
build (`work/build_menu_proof.py`) patches `BATES_MENU_PAUSED` with a
distinct Latin marker per locale (`ZZ-UD-EN-OK-ZZ` in `en/Game.locres`,
`ZZ-UD-TR-OK-ZZ` in `tr/Game.locres` — Turkish picked arbitrarily as "any
non-native LTR locale"), plus identical Hebrew test text in 8 other
menu/settings keys in both copies, plus Hebrew-injected Univers+Cotford
fonts. One deploy, one in-game check with Text Language = English (no
setting change) tells us if the native slot works; if not, switching Text
Language = Turkish tests the guaranteed-safe fallback path.

- **If `en` works**: simplest possible mod — zero in-game settings to change,
  install-and-play. This is the outcome to hope for.
- **If only `tr` (or another non-native slot) works**: same mechanism as
  every other LTR-hijack game in this project — user picks that language in
  Text/Subtitle Language settings, keeps Speech Language = English.

Either way the **mechanism is proven at once** and Phase 2 can start
immediately after this single deploy is checked.

## ✅ bidi — confirmed LOGICAL in-game

Until Dawn is Unreal Engine 5 — same Slate-based text rendering family as
Hogwarts Legacy (Unreal Engine 4), where native ICU bidi reordering was
**confirmed in-game** to work with zero custom bidi code, storing Hebrew
**LOGICAL**. There is a reasonable expectation this carries over (Slate's
bidi/shaping operates on the actual Unicode content of a text run, not on
the active culture), but per the playbook's golden rule this is **never
assumed** — the menu-proof's Hebrew test strings (mixed with Latin markers,
settings labels with punctuation) will show definitively whether storage
should be LOGICAL (expected) or needs a VISUAL bake instead.

## Font

Both font families (Univers=TrueType/glyf, Cotford=CFF) had Hebrew injected
successfully and verified offline (27/27 Hebrew codepoints present, 26/26
Latin preserved, `fontTools` loads both outputs cleanly). This is the
**easiest font case in the project** — no atlas, no uasset wrapper, no
byte-length constraint; `.ufont` cooks as a bare font file. Aesthetic choice
(currently defaulting to Heebo, reused from `games/spiderman2/extracted/
_heebo/`) is a placeholder for the menu-proof; per playbook §4.5 a final
choice should be shown to the user once the mechanism is confirmed working
(a moodier serif might suit the horror-teen-drama tone better than a clean
grotesque — worth revisiting once Phase 2 starts).

## Count report

```
--- דוח קרקע: Until Dawn (2024) ---
מנוע / פורמט: Unreal Engine 5 · Pak V11 (repak) · טקסט ב-Content/Localization/Game/<culture>/Game.locres (LocRes v3)
סלוט ערבית: לא קיים (20 לוקאלים LTR)  → RTL בחינם: לא — חוטפים סלוט LTR (en, עם fallback ל-tr)
מצב bidi: ממשק=? · כתוביות=? (ממתין לתוצאת ה-menu-proof; צפוי LOGICAL כמו Hogwarts Legacy/UE5)
פונט: צריך הזרקה (0/27 עברית) — בוצעה ל-Univers (glyf merge) + Cotford (CFF replace), 27/27 מאומת אופליין
repack round-trip: עבר (semantic-identical, אותו גודל, key/value זהים; מבנה ה-pak אומת עם repak)
הוכחת תפריט in-game: פרוס, ממתין לבדיקת המשתמש

ספירה לתרגום (מתוך en/Game.locres, namespace יחיד ST_Localized):
  • ממשק/הגדרות (BATES_*, PSPC_*, BM_TTS*, PC_LOADING):  ~795 מחרוזות
  • כתוביות עלילה (SMG###_* + epilogue_subtitle_*):      11,636 מחרוזות
  • כתוביות making-of/בונוס (Bonus_Material_*/bts_video_*): ~266 מחרוזות (עדיפות נמוכה, אופציונלי)
  • סה"כ (רשומות):    12,689   |   ייחודי (אחרי dedup): 9,863
  • skip צפוי: 1 (הערת מפתחים ".HOWTO" — לא טקסט משחק)

מגבלות ידועות: אין עדיין אישור in-game לאיזה סלוט (en/tr) באמת נטען; פונט זמני (Heebo) לבחירה סופית
מוכן לשלב 2 (מסירה לסוכן תרגום)? כן, מיד אחרי אישור ה-menu-proof
--- END ---
```

## מסמכים קשורים
- באותה תיקייה: [[games/until_dawn/PIPELINE|PIPELINE]], [[games/until_dawn/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#until_dawn|CLAUDE_INDEX_games]]
