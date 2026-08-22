# 🧱 פלייבוק — "מתחילים את הקרקע למשחק חדש"

> **מתי להפעיל את המסמך הזה:** ברגע שהמשתמש אומר *"מתחיל את הקרקע למשחק חדש"* (או כל ניסוח דומה).
> זה ה-**שלב 1** של כל פרויקט תרגום: **כל מה שעושים ובודקים *לפני* שמתחילים לתרגם בפועל** —
> גם ממשק וגם כתוביות. בסוף השלב הזה אני מגיש למשתמש דוח, מתרגם מסך תפריט אחד להוכחה,
> והוא מאשר. רק *אחרי* האישור עוברים ל-**שלב 2** (המסמך הנלווה
> [`AGENT_TRANSLATION_HANDOFF_TEMPLATE.md`](AGENT_TRANSLATION_HANDOFF_TEMPLATE.md) — מסירת התרגום לסוכן שני).
>
> המסמך נכתב מתוך **כל** הלקחים שנצברו ב-CP2077 · Spider-Man 2 · Watch Dogs 2 ·
> God of War Ragnarök · AC Shadows · AC II · Steam. כל "מלכודת" כאן עלתה לנו שעות-ימים-שבועות
> פעם אחת — היא כאן כדי שלא תחזור.

---

## עקרון-העל: חטיפת סלוט ערבית (Arabic-slot hijack)

מנועי משחק כמעט **אף פעם** לא כוללים לוקאל עברית, אבל **כמעט תמיד** כוללים לוקאל **ערבית** רשמי —
עם pipeline של RTL/bidi שכבר נבדק ע"י המפתחים. **שותלים את הטקסט העברי בתוך סלוט הערבית**
(אותם בתים UTF‑8/UTF‑16), המשתמש מגדיר את שפת הממשק במשחק ל**ערבית**, והעברית יורשת את ה-RTL בחינם —
**אפס קוד bidi משלנו.**

* מוכח על: CP2077 (`ar-ar` ב-CR2W) · SM2 (`variant_18`) · WD2 (`main_arabic.loc`, `TextLanguage2=22`) ·
  GoWR (`r_lang_ar.wad`) · AC Shadows (`ar-AE`) · Steam (`language:"arabic"`).
* **הנתון הערבי המקורי הוא ה-ground-truth** למבנה, רווחים, ירידות שורה ומיקומי `&rlm;`. מתאימים אליו.
* **הטקסט והקול עצמאיים** — קביעת שפת הטקסט לערבית משאירה דיבוב אנגלי (CP2077; SM2 נועל `englishVO=1`).
* **חריג — משחק בלי סלוט ערבי כלל** (AC II 2009): חוטפים סלוט **LTR** (אנגלית) ו**אופים סדר ויזואלי** ידנית.

---

## ⛓️ סדר העבודה המחייב (אסור לדלג ואסור להקדים)

הקריאה הפיכה; הכתיבה הרסנית. לכן בונים את כל שרשרת ה-`read → repack → deploy` על **round-trips של זהות**
לפני שנוגעים בתרגום. הסדר שהציל אותנו (וקריסות שנגרמו מהפרתו):

1. **שלב 0 — מיפוי בנייה:** מנוע, פורמט הארכיון, **איפה הטקסט** (ממשק מול כתוביות), **איפה הפונט**.
2. **שלב 1 — סלוט ערבית קיים?** מאמתים שיש לוקאל ערבי + שמחלצים ממנו טקסט (השלד).
3. **שלב 2 — מצב bidi:** האם המנוע עושה bidi? לאחסן **logical** או **visual**? (יכול להשתנות לפי משטח!)
4. **שלב 3 — פונט:** יש בו עברית? אם לא → הזרקה. + **האם הוא מתאים גרפית לאווירה**.
5. **שלב 4 — הוכחת repack (identity round-trip):** read → repack בלי שינוי → bit-identical. **רק אחרי שזה עובר** —
   test-string בודד → ורק אז תרגום. (ב-GoWR דילוג על הצעד הזה עלה **3 שבועות** debugging.)
6. **שלב 5 — תרגום המסך הראשון של התפריט הראשי** → המשתמש בודק שהעברית תקינה ונראית טוב in-game.
7. **שלב 6 — דוח ספירה:** כמה משפטים בממשק וכמה בכתוביות — **ספירה נפרדת**.
8. רק אחרי שכל זה ✅ — עוברים לשלב 2 (מסירת התרגום לסוכן).

> ⚠️ **כלל הזהב:** *אל תתחיל לתרגם 40,000 שורות לפני שהוכחת end-to-end שמחרוזת עברית אחת מופיעה במשחק
> נכון, RTL, בפונט קריא, בלי קריסה.* כל שעת groundwork חוסכת ימי debugging.

---

## שלב 0 — איך המשחק בנוי

### 0.1 לזהות את הפורמט מה-magic, לא מהסיומת
קוראים את ה-magic (4–20 בתים ראשונים) **לפני** כל הנחה. `.loc` יכול להיות Huffman (WD2) או oasis UTF‑16
(AC Shadows); `.wad` = LZ4‑framed → WAD/WTOC פנימי; `.forge` = Oodle‑Kraken. זיהוי לפי תוכן חוסך 100+ שעות debugging מעגלי.

### 0.1b 🔑 לפני שמפצחים — לבדוק אם הפורמט כבר **פומבי/פתוח** (הלקח הכי חוסך-זמן בפרויקט)
רוב המשחקים כאן דרשו פיצוח קנייני מאפס (לפעמים ימים). אבל **מנועים מסחריים גדולים לרוב מתעדים את
פורמט הטקסט שלהם, או שקיים מימוש-ייחוס בקוד פתוח.** הצעד הראשון בכל משחק חדש: לזהות את המנוע →
לחפש reader/writer קוד-פתוח לפורמט הטקסט **ולקונטיינר**. דוגמאות מוכחות:
* **Until Dawn (UE5):** הטקסט הוא `FTextLocalizationResource` של Unreal עצמה, ומימוש-ייחוס מלא
  (`akintos/UnrealLocres`) נתן את פריסת הבתים המדויקת ב-**~2 דקות** דרך `curl raw.githubusercontent.com`
  — במקום ימי RE. גם הקונטיינר היה חינם (**`repak`**, כבר מוטמע בפרויקט מ-Hogwarts Legacy).
* **Hogwarts Legacy (UE4):** אותו `repak` + `parseltongue` ל-AVAFDICT.
* גם כשהכלי הוא GUI/‏.NET סגור — **decompile** (`ilspycmd`) נותן את המפרט בלי להריץ אותו
  (AC2/AC Shadows/BF6). ⚠️ `gh` לא מאומת בפרופיל הזה → `curl` ל-`api.github.com`/`raw.githubusercontent.com`
  עובד אנונימית לריפו ציבורי.

### 0.1c 🔑 writer שמשנה רק VALUES לא צריך את פונקציית ה-HASH של הפורמט
פורמטים רבים שומרים hash/checksum מחושב-מראש של שדות שאנחנו **לא** נוגעים בהם (ב-LocRes v3: CityHash64
של שמות namespace/key). מכיוון שתרגום רק מחליף ערכים למפתחות **קיימים** — **מעתיקים את בתי ה-hash
שנקראו** במקום לממש מחדש את אלגוריתם ה-hash. חסך מימוש CityHash64 שלם ב-Until Dawn. כלל כללי לכל
פורמט עם hash/checksum מעל שדות שלא משתנים.

### 0.2 לבנות decoder קריאה-בלבד ב-Python (בלי GUI)
מאתרים פורמט → בונים reader → מפיקים `{id, en, ar, context}` JSON. **enumerate כל קובץ בארכיון** כדי להפריד
טקסט מתרגם מ-assets מחוץ לסקופ (`.inkwidget` תבניות UI, `.bk2` וידאו, `.xbt`/`.xbm` תמונות, strings ב-exe).
לסנן `voiceovermap*.json` (mapping בינארי של cue אודיו, null-bytes) — אלה לא "תרגום חסר".

### 0.3 "crash-as-proof" — אימות הפוך
אם עריכת resource גורמת לקריסה ב-load — זו **הוכחה** שהמנוע קורא אותו. מזריקים marker (`"TEST"`) ל-resources
מועמדים: קריסה או marker-על-המסך = הוכחת טעינה; resource שלעולם לא נטען לא יכול לקרוס. כך מפרידים dev-source מת
מ-runtime data אמיתי.

### 0.4 ⚠️ קובץ ה-export האנגלי לרוב **לא שלם** — לחלץ מהמשחק עצמו
`localization_export.json` חיצוני חיסר אצלנו 25–36% מהטקסט (חולץ pre-patch). ב-CP2077: ה-export החזיק 44,998
onscreens בעוד הארכיונים של המשחק החזיקו 60,296–70,572 → פער של ~25k מחרוזות = UI בלתי-נראה בכל מקום.
**תמיד מחלצים את האמת האנגלית ישירות מ-`lang_en_text.archive` של המשחק (+ DLC), עושים UNION, ומצליבים מול ה-export.**

### 0.5 איפה הפונט גר (לזהות מוקדם)
TTF מוטמע ב-CR2W (`.fnt` עוטף base64 TTF — CP2077/SM2) · atlas DDS (`.ffd`/`.xbt` — WD2 · `copperplate` BC4 — GoWR)
· DDS bitmap atlases (AC2) · TTF רגיל ב-`resources/` (AC Shadows). זה קובע אם ולאיך מזריקים עברית בשלב 3.

---

## שלב 1 — בדיקת ממשק + "האם יש ערבית" (קיצור הדרך RTL)

1. **האם קיים לוקאל ערבי רשמי?** מחפשים `ar`/`ar-ar`/`ar-AE`/`arabic`/`variant_18` ברשימת השפות
   (`LANGS_*.txt`, `boot-options.json`, רשימת locales בארכיון). אם **כן** — קיבלנו RTL בחינם (עקרון-העל).
2. **לאמת end-to-end לפני השקעה:** מפנים/מזריקים את הטקסט **הערבי המקורי** → מפעילים את המשחק עם
   Language=Arabic → מוודאים RTL נכון on-screen. אם ערבית מתרנדרת RTL — עברית תירש את זה.
   *(AC Shadows: עשינו בדיוק את זה ב-2026‑06‑17 — מסך ההגדרה הראשוני התרנדר ערבית RTL מושלם, מאשר שהסלוט אמיתי.)*
3. **אזהרת caveat — רק טקסט יורש RTL.** frontend מקודד-קשיח LTR יישאר LTR: ב-WD2 התפריט הראשי **נעול-אנגלית**
   גם כשהחטיפה עובדת. תיעד את זה כמגבלה ידועה, אל תבזבז שעות לנסות "לתקן" frontend נעול.
4. **אם אין ערבית כלל** (AC2): חוטפים סלוט LTR (אנגלית/נורווגית) ואופים סדר ויזואלי (שלב 3, מצב VISUAL).

---

## שלב 2 — לוודא שיש לנו את הטקסטים של ערבית (השלד)

* מחלצים את ה-**שלד הערבי** = כל ה-keys/ids, אפס זיהום אנגלי. זה ה-**TARGET** שממלאים עברית לתוכו.
* **השלד מגדיר את הסקופ:** מחרוזת אנגלית בלי מקבילה ערבית = dev-only/engine-driven — **קורסת אם משתילים בה עברית.**
  הסקופ = חיתוך המפתחות `EN ∩ AR`.
* **diff מבני EN-מול-שלד לפני תרגום:** אם לשלד יש `&#xA;` הוא חייב להיות ב-EN; אם ל-EN יש `[TOKEN]` שאין בשלד —
  ה-EN פגום. ids זהים בין שפות (oasis/MSGS) — ממזגים עברית לתוך השלד הערבי **לפי id**.
