# מעצב התוכנה — Launcher Designer ("עריכה חיה")

כלי עיצוב ויזואלי שמראה את **התוכנה האמיתית 1:1** ומאפשר לערוך כל אלמנט (צבע, גודל,
ריווח, פינות, מיקום, טקסט, הסתרה) בסגנון DevTools — והעיצוב הופך ל-UI האמיתי של התוכנה.

## איך זה עובד
- עמוד **`/preview`** מרנדר את ה-App האמיתי של התוכנה (`../frontend/src/App`) עם ה-CSS
  האמיתי, כך שזה נראה בדיוק כמו התוכנה. plugin של Vite (`designer-mock-eel`) מחליף את מודול
  ה-backend `lib/eel` ב-mock (`src/mock/eel.ts`) עם נתוני-דמה, כך שהאפליקציה עולה בלי
  ה-backend של Qt/Eel.
- העמוד הראשי הוא **inspector**: `<iframe src="/preview">` של התוכנה האמיתית + פאנל עריכה.
  במצב "בחירה" — ריחוף מסמן אלמנט, לחיצה בוחרת אותו, והפאנל מימין עורך אותו.
- כל עריכה נשמרת כ-**override** לפי selector יציב (`#root > … :nth-child`) ומוזרקת חי
  כ-`<style>` ל-iframe. **אותם overrides** נטענים ע"י התוכנה האמיתית
  (`../frontend/src/designer/applyOverrides.ts`) → העיצוב הופך לאפליקציה.

## הרצה
```bash
cd launcher-designer
npm install
npm run dev      # http://localhost:5180  (אם תפוס → 5181/5182…)
```
**חשוב:** להריץ רק `npm run dev` — בלי להדביק טקסט/חצים אחריו (הם הופכים ל-root ארגומנט של vite).

## תהליך העבודה
1. פותחים את ה-designer. ברירת המחדל = "בחירה: פעיל".
2. **לניווט בין מסכים** (דף הבית / ספרייה / הורדות / הגדרות / כרטיס משחק): מכבים "בחירה",
   לוחצים בסרגל הצד של התוכנה בתוך התצוגה, ואז מפעילים "בחירה" שוב.
3. לוחצים על אלמנט → עורכים מימין (רקע/צבע/גופן/ריווח/פינות/רוחב/גובה/שקיפות/מסגרת/יישור/
   הזזה חופשית/טקסט/הסתרה). השינוי מופיע מיד בתצוגה.
4. **שמירה** (localStorage) → **ייצוא** ל-`design-overrides.json`.
5. כדי שזה יחול על התוכנה האמיתית: מחליפים את התוכן של
   `frontend/src/designer/design-overrides.json` בקובץ שייצאתם, ובונים את התוכנה מחדש
   (`build_exe.bat`). ברירת המחדל היא `{}` ⇒ אפס שינוי עד שמכניסים עיצוב אמיתי.

## כפתורי הסרגל
- **בחירה** — מצב עריכה (פעיל) מול מצב ניווט (כבוי).
- **רענן תצוגה** — טוען מחדש את ה-iframe.
- **אפס הכול** — מוחק את כל העיצוב.
- **ייצוא / ייבוא** — קובץ `design-overrides.json`.
- **שמירה** — ל-localStorage.

## קבצים
| קובץ | תפקיד |
|---|---|
| `preview.html` + `src/preview/main.tsx` | מרנדר את ה-App האמיתי (mock eel + CSS אמיתי). |
| `src/mock/eel.ts` | mock מלא של `lib/eel` עם נתוני-דמה (משחקים/חדשות/משתמש/prefs). |
| `vite.config.ts` | alias `@fe`→frontend/src, plugin `designer-mock-eel`, multi-page. |
| `src/App.tsx` | ה-inspector (iframe + בחירה + פאנל עריכה). |
| `src/inspector/overrides.ts` | מודל ה-overrides: `cssPath`, `buildCss`, `applyOverrides`. |
| `frontend/src/designer/applyOverrides.ts` | התוכנה האמיתית מזריקה את אותם overrides ב-boot. |
| `frontend/src/designer/design-overrides.json` | העיצוב שיחול (ברירת מחדל `{}` = no-op). |

## מגבלות (גילוי נאות)
- זו **עריכה-מחדש של ה-UI הקיים** (override של אלמנטים), לא גרירת רכיבים חדשים מאפס.
- **טקסט + הסתרה** = best-effort (React עלול לדרוס; יש MutationObserver שמחזיר טקסט).
- selector מבוסס מבנה (`:nth-child`) — אם מבנה ה-DOM של רכיב משתנה בקוד, ייתכן ש-override
  ישן לא יתפוס עד שיבחרו מחדש. נתוני-הדמה ב-mock לעריכה בלבד; התוכנה האמיתית משתמשת בנתונים אמיתיים.

## אומת (Chrome headless)
התוכנה נטענת 1:1 בתצוגה (סרגל אמיתי, Hero, כרטיסי משחק עם כריכות אמיתיות), 0 שגיאות;
לחיצה על כפתור Hero בחרה אותו, ושינוי רקע צבע אותו ירוק חי + הזריק `<style id="design-overrides">`.
