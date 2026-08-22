# GoWR — תיקון מגדר מהערבית של המשחק (מחרוזת בודדת)

**רקע:** האנגלית לא מבחינה מגדר, אז חלק מהשורות העבריות קיבלו צורת מגדר שגויה של הנמען
("אתה" במקום "את" ולהפך). הערבית המקצועית של המשחק כבר קבעה נכון. **בניגוד ל-CP2077,
GoWR הוא spine של מחרוזת אחת לכל id** (אין femaleVariant/maleVariant) — יש טקסט עברי
יחיד, אז פשוט מתקנים את מורפמת-המגדר של אותה מחרוזת. השיטה: `universal/GENDER_ORACLE_ROLLOUT.md`
+ `orchestration/RULES.md` #12.

> **היקף:** ציר ה**פנייה** (אתה↔את, שואל↔שואלת) — סימנים חד-משמעיים בערבית בלבד. **לא**
> לגעת במשמעות, בשמות (Kratos/Atreus/Odin נשארים), ב-tokens (`[[S:...]]`, `\n`, `[style=...]`,
> `[i]`, `%d`, `[Icons:...]`), ולא בפעלים דו-משמעיים. אל תמציא תיקונים מעבר ל-suspects.

## הקלט (כבר קיים — לא צריך לחלץ מהמשחק)
- `work/hebrew.json` — `{id: he_logical}` (הטקסט העברי הלוגי; VISUAL מוחל רק ב-build).
- `work/arabic.json` — `{id: ar}` (הערבי הפריסטין = אמת-הקרקע למגדר). join לפי **id מספרי**.
- `work/english.json` — `{id: en}` (מקור המשמעות בלבד).

## מה לעשות (Claude בונה כלים + מאמת; הסוכן מתקן — [[delegate-all-translation]])

1. **סרוק** (Claude, single-string mode): לכל id שקיים גם ב-hebrew.json וגם ב-arabic.json,
   השווה `gender_oracle.he_addressee(he)` מול `gender_oracle.ar_addressee(ar)`. פלט
   `gender_oracle_suspects.jsonl` = השורות שבהן שתיהן חד-משמעיות ו**סותרות** (למשל
   ar='f'/he='m'). כל שורה: `{"id":..., "en":..., "he":..., "ar":..., "ar_gender":..., "he_gender":...}`.
   ```python
   import json, sys; sys.path.insert(0, "../../universal"); import gender_oracle as go
   he = json.load(open("work/hebrew.json", encoding="utf-8"))
   ar = json.load(open("work/arabic.json", encoding="utf-8"))
   out = []
   for k, h in he.items():
       a = ar.get(k)
       if not a: continue
       ag, hg = go.ar_addressee(a), go.he_addressee(h)
       if ag in ("m","f") and hg in ("m","f") and ag != hg:
           out.append({"id":k,"he":h,"ar":a,"ar_gender":ag,"he_gender":hg})
   json.dump(out, open("gender_oracle_suspects.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
   ```
2. **האצל לסוכן Google** את התיקון: לכל שורה, הפוך את **פניית הנמען** ב-`he` כך שתתאים
   ל-`ar_gender` (אתה→את או את→אתה, שואל↔שואלת, צריך↔צריכה). **רק מורפמת-המגדר** — משמעות
   לא נגעת, tokens נשמרים מילה-במילה, שמות באנגלית. handoff סטנדרטי (folders + get_batch/
   merge_batch + INSTRUCTIONS עם דוגמאות מהערבי), md5-partition ל-N סוכנים, anti-cheat:
   דחה שורה שבה ה-scaffold השתנה או שהמגדר לא התהפך לכיוון של `ar_gender`.
3. **אמת עצמאית (אל תסמוך על הסוכן):** לכל תיקון —
   - `universal/dualgender_verify_agents.classify_fill(fixed, he)` → scaffold זהה + שינוי-מגדר
     אמיתי + בלי niqqud/internal-edit.
   - `gender_oracle.he_addressee(fixed) == ar_gender` (הפנייה אכן התהפכה לכיוון הערבי).
   דחה כל שורה שנכשלת → החזר לסוכן.
4. **החל ל-`work/hebrew.json`** עם בטיחות: גיבוי `work/hebrew.json.bak.goracle.<ts>` +
   כתיבה אטומית + **guard פר-שורה** (כתוב רק אם `he[id]` עדיין שווה לערך שנסרק). זה spine
   של מחרוזת בודדת → פשוט `he[id] = fixed` (אין פיצול variant).
5. **בנה + פרוס** (המשחק סגור; VISUAL + font מוחלים ב-build): `python work/build_wad.py`
   (ברירת מחדל פורסת ל-Game Lab בלבד; `--deploy` ל-C:\Games אם צריך). ה-build קורא את
   `hebrew.json` המעודכן ומחיל את כל הטרנספורמציות (unwrap parens, decimal, italic-strip,
   visual, font).
6. **סרוק שוב** (חזרה על שלב 1) — מספר ה-suspects צריך לצנוח כמעט לאפס.

## פרסום (רק אחרי "פרסם")
GoWR כבר פורסם `v1.0.0-beta.1` (חינם, GitHub `hebrew-translation-hub/godofwar-ragnarok-hebrew-mods`).
לריליז חוזר: re-pack + `gh release upload v1.0.0-beta.1 --clobber` + PATCH Supabase sha/size
(`publish_version.py gowragnarok ...`). **אל תפרסם בלי שהמשתמש אומר "פרסם".**

## ⚠️ אל תעשה
- אל תריץ אינפלקטור דטרמיניסטי על הטקסט הנראה (over-flip מוכח: "מנסה"→"מנסי" וכו') — התיקון = **סוכן**.
- אל תתרגם מחדש משמעות. אל תיגע ב-`work/english.json`/`work/arabic.json` (מקור בלבד).
- שמור את ה-tokens של GoWR מילה-במילה: `[[S:CHAR:...]]`, `\n`, `[style=Highlight]`/`[/style]`,
  `[i]`/`[/i]`, `%d`, `[Icons:...]`.

## מסמכים קשורים
- באותה תיקייה: [[games/godofwar_ragnarok/FEASIBILITY|FEASIBILITY]], [[games/godofwar_ragnarok/FONT|FONT]], [[games/godofwar_ragnarok/PIPELINE|PIPELINE]], [[games/godofwar_ragnarok/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#godofwar_ragnarok|CLAUDE_INDEX_games]]