* **תחום ה-key חייב להיות עקבי** בכל הצנרת (source/spine/archive). החלפת domain באמצע (extraction של משחק אחר
  שמַפתח לפי `line_id` במקום `stringId`) משתילה עברית תחת מפתחות שגויים → blank in-game.

---

## שלב 3 — מצב bidi: LOGICAL מול VISUAL (per surface!)

שתי מחלקות מנועים — **לזהות את המצב קודם כל**:

| מחלקה | אחסון | דוגמאות | איך |
|---|---|---|---|
| **BIDI-RENDERING** | **LOGICAL** (סדר קריאה טבעי) | cohtml/GameFace, CR2W, oasis, WD2 *כתוביות* | המנוע הופך ל-RTL בזמן render; משתמשים ב-`&rlm;` anchors תואמי-ערבית |
| **NON-BIDI** | **VISUAL** (הפוך-מראש לכל שורה) | WD2 *תפריטים/UI*, Disrupt legacy, AC2 | הופכים כל ריצת-עברית + הופכים סדר הריצות; Latin/מספרים/tokens נשארים קדימה; מראה סוגריים |

> ⚠️ **אותו משחק יכול לערבב מצבים לפי משטח!** ב-WD2: תפריטים = **VISUAL** (`visual()`/`to_visual()`),
> כתוביות = **LOGICAL** (renderer הכתוביות עושה bidi). אחסון משטח אחד במצב הלא-נכון → טקסט מראה/ג'יבריש in-game
> (באג "עברית ראי"). **קובעים כיוון פעם אחת מראש דרך test-apply, ואז כל ה-builders בנויים עליו.**

* סוכנים והקהילה תמיד עובדים ב-**LOGICAL** (עברית קריאה); `visual()` מוחל **רק** בזמן build/deploy.
* **מאמתים בעין in-game / דובר עברית — לא בהיוריסטיקה.** אין compile error שתופס טקסט-מראה.
* `python-bidi` לסימולציה לפני שילוח (מילים אנגליות שלמות, פיסוק בצד הנכון, גלישת שורות). **הערה:** python-bidi
  לא מיישם L4 bracket-mirroring → סוגריים נראים הפוכים בדוח אבל המנוע (ICU) מהפך אותם נכון. אל תהפוך סוגריים מראש.

---

## שלב 4 — פונט: יש בו עברית? אם לא — הזרקה. ובדיקת התאמה לאווירה

### 4.1 קודם — האם הפונט של סלוט הערבית כבר מכיל עברית?
בודקים אם יש codepoints `U+05D0–U+05EA` עם outlines אמיתיים (לא `.notdef`). **AC Shadows** (`AvenirNextWorld-Regular.ttf`:
52 גליפי עברית + 104 ערבית + 133 presentation forms) ו-**GoWR** (חלקית) — לפעמים יש → **אפס עבודת פונט**.
**WD2** (הפונט הערבי כבר מכסה עברית — אין צורך) · **SM2/CP2077** — צריך הזרקה.

### 4.2 שלוש טכניקות הזרקה (לפי איפה הפונט גר — שלב 0.5)
* **TTF embed** (CP2077/SM2): subset של Heebo מוטמע דרך fontTools לתוך ה-`.fnt` (CR2W rendFont עוטף base64 TTF).
* **Atlas inject** (SM2/WD2): חורצים glyph box חדש ב-DDS atlas (TBX + DXT5), מעדכנים metrics ב-`.fnt`/SMF.
  **מדביקים את ה-DDS header המקורי (128 בתים) על גוף ה-DXT5 החדש** — Pillow כותב `dwPitchOrLinearSize`/mipcount שגוי → corruption.
  גליפים = white-RGB + alpha=coverage. ה-atlas המקורי לרוב מלא → atlas **גבוה יותר** (1024×2304).
* **Atlas generate** (WD2): בונים atlas עברי טרי מ-TrueType, שומרים כל גליף מקורי, מוסיפים עברית בקנבס גבוה יותר.

### 4.3 ⚠️ מלכודת ה-OFF-BY-ONE בטבלת הגליפים (GoWR, SMF גנרי) — קריטי
חלק מטבלאות הגליפים שומרות, ברשומה בקוד-נקודה X, את ה-**outline של X+1**. המנוע מרנדר codepoint C ע"י exact-match
לרשומה `cp==C`, ואז מצייר את גליף ה-**רשומה הקודמת**. לכן אות עברית L צריכה: (א) glyph(L) ברשומה `cp=L-1`,
**ו**-(ב) רשומת-עוגן ב-`cp==L`. ל-`U+05D0–U+05EA` מזריקים 27 רשומות ב-`cp=0x5CF..0x5E9` **ועוד עוגן ריק ב-`0x5EA`**
כדי שת' (cp הגבוה) יקבל exact-match. חסר העוגן → האות האחרונה נופלת ("הגדרות"→"הגדרו"). **אבחון:** מזריקים markers
לטיניים לסלוטים העבריים וקוראים אילו אותיות מופיעות in-game → חושף את ה-±1 בלי עמימות.

