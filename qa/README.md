# בדיקת תאימות של הלאנצ'ר על גרסאות/מחשבים שונים

מטרה: לוודא שה-Translation Manager מתקין, עולה ורץ **בלי קריסות** על Windows שונים
ועל מחשב "נקי" (בלי כלי הפיתוח שלנו). כל הכלים כאן חינמיים, רובם מובנים ב-Windows 11 Pro.

## ⚠️ הסתייגות אחת קריטית - QtWebEngine ב-VM

כל ה-UI הוא **QtWebEngine (Chromium)**. ב-VM בלי GPU אמיתי הוא נופל ל-**software
rendering**: התוכנה **עובדת ולא קורסת**, אבל איטית וה-FPS לא מייצג. ב"הגדרות → ביצועים"
"מצב עיבוד גרפי" יראה **"עיבוד תוכנה"** - זה **צפוי ב-VM ולא באג אצל משתמש אמיתי** (למשתמש
יש GPU). לכן VM בודק: *מתקין / עולה / לא קורס / הזרימות עובדות* - לא ביצועי גרפיקה.

---

## 1. Windows Sandbox - "מחשב נקי" בקליק (הכי מהיר)

חד-פעמי, מתאפס בכל הפעלה, אין שאריות. **אותה גרסת Windows כמו המארח** (Win11), אז לא בודק
גרסאות ישנות - אבל מושלם ל"האם זה מתקין ועולה על מחשב בלי שום כלי פיתוח".

הפעלה (פעם אחת, כמנהל):
```powershell
Enable-WindowsOptionalFeature -Online -FeatureName 'Containers-DisposableClientVM' -All
# אתחול, ואז:
```
אחרי אתחול - **דאבל-קליק על `TranslationManager-Test.wsb`** (בתיקייה הזאת). הוא:
- ממפה את `Output\` (קובצי ההתקנה) ל-`C:\Installer` בתוך ה-sandbox (קריאה בלבד),
- פותח את התיקייה ומניח `SMOKE-TEST.txt` על שולחן העבודה עם רשימת הבדיקות.

> אם הנתיב `C:\Users\Nehoray_Cohen\Projects\Game translator\` ישתנה - עדכן את שני
> ה-`HostFolder` ב-`TranslationManager-Test.wsb`.

## 2. Hyper-V - גרסאות Windows שונות (מובנה ב-Win11 Pro)

הדרך לבדוק **גרסאות שונות** (Win10 1809 = רף המינימום של המתקין, Win10 22H2, Win11 23H2/24H2).

הפעלה (כמנהל) + אתחול:
```powershell
Enable-WindowsOptionalFeature -Online -FeatureName 'Microsoft-Hyper-V-All' -All
```
- **ISO חינמי:** Microsoft Evaluation Center (Win10/11 Enterprise eval, 180 יום) או
  "Windows 11 dev environment" - VM מוכן להורדה (Hyper-V/VMware/VirtualBox, ~90 יום).
- ליצור VM: Hyper-V Manager → Quick Create → בחר את ה-ISO. תן ≥4GB RAM.
- **QtWebEngine:** ב-Hyper-V רגיל = software rendering. לנאמנות גבוהה אפשר **GPU-P**
  (חלוקת ה-GPU האמיתי ל-VM) - הגדרה מתקדמת ב-PowerShell (`Add-VMGpuPartitionAdapter`).

## 3. VirtualBox / VMware - מטריצה רחבה, פחות נאמן

חינם, כל גרסת Windows מ-ISO. 3D מוגבל → כמעט תמיד software rendering. טוב לבדיקת "לא קורס"
על הרבה גרסאות. (ענן: Azure/AWS Windows VM אם רוצים מנוהל, בתשלום.)

---

## מה בעצם לבדוק (רשימת עשן - לפי נקודות הכשל הידועות של התוכנה)

- [ ] **המתקין רץ** על מחשב נקי (בלי Python/Node) - הבאנדל מכיל את הכל (VC++ redist, certifi).
- [ ] **SmartScreen "מוציא לא ידוע"** → "מידע נוסף" → "הפעל בכל זאת" (המתקין לא חתום).
      *(קובץ ממופה ב-Sandbox לא מפעיל SmartScreen - כדי לבדוק אמיתי, הורד מה-GitHub בתוך ה-VM.)*
- [ ] **עולה בלי קריסה / מסך לבן** - סרגל צד + בית + כרטיסים נטענים.
- [ ] **QtWebEngine מרנדר** - הגדרות → ביצועים. ב-VM יראה "עיבוד תוכנה" = **תקין ל-VM**.
- [ ] **רף גרסה:** על מתחת ל-Win10 1809 המתקין **מסרב בהודעה נקייה** (לא שגיאת DLL). ✔ זה תקין.
      (אין טעם לבדוק Win7/8 - חסום בכוונה.)
- [ ] **הפעלה ראשונה ללא רשת** - fallback לקטלוג המובנה (לנתק את הרשת ולפתוח).
- [ ] **התחברות Google** - הדפדפן נפתח, "בטל וחזור" מגיב, "העתק קישור" מעתיק, 2FA עובד.
- [ ] **זרימות מוד** - פתיחת כרטיס משחק, החלפת שפה, מסך הורדות - בלי קריסה.
- [ ] **הסרה** דרך הגדרות → אפליקציות - לא נשארות שאריות.
- [ ] **session יחיד:** כל VM מקבל `device_id` משלו; התחברות ב-VM **מנתקת** את המארח (צפוי).

לוגים לאיסוף אם משהו נשבר: `%USERPROFILE%\.translation_manager\*.log`
(`launcher.log`, `auth_debug.log`).

## הערות
- ה-Sandbox/VM ירשמו שורות ב-`launcher_installs` (טלמטריית התקנה). אפשר לנקות שורות בדיקה.
- אין דרך אמינה לבדוק ביצועי GPU אמיתיים ב-VM - לזה צריך חומרה פיזית שנייה, או GPU-P ב-Hyper-V.
