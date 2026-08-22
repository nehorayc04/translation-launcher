# 🤝 תבנית מסירת תרגום לסוכן שני — שלב 2

> **מתי משתמשים:** אחרי ש[`NEW_GAME_GROUNDWORK_PLAYBOOK.md`](NEW_GAME_GROUNDWORK_PLAYBOOK.md) הושלם
> (הקרקע מוכנה, התפריט אושר in-game, הספירה ידועה). עכשיו מתרגמים את **כל** המחרוזות —
> ואת זה עושה **סוכן שני נפרד בלי ההיסטוריה שלנו**, לכן Claude כותב לו הנחיה עצמאית ומלאה.
>
> **חלוקת התפקידים (כלל-ברזל — [[delegate-all-translation]]):**
> * **Claude** בונה את הכלים, חוקי הוולידציה, ה-glossary, וההנחיה — **ולעולם לא מתרגם בעצמו.**
> * **התרגום עצמו** נעשה ע"י: (א) **סוכן Google/Gemini ב-IDE** שמתרגם בעצמו (מסלול "self-translate"),
>   או (ב) **LM מקומי** (gemma/qwen ב-LM Studio) דרך שלישיית `<game>_translate.py` (מסלול "local-LM").
>
> המסמך הזה הוא **שלד למילוי** — Claude מעתיק את חלק B, ממלא את כל ה-`<PLACEHOLDERS>` לפי המשחק,
> ומוסר לסוכן. התקן המוכח (Watch Dogs 2) נמצא ב-`games/watchdogs2/agent_handoff/` — זה ה-reference החי.

---

## חלק A — מה Claude מכין לפני המסירה (checklist)

1. **תיקיית עבודה עצמאית** `games/<game>/agent_handoff/` (כל מה שהסוכן צריך, נתיב מלא).
2. **`to_translate.json`** = `{id: "English text"}` — **קובץ אחד שטוח** (לא 3 קבצים נפרדים — זה מציף permission prompts).
   רק מחרוזות בסקופ (`EN ∩ AR`, שלב 2 בקרקע), בלי dev-meta. **המקור האנגלי הוא הייחוס המבני** (התגים בו).