### 4.4 baseline / cell / מספרים ערביים
* **Union-extent cell:** מרנדרים את כל הגליפים על קנבס אחד ב-baseline אחד, לוקחים את ה-UNION ink-extent כגובה התא
  (כדי ש-ל' לא תיחתך); מיישרים את baseline התא ל-Latin baseline דרך `y_off` החתום. המנוע baseline-anchored:
  `bitmap_bottom = line_baseline + y_off`.
* **כתוביות ריקות (בלי tofu)** = הטקסט נותב נכון אבל **פונט הכתוביות חסר עברית** (משחקים מפרידים פונט תפריט מפונט דיאלוג).
* **ספרות ערביות-הודיות:** בלוקאל ערבי המפַרמט פולט `U+0660–U+0669` (+ `U+06F0–U+06F9`, `U+066A/B/C` עבור `% . ,`),
  **לא** Latin. אם לפונט העברי אין אותם → מספרים/פיסוק **בלתי-נראים** בעוד הטקסט תקין. תיקון: cmap-alias של כל הטווח
  ל-Latin (בלי עיצוב גליף, `cmap_format_4`) ב-fontTools בפעם אחת. (בלתי-נראה במצב אנגלית, **קריטי במצב ערבית**.)
* **Font fallback** — הרבה widgets מקודדים-קשיח משפחת פונט Latin-only (Raj/Industry/Arial). הרבה מנועים לא עושים
  glyph-level fallback בין משפחות → צריך להחליף את ה-`.fnt` בכל סלוט מקודד, לא רק את משפחת הערבית האחת.

### 4.5 ⚠️ הפונט צריך להתאים לאווירה הגרפית של המשחק
לא רק *קריא* — *מתאים*. בוחרים פונט עברי שמשתלב באסתטיקה ובהעדפת המשתמש: GoWR קיבל **David Regular**
(קליל/אוורירי, לפי בקשת המשתמש) — פונט עברי "GoW-themed" לא קיים (פונטי copperplate/godofwar של המשחק נושאים
**אפס** עברית, וזו בדיוק הסיבה שמזריקים). מראה "engraved" רך: supersample + GaussianBlur glow (`max(sharp, glow*1.4)`,
peak clamped 180) — `alpha=255` קשיח נראה שטוח/"מקוטע". **מציגים למשתמש את בחירת הפונט ומאמתים בעין לפני שממשיכים.**

---

## שלב 5 — הוכחת repack (identity round-trip) — לפני כל תרגום

> **זה הצעד הכי חשוב במסמך.** read original → extract/decompress בלי שינוי → re-pack בלי שינוי → **MD5 זהה למקור** (delta=0).
> רק *אחרי* שזה עובר — בודקים delta קטן (test-string בודד), ואז תרגום. delta של בית אחד מזיז offsets של streams →
> sections downstream (atlas פונט, UI) נהרסים → טקסט ריק או קריסה.

* **LZ4:** `lz4.frame.compress(..., compression_level=0, block_linked=False, content_checksum=True, store_size=True)`.
  **level 0 = byte-identical** לפַקֵר של המשחק; level 9 הוא LZ4 תקין אבל פיצול 64KB שונה → **המנוע דוחה בשקט** (טקסט ריק + קריסה).
* **Oodle-Kraken:** רק `compression_level=0` byte-identical. עוטפים `oo2core_<N>_win64.dll` דרך ctypes (AC Shadows לא משלח
  אחד → שואלים מ-title אחר; רק הפצה חסומה, לא קריאות מקומיות; lead byte `0x8C` = forge blocks).
* **delta=0 הוא ברירת-המחדל המוגנת:** עברית לרוב קומפקטית יותר מערבית → מרפדים את ה-section המתורגם חזרה לגודל-בתים
  המקורי **בדיוק** ב-`\x00` (ומחזירים את ה-`\x00` terminator המקורי — הסרתו = corruption של delta=-1). שום דבר downstream לא זז.
* **delta>0 (סיכון גבוה, חובה לאמת in-game):** כשגדילה בלתי-נמנעת, מתקנים **את כל** שדות ה-header שמַפנים streams.
  ב-GoWR WTOC: (1) שדה גודל הרשומה, (2) כל voff של sections באותו stream אחריה, **ו-(3) שדה גודל-ה-stream המצטבר
  ב-header (בתים 20–23 ל-stream-0)** — שממנו המנוע גוזר כתובות-בסיס של streams downstream. השמטת אחד → offsets זבל → blank/crash.
* **content מול structural validation:** loader עשוי לאמת מבנה (פורמט, alignment, header) בנפרד מתוכן (hash מחרוזת, marker, ספירה).
  אם עריכה מבנית-מושלמת עדיין קורסת — המנוע בודק תוכן. (AC Shadows CFD: ה-checksum הוא **Adler-32 = `zlib.adler32(data,0)`** —
  בדיקת-נתונים פשוטה, לא anti-tamper; ניתן לחישוב מחדש.)
* **forge override priority:** boot < patch_01 < patch_02 (מאוחר גובר). patch_02 לרוב integrity-protected (קורס על כל עריכה) →
  ה-mod slot הוא **patch_01**.
* **הבנייה חייבת להיות דטרמיניסטית** (בלי uuid/timestamp/hash-order אקראי) — rebuild של אותו spine חייב להפיק אותו sha256,
  אחרת version-tracking + deploy-verify נשברים.

---

## שלב 6 — תרגום המסך הראשון של התפריט הראשי (הוכחת חיים)

מתרגמים **רק** את מחרוזות התפריט הראשי / מסך ההגדרות הראשון (מעט עשרות), בונים, פורסים ל-staging, ומבקשים מהמשתמש
לבדוק **in-game**: עברית תקינה? RTL נכון? פונט קריא ומתאים? ספרות/פיסוק נראים? בלי tofu / מראה / קריסה?
זו ההוכחה ש**כל** השרשרת (extract → apply → font → repack → deploy → activation) עובדת end-to-end לפני ה-haul הגדול.
המשתמש (דובר עברית) הוא ה-gate הסופי — structural parsers הכרחיים אבל לא מספיקים.

### 6.1 🔴 חובה: לבדוק **COLD BOOT**, לא רק אחרי החלפת שפה (מחלקת-כשל שלישית)

**הוכחת-תפריט שעברה אחרי החלפת-שפה חיה עדיין לא סוגרת כלום.** יש מנוע שבו הטקסט מרונדר **מושלם אחרי
החלפת שפה בריצה** אבל **חלקי + "????" בעלייה מאפס** (Anno 1800). זה לא פונט ולא bidi — למנוע יש **שני
מסלולי גליפים**: prebake **סטטי וצר** בעלייה, ו-rasterizer **דינמי** שנדלק ב-re-init של שפה. ב-Anno
רוחב ה-prebake נקבע לפי **מחלקת השפה** בקוד (CJK=רחב וטוען עברית · LTR=צר ומשמיט) — **ואין שום לֵיבֶר
בנתונים**.

**לכן בשלב 6 תמיד מבקשים מהמשתמש שתי בדיקות:** (א) עלייה מאפס; (ב) החלפת שפה בריצה. אם (ב) תקין ו-(א)
שבור — אתה במחלקה הזאת: אל תחפש עוד בנתונים לפני שסרקת charset/glyph-preload והשוואת רשומה per-language
בין CJK ל-LTR (אם הן זהות בייט-בבייט חוץ מהשם וה-GUID של הנכס — אין מה להפוך), ולפני שסיננת **exe ארוז**
(entry ב-`.xtls` · סקשן ענק writable+executable · `.reloc` זעיר ⇒ patch סטטי מת).
הלֵיבֶר הבטוח היחיד: **החלפת binding באותו גודל לנכס קיים ותקין** (לא לערוך את הנכס ולא דגלי descriptor),
ורק **הוספה** לפונט בטוחה — כל שינוי של גליף/advance/רווח קיים מפיל את ה-prebake ל-"????" מוחלט.
פירוט מלא: CLAUDE.md §8d + [[coldboot-atlas-breadth]].

---

## שלב 7 — דוח ספירה: ממשק מול כתוביות (בנפרד)

* **ממשק (UI)** = תפריטים/הגדרות/labels/HUD/יעדי-משימה/prompts/שמות+תיאורי פריטים-רכבים-בגדים/הודעות מערכת — קצר, keyed.
* **כתוביות (Subtitles)** = דיאלוג/bark/cutscene — ארוך, רב-שורתי, לרוב עם timing tags + voice cues.
* **סופרים לפי enum/section HEADERS, לא לפי גודל גס.** ב-WD2 ה-**enum הוא המבחין היחיד האמין** — שמות sections
  (`CinemaSubtitles`/`BarkSubtitles`) **חסרי-ערך** (UI אמיתי כמו "Brightness" יושב בתוכם): `enum="soundbinary\N.bnk"` = כתובית-אודיו;
  שם סימבולי (`Brightness`, `actNavigate`) = UI. דוגמת WD2: 48,138 סה"כ / 16,537 אודיו / 27,573 UI-named / 4,032 not-in-oasis.

**פורמט הדוח שאני מגיש למשתמש בסוף השלב:**

```
--- דוח קרקע: <שם המשחק> ---
מנוע / פורמט: <engine> · ארכיון <format/version> · טקסט ב-<path>
סלוט ערבית: <כן/לא> (<ar-ar / variant_18 / main_arabic.loc / ...>)  → RTL בחינם: <כן/לא>
מצב bidi: ממשק=<LOGICAL/VISUAL> · כתוביות=<LOGICAL/VISUAL>
פונט: <כבר מכיל עברית / צריך הזרקה ב-<מנגנון>>  · אווירה: <שם פונט נבחר>
repack round-trip: <עבר MD5-identical / נכשל>
הוכחת תפריט in-game: <אושר ע"י המשתמש / ממתין>

ספירה לתרגום:
  • ממשק (UI):     <N_ui>  מחרוזות
  • כתוביות:       <N_subs> מחרוזות
  • סה"כ:          <N_total>
  • (לא-מתורגם/skip צפוי: <שמות/קודים/handles>)

מגבלות ידועות: <frontend נעול-אנגלית / delta>0 לא מאומת / וכו'>
מוכן לשלב 2 (מסירה לסוכן תרגום)? <כן/חסר X>
--- END ---
```

---

## "ועוד דברים שאולי שכחת" — מלכודות-חובה לפני שמתחילים לתרגם

אלה דברים שלא תמיד עולים מפורשות אבל **כל אחד מהם עלה לנו שעות**:

### יעד ה-deploy — ה-killer הסמוי
**תיקיית ה-install של המשחק ≠ התיקייה שהמשתמש משחק בה.** path שגוי בסקריפט deploy → כל re-pack נוחת איפה שהמשתמש
לא מסתכל → הוא טוען ארכיון ישן שעות → "כתוביות ריקות" בזמן שהדאטה תקין 95%. (בזבזנו שעות **פעמיים** על תיאוריות פונט/widget
כשהבאג היחיד היה ה-path.) **שואלים את המשתמש פעם אחת באיזו תיקייה הוא משחק** (שני installs שניהם עוברים sanity), מקודדים-קשיח
את היעד בכל סקריפט, **בודקים את mtime של הארכיון הפרוס** ("עכשיו"?) לפני כל אבחון "למה X עדיין שבור". פורסים ל-**staging
וגם ל-play copy**. עובדים רק על staging נייטרלי (Game Lab/Projects), **לעולם לא `C:\Games`** (המשתמש מאפס אותה).

### gender variants — שורש ה-"UI ריק"
משחקים עם טקסט מפוצל-מגדר (`femaleVariant`/`maleVariant`) בוחרים לפי מגדר השחקן. מתרגמים ממלאים רק `femaleVariant`;
שחקן זכר (V ב-CP2077) קורא `maleVariant` שנשאר שלד ערבי → Heebo בלי גליפי ערבית → המסך מציג רק ASCII `( )`. **תיקון בזמן BAKE
(לא ב-spine):** כשהapply ממלא `femaleVariant` וה-`maleVariant` ריק/ערבי → `maleVariant = femaleVariant`. **חובה בכל ה-appliers**
(onscreens, subtitles, DLC). (ב-CP2077 זה היה בכתוביות+DLC אבל **חסר ב-onscreens** → 7,400 שורות ריקות; mv-updated קפץ 126→7,471.)
שים לב: עברית מטה זכר/נקבה אחרת — backfill ממלא את הסלוט הריק מהמתורגם, בכיוון הנכון.

### activation — איך המשתמש מדליק את התרגום
מתעדים מראש: לרוב = להגדיר שפת-ממשק/טקסט במשחק ל**ערבית** (العربية). WD2: Settings → Written Language → Arabic
(`TextLanguage2=22`), ומפעילים `WatchDogs2.exe -eac_launcher` (EAC כבוי). SM2: HKCU DWORD `TextLanguage=18` + `englishVO=1`.
CP2077: Settings → Language → Interface = العربية. **בודקים שזו הדרך האמיתית** — ב-WD2 ניסיונות registry/reboot נכשלו עד שהמשתמש
הצביע על אופציית ה-Settings.

### EAC / Denuvo / anti-cheat
Denuvo מגן על ה-EXE, לא על asset forges (mods של retexture נטענים — AC Shadows). EAC חוסם ארכיונים מודפקים → WD2 דורש
`-eac_launcher`. בודקים מראש שאין חסם anti-cheat לפני ש-deploy "לא עובד".

### dual-section mirror + סקופ DLC
CP2077 שומר onscreens ב-**שני** קבצים זהים (`onscreens.json` + `onscreens_final.json`) — ממלאים את **שניהם**.
DLC (Phantom Liberty) = ארכיון `ep1/` נפרד — keys של ה-base אין להם סלוט בשלד הערבי של ה-base → אופים בנפרד. ה-bake
חייב לדעת אילו keys הם base-only/DLC-only/shared.

### תאימות source_en ↔ current_he (זריעת pool קהילתי)
אם זורעים pool תרגום-קהילתי: `source_en` ו-`current_he` **חייבים** לבוא מאותו id-mapping authoritative של המשחק.
ב-WD2 73% מהשורות היו mis-paired (EN מ-extraction מקולקל, HE מהשלד הערבי) → שגיאות שקטות מסוג "Take"→"זום".

### זיהוי המשחק (כדי שה-launcher ימצא את ה-install)
מתחזקים `_PATTERNS` (שמות תיקיות) + `_EXE_PATTERNS` (שמות exe). exact-match גובר על substring (מונע `aot2`→`aot2extra`).
**מפתח הזיהוי = `games.id` ב-Supabase בדיוק** (`ac-shadows` עם המקף) — סטייה → ה-installer לא מוצא את המשחק בשקט.

### תיעוד פר-משחק
יוצרים `games/<game>/`: `FEASIBILITY.md` · `RECON.md` · `PIPELINE.md` · ותיקיית `work/` (מעתיקים את שלישיית SM2 כתבנית).
מתעדים את שרשרת הבנייה ב-`CLAUDE.md`. תלויות כלים עם **גרסה** (WolvenKit CLI v8.17.4 — נפרד מה-GUI; אחרי PC-reset
סקריפטי bake נכשלו בשקט).

---

## ✅ צ'קליסט סיום שלב 1 (לפני מעבר לשלב 2)

- [ ] **פורמט מופה** (magic, container, איפה UI, איפה כתוביות, איפה הפונט) → `FEASIBILITY.md`/`RECON.md`.
- [ ] **סלוט ערבית אומת** (קיים + מחלצים שלד) — או הוחלט על hijack של סלוט LTR + VISUAL.
- [ ] **מצב bidi נקבע פר-משטח** (UI=? כתוביות=?) דרך test-apply.
- [ ] **פונט:** מכיל עברית? אם לא — הזרקה עובדת (off-by-one/atlas/cmap טופלו). + **פונט מתאים-אווירה נבחר**.
- [ ] **identity round-trip עבר** (MD5-identical) → ואז test-string בודד מופיע in-game.
- [ ] **תפריט ראשי תורגם + אושר in-game** ע"י המשתמש (RTL, פונט, מספרים, בלי tofu/מראה/קריסה).
- [ ] **🔴 COLD BOOT נבדק בנפרד מהחלפת-שפה** (שלב 6.1) — אם תקין רק אחרי החלפה, זו מחלקת ה-atlas הצר
      ([[coldboot-atlas-breadth]]) והמסקנות (סלוט CJK / החלפה אחת) חייבות להיסגר **לפני** ה-haul.
- [ ] **ספירה:** N_ui + N_subs (בנפרד) + skip צפוי → **דוח הוגש**.
- [ ] **יעד deploy** מקודד-קשיח (staging + play), activation מתועד, EAC/Denuvo נבדק.
- [ ] **gender-variant backfill** קיים בכל applier; **dual-section** + **סקופ DLC** טופלו.
- [ ] **זיהוי המשחק** = `games.id` בדיוק.
- [ ] **שלישיית work/** (`<game>_translate.py` / `_watchdog.py` / `_progress.py`) הותאמה.

---

## 📚 נספח — טבלת עובדות לכל מנוע שכבר נפצח (ייחוס מהיר)

> כשמשחק חדש דומה לאחד מאלה — מתחילים מהשורה המתאימה במקום לגלות מחדש.

### Cyberpunk 2077 — CDPR RED Engine 4 / CR2W, cohtml UI
* טקסט = CR2W בתוך `.archive`; WolvenKit CLI 8.17.4 (`convert serialize`/`deserialize`, `pack`).
* `lang_<loc>_text.archive` → `onscreens.json` (UI, ~60k) + `subtitles/` (~700 CR2W, דיאלוג ~100k). שני onscreens זהים
  (`onscreens.json`+`onscreens_final.json`) — למלא **שניהם**. סלוט = `base/localization/ar-ar/`.
* keying: onscreens לפי `primaryKey`, subtitles לפי `stringId`. **gender:** מילוי `femaleVariant` + **backfill `maleVariant`**.
* markup: בתי-בקרה `0x01–0x05`; `<kiroshi l="jpn" o=.. t=.. b=.. a=..>` (o/m=ערבי לשמר, t/b/a=לתרגם); `<mothertongue>`, `<Rich>`.
  **percent gate פר-key, ערבי-מונע:** אם `arabic[key]` מכיל `%%` → printf (לשמר `%%`); אחרת display (`%` בודד).
* פונט: Heebo subset; **לרוקן גליפי `U+200F`/`U+200E`** (4-contour נראים → tofu); cmap-alias ספרות ערביות→Latin.
  להזריק עברית ל-`.fnt` של Raj/Industry/Arial (לא רק משפחת הערבית). `fallbackFontFamilyPath` **לא עובד** ל-font מקודד.
* cohtml מתעלם מ-CSS `direction`/`dir`; ה-fix המכריע ל-RTL = שינוי **script** של שם Latin→עברית (V→וי לתווית-דובר).
* deploy: `z_hebrew_translation.archive` ב-`archive/pc/mod/`; **המשחק חייב להיות סגור**; backup ל-`mod_backups/<ts>/`.
* **`V` נשאר Latin בפרוזה, אבל רשומת שם-דובר בודדת (`pk=48683`) חייבת "וי"** כדי שה-colon RTL ישב נכון.

### Spider-Man 2 — Insomniac, DAT1/TOC2, cohtml UI
* DAT1/DSAR; TOC2/I29 (`[u32 0x34E89035][u32 logical_len][raw DAT1 '1TAD']`, uncompressed). span 144 = ערבית = `variant_18`.
* mod = `.modular` (ZIP של `.stage` ZIPs); כל asset = `{span}/{UPPER_HEX_ID}`. **applier נייטיב** (`spiderman2_mod.py`,
  בלי Overstrike): DAT1 raw ל-`d/mods/tm_he_<i>` + 66-byte RCRA entry + redirect של `RcraSizeEntry`; הפיך (`toc.tm_he_backup`).
* activation: HKCU DWORD `TextLanguage` (0=EN,18=AR) + `englishVO=1`. **באג path לא-ASCII = 0xe06d7363** → junction ל-`C:\SM2`.
* cohtml: סלוט ערבי **PARTIAL RTL** (`cohinline` בלי bidi controls) → `&rlm;` (U+200F, **לא** RLE) anchors תואמי-ערבית.
  Heebo: לרוקן `U+200F`/`U+200E`. הזרקת 27–32 גליפים ל-DDS atlas (SDF), **off-by-one**, baseline שורה 37, union-extent cell.
* שרשרת בנייה **חובה** `10→91→94→95→96→97→15→80` (שלב 15 בונה את ה-stage; דילוג עליו = stage ישן/תרגום בלתי-נראה).
* Mods Library — **שתיים** (Downloads + Game Lab) — לפרוס ל-שתיהן + לנקות `Cache.json`+`Suits Cache.json`; להעלות `BUILD_VERSION`.

### Ratchet & Clank: Rift Apart — Insomniac (אותו מנוע כמו SM2) — **תבנית ה-reuse בין-כותרים**
* **קודם כול לבדוק את ה-magic:** `toc` = `0x34E89035`+`1TAD` → dat1lib `TOC2 version 202300 == VERSION_RCRA` = **בדיוק הענף
  של SM2**. קריאה אחת קיפלה container+text+repack+applier ל"שימוש חוזר" (147 ארכיונים / 340,665 assets / 256 spans).
* טקסט = `localization/localization_all.localization` (aid `0xBE55D94F171BF8DE`, **32 ווריאנטים**, variant *N* → span *N*×8;
  כולם חולקים aid אחד — **ה-span בוחר שפה**). מבנה DAT1 **זהה ל-SM2**: אותם 9 tags (VALUES `0x70A382B8`, KEYS `0x4D73CEBD`,
  TEXT_OFFSETS `0xF80DEEB4`, KEY_OFFSETS `0xA4EA55B2`, ENTRY_COUNT `0xD540A903`), 24,575 entries. סמן כתוביות = `<ts="a;b">`.
* **🔴 אין סלוט ערבי בכלל** (0 codepoints ב-32 הווריאנטים — אומת יריבית) → **חטיפת סלוט LTR (אנגלית)**, לא חטיפת ערבית.
  אנגלית = v0/v1 (en-US, המקור) + v2/v18 (en-GB); סלוט-הקרבה חלופי = טורקית v19. ⚠️ **סדר הווריאנטים שונה מ-SM2**
  (ה-`variant_18` שהוא ערבית ב-SM2 הוא שפה לטינית כאן) — אל תניח מיפוי זהה רק כי המנוע זהה.
* **⚠️ לסווג שפה לפי section הערכים בלבד** — sniff על הקובץ המלא הראה ~3,400 "ערבית" בכל ווריאנט (רעש מ-sections משותפים).
* פונט = **Proxima Nova** Reg (`0xA2197874D2B7B1AC`) + Bold (`0xB5F411285669C55D`), archive 109 `d\userinterface`,
  **sfnt TTF נקי בלי wrapper** (פשוט מ-SM2). 0/27 עברית בכל 10 הפונטים → הזרקה דרך `anno_font._add_hebrew` (Heebo/Rubik),
  **+ למפות U+200F/E/202A-E לגליף ריק zero-width** (בלי זה עוגן `&rlm;` = tofu).
* **applier = `spiderman2_mod.py` AS-IS, אפס שינוי קוד.** `.stage` = `{span}/{HEXID}`; blob של loc = DAT1 **בלי** 36-byte
  header (`header_offset=3123756`, value=filesize−36); blob של פונט = **TTF שלם** (`header_offset=-1`, value=filesize).
  פריסה: `d\mods\tm_he_*` + append archive + redirect; גיבוי `toc.tm_he_backup`; revert משחזר.
* repack = **SEMANTIC-PASS** (0/24,575 אי-התאמות ב-re-parse, לא byte-identical — דפוס SM2/TLOU2 המוכח).
* היקף: **ממשק 7,521 · כתוביות 10,033 · skip 7,021 = 17,554 לתרגום.** activation = Settings → Game Settings →
  Text Language = English (VO עצמאי → דיבוב אנגלי בחינם). **אין Denuvo/EAC.** bidi = הוכחת-תפריט מכריעה (cohtml מריץ UBA
  → ברירת-מחדל LOGICAL+`&rlm;`, גיבוי VISUAL).

### Watch Dogs 2 — Ubisoft Disrupt, FAT5 v11
* `.fat`+`.dat`, common < patch < patch2. טקסט = `languages/main_arabic.loc` (**Huffman "SL"**, UTF-16). `oasisstrings.rml`
  **לא נקרא ב-runtime**. שלד-אמת = oasis XML, מבחין לפי `enum`. **loctool `.loc.txt` מקולקל ל-barks — להשתמש ב-oasis XML.**
* FAT5 entry = 20 בתים; **stored (scheme 0) ⇒ UncompressedSize חייב = 0** (אחרת fallback לארכיון נמוך-עדיפות). name-hash = Gibbed FNV1a64.
* **UI = VISUAL, כתוביות = LOGICAL** (הפוך!). line-breaks → token `[LF]`.
* פונט `helveticaneuelt_w1g_65_md_arabic.ffd` + atlas `.xbt` — **כבר מכסה עברית, אין הזרקה**.
* deploy = fat-redirect ל-**כל 3 הארכיונים**; backup `F:\WD2_lang_backup`; activation Settings→Arabic + `-eac_launcher`.
  **frontend נעול-אנגלית** (HUD/missions/subtitles כן עוקבים). כלים: `wd2_loc.py`/`wd2_archive.py`/`wd2_font.py`.

### God of War: Ragnarök — Sony Santa Monica
* `exec/wad/pc_le/r_lang_<loc>.wad` = LZ4-frame (`04 22 4D 18`) → WAD/`WTOC` → `MSGS_TXT` רשומות UTF-8 `*<id>*\n<value>\n`,
  ids זהים בין שפות. סלוט ערבי רשמי. סקופ = **48,886** (EN∩AR). לשמר: `[[S:CHAR:vo_…]]`, `\n`, `[style=..]`, `%d`, `[Icons:…]`.
* repack: **LZ4 level=0 byte-identical** (level 9 נדחה→blank+crash); **MSGS pad ל-delta=0**; delta>0 = ניתוח offsets מרובה-streams.
* פונט: copperplate `BC4 1024×1024`, טבלה `SMF_1` (28-byte records, **off-by-one**, עוגן ב-0x5EA). פונט = **David Regular** + glow.
* מגבלות engine-native (כמו ב-ערבית הרשמית): חלק מהפאנלים LTR, bullets/nav-icons בצד LTR — לא mod-fixable.

### Assassin's Creed Shadows — Ubisoft Anvil, scimitar v42 (2025)
* `.forge` (`scimitar\x00`+`0x2A`); בלוקים Oodle-Kraken (lead `0x8C`); אין `oo2core` → לשאול `oo2core_9_win64.dll`.
* טקסט = UTF-16LE; oasis line records (`[lineID u64][0xFADE9F44]...`) + bare UI strings. ב-`DataPC_boot.forge` + patches.
* **פונט כבר מכיל 52 גליפי עברית — אפס עבודת פונט.** activation = INI flip ל-`ar-AE` (**RTL אומת in-game**).
* deploy = repack של `patch_01` (patch_02 integrity-protected). Denuvo על EXE בלבד. **ה-gate: אין repacker v42 חופשי** (חוסם pipeline אוטומטי).

### Assassin's Creed II — Ubisoft Anvil, scimitar v25 (2009 קלאסי)
* `.forge` v25. טקסט ב-`DataPC.forge` → `LocalizationPackage_<Lang>` (**char-INDEX serialization**, לא UTF-16 שטוח).
  **14 שפות LTR, אפס ערבית** → חוטפים סלוט **אנגלית** + **VISUAL order**. פונטים = DDS bitmap atlases ב-`DataPC_extra.forge`.
* repack ב-pure Python (פוענח מ-AnvilToolkit דרך `ilspycmd`). Persian/Arabic fan-translations מוכיחים שהשרשרת עובדת.

### Assassin's Creed Unity — Ubisoft AnvilNext 2.0, scimitar v27 (2014)
* `.forge` v27 (בין AC2 v25 ל-AC Shadows v42). **קונטיינר פוצח מלא** — `games/acunity/tools/acu_forge.py` (reader pure-Python):
  header(magic+u32 ver@9+i64 idxOff@13) → מערך רשומות 20-בתים `[u64 off][u32 fid][u32 flags][u32 usz]` ב-`idxOff+0x70` →
  טבלת descriptors **קבועה 192-בתים** (record-index ב-+0x20, שם ב-+0x2b) → משאב לפי שם. resources = Anvil DataFile chunks (magic `0x57FBAA33`/`0x1004FA99`, כמו AC2/ACS).
* טקסט ב-`DataPC.forge` → `TLocalizationPackage_<Lang>` (+`_Subtitles`,`_EManual`), **char-INDEX u16** (כמו AC2), **מאוחסן uncompressed** → קריא בלי codec.
* **🟢 יש סלוט ערבית רשמי** (`TLocalizationPackage_Arabic` + `_Subtitles` 204KB + `Support/Readme/Arabic/`) — חטיפת-סלוט-ערבית חלה (בניגוד ל-AC2). **מלכודת:** ה-UI הערבי = stub ריק 139B (Ubisoft שילחה ערבית = כתוביות + תפריט אנגלי) → כתוביות = סלוט ערבי; UI = או למלא את הסלוט הערבי או לחטוף אנגלית. **bidi = VISUAL, לא logical** (מתוקן — AnvilNext של Unity בלי RTL מנועי; נוסף רק ב-Valhalla/Mirage, Al-Batineh 2024) → `visual_line` לשני המשטחים.
* פונט = **`.ffd` (Fire_Font_Descriptor) + FTX/DDS atlas — מודל WD2** (מתוקן: סמני FFD x41/x25/x30, לא Scaleform) → FFDConverter/`wd2_font.py` (עוצר ב-AC Rogue → v27 אולי צריך התאמה). **codec = LZO** (mode byte 0/1→lzo1x,2→2a,5→1c; stored כש-src==dst; אין Oodle) — loc מאוחסן ⇒ READ בלי codec. DRM = Uplay/VMProtect, **אין Denuvo**.
* **repack: AnvilToolkit** (חינם, Nexus, תומך Unity, XML loc export/import) + ACExplorer/pyUbiForge (Python read, אימת את מבנה הקונטיינר). **מוד English-loc קהילתי 2025 משלח DataPC.forge מודפק שהמשחק טוען → השרשרת מוכחת.** **#1 GATE:** repack v27 ש**גם נטען וגם שורד את בדיקת התקינות של Ubisoft Connect** (עלול לדרוש מפתח הפעלה אחרי החלפת forge → עדיף runtime Asset-Overrides loader) + writer פייתון ל-bundle. **צעד הבא = Stage-0 identity round-trip.** מסמכים: `games/acunity/{FEASIBILITY,RECON,PIPELINE,BRIEF}.md`. **מצב: קרקע שלב-1 הושלמה, GO-with-caveats.**

### Steam — Valve client
* 8 קבצים: 4 JSON (`*_arabic-json.js`) + 4 VDF (`*_arabic.txt`). JSON = webpack `JSON.parse('…')` (escape `\'`,`\\`; לברוח U+2028/U+2029).
  VDF = **UTF-8 BOM** (לא UTF-16!); מפתח `"Language"` הוא **sibling של `"Tokens"`** (לפניו). חטיפה = `language:"arabic"`.
* deploy = backup-then-overwrite עם `.orig` (נכתב **פעם אחת**; scheme עם timestamp לא יכול לעשות toggle).

### Anno 1800 — Ubisoft Mainz "Anno" engine, RDA V2.2, native HUD + CEF panels
* ארכיון = **RDA "Resource File V2.2"** (`maindata/data*.rda` + per-lang `en_us0/de_de0/fr_fr0/ru_ru0.rda`). header 0x318
  (firstBlockOffset u64 @0x310) → שרשרת **BlockInfo(32)** בזנב כל block → **DirEntry(560)** (name[520] UTF-16LE+off+csz+usz+ts+unk).
  דחיסה **zlib/deflate** (לא lz4). reader פייתון-טהור read-only: `work/rda_reader.py` (seek-only, בלי לטעון GB ל-RAM). פירוק/אריזה: RdaConsole/RDAExplorer (רק לקריאה — לא צריך repack).
* טקסט = `data0.rda` → **`data/config/gui/texts_english.xml`** (NOT `en_us0.rda`=Wwise audio). 12 שפות LTR; `<TextExport><Texts><Text><GUID>n</GUID><Text>s</Text></Text>`,
  UTF-8/CRLF, **GUID מספרי משותף בין כל השפות** = id-mapping. ~28,165 רשומות בסיס (~1.5–2× עם DLC). UI-dominant.
* **אין ערבית כלל** → **חטיפת סלוט אנגלית (AC2-class)**: עברית ב-`texts_english.xml`, המשתמש נשאר Language=English.
  `engine.ini`: `TextLanguage`/`AudioLanguage` נפרדים → VO אנגלי בחינם.
* **פיצול UI (מלכודת!):** ה-HUD הראשי = GUI **נייטיב** (layouts XML/בינארי, `data/ui/*.dds`, פונטי `data/fonts/*.ttf`) — **לא** CEF.
  **CEF/Chromium 108** מרנדר רק פאנלי סטטיסטיקה/גרפים/דיבאג (`data/config/http`). **מצב bidi של ה-HUD הנייטיב הוכח in-game = NON-bidi**
  (VISUAL נקרא נכון, LOGICAL הפוך) → **לאחסן VISUAL** (כמו WD2 menus/AC2). `build_mod.py` ברירת-מחדל VISUAL; המתרגם פולט LOGICAL, ה-visual מוחל רק ב-build.
* **פונט:** אף פונט UI לא מכיל עברית (Meta/Kelvinch/Heuristica/Roboto = Latin+Cyrillic) → הזרקה **קלה** (TTF loose, לא atlas/CR2W):
  `work/anno_font.py` מוסיף U+0590–05FF מ-`frank.ttf` (Frank Ruehl, מתאים-אווירה) לכל TTF דרך fontTools (DecomposingRecordingPen+TransformPen),
  שומר את שם/Latin/Cyrillic של הפונט המקורי, נשלח כ-override loose ב-`data/fonts/`. **הוכח in-game: עברית מרונדרת מושלם.**
* **deploy = מוד loose-file, בלי repack כלל.** טעינת מודים **מובנית במשחק** (xforce/anno1800-mod-loader שולב; אין DLL). `Documents\Anno 1800\mods\<name>\`
  (גובר, חסין ל-Ubisoft Connect Verify, בלי admin) = `modinfo.json` + `data/config/gui/texts_english.xml` (ModOp `Type="add" Path="/TextExport/Texts"` — הוספת GUID קיים = override) + `data/fonts/<TTF מוזרק>`.
  **אין anti-cheat.** **פורסם v1.0.0-beta.1 (2026-06-22)**, ~56,400 מחרוזות.
  לקח: ב-Anno/mod.io מודים יושבים ב-`C:\Users\Public\mod.io\<gameid>\mods\` (לא ב-Documents) — להזיז אותם הצידה (rename) לבדיקות מהירות.
* **🔴🔴 תיקון קריטי לשתי השורות מעליי — "חטיפת סלוט אנגלית" ו"הכי קל בפרויקט" היו נכונים רק עד ה-cold-boot.**
  הסלוט האנגלי **לא** נותן עברית מלאה בעלייה מאפס: רוחב ה-glyph-atlas ב-cold-boot נקבע לפי **מחלקת השפה בקוד**
  (CJK=רחב וטוען עברית · אנגלית/LTR=צר ומשמיט) — **ואין לֵיבֶר בנתונים** (אומת ב-3 סריקות עומק בלתי-תלויות על
  373k רשומות; רשומות per-language זהות בייט-בבייט חוץ מהשם ו-GUID הפונט), וה-**exe ארוז** (`.xtls` + סקשן
  320MB writable+exec + `.reloc` זעיר) ⇒ patch סטטי מת. לכן שתי מצבי-הקצה היחידים: **(A) סלוט CJK** (קוריאנית —
  עברית מלאה מיד, בלי החלפה; אבל תווית התפריט + פאנלי web חיים בקוריאנית) או **(B) אנגלית + החלפת-שפה אחת
  בכל הפעלה** (תפריט ו-web באנגלית). המוד נשלח עם **כל 5 הסלוטים** מלאים עברית + 2,595 fallback אנגלי
  (כיסוי 100%, בלי "????"), וה-readme מתעד את שני המסלולים. פירוט: CLAUDE.md §8d + [[coldboot-atlas-breadth]].
* **הלֵיבֶר הבטוח שנמצא (PHXLF):** החלפת **binding באותו גודל** — GUID הפונט של השפה הקוריאנית → פונט ה-Meta
  הלטיני, ב-4 קבצי `data/ui/studio/generated/<guid>` (magic `PHXLF`). זה שומר על ה-atlas הרחב (שנגזר מהשפה,
  לא מהפונט) ומתקן את הלטינית/ספרות הרחבות של פונט ה-CJK. **אסור** לערוך את הפונט עצמו (מעבר להוספת גליפים)
  ואסור להפוך את דגל ה-KIND ב-PHXFT — שניהם ⇒ "????" מוחלט ב-cold-boot.

### The Witcher 3: Wild Hunt — CDPR REDengine 3 (`.w3strings`)
* טקסט = `<lang>.w3strings` (magic **"RTSW"**, version **163**/0xA3) ב-`content\content0..12\` + `dlc\*\content\`.
  **17 שפות כולל `ar` רשמי (next-gen 4.0)**. אין פיצול UI/כתוביות — הכול מעורבב, keyed לפי `str_id` מספרי;
  שם ה-key האנושי **לא נשמר** (רק hash). קודק פייתון-טהור: `games/witcher3/work/w3strings.py` (read+write, מאומת).
* מבנה: magic+version+key1 → block1 `{str_id^encKey, offset, strlen}×N` → block2 `{key_hash, str_id^encKey}×N`
  → block3 UTF-16LE blob → footer key2. `keyID=key1<<16|key2` → טבלת מפתחות → encKey. varint מותאם `bit6`.
* **🔑 מחרוזות מוצפנות XOR פר-שפה — אבל keyID 0 = CLEARTEXT, וסלוט הערבית = cleartext** → עברית = UTF-16LE פשוט,
  אפס הצפנה. **`str_id` זהה בין שפות** אחרי `^encKey` → מיפוי EN→HE לפי id.
* **⚠️ bidi = VISUAL (הפוך-מראש, `visual_line`, בלי RLO) — אומת in-game.** הערבית מאוחסנת logical+U+202E RLO, אבל
  **המנוע עושה bidi רק לערבית, לא לעברית** (הוכחה: menu v1 logical+RLO=מראה הפוך, v2 VISUAL=תקין). המתרגם כותב
  LOGICAL, ה-visual מוחל רק ב-build. **לקח כללי: RTL רשמי של סלוט ערבי לא מבטיח bidi לעברית — לבדוק visual מול logical in-game.**
* **פונט: הפונט של סלוט הערבית כבר מכסה עברית — אפס עבודת פונט** (הוכחה: תפריט עברי בלי tofu). (לעיון: פונטים=
  Scaleform SWF `fonts_*.redswf` ב-`r4gui.bundle`; כלים אם צריך = TW3 ModKit `wcc_lite`/WolvenKit **0.6.1** לא 8.x + JPEXS + FontForge.)
* **אין anti-cheat; deploy טקסט בלי repack של bundle** — `Mods\mod<X>\content\<mirror>\ar.w3strings` (או דריסת base, הפיך).
  activation = Options → Text Language=Arabic, Speech=English (`user.settings [Localization] TextLanguage=AR`).
  identity round-trip: byte-identical קטנים, semantic-identical (תקין, נטען in-game) גדולים. **easy tier** (כמו Anno).
  קודק פייתון read/write + `visual_line` + הוכחת תפריט ב-`games/witcher3/work/`. **כל השערים נסגרו 2026-07-01.**

### A Plague Tale: Requiem (+ Innocence) — Asobo "Zouna" engine, loose TRTEXT
* **הטקסט הכי קל בפרויקט:** קבצי טקסט **רופפים** ב-`TRTEXT/ttNN.pc` (NN = TSC_ID מ-`LangDef.tsc`):
  **`tt01.pc`=אנגלית (מקור), `tt23.pc`=ערבית (סלוט העברית)**, tt02..22 = 13 שפות. פורמט UTF-8/CRLF/ללא-BOM:
  `FreeLanguage`/`ResetEnumTT`/`TT <idx> "<value>" <KEY>` (20,661)/`EndLoadTT`. ערכים ללא `"` (פרסינג חד-משמעי);
  KEY משותף בין שפות → מיפוי 1:1; ירידת-שורה בערך = **`|`** (אין `\n`); `{STR_…}` = tokens של מקשים.
  נקרא **loose ב-runtime** (לא ארוז ב-COMMON.DPC) → **deploy = דריסת `tt23.pc`, אפס repack/דחיסה.** `.IGN` = וריאנט שני
  שונה של כל קובץ (`.pc` הוא ה-live ל-PC). **אין Denuvo/anti-cheat.** קודק+טרנספורם: `games/plague_tale_requiem/work/{pt_text,pt_rtl}.py`.
