# RDR2 עברית — מדריך התקנה (הוכחת תפריט)

מטרה: להתקין את ה-menu-proof ולראות עברית in-game, כדי לסגור את שלב 1. **Story mode בלבד.**

תיקיית המשחק (ה"root", שם נמצא `RDR2.exe`):
`C:\Program Files (x86)\Steam\steamapps\common\Red Dead Redemption 2`

---

## אפשרות A — Drop-in מוכן (הכי קל, מומלץ)

הקובץ `RDR2_Hebrew_menu_proof_READY.zip` כבר מכיל **הכל**: את מנוע הטעינה (Lenny's Mod Loader
`vfs.asi` + `ScriptHookRDR2.dll` + `dinput8.dll` ASI loader), ואת התוכן העברי שלנו (פונט + טקסט).

1. **סגור את RDR2 לגמרי** (וגם את Rockstar Launcher).
2. פתח את תיקיית המשחק (הנתיב למעלה). כי היא תחת `Program Files`, ייתכן שתצטרך **הרשאות
   מנהל** כדי להעתיק אליה (Windows יבקש אישור — אשר).
3. חלץ את כל התוכן של `RDR2_Hebrew_menu_proof_READY.zip` **ישירות לתיקיית המשחק** (מיזוג).
   בסוף אמורים להיות שם, ליד `RDR2.exe`:
   ```
   dinput8.dll   ScriptHookRDR2.dll   vfs.asi   ModManager.Core.dll
   ModManager.NativeInterop.dll   NLog.dll   lml.ini   lml\
   ```
4. **הפעל את המשחק דרך `PlayRDR2.exe`** (או Steam) כרגיל.
5. במסך העלייה (ה-legal splash של Rockstar) אמור להופיע הטקסט העברי שלנו + הסימן
   **`ZZ-RDR2-OK-ZZ`**; ואז ב-Pause menu / Player menu תראה: אפשרויות · סיפור · משחק חדש ·
   טעינת משחק · שמע · השהיה · יציאה וכו'.
6. **צלם מסך ושלח לי.** מה שאני צריך לדעת:
   - האם רואים את `ZZ-RDR2-OK-ZZ`? (מוכיח שה-override נטען + הפונט עובד)
   - האם העברית נקראת נכון **מימין לשמאל** (ולא הפוך/מראה)? (מאמת שהמצב VISUAL נכון)
   - האם יש ריבועים ריקים (tofu) במקום אותיות? (מעיד על פונט חסר — לא צפוי)

**הסרה:** מחק מתיקיית המשחק את `dinput8.dll` (מנטרל הכל) — או את כל הקבצים מסעיף 3.

---

## אפשרות B — התקנה ידנית ממקורות רשמיים (אם מעדיף)

אם אתה מעדיף להוריד את כלי הטעינה בעצמך במקום להשתמש בבינאריים שצורפו:

1. **ScriptHookRDR2** — הורד מ-`dev-c.com` (Alexander Blade). חלץ ל-root של המשחק:
   `ScriptHookRDR2.dll` + `dinput8.dll` (זה ה-ASI loader).
2. **Lenny's Mod Loader (LML)** — הורד מ-`lennysmod.com` (או מהמוד של Ko Games ב-Nexus
   `reddeadredemption2/mods/2033`). התקן/חלץ ל-root: `vfs.asi`, `lml.ini`, `ModManager.*.dll`,
   `NLog.dll`, ותיקיית `lml\` עם `mods.xml` + `patterns.dat`.
3. חלץ מ-`RDR2_Hebrew_menu_proof_lml.zip` **רק את תיקיית `lml`** (הפונט + הטקסט העברי) ומזג
   אותה ל-`lml\` של המשחק (או השתמש במבנה שלנו `rdr2he_font`/`rdr2he_text`).
4. הפעל → בדוק כמו בסעיף 5-6 למעלה.

---

## הערות ופתרון תקלות

- **Story mode בלבד.** אל תיכנס ל-RDR Online עם המודים — מודים ברשת = סיכון ban (ScriptHookRDR2
  ממילא מנטרל את עצמו online, אבל עדיף לצאת מכל הקבצים לפני משחק online). ל-story mode אין
  anti-cheat.
- **המשחק לא נפתח / קורס בעלייה** → מחק את `dinput8.dll` (מנטרל את כל שרשרת המודים) ובדוק שהמשחק
  עולה נקי. אם כן — כנראה גרסת ScriptHookRDR2 לא תואמת לעדכון משחק אחרון (ראה למטה).
- **עדכון משחק שבר את זה** → אחרי כל עדכון של RDR2, **ScriptHookRDR2 עלול להפסיק לעבוד** עד
  שאלכסנדר בלייד מוציא גרסה תואמת. זו מגבלה ידועה של כל המודים ב-RDR2. פשוט להמתין לעדכון של
  ScriptHookRDR2 ולהחליף את ה-`.dll`.
- **Steam "Verify integrity of game files"** לא ימחק את קבצי המוד (הם קבצים loose, לא בתוך
  ה-RPF) — אבל אל תריץ אימות אם אתה רוצה שהמוד יישאר.
- **אין צורך לשנות שפה בתוך המשחק.** ה-override מחליף את מחרוזות השפה הפעילה — השאר את המשחק
  באנגלית. (הדיבוב האנגלי נשאר, כי שפת הטקסט והקול נפרדות.)
- אם רוצים שה-loader ירשום לוג של כל מפתחות ה-GXT שהמשחק מבקש (עוזר לזהות מפתחות תפריט) —
  ב-`lml.ini` שנה `LogAllGxt=false` ל-`true`.

---

## מה זה מוכיח

אם העברית מופיעה נקייה ו-RTL — **כל שרשרת הבנייה מאומתת end-to-end** (LML override + הפונט
המוזרק + מצב VISUAL), וסוגרים את שלב 1. אחר כך עוברים לשלב 2: תרגום ~218K השורות (הקורפוס
האנגלי כבר בידינו, `extract/en_corpus.json`) → בנייה → פרסום.

## מסמכים קשורים
- באותה תיקייה: [[games/rdr2/FEASIBILITY|FEASIBILITY]], [[games/rdr2/PIPELINE|PIPELINE]], [[games/rdr2/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#rdr2|CLAUDE_INDEX_games]]