3. **`hebrew.json`** = `{id: "Hebrew"}` — הפלט המצטבר (מתחיל ריק או עם מה שכבר תורגם). "תורגם" = id קיים כאן.
4. **`skip.json`** = מערך ids שלא ניתנים לתרגום (יוזרע ע"י הסוכן תוך כדי).
5. **4 סקריפטי העזר** (חלק C): `qa_scan.py` · `get_batch.py` · `loop_split.py` · `loop_merge.py` — **כלי I/O בלבד, לא מתרגמים.**
   לכוונן בהם פר-משחק: ה-`TOKEN` regex (לפי התגים האמיתיים), גודל באטץ', ונתיבים.
6. **להחליט LOGICAL מול VISUAL** (שלב 3 בקרקע) ולכתוב את זה מפורש בהנחיה. הסוכן **תמיד** כותב עברית **לוגית** (קריאה);
   ההיפוך ל-VISUAL נעשה ע"י Claude בזמן build — לא ע"י הסוכן.
7. **לכתוב את ה-brief האווירתי + ה-glossary של המשחק** (חלק B §"אווירה") — זה מה שהופך תרגום סביר לתרגום מעולה.
8. **מסלול placeholder לתגים מסוכנים:** אם יש timing-tags/JSON-שביר (`<ts="...">`), להמיר ל-markers נקיים (`@@TS1@@`)
   לפני המסירה — הסוכן עורך טקסט פשוט, וסקריפט merge מחזיר את התגים האמיתיים ומאמת. (סוכנים שוגים ב-escaping של מרכאות בתגים.)

> **מתי מסלול self-translate ומתי local-LM:**
> * **self-translate (Google/Gemini ב-IDE)** — איכות שפה גבוהה, אפס API key, טוב ל-tail/QA ולכמויות בינוניות. **caveat:**
>   סוכן לא שורד "תרגם בעצמך, בלי מודל" תחת עומס של 14k+ מחרוזות (~3 באטצ'ים והוא עובר חרש ל-gemma). לכמות גדולה — לחתוך לבאטצ'ים של ~500.
> * **local-LM (gemma/qwen)** — ל-haul ארוך (עשרות אלפי שורות, ימים-שבועות), אוטונומי, דרך השלישייה + watchdog.

---

## חלק B — ההנחיה לסוכן (להעתיק, למלא `<...>`, ולמסור)

> *(זה הטקסט שמוסרים לסוכן. נכתב בעברית כי הסוכן מתרגם **לעברית** וצריך חוש לשפה. כל `<...>` ממלאים פר-משחק.)*

---

### הנחיה לסוכן — תרגום `<שם המשחק>` לעברית (`<ממשק / כתוביות / הכול>`)

**משימה:** תרגם אנגלית→עברית את כל מה שנשאר (`~<N>` מחרוזות) **ותקן את כל הבאגים** בשורות שכבר תורגמו,
עד כיסוי מלא ונקי. עבוד **ברצף ואוטונומית** — אל תעצור בין באצ'ים, אל תחזור לדווח עד שהכול הושלם או עד תקלה חוסמת אמיתית.

ספריית העבודה (כל הקבצים כאן, השתמש בנתיב המלא): `<C:\...\games\<game>\agent_handoff\>`

#### ⚠️ הכי חשוב — אתה המתרגם, לא מודל חיצוני
* **אתה (הסוכן) מתרגם אנגלית→עברית בעצמך**, מחרוזת אחר מחרוזת, ביכולת השפה שלך.
* **אסור להתחבר למודל מקומי/חיצוני כלשהו** — לא LM Studio / `localhost:1234` / `127.0.0.1` / gemma / שום AI endpoint. כל מילה עברית מגיעה ממך.
* **אל תריץ** סקריפטי תרגום של פייפליינים אחרים (`*_translate.py`, `*_watchdog.py`, `*_merge.py`). הסקריפטים שאתה כן מריץ
  (`qa_scan.py`, `get_batch.py`, `loop_split.py`, `loop_merge.py`) הם **רק** כלי I/O שמזיזים JSON — הם **לא מתרגמים**.

#### מבנה הנתונים
* `to_translate.json` — `{id: "טקסט אנגלי"}` — המקור (`<N_total>` מחרוזות). **לקריאה בלבד.**
* `hebrew.json` — `{id: "טקסט עברי"}` — הפלט המצטבר. "תורגם" = id קיים כאן. **רק מוסיף/מתקן (דרך loop_merge), לעולם לא מוחק.**
* `skip.json` — מערך ids שלא ניתנים לתרגום (ראה למטה).
* `<אין קובץ ערבית — המקור האנגלי הוא הייחוס המבני (התגים בו).>` *(או, אם רלוונטי: `arabic.json` כייחוס מבני.)*

#### ⚠️ סדר כתיבה — `<LOGICAL: עברית רגילה, אל תהפוך כלום>` / `<VISUAL: ראה הערה>`
> **למלא לפי שלב 3 בקרקע.** ברירת המחדל היא **LOGICAL**:
כתוב עברית **בסדר קריאה רגיל (לוגי)**, בדיוק כמו עברית תקנית. **אל תהפוך אותיות, אל תהפוך מילים, אל תעשה "סדר ויזואלי".**
סקריפט בנייה נפרד (לא שלך) מטפל בהיפוך RTL בזמן הבנייה. דוגמה: "New Game" → `משחק חדש` (ולא `שדח קחשמ`).

#### הלולאה האוטונומית — חזור עד "All done!"
**שלב 0 (פעם אחת):** `python qa_scan.py` — סורק את כל המתורגמים, **מסיר אוטומטית** שורות עם באגים מבניים
(סקריפט זר / ניקוד / תגים אבודים / דליפת סירוב / אורך חריג / אנגלית שלא תורגמה). השורות שהוסרו הופכות ל"לא מתורגם"
ותעשה אותן מחדש בלולאה — זה **תיקון הבאגים**, מקופל לתוך התרגום.

> ⚠️ **זו לולאה — אסור לעצור אחרי באטץ' אחד!** כל סבב מתרגם עד `<500>`. יש מאות/אלפים. חזור **שוב ושוב** עד
> ש-`get_batch.py` מדפיס בדיוק `All done!`. תרגמת באטץ' אחד ועצרת = **לא סיימת.**

**חזור על המחזור עד "All done!":**
1. `python get_batch.py` → אם `All done!` → **סיים** (עבור לסיום). אחרת נוצר `current_batch.json` עם עד `<500>` מחרוזות הבאות.
2. `python loop_split.py` → מפצל ל-`batch_part1.json`..`batch_part4.json` (`{id: english}`).
3. **תרגם בעצמך** כל חלק → כתוב `trans_part_1.json`..`trans_part_4.json` (`{id: "תרגום עברי"}`, **אותם ids בדיוק**).
   מחרוזת **שלא ניתנת לתרגום** (ראה skip.json) — אל תשים ב-trans_part; הוסף את ה-id ל-`skip.json`.
4. `python loop_merge.py` → מאמת תגים+סקריפט+ניקוד וממזג **רק את הנקיים** ל-`hebrew.json` (כתיבה אטומית).
   אם מודפס `TAG MISMATCH`/`FOREIGN SCRIPT`/`NIQQUD`/`EMPTY` על id — **תקן רק את אותו id** בקובץ ה-trans_part שלו והרץ `loop_merge.py` שוב, עד שהכול נקי.
5. **מיד** חזור לשלב 1. בלי להמתין, בלי לשאול, בלי לדווח באמצע.

#### skip.json — מחרוזות שלא ניתנות לתרגום (כדי שהלולאה תסתיים)
חלק מהמחרוזות הן **שמות משתמש / כינויי hacker / גרפיטי / leetspeak / קוד / קודי שגיאה / שמות בשפה זרה** —
אין להן תרגום עברי, נשארות בלטינית במשחק. דוגמאות: `rekt`, `doneGOOFED`, `http 404`, `dedsec sux`, `params.bellw = true;`,
`eKart07`, `[EMOTION1]`, `purplepowah`, `F.E.A.S.T.`, `5x[CURRENCY]`. **עבור כל מחרוזת כזו:** אל תתרגם, הוסף את ה-id
ל-`skip.json` (מערך JSON של מחרוזות id). `get_batch.py` מתעלם מ-skip (סופר כ"בוצע") → הלולאה מגיעה ל-"All done!".
**הכלל:** אם לא הצלחת להפיק עברית אמיתית אחרי ניסיון כן — שים ב-skip ותמשיך. **אל תיתקע על מחרוזת אחת, ואל תכניס
"תרגום" שהוא העתקת האנגלית.**

#### אימות תגים (החוק ש-loop_merge/qa_scan מחייבים)
לכל id, ה-tokens חייבים להופיע **באותה כמות** במקור ובתרגום (**multiset זהה**). העתק verbatim ובמיקום היחסי:
```
<[TOKEN] [UPPER] [CSS_BLUE] [RELOAD] ...   ← כל [TOKEN] באותיות גדולות — as-is>
<{VALUE} {ANY}                              ← as-is>
<%d %s %ls %0.2f %% (לעולם אל תכווץ %% ל-%) ← אותו מספר מופעים>
<&#xA; &amp; &gt; &lt; &nbsp;               ← ישויות HTML as-is>
<<ts> <br> [LF] [CR] [style=..] [[S:CHAR:vo_..]] ← לפי המשחק>
```
אם המספר/הסוג לא תואם → loop_merge יסרב למזג. **תרגם רק את הטקסט שמחוץ/בין התגים.**
דוגמה: `Press [RELOAD] to reload` → `לחץ [RELOAD] לטעינה מחדש`. `2600[LF]T-Shirt` → `2600[LF]חולצת טי`.
> **שים לב לקונבנציית ירידת-שורה של המשחק:** חלקם שומרים `\n` ליטרלי (backslash-n), חלקם newline אמיתי — שמר את **קונבנציית המקור.**

#### כללי תרגום נוקשים (לכל מחרוזת)
1. **עברית תקנית וקצרה** בטון ממשק-משחק אמיתי. **אסור ניקוד** (נקודות/קווים מתחת/מעל אותיות) — אף פעם.
2. **רק עברית + לטינית.** אסור סקריפט אחר (ערבית/קירילית/יוונית/תאית/סינית/קוריאנית/יפנית/דוונגארי).
3. **שמור כל tag/placeholder verbatim ובמיקום היחסי** (ראה "אימות תגים").
4. **ירידות שורה:** העתק `<\n / [LF] / [CR]>` בדיוק (אותו מספר, אותו מיקום יחסי).
5. **שמות פרטיים נשארים אנגלית** (תווים/מקומות/חברות/מותגים/רכבים/נשקים) — אל תתעתק:
   `<מלא רשימה: Marcus · Wrench · DedSec · ctOS · San Francisco · ... — שמות המשחק הספציפי>`.
6. **ראשי תיבות נשארים אנגלית:** XP · GPS · HUD · FPS · AI · ID · ATM · `<...>`.
7. **קוד/מספר/סמל בלי מילה אמיתית** ("TBT-7000", "%ls", "eKart07") — החזר ללא שינוי.
8. **מתגים:** ON→`פעיל` · OFF→`כבוי` · YES→`כן` · NO→`לא` · OK→`אישור` · BACK→`חזרה`.
9. **עקביות מונחים** (אותו תרגום לאורך כל הריצה) — ה-glossary של המשחק:
   `<Hacking→פריצה · Reload→טען מחדש · Ammo→תחמושת · Health→בריאות · ... — המונחים של המשחק>`.
10. אם המחרוזת היא **כולה תגים/קוד בלי מילה אמיתית** — החזר ללא שינוי.

#### ⚠️ כלל ה-passthrough של שמות/קודים (load-bearing — מונע churn אינסופי)
**קבל אפס-עברית** כשהמקור הוא שם-פרטי / ראשי-תיבות / קוד / כותרת-מדיה / שם נשק-מוצר / ערך-FPS / serial — **זה לא באג.**
היוריסטיקה ל"אין מילה לטינית אמיתית": הפשט רווחים/ספרות/פיסוק, ואז בדוק אם יש token `[a-z]` ≥2 תווים. קבל גם: שם-פרטי
עד 4 מילים בלי מילית/case-marker; תו בודד; token בודד שהוא **handle** (camelCase / יש ספרה / ≥11 תווים: `purplepowah`).
מחרוזות **markup-בלבד** (`&lt; %s`, `&nbsp;<br>`): הפשט entities/tags לפני בדיקת המילה. **בלי החוק הזה הלולאה ננעלת
על כל שם-פרטי לנצח.**

#### ⚠️ שם-דובר / colon RTL (אם המשחק מציג `שם: שורה`)
שם פרוטגוניסט (כמו `V`) נשאר **Latin בתוך פרוזה/דיאלוג**, לעולם לא `וי` שם. **חריג:** רשומת **שם-דובר בודדת**
(הערך כולו = השם) חייבת להיות **עברית** (`וי`) כדי שה-colon RTL ירונדר בצד הנכון. גם שמות-תווים בהקשר דיאלוג מתועתקים
(Levi→ליווַאי). קודים עם V (`V8`, `VIP`) נשארים Latin.

#### ⚠️ cue-קולות/אינטרים' — לתרגם; קוד — לא
sound cues בסוגריים **כן** מתורגמים: `[laughs]`→`[צוחק]`, `[gasping]`→`[נאנח]`, `[grunting]`→`[נחירה]`.
אינטרים' חוזרות: `Hmm…`→`המממ…`, `Haha.`→`חה חה.`, `Heh…`→`חה…`. **שמות tokens/קוד — לא מתרגמים.**

#### האווירה הספציפית של המשחק (זה מה שהופך סביר למעולה)
> **Claude ממלא את הסעיף הזה פר-משחק — זה החלק הכי חשוב לאיכות:**
* **רגיסטר/טון:** `<למשל CP2077 = "טון Night City", סלנג סייברפאנק; GoW = אפי/מיתולוגי; WD2 = hacker צעיר/אירוני; SM2 = קליל/הרואי>`.
* **glossary נעול** (תעתיק קבוע, לעולם לא חלופה): `<GoW: קרייטוס/אטראוס/מימיר/ראגנארוק... · SM2: רחפן/ונום/קרב מגע · CP2077: שארד/אדג'ראנר/סייברוור>`.
* **דיאלקטים/שפה זרה מכוונת לשמר:** `<CP2077: ספרדית Valentinos / קריאולית Voodoo-Boys נשארות זרות — המקור עצמו זר, זה לא leak>`.
* **לא תרגום מילולי:** מתרגם-מקומֵן, לא MT. דוגמה: `BREAKING NEWS`→`מבזק!` (לא "חדשות חמות"), `rampage`→`משתולל!` (התאמת-פועל).

#### בטיחות וקבצים — מותר/אסור
**מותר לכתוב רק ל:** `trans_part_1..4.json` · `hebrew.json` (רק דרך `loop_merge.py`) · `current_batch.json`/`batch_part*.json`
(נוצרים ע"י הסקריפטים) · `skip.json` · `progress.md` (עדכן כל ~10 באצ'ים).
**אסור בהחלט:** ❌ למחוק מפתחות מ-`hebrew.json` · ❌ לגעת ב-`to_translate.json` · ❌ לגעת בקובץ מחוץ לספרייה (קבצי משחק,
WAD/loc/פונט, סקריפטי `*_translate`) · ❌ לפרוס למשחק / להריץ build/encode/deploy (לא תפקידך — מישהו אחר יבנה) · ❌ לגעת במודל AI.

#### היקף וסיום
* **היקף:** כל הנותרים (`~<N>`) עד `get_batch.py` = `All done!` **וגם** `qa_scan.py` = 0 הוסרו (אין באגים מבניים).
  אם qa_scan עדיין מסיר — חזור ללולאה.
* **דווח רק בסיום** (או בתקלה חוסמת), בפורמט:
```
--- SUMMARY ---
תאריך: [תאריך ושעה]
משימה: תרגום <שם המשחק> <ממשק/כתוביות> + תיקון באגים
בוצע: [כמה באצ'ים, כמה תורגמו בריצה זו, כמה תוקנו]
מצב: [סה"כ ב-hebrew.json] / <N_total>
נתונים מספריים: מתורגם X/<N_total>, נותר Y
דילוגים: [ids ב-skip.json + סיבה]
--- END SUMMARY ---
```

---

## חלק C — סקריפטי העזר המוכנים (תקן WD2, להעתיק ולכוונן)

> ה-`TOKEN` regex, `SIZE`, ונתיבים — מכווננים פר-משחק. שאר הלוגיקה זהה בכל המשחקים.

### `get_batch.py` — פולט את ה-`<500>` הבאים שלא תורגמו
```python
"""I/O helper — emit the next N UNtranslated strings. Does NOT translate."""
import json, os
SIZE = 500
to  = json.load(open("to_translate.json", encoding="utf-8"))
heb = json.load(open("hebrew.json", encoding="utf-8"))
skip = set(json.load(open("skip.json", encoding="utf-8"))) if os.path.exists("skip.json") else set()
rem = sorted([k for k in to if k not in heb and k not in skip], key=lambda x: int(x))
if not rem:
    print("All done!")
else:
    batch = {k: to[k] for k in rem[:SIZE]}
    json.dump(batch, open("current_batch.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"batch: {len(batch)} written  (remaining {len(rem)})")
```

### `loop_split.py` — מפצל ל-4 חלקים
```python
"""I/O helper — split current_batch.json into 4 parts. Does NOT translate."""
import json
b = json.load(open("current_batch.json", encoding="utf-8"))
items = list(b.items()); n = (len(items) + 3) // 4
for i in range(4):
    part = dict(items[i*n:(i+1)*n])
    json.dump(part, open(f"batch_part{i+1}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(f"split {len(items)} into 4 parts")
```

### `loop_merge.py` — מאמת + ממזג רק את הנקיים (אטומי)
```python
"""I/O helper — validate + merge trans_part_*.json into hebrew.json. Does NOT translate."""
import json, re, os
from collections import Counter
# כל token/placeholder שחייב להישמר (multiset זהה) — כוונן ל-tokens של המשחק:
TOKEN = re.compile(r'\[CSS_[A-Z]+\]|\[[A-Z][A-Za-z0-9_]*\]|\{[^}]*\}'
                   r'|%[0-9.]*[diufslxX]+|%%|&#?[A-Za-z0-9]+;')
NIQQUD = re.compile(r'[֑-ׇ]')
BAD    = re.compile(r'[؀-ۿЀ-ӿͰ-Ͽ฀-๿ऀ-ॿ一-鿿가-힯]')   # ערבית/קירילית/יוונית/תאית/דוונגארי/CJK/הנגול
src = json.load(open("to_translate.json", encoding="utf-8"))
merged = {}; problems = []
for i in range(1, 5):
    p = f"trans_part_{i}.json"
    if not os.path.exists(p): continue
    for k, he in json.load(open(p, encoding="utf-8")).items():
        en = src.get(k, "")
        if not he or not he.strip():                              problems.append((k, "EMPTY")); continue
        if Counter(TOKEN.findall(en)) != Counter(TOKEN.findall(he)): problems.append((k, "TAG MISMATCH")); continue
        if BAD.search(he):                                        problems.append((k, "FOREIGN SCRIPT")); continue
        if NIQQUD.search(he):                                     problems.append((k, "NIQQUD")); continue
        merged[k] = he
if problems:
    for k, r in problems[:60]: print(f"{r} {k}: en={src.get(k,'')[:50]!r}")
    print(f"--- {len(problems)} problem ids — fix ONLY those, re-run ---")
if merged:
    heb = json.load(open("hebrew.json", encoding="utf-8"))
    heb.update(merged)
    json.dump(heb, open("hebrew.json.tmp", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    os.replace("hebrew.json.tmp", "hebrew.json")          # אטומי — kill באמצע לא משחית
    print(f"merged {len(merged)} clean -> hebrew.json (total {len(heb)})")
else:
    print("nothing merged")
```

### `qa_scan.py` — מעבר תיקון-באגים (מסיר פגומים → יתורגמו מחדש בלולאה)
```python
"""BUG-FIX pass — scan translated lines for STRUCTURAL defects, REMOVE the bad
from hebrew.json so get_batch re-serves them. Does NOT translate."""
import json, re, os
from collections import Counter
TOKEN = re.compile(r'\[CSS_[A-Z]+\]|\[[A-Z][A-Za-z0-9_]*\]|\{[^}]*\}|%[0-9.]*[diufslxX]+|%%|&#?[A-Za-z0-9]+;')
NIQQUD = re.compile(r'[֑-ׇ]'); BAD = re.compile(r'[؀-ۿЀ-ӿͰ-Ͽ฀-๿ऀ-ॿ一-鿿가-힯]'); HEB = re.compile(r'[א-ת]')
REFUSAL = re.compile(r"(as an ai|i\s+(cannot|can'?t|am unable|am sorry)|here('?s| is) the translation"
                     r"|אינני יכול לתרגם|לא ניתן לתרגם)", re.I)
src  = json.load(open("to_translate.json", encoding="utf-8"))
heb  = json.load(open("hebrew.json", encoding="utf-8"))
skip = set(json.load(open("skip.json", encoding="utf-8"))) if os.path.exists("skip.json") else set()
bad = {}
for k, he in heb.items():
    if k in skip: continue
    en = src.get(k, ""); r = None
    if not he or not he.strip():                                  r = "empty"
    elif BAD.search(he):                                          r = "foreign_script"
    elif NIQQUD.search(he):                                       r = "niqqud"
    elif Counter(TOKEN.findall(en)) != Counter(TOKEN.findall(he)): r = "placeholder_mismatch"
    elif REFUSAL.search(he):                                      r = "refusal_leak"
    elif len(en) >= 8 and len(he) > 2.4 * len(en) + 40:           r = "length_anomaly"
    elif he.strip() == en.strip() and not HEB.search(he):
        core = TOKEN.sub("", en).strip()
        words = re.findall(r"[A-Za-z][A-Za-z'.\-]*", core)
        is_namey = bool(words) and len(words) <= 4 and all(w[0].isupper() for w in words)
        no_real_word = not re.search(r'[a-z]{2,}', core)
        is_handle = (" " not in core and bool(re.search(r'[a-z][A-Z]', core) or re.search(r'\d', core) or len(core) >= 11))
        if core and not (is_namey or no_real_word or is_handle):  r = "untranslated"   # name/code passthrough
    if r: bad[k] = r
if bad:
    for k in bad: heb.pop(k, None)
    json.dump(heb, open("hebrew.json.tmp", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    os.replace("hebrew.json.tmp", "hebrew.json")
    json.dump(bad, open("qa_removed.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(f"removed {len(bad)} defective (now {len(heb)} good) -> re-do in the loop. see qa_removed.json")
```

> **שים לב:** ה-`name/code passthrough` ב-`qa_scan.py` **חייב להיות זהה** לחוק שב-`validate()` של המתרגם.
> אם הם מתפצלים — ה-QA יסמן כל שם-פרטי לנצח (churn × אינסוף). שתף פונקציה אחת.

---

## חלק D — לולאת QA שנייה (מעבר ביקורת EN-מול-HE) — אופציונלי, לאיכות גבוהה

הסורקים הדטרמיניסטיים (חלק C) תופסים ~99% מהבאגים ה**מבניים** אבל **אפס** סמנטיים (תרגום שגוי, תעתיק-חצי שבור,
דליפת מילה זרה, עברית לא-טבעית, רגיסטר שגוי). לאיכות-שיא מוסרים מעבר שני לסוכן (תקן: `games/watchdogs2/agent_handoff_subs/`
+ `QA_INSTRUCTIONS.md`):

* **`qa_get_batch.py`** נותן לסוכן באטץ' של `{id, en, he}` (המקור + העברית החיה).
* הסוכן **משווה EN מול HE** ומחזיר תיקונים רק לשורות שגויות באמת (default = השאר; ברירת-מחדל היא לא לגעת — over-correction זה כשל #1).
* **`qa_merge.py`** מאמת מבנית את התיקון (multiset/foreign/niqqud) וממזג חזרה כ-pending.
* **שתי שכבות שמירה ("כלבי שמירה"):** (1) guard-dog דטרמיניסטי שמנקה (niqqud strip, foreign strip, seam-fix) **לפני** דחייה;
  (2) re-validation אחרי כל תיקון. **לעולם לא דוחים את הסוכן בהודעת שגיאה אדומה — מתקנים.**
* **לאיכות סמנטית אמיתית** (mistranslations שעוברים ולידציה מבנית): frontier-model (Opus/Sonnet) — qwen-32B מקומי נמדד
  ~32% precision / 23% recall (חלש מדי); Haiku/Gemini-Flash over-flag. שיטה: review → **independent adversarial verify**
  (סוכן שני שמאשר רק high-confidence, default REJECT), short-save רק chunks שהושלמו, שחזור `old` byte-exact מהדיסק (לא דרך ה-LLM).

---

## חלק E — מסלול local-LM (haul ארוך, אוטונומי) — שלישיית `<game>_translate.py`

ל-עשרות אלפי שורות (ימים-שבועות) משתמשים ב-LM מקומי דרך שלישייה (מעתיקים את שלישיית SM2 כתבנית). זה **לא** הסוכן —
זה Claude שמריץ pipeline אוטונומי. הכללים שעלו ביוקר:

### LM Studio — מציאות החומרה (RX 9070, 16GB, Vulkan)
* מודל 31B (~20GB) **גולש ל-RAM** (`lms ps` DEVICE=Local) → ~1–2 tok/s. **חובה `--parallel 1`** (בקשות מקבילות על מודל
  שגולש מפצלות throughput קבוע + timeout). **quant שנכנס ל-VRAM** (q2_k_xl ~14GB) = פי 5–15 מהיר.
* **context-per-slot:** LM Studio מחלק `--context-length` ב-`--parallel`. `ctx 2048 ÷ 4 = 512/slot` → batch של 1,200 tok
  קורס "Context size exceeded" → fallback ל-single → קריסת throughput. ודא `expected_tokens ≤ ctx/parallel × 0.8`.
* **reload recipe:** `attrib -R %USERPROFILE%\.lmstudio\.internal /S /D` → `lms load <model> -y --gpu max --context-length 8192 --parallel 1`.
* **חתימת hang:** `lms ps` STATUS=GENERATING דקות עם אפס פלט. **סדר recovery (אסור להפוך):** הרוג את ה-client **קודם**
  → `lms unload --all` (לא `unload MODEL` על מודל תקוע) → load → **probe בבקשה אמיתית זעירה**. (reload-while-busy עלה 10 שעות ב-SM2.)

### ⚠️ שתי המלכודות הקטלניות (10 שעות ב-SM2 — לעולם לא לחזור)
1. **cp1255 stdout crash:** child ב-Windows בלי `PYTHONIOENCODING` מקבל stdout cp1255; ה-`print` הראשון עם `→`/`…`/emoji
   זורק `UnicodeEncodeError` והורג את התהליך **בשקט**. תיקון: `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`
   בתחילת **כל** סקריפט **וגם** הרצת children עם `env PYTHONIOENCODING=utf-8`.
2. **reload-while-busy** (ראה למעלה).

### המתרגם (`<game>_translate.py`)
* **system prompt קצר (~400 tok, לא ~1000)** — מתבצע re-prefill בכל batch; prefill שולט על מודל איטי. כל החוקים הקשיחים, בלי פרוזה/דוגמאות.
* **batching לפי תקציב-tokens** (לא ספירה) — מחרוזת כתובית אחת יכולה להיות סצנה של 1000+ tokens; batch קבוע **חותך**. סצנה ענקית → solo.
* **`validate()`** = niqqud/foreign/empty/multiset + **name/code passthrough** (זהה ל-`qa_scan`); **כתיבה אטומית** (temp+`os.replace`).
* **3-strike park** ל-`<game>_skip.json` — כל reject **חייב** park, אחרת entry בלתי-פתיר לופ את התור לנצח (SM2 קפא ב-12603).

### ה-watchdog (`<game>_watchdog.py`) — מריצים אותו, הוא בעל-הבית
* **משיק תחת BASE python** (לא venv stub — הוא double-spawn ושובר singleton). liveness דרך `Popen.poll()`; children detached.
* **heartbeat per-ROW** (`os.utime(checkpoint)` אחרי כל שורה — לא per-batch, אחרת batch איטי-אך-בריא נראה תקוע ונהרג).
* **QA כל שעה:** re-check שורות מאז הtick, הסר פגומים (אטומי) → יתורגמו מחדש, park אחרי 3. ה-QA חולק את ה-passthrough של המתרגם.

### progress לאתר (`<game>_progress.py`)
לולאת 60ש' → `POST /api/admin/progress` (`MONITOR_TOKEN` מ-`.env`) עם `{gameId, phase, processed, total, meta.alive:true}`.
`gameId` = `games.id` ב-Supabase בדיוק.

---

## אחרי שהתרגום הושלם — בנייה + פרסום

1. **build** מה-spine המאוחד (כל ה-sections מ-`hebrew.json`) → encode → deploy ל-staging **וגם** ל-play copy.
   (אם המשחק = VISUAL — להחיל `visual()` בזמן build בלבד.) לאמת in-game (דובר עברית) לפני שילוח.
2. **publish** (אם רלוונטי): GitHub **FULL release** (תג stable יחיד, **clobber assets** — לא למַטבע תגי `v…-beta.N`),
   slug ב-Worker, שורת `games` + `mod_version_history` ב-Supabase, `manifest.json` עם `version`+`sha256`. **4 משטחים חייבים להסכים.**
3. **חדשות:** `universal/claude_suggest.py` (`source='claude'`) → 2–4 הצעות עברית לאישור admin.

---

*נכתב 2026-06-21. התקן החי: `games/watchdogs2/agent_handoff/` (+ `agent_handoff_subs/` ללולאת ה-QA).
כשמוסרים משחק חדש — מעתיקים חלק B, ממלאים את כל ה-`<...>`, ומכוונים את 4 הסקריפטים ל-tokens של המשחק.*

## מסמכים קשורים
- באותה תיקייה: [[universal/GENDER_ORACLE_ROLLOUT|GENDER_ORACLE_ROLLOUT]], [[universal/NEW_ERA_LANGUAGE_ROLES|NEW_ERA_LANGUAGE_ROLES]], [[universal/NEW_GAME_GROUNDWORK_PLAYBOOK|NEW_GAME_GROUNDWORK_PLAYBOOK]], [[universal/QA_REVIEW_HANDOFF|QA_REVIEW_HANDOFF]], [[universal/cross_audit_dashboard|cross_audit_dashboard]]
- פלייבוקים כלל-פרויקטיים: [[CLAUDE_INDEX#⚙️ סביבה / כלים / אורchestration|CLAUDE_INDEX]]