* **⚠️ bidi = מחלקת-מנוע שלישית (חדשה) — RTL-layout בלי bidi לאיי-LTR.** המנוע ממקם תווים **ימין-לשמאל** אבל
  **לא** מסדר-מחדש ריצות-LTR ו**לא** עושה shaping. לכן STORED = **LOGICAL** עם: כתב-RTL (ערבית/עברית) נשאר לוגי,
  **איי-LTR (לטינית/ספרות) הפוכים במקום**, tokens `{STR_}` verbatim, **סדר ריצות נשמר**. הוכחה מהערבית של המשחק:
  ספרה `"12"→"21"`; ספרה רומית `"XVII"→"IIVX"` (IV→VI, IX→XI…), המפריד `" - "` נשאר אחרי הספרה; `"Asobo Studio"→"oidutS obosA"`
  (לטינית רב-מילתית מתהפכת כיחידה). **עברית קלה יותר מערבית — בלי shaping:** לאחסן עברית בסיסית U+05D0–05EA לוגית + להפוך רק איי-LTR.
  (זו מחלקה **הפוכה** ל-VISUAL של WD2/Anno/AC2, ושונה מ-LOGICAL המלא של CP2077/cohtml — שם המנוע כן מטפל באיי-LTR.)
* **פונט = השער היחיד.** פונטי Zouna = **atlas ביטמאפ** (מחלקה `Fonts_Z` ב-`FONT/ENGLISH.DPC`, סלוט = `BIG_ARABIC`;
  `CharacterID`=בתי UTF-8 של הגליף הפוכים+null-padded, UV rect+descent, גליפים ב-`Bitmap_Z`). אין TTF מוטמע, כמעט בוודאי אין עברית
  → menu-proof מכריע (מרונדר ⇒ אפס עבודה; tofu ⇒ הזרקת 27 גליפים ל-atlas, מחלקת SM2/WD2/GoWR/Anno). DPC = Asobo BigFile
  (hashes 64-bit + **LZ4**, `compressedSize==0`=raw). כלים: **amrshaheen61/APT_DPC_Tool** (extract עובד, import באגי),
  **widberg/bff** (Requiem PARTIAL), **widberg/fmtk** wiki + **widberg/ImZouna** hexpat. ה-repacker אולי צריך תיקון/RE.
* **מצב:** קרקע שלב-1 הושלמה 2026-07-03, GO easy-tier. scope 17,476 כתוביות + 1,433 UI + 1,752 credits. menu-proof בנוי (`work/build_proof.py`),
  ממתין להפעלת המשתמש. activation = Options → Text language = العربية (VO אנגלי נשמר). מסמכים: `games/plague_tale_requiem/{RECON,FEASIBILITY,PIPELINE}.md`.

### Hogwarts Legacy — Avalanche Software, Unreal Engine 4 ("Phoenix")

* היברידי pak+IoStore; הטקסט **כולו בתוך ה-pak הישן** (`pakchunk0-WindowsNoEditor.pak`, גרסה 11
  "Fnv64BugFix", **בלי הצפנה**, Zlib+Oodle). **`.locres` הוא dead-end** (כמעט ריק, boilerplate) —
  הטקסט האמיתי ב-`Phoenix/Content/Localization/WIN64/{MAIN,SUB}-<locale>.bin` (פורמט קנייני
  "AVAFDICT 2.0", **פוצח מ-`insomnious/parseltongue`** ופוענח מחדש בפייתון טהור: `work/hl_bin.py`).
  MAIN=UI (18,889), SUB=כתוביות/דיאלוג (34,955 ∩ EN, +4,729 AR-only מחוץ לסקופ).
* **סלוט ערבית רשמי אמיתי** (`arAE`) — 100% מהמפתחות תואמים EN↔AR.
* **קונטיינר עם כלי קוד-פתוח בוגר וקיים** — `repak` (Rust, MIT/Apache, `trumank/repak`) קורא
  **וכותב** גרסה 11 בלי מפתח AES; אומת: pack→get round-trip **bit-identical**. שונה מכל שאר
  המשחקים כאן (איפה שתמיד היה צריך reader/writer עצמאי) — **אין צורך לפצח קונטיינר בעצמנו**.
* **Unreal Engine עושה bidi (ICU) באופן טבעי — ✅ אומת in-game 2026-07-04: אוחסן LOGICAL ורונדר
  בסדר RTL נכון** → **מאחסנים LOGICAL, אפס קוד bidi משלנו** (ראשון בפרויקט — כל מנוע אחר כאן דרש
  היפוך ויזואלי או עוגני `&rlm;`). **הפונט — אפס עבודה** (אומת באותו proof: העברית רונדרה נקייה בלי
  tofu → פונט הסלוט הערבי כבר מכסה עברית; אין צורך ב-Composite Font injection). **deploy = pakchunk
  תוסף לא-הרסני ב-`~mods\`** (מוסכמת UE4 סטנדרטית, מאומתת ע"י כל מוד ב-Nexus) — לעולם לא נוגעים
  ב-pakchunk0. **DRM = Denuvo על ה-exe בלבד** (לא paks), **אין EAC/BattlEye**, סינגל-פלייר בלבד.
* **✅ menu-proof עבר — אישור in-game של המשתמש 2026-07-04.** `work/build_menu_proof.py --deploy`
  שינה 4 מפתחות ב-`MAIN-arAE.bin` (marker לטיני `ZZ-HL-PIPELINE-OK-ZZ` + בהירות/כתוביות/בחר שפה),
  ארז `repak pack --version V11`, פרס ל-`~mods\pakchunk111-WindowsNoEditor_P.pak`. עם המשחק בערבית
  (العربية), התפריט הראה `כתוביות` בעברית נקייה ובסדר נכון → override נטען + bidi + פונט, כולם
  אומתו בבת אחת. **מצב: קרקע שלב-1 הושלמה, כל השערים סגורים, GO (easy-tier) — מוכן ל-Phase 2**
  (האצלת תרגום 53,844 שורות → build עם `hl_bin.encode` LOGICAL → pack V11 → `~mods` → פרסום).
  מסמכים: `games/hogwarts_legacy/{RECON,FEASIBILITY,PIPELINE}.md`.

### The Last of Us Part I — Naughty Dog engine, PSARC v1.4 + Oodle (2023 PC port)

* **קונטיינר = PSARC v1.4 (`PSAR`) דחיסת Oodle** (`oo2core_9_win64.dll` **מגיע עם המשחק** — אין
  שאילה). reader פייתון-טהור: `games/tlou1/tools/{oodle,psarc}.py`. header 32B (u32 BE) + TOC entry 30B
  (`16 md5(path) + u32 blockStart + u40 origSize + u40 offset`) + block-table u16 BE (0=בלוק raw מלא).
  **⚠️ המלכודת שעלתה הכי הרבה: רשומות ה-TOC ממוינות לפי `md5(path)` עולה — לא לפי סדר ה-manifest.** מיפוי
  positional (`manifest[i]→entry[i+1]`) מתייג כמעט כל קובץ שגוי (נתיב `text2/*` נפתר ל-`sfx1` אודיו אקראי →
  "XVAG audio" red-herring). למפות לפי `entry.name_hash == md5(path).digest()`. manifest (entry 0)
  מופרד ב-NUL. repackers חיצוניים קיימים: **ndarc** (Nexus), UnPSARC, TLOU_PSARC_Tool, NaughtyDogLocalizationTool.
* **טקסט = `core.psarc/text2/<lang>.{common,subtitles,subtitles-systemic}` + `sid-lookup`.** פורמט ND
  **loc v2**: `u32 count; count×{u64 SID, u64 offset}; UTF-8 NUL-terminated blob (blob_start=4+count*16)`.
  קודק `games/tlou1/tools/tlou_loc.py` (decode+encode, roundtrip). **SID זהה בין שפות** → מיפוי EN→HE לפי id.
  **אין פיצול מגדר** (מחרוזת אחת ל-SID → אין backfill של maleVariant). scope ≈ **33,800 ייחודי** (UI/common
  13,049 + subtitles 10,970 + barks systemic 9,814). tokens: `<font>…</font>`, `<br>`, `<break/>`, `<hang>`,
  `|gen:interact|`/`|l3|`/`|@01|`, `[A]`/`[TEXT]`, `\n` literal.
* **אין ערבית / אין RTL כלל** (26 שפות LTR) → **חטיפת סלוט LTR + VISUAL** (מחלקת AC2/Anno/GTA/Witcher-menu,
  לא free-bidi). המנוע לא עושה bidi/shaping (raw byte order) → לאחסן VISUAL דרך `games/tlou1/work/tlou_rtl.py`
  `to_visual` (עברית הפוכה, איי-Latin/מספר/glyph קדימה, סוגריים מראה, זוגות markup נשארים LOGICAL; 9/9 selftest).
* **אף פונט לא מכיל עברית** (cmap 0/26 בכל 16 הפונטים; DINPro=UI ראשי, CFF/OTF → glyf-inject no-op) →
  **REPLACE בפונט Latin+Hebrew** (`games/tlou1/work/tlou_font.py`, loose OTF/TTF, בלי atlas/byte-length).
  אסתטיקה: DIN → Heebo/Assistant/Rubik (להציג למשתמש). **deploy = loose override** (drop/extract+rename
  core.psarc) או ndarc. **אין Denuvo/EAC** (single-player). activation = Options → Language → Text+Subtitles
  = הסלוט שנחטף. loc יכול לגדול חופשי (offsets עצמיים, אין delta-0). **precedent: תרגומי ערבית full ל-Part I
  קיימים + מוד יפני (Nexus 138) מחליף `text2`+`seriffont` וטוען.** menu-proof בנוי (`work/build_menu_proof.py`).
  **מצב: קרקע שלב-1 הושלמה 2026-07-06, GO medium-tier, ממתין ל-menu-proof in-game.** מסמכים: `games/tlou1/{RECON,FEASIBILITY,PIPELINE}.md`.

### Ghost of Tsushima Director's Cut — Sucker Punch (Nixxes PC port), DSAR→PSARC + KCAP text

* **קונטיינר = DSAR→PSARC — זהה ל-TLOU Part II.** כל `cache_pc/psarc/*.psarc` הוא magic **`DSAR`** (חיצוני LZ4,
  entry flags low-byte `0x03`) → PSARC v1.4 פנימי (`zlib`, block `0x10000`, TOC לפי `md5(path)`). ה-reader/writer של
  `games/tlou2/tools/{dsar.py,psarc_write.py,dsar_write.py}` עובדים **ללא שינוי** (round-trip semantic-PASS על GoT).
  **דלתאות GoT:** inner PSARC **`flags=0x0e`** (TLOU2=0x0c), inner **STORED** (`compress=False`), DSAR filler `55*7`,
  יישור 16-בייט. repack **לא** byte-identical (LZ4 encoder + סדר data md5-מול-manifest) — תקין, כמו TLOU2. **גדילה
  חופשית, אין delta-0.** ⚠️ `dsar.py` קורס על sentinel `ct=254 PADDING*` (`gapack_misc_b`); ארכיוני היעד נקיים.
  (`music_*.psarc` = PSAR רגיל, אודיו.) DRM-free (RUNE `steam_api64.rne`), אין Denuvo/EAC, אין checksum על הארכיון.
* **טקסט = `gapack_misc_l.psarc` → `lang_<lang>_text.xpps`** (~34 שפות). מקור `lang_english_text.xpps` (16.5MB),
  **סלוט העברית = `lang_arabic_text.xpps` (17MB, ערבית רשמית קיימת)**. פורמט **`KCAP`** (="PACK" LE, חבילת Sucker
  Punch): header + STRING BLOB **UTF-8 מופרד ב-NUL** + טבלאות index 16-בייט `{u64 KEY, u64 OFFSET}` (file_pos=BASE+off,
  BASE@0x28) + trailer @0x2c. **שני סוגי KEY:** (א) hash-64bit גדול = **גלובלי, זהה בין שפות → מיפוי EN↔AR לפי key**
  (UI/תוכן ~13k); (ב) small-id דיאלוג `{u16,u16}` — **מתנגש גלובלית, join לפי block+position** (~28k). קודק
  `games/ghost_of_tsushima/tools/xpps.py` (identity byte-identical, override כירורגי append+repoint). **⚠️ ה-reader
  סופר-חסר (~15k מתוך ~36k) — מוצא רק טבלאות ascending רציפות; להרחיב ל-Phase 2 (לפרסר את trailer @0x2c לכל ה-index
  sections).** **סקופ ≈ 36,000 מחרוזות ייחודיות** (~17.5k קצר UI + ~17.4k בינוני + ~1.4k lore). Tokens: גליפי PUA
  `U+E000–F8FF`, `{VARS}`, `%d/%f`, `\n`.
* **bidi = נוטה LOGICAL** (הערבית לוגית + python-bidi מהפך אותה) — **חייב menu-proof** (לקח W3/GoWR: ערבית≠עברית).
* **🔴 פונט = השער הקשה.** גליפי התפריט/כתוביות = פורמט **`fOnk` וקטורי קנייני דחוס** (`SFontData`/`FontGlyphs`/
  `FontVerts`) בתוך `game.sprig.texmeshman` (`gapack_misc_g`) — **לא TTF, לא atlas DDS.** ערבית מכוסה, עברית לא;
  ה-`lang_<x>.msac.d.0.sps` (87KB) הם תמונות button-legend מקומיות, לא atlas גליפים. הזרקה דורשת פיצוח `fOnk`
  (פרויקט-משנה, קשה מ-SM2/WD2/GoWR). ה-menu-proof מכריע אם הפונט כבר מכסה עברית.
* **deploy = override .psarc** קטן (רק `/lang_arabic_text.xpps`, נתיב **עם / מוביל**) בשם שממיין **אחרי**
  `gapack_misc_l` → `cache_pc/psarc/` (סריקה אלפביתית, מאוחר גובר; **בלי rebuild של גייפאק 1.43GB**, הפיך=מחיקת קובץ).
  activation = Settings → Options → General → Text Language = العربية. תקדים: Austronesian Lang Pack (Nexus #807) +
  לוקאליזציית פרסית RTL מסחרית טוענים. **מצב: קרקע שלב-1 הושלמה 2026-07-07, GO-with-caveats (medium–hard) — ה-menu-proof
  (`work/build_menu_proof.py --deploy`, בנוי+אומת offline) סוגר bidi+font בהשקה אחת.** מסמכים: `games/ghost_of_tsushima/{RECON,FEASIBILITY,PIPELINE}.md`.

### Battlefield 6 — EA DICE, Frostbite engine (`.toc`+`.cas`)

* **המנוע הראשון בפרויקט מבית EA/Frostbite.** קונטיינר = `.toc` (אינדקס) + `cas_NN.cas`
  (בלובי Content-Addressable-Storage, עד ~1GB כל אחד). Magic `00 D1 CE 01` ("D1CE"≈"DICE").
  **⚠️ מלכודת-מחשבה שכמעט תקעה את הפרויקט:** hex dump ראשוני של `.toc` נראה **מוצפן**
  (entropy גבוה לחלוטין, בניגוד לכל משחק אחר כאן שדרש לכל היותר קודק דחיסה) — הפרשנות
  הראשונית "AES מוצפן כמו BFV/BF2042" הייתה **שגויה**. פירוק (decompile) של הכלי הקהילתי
  **FMT** (Frostbite Modding Tool, FMTDev — הוסיף פרופיל BF6 "EARLY WIP" ב-2026-06-07,
  `github.com/FMTDev/FMT.Releases`) חשף את ה-**Read()** של `FMT.Core.TOCFile` במלואו:
  **אין קריאת הצפנה בכלל.** ה"אנטרופיה הגבוהה" היא **חתימה קריפטוגרפית שקופה** (`ToCSig`,
  256 בתים — כנראה RSA-2048, לזיהוי-שיבוש, לא צופן) + שדה שמור (`ToCXor`, 292 בתים) — שני
  השדות **לא מפוענחים בקריאה**, רק "מדולגים". התוכן האמיתי מתחיל **plain** ב-offset קבוע
  **556**. אושר: `BF6Profile.json` **חסר** `RequiresKey`/`KeyFile`/`Deobfuscator` (לעומת
  BFV `RequiresKey:true`, BF2042 `RequiresKey:true`+`KeyFile:"FIFA21.key"` — חוזר על מפתח
  של FIFA21!). **פוצח + אומת ב-Python טהור** מול 6 קבצי `.toc` אמיתיים
  (`games/battlefield6/tools/bf6_toc.py`): `characters.toc`=314 bundles/5,322 chunks,
  `globals.toc`=126/2,645, `ui.toc`=248/7,349, `vehicles.toc`=82/1,561,
  `weapons.toc`=9,101/9,183 — כולם offsets קטנים/מונוטוניים/בתוך-הקובץ; `loc/en.toc`
  ריק (0/0) — decode תקין. `layout.toc` פורמט **שונה** (עץ key-value גנרי, כמו
  `chunkmanifest` — עוד לא נדרש).
* **מתודולוגיית הפיצוח — RE סטטי בלבד על כלי ציבורי, אפס נגיעה בתהליך המשחק החי.**
  FMT.exe (325MB) הוא **.NET single-file bundle** בלי metadata ברמה עליונה (ilspycmd
  נכשל ישירות) — נפתר ע"י סריקת כל הקובץ ל-**628 PE embedded תקפים** (`MZ`→`e_lfanew`→
  `PE\0\0`), התאמת מחרוזות שם-מחלקה (`TOCFile`/`IDeobfuscator`/`KeyManager`) ל-assembly
  המכיל הקרוב ביותר, וחיתוך אותו ל-`.dll` נפרד לפני decompile. **הרצת FMT.exe עצמו
  נחסמה ע"י ה-classifier** ("third-party binary the user never authorized") — כיבוד
  מלא של החסימה, בלי לעקוף. `ilspycmd` global 8.2.0.7535 קרס על assembly שממוקד
  **net10.0** (`System.Version` fieldCount bug) — תוקן ע"י גרסה מוצמדת **9.1.0.7988**
  (10.0.x/10.1.x חדשים יותר עם NuGet package שבור).
* **סלוט ערבית רשמי מאושר** (`chunkmanifest` בלתי-מוצפן, TLV קריא: "ArabicSA" +12 שפות
  נוספות — תואם רשימת השפות הרשמית של EA Battlefield Bulletin; EA Forums thread על
  נגישות-Arabic מרמז RTL כבר עובד in-game). **לא מותקן מקומית** ברפאק הזה (רק en/voen
  על הדיסק) — התקנת חבילת השפה הערבית היא צעד ראשון לשלב הבא.
* **שמות ה-bundle גם הם קריאים — פוצח באותו סשן.** שמות ה-bundle לא מאוחסנים כמחרוזות
  רגילות אלא ב-**עץ Huffman בינארי** קנייני (`FMT.Core.CompressedStringHandler` —
  `CompressedStringTable`=עץ שטוח + `CompressedStringNames`=bitstream ארוז,
  `BundleNameOffset`=אינדקס-ביט התחלתי). פוצח + הוטמע ב-Python טהור (`read_huffman_string`
  ב-`bf6_toc.py`) — **אימות: כל 248 שמות ה-bundle ב-`ui.toc` פוענחו נכון**, למשל
  `win32/common/ui/assets/fonts/fontconfiguration_languageformat_arabicsa` (idx 185,
  321B) ו-`win32/common/ui/legal/arabicsa/legaltexts_arabicsa_bundle` ב-`globals.toc` —
  שני אישורים בלתי-תלויים ש-**ArabicSA הוא לוקאל אמיתי עם תוכן**, לצד אנגלית/גרמנית/
  צרפתית/יפנית/קוריאנית/ספרדית/פולנית/רוסית/סינית/פורטוגזית. **רמז לטקסט האמיתי:** סריקת
  `installation/commonbase/en/cas_01.cas` (בלוב ה-loc האנגלי) חשפה שורת debug בהירה
  יחידה — `"Entry = 0x300d Char = '_' Frequency = ..."` — עקבה קלאסית של בונה-טבלת-Huffman,
  מרמזת שגם **הטקסט המתורגם עצמו מקודד ב-Huffman** (טכניקה דומה לזו של שמות ה-bundle).
* **פתרון-קטלוג פוצח (סבב המשך שני, אותו סשן).** דה-קומפילציה של `FrostySdk.FileSystem`/
  `FMT.ServicesManagers.FileSystemService` (נמצא ב-`FMT.ServicesManagers.dll` — בדיוק
  ה-assembly שנחזה) + `FMT.FileTools.Readers.DbReader` — הפורמט הגנרי **DbObject** של
  Frostbite (key-value רקורסיבי, byte-tag + 7-bit varint length). הוטמעו ב-Python:
  `bf6_dbobject.py` (קורא DbObject מלא) + `bf6_catalog.py` (רזולוציית אינדקס-קטלוג).
  ביחד פוצחים את **`Data/layout.toc`** במלואו: 135 install chunks אמיתיים, 82 שמות
  superbundle, 9 חבילות התקנה עם גדלים אמיתיים (אחת 18.5GB — סביר לגמרי ל-BF6). **אישור
  שלישי ובלתי-תלוי לסלוט ערבית אמיתי**: install chunk שלם `installation/commonbase/ar`
  עם `language=ArabicSA`, `alwaysInstalled=True`. אינדקס-הקטלוג (`CASBundle.Catalog`
  byte → תיקיית `installation/<package>/` אמיתית) הוא פשוט מיקום סידורי (0-based) ב-
  `installChunks` (מדלגים על `testDLC`) — אומת: אינדקס 26=ערבית, 30=אנגלית, תואם בדיוק
  לתיקיות האמיתיות בדיסק.
* **🔑 מבנה ה-byte של ה-CASBundle נפרץ (סבב המשך שלישי, אותו סשן) — שרשרת הקריאה המלאה
  הוכחה מקצה לקצה.** ה-`FMT.Core.TOCFile.ReadCasBundles` הגנרי (סבב 2) התברר כמחלקה
  **לא נכונה לגמרי** — `BF6Plugin.BF6TOCFile` (override ספציפי ל-BF6, נשמר ב-`notes/`
  כבר בסבב הראשון של הפרויקט הזה אבל לא נבדק עבור המתודה הזו עד עכשיו) משתמש בלוגיקה
  שונה לגמרי: **9 שדות int32 בכותרת** (לא 8 — בדיוק מסביר למה `HeaderSize` תמיד קרא 36),
  **דגל-סנטינל `128`** (לא `1`), ו-prefix של **8 בתים** `{isInPatch:int16, catalogPersistentIndex:int32,
  cas:int16}` (לא 4 בתים) — ערך הקטלוג בדיסק הוא ה-`persistentIndex` הגדול של ה-chunk
  מ-`layout.toc`, לא האינדקס הסידורי הקטן ישירות. הוטמע ב-`bf6_toc.py:read_cas_bundle()` +
  `bf6_catalog.py:build_persistent_index_map()`. **אומת סופית**: כל entry בכל bundle
  שנבדק יוצר שרשרת byte רציפה נקייה, מתפענח לקובץ אמיתי, וה-bytes עצמם הם משאב
  `RIFF`+`EBX`/`EBXD` אמיתי עם **נתיב אסט קריא בטקסט רגיל**:
  `Common/UI/Assets/Fonts/FontBFText/BFText-Regular-AR` — הפניית הפונט הערבי האמיתית
  בתוך `fontconfiguration_languageformat_arabicsa`, לצד TC/KR/JP/SC/בסיס. **זה התוכן
  הראשון, אמיתי ובעל משמעות אנושית, שחולץ מ-bundle של BF6 בפרויקט הזה** — שרשרת
  container→שמות-bundle→קטלוג→byte-range→תוכן-מפוענח-אמיתי מוכחת עכשיו מקצה לקצה.
* **גם ה-chunks וגם הפורמט הפנימי האמיתי של SuperBundle נפרצו (סבב המשך רביעי) — אבל חיפוש
  ממצה מוכיח שהטקסט לא נמצא שם בכלל.** פוצח `ReadChunkData` (מנגנון שני, מבוסס GUID — אומת
  על 7,349 chunks אמיתיים ב-`ui.toc`, התבררו כווידאו/אודיו לא טקסט) ו-`SBHeaderInformation`/
  `BundleReader` — מבנה ה-"SuperBundle" הקלאסי של Frostbite (רשימות ebx/res/chunk עם שם+גודל+
  `resType`), כולל תגלית של **אנדיאניות מעורבת** (המכל החיצוני BE, המבנה הפנימי הזה LE —
  אומת ע"י התאמת חשבון בתים מדויקת, לא ניחוש). נמצא `ResourceType.LocalizedStringResource =
  1585851909u` (enum אמיתי) וסריקה ממצה של **כל 9,871 ה-bundles בכל 5 קבצי ה-.toc** של
  gameplay החזירה **0 hits, 0 כשלי-פענוח** — הוכחה נקייה שהטקסט המתורגם **לא** עובר דרך
  מערכת ה-asset/bundle/chunk הגנרית בכלל; הוא נטען ע"י תת-מערכת לוקליזציה ייעודית שקוראת את
  `en/cas_01.cas` ישירות, בפורמט **ללא שום קוד-ייחוס ב-FMT וללא תקדים קהילתי שנמצא**.
* **מצב: קרקע שלב-1 מתקדמת מאוד — עדיין 🟡 GO-WITH-CAVEATS, אך "קיר" אמיתי אותר.** כל שרשרת
  ה-READ הגנרית של Frostbite (container, שמות bundle, layout.toc/DbObject, פתרון-קטלוג,
  byte-range לכל bundle, chunks, ומבנה SuperBundle פנימי) פוצחה ומוכחת מקצה לקצה עם תוכן
  אמיתי מפוענח (הפניית פונט ערבי אמיתית). אבל **הטקסט המתורגם עצמו יושב מחוץ למערכת הזו
  לגמרי**, בפורמט לא-מתועד — פיצוחו דורש ניתוח בתים עיוור מאפס, ללא רשת ביטחון, שונה מהותית
  מכל מה שנפתר עד כה (שם תמיד היה איזשהו קוד-ייחוס לעקוב אחריו, גם אם בהתחלה המחלקה הלא
  נכונה). כתיבה/repack/פריסה/אימות-במשחק **לא נוסו כלל** (הכול קריאה-בלבד עד כה); BF6 גם מריץ
  EA AntiCheat, מה שמצדיק זהירות נוספת סביב כל אינטראקציה עם תהליך חי, מעבר למשחקי
  single-player הטהורים בפרויקט הזה. הגעה לעברית נראית-לעין דורשת ריאליסטית עוד כמה סשנים
  ייעודיים: פיצוח הפורמט (RE עיוור), בניית נתיב כתיבה, אישור ש-`ToCSig` לא חוסם repack, פתרון
  כיסוי עברית לפונט הערבי (תת-פרויקט גופן ייעודי משלו), ואז צילום מסך אמיתי (השקה ע"י המשתמש
  או צינור לכידה ייעודי — אף אחד מהם לא קיים עדיין ל-BF6). מסמכים:
  `games/battlefield6/{RECON,FEASIBILITY,PIPELINE}.md`. כלים:
  `games/battlefield6/tools/{bf6_toc,bf6_dbobject,bf6_catalog,bf6_resolve,bf6_chunk,bf6_bundle,
  bf6_find_loc,bf6_oodle,bf6_bundle_grep}.py`.

### Until Dawn (2024 remake) — Ballistic Moon, Unreal Engine 5 (codename "Bates")

* **הקונטיינר הכי קל בפרויקט — אין כלל צורך ב-RE.** Pak V11 סטנדרטי, **בלי הצפנה**,
  זהה בדיוק לפורמט של Hogwarts Legacy → `repak.exe` (הכלי הקיים, ללא שינוי) קורא/כותב
  אותו במלואו. **הטקסט = LocRes תקני (`FTextLocalizationResource`), פורמט מתועד ופומבי**
  (לא קנייני!) — `tools/ud_locres.py` הוא port ישיר של ה-reference implementation הפומבי
  `akintos/UnrealLocres` (הובא ב-WebFetch/curl, לא ניחוש) — קריאה+כתיבה ב-Python טהור,
  version 3 (Optimized_CityHash64_UTF16). מאחר ומשנים רק VALUES של keys קיימים (לא
  מוסיפים/משנים שמות), ה-writer **לא צריך** מימוש CityHash64/CRC32 — משתמש מחדש בבתי
  ה-hash שנקראו. round-trip: אותו (key,value) sequence, אותו גודל בייט-בייט, לא
  byte-identical (סדר string-table שונה — לא משנה, ה-reader מתעלם מ-refCount ב-load).
* **אין סלוט ערבית כלל** (20 לוקאלים LTR: da/de/en/es/fi/fr/it/ja/ko/nl/no/pl/pt/ru/sv/tr/
  zh — ללא ar) → מחלקת LTR-hijack (כמו AC2/Anno/GTA/TLOU). **`en` הוא ה-superset האמיתי**
  (כל לוקאל אחר = תת-קבוצה מדויקת של מפתחות ה-en, 0 extra) — קל למפות EN→HE לפי key.
  **טקסט שלם ב-namespace יחיד `ST_Localized`** (אין פיצול MAIN/SUB כמו Hogwarts) — מסווגים
  UI מול כתוביות **לפי prefix של שם המפתח** (`BATES_*`=UI, `SMG###_*`=דיאלוג עלילה,
  `Bonus_Material_*`/`bts_video_*`=making-of, `.HOWTO`=הערת-מפתחים לדלג). 12,689 רשומות
  (9,863 ייחודי) — סקופ קטן ונוח יחסית לפרויקטים אחרים כאן.
* **3 הגדרות שפה נפרדות** (`Speech Language`/`Subtitle Language`/`Text Language`) — VO
  אנגלי תמיד נשמר לא משנה מה בוחרים לטקסט/כתוביות (כמו כל שאר המשחקים).
* **✅ נסגר — `en/Game.locres` אכן נטען גם כשה-culture הפעיל הוא native.** זו הייתה השאלה
  הפתוחה היחידה (חלק ממנועי UE מדלגים על locres של תרבות-הבית ומסתמכים על הטקסט הקומפול-פנימה).
  **🔑 השיטה — menu-proof שבודק את שני התרחישים בבת אחת:** marker לטיני **שונה** ב-`en` וב-`tr`
  (`ZZ-UD-EN-OK-ZZ`/`ZZ-UD-TR-OK-ZZ`) + אותה עברית-לבדיקה בשני העותקים + פונט מוזרק, הכול
  ב-build אחד. צילום מסך אחד זיהה מי מהם נטען — במקום לנחש ולבזבז שתי הפעלות. **זה הרחבה של
  טריק ה-Latin-marker מ"האם הקובץ נטען?" ל"**איזה** מהמועמדים שלי נטען?" — להשתמש בו בכל פעם
  ששני מנגנונים סבירים.** התוצאה (en) = **ההפעלה הכי פשוטה בפרויקט: 0 פעולות מהמשתמש** (בלי
  לשנות שום הגדרה במשחק) — עדיף מכל LTR-hijack אחר עד היום.
* **פונט = `.ufont` הכי קל בפרויקט — בלי wrapper בכלל.** `repak get` מחזיר bare TTF/OTF
  בייט-בבייט (ה-sfnt magic ב-offset 0 ממש). **Univers** (6 משקלים, TrueType/`glyf`) →
  merge (טכניקת Anno). **Cotford** (3 משקלים, CFF) → glyf-merge no-op → replace עם donor +
  masquerade של ה-`name` (טכניקת TLOU1). שניהם אומתו אופליין 27/27 עברית + 26/26 לטינית
  שמורה. `FallbackFonts/` per-script קיים (cyr/jp/kr/ch) בלי ar/he — צפוי tofu לפני הזרקה.
* **✅ bidi = LOGICAL, אושר in-game** (Unreal/Slate ICU, אותה משפחת מנוע Hogwarts Legacy) —
  אפס קוד bidi משלנו. **✅ הפונט המוזרק רונדר נקי** (בלי tofu, באותו משקל ויזואלי כמו הלטינית
  שסביבו).
* **✅ מצב: שלב-1 הושלם 2026-07-08 — כל השערים סגורים, menu-proof עבר in-game** (התפריט הראשי
  הציג `BATES_MENU_QUIT` כ-**"יציאה"** עם Text Language על ברירת המחדל האנגלית). deploy =
  `~mods\pakchunk999-Windows_P.pak` (מוסכמת `_P` של Hogwarts Legacy, base pak לא נגוע;
  revert = מחיקת הקובץ). **המשחק נוסף לאתר+לתוכנה כ"בקרוב"** (שורת `games` id=`until-dawn`,
  DB-only בלי deploy) ו-**ה-pool הקהילתי `/translate` עלה: 12,617 שורות** ב-3 קטגוריות
  (ממשק 780 → כתוביות עלילה 11,570 → חומרי רקע 267; `string_key` = מפתח המשחק הגולמי, ייחודי
  → מיפוי 1:1 בשלב 2). מסמכים: `games/until_dawn/{RECON,FEASIBILITY,PIPELINE}.md`.
  **שלב 2 (התרגום) טרם התחיל — ממתין לאישור המשתמש.**

---

*נכתב 2026-06-21 מתוך מיצוי כל הצ'אטים, הסיכומים, וקבצי המשחקים. כשמסיימים קרקע למשחק חדש — לעדכן את הנספח בשורה שלו. (עודכן 2026-07-01: Witcher 3 / REDengine 3; AC Unity / AnvilNext v27. עודכן 2026-07-03: A Plague Tale Requiem / Asobo Zouna — מחלקת-bidi שלישית. עודכן 2026-07-04: Hogwarts Legacy / Unreal Engine 4 — המנוע הראשון בפרויקט עם bidi/ICU מובנה + כלי קוד-פתוח בוגר לקונטיינר. עודכן 2026-07-06: The Last of Us Part I / Naughty Dog PSARC+Oodle — מלכודת מיון-TOC לפי md5, אין סלוט ערבי → LTR+VISUAL. עודכן 2026-07-08: Battlefield 6 / EA Frostbite — המנוע הראשון מבית EA כאן; "הצפנה" חשודה התבררה כחתימה קריפטוגרפית שקופה אחרי decompile של כלי קהילתי; RE סטטי-בלבד על כלי ציבורי, אפס הרצה של בינארי חיצוני לא-מאושר. עודכן 2026-07-08: Until Dawn / Unreal Engine 5 (Bates) — הקונטיינר+קודק הקלים בפרויקט (Pak V11 לא-מוצפן + Unreal LocRes תקני ומתועד פומבית, אפס RE); אין סלוט ערבי; menu-proof בודק בבת-אחת אם en נטען או שצריך fallback ל-tr.)*

## מסמכים קשורים
- באותה תיקייה: [[universal/AGENT_TRANSLATION_HANDOFF_TEMPLATE|AGENT_TRANSLATION_HANDOFF_TEMPLATE]], [[universal/GENDER_ORACLE_ROLLOUT|GENDER_ORACLE_ROLLOUT]], [[universal/NEW_ERA_LANGUAGE_ROLES|NEW_ERA_LANGUAGE_ROLES]], [[universal/QA_REVIEW_HANDOFF|QA_REVIEW_HANDOFF]], [[universal/cross_audit_dashboard|cross_audit_dashboard]]
- פלייבוקים כלל-פרויקטיים: [[CLAUDE_INDEX#⚙️ סביבה / כלים / אורchestration|CLAUDE_INDEX]]
