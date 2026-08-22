# מחשוב קהילתי · Community Compute

תוכנה עצמאית (EXE לדסקטופ + APK לאנדרואיד, **באותו עיצוב כמו הלאנצ'ר**) שבה כל מתנדב מוסיף
**3 מפתחות API חינמיים** (Groq · SambaNova · NVIDIA NIM), לוחץ על **מתג גדול אחד**, והמכשיר שלו
הופך ל-worker אנונימי שמתרגם מנות-עבודה שאתה מזרים אליו — **בלי שתראה את המפתח או את כתובת ה-IP**.

## 📦 מוכן להתקנה — `community_compute/dist/`

| קובץ | פלטפורמה | גודל | התקנה |
|---|---|---|---|
| `CommunityCompute-Setup-1.0.0.exe` | Windows | 53 MB | הרצה → מתקין לכל-משתמש (ללא UAC) + קיצור-דרך |
| `CommunityCompute-1.0.0.apk` | Android | 48 MB | העברה למכשיר → התקנה (אפשר "מקורות לא ידועים") |

> ה-APK חתום בזמנית במפתח-debug (ניתן להתקנה מיד). להפצה בחנות — הוסף keystore אמיתי ב-`android/android/app`
> ובנֵה שוב עם `flutter build apk --release`.

> ⚖️ **הבהרה (מתועד ב-CLAUDE.md):** הארכיטקטורה עצמה לגיטימית (BYOK + הסכמה + pull-model). האזור
> הרגיש היחיד הוא **תנאי-השימוש של הספקים** לגבי איגום מפתחות חינמיים לסקייל-ייצור. אתה מודע לזה.
> ההגנות בקוד תוכננו כך שהמתנדב מוגן במלואו; החלטת הפצה נשארת שלך.

---

## איך זה בטוח (למפעיל ולמתנדבים)

| רכיב | ההגנה |
|---|---|
| **מפתחות** | מוצפנים במכשיר (Windows: keyring+Fernet · Android: Keystore). **לעולם לא נשלחים** — נשארים על מכונת המתנדב ומשמשים רק לקריאות לספקים. |
| **כתובת IP** | **מודל משיכה** — ה-worker מתחבר החוצה; השרת אף פעם לא מתחבר אליו. אין שום מקום שבו IP נשמר (`cc_workers` מחזיק UUID אקראי בלבד). |
| **spam / הרעלה** | תור מבוסס-lease (אין עבודה כפולה, אין אובדן); כל תרגום שחוזר הוא **לא-אמין** ועובר את ה-QA-gate + אישור-מנהל לפני שהוא נכנס לתרגום עצמי. שער-`app_secret` רך + RLS מונעים ספאם. |
| **קוד שרירותי** | אין. ה-worker מבצע **אך ורק קריאות-תרגום** לספקים שהמתנדב בחר. |
| **VPN** | **לא מובנה בכוונה** — זה היה מרכז את התעבורה ל-IPs ספורים ומזיק לפיזור ולתאימות. במקום זה: מכובד VPN/פרוקסי-מערכת, + שדה פרוקסי אופציונלי שהמתנדב ממלא בעצמו. |

**מתג גדול + אגירה במצב-נתק:** כשהמתג פעיל אבל אין קשר לשרת — ה-worker **ממשיך לתרגם ממאגר מקומי
ואוגר את התוצאות**, ושולח אוטומטית ברגע שהחיבור חוזר. כלום לא הולך לאיבוד, גם אחרי הפעלה-מחדש.

---

## ארכיטקטורה

```
   ┌─ אתה (מפעיל) ─┐        ┌──── Supabase (control plane) ────┐        ┌─ מתנדבים ─┐
   │ seed_jobs.py  │──────▶ │  cc_jobs (תור)  ·  RPCs מאובטחים │ ◀──────│  EXE      │
   │ collect_*.py  │◀────── │  cc_workers (אנונימי, ללא IP)     │ ──────▶│  APK      │
   └───────────────┘        └──────────────────────────────────┘   pull  └───────────┘
                             (service key = אצלך בלבד)          (anon key + app_secret)
```

- `control_plane/schema.sql` — הטבלאות + ה-RPCs (`cc_enroll` · `cc_claim` · `cc_submit` · `cc_stats`).
  ה-RPCs הם `SECURITY DEFINER` ומבצעים claim אטומי; הטבלאות עצמן חסומות ל-anon (RLS).
- `control_plane/seed_jobs.py` / `collect_results.py` — הזרמת עבודה ואיסוף תוצאות (service key בלבד).
- `desktop/` — ה-worker לדסקטופ (PySide6, מייבא את עיצוב-הלאנצ'ר `ui.py`).
- `android/` — ה-worker לאנדרואיד (Flutter, אותה שפת-עיצוב).

---

## הפעלה (מפעיל — פעם אחת). *לא מבוצע אוטומטית — אלה פקודות שאתה מריץ.*

1. **הרצת הסכמה** ב-Supabase (SQL editor או ה-Management API), ואז קביעת הסוד המשותף:
   ```sql
   -- הרץ את כל control_plane/schema.sql, ואז:
   insert into public.cc_config (id, app_secret)
   values ('main', 'cc_06950e1d42d186525b087a400bc522460ae3034fae0c75d4')
   on conflict (id) do update set app_secret = excluded.app_secret;
   ```
   (הסוד כבר מוטמע ב-`desktop/config.py` ו-`android/lib/config.dart`. להחלפה — עדכן את שלושתם.)

2. **הזרמת עבודה** (קורפוס `{id: english}`):
   ```
   python control_plane/seed_jobs.py corpus.json --game rdr2 --target subs --batch 40
   ```

3. **איסוף תוצאות** (מוזן ל-QA-gate הרגיל של הפרויקט לפני bake):
   ```
   python control_plane/collect_results.py --out cc_results.json --game rdr2 --mark
   ```

4. **כיבוי/הפעלה של כל הצי** (מתג-חירום): `update public.cc_config set paused = true;`

---

## דסקטופ (EXE) — **נבנה**

- קוד: `desktop/*.py` · עיצוב: `desktop/ui.py` (עיצוב-הלאנצ'ר) · פונטים: `desktop/fonts/`.
- בנייה: `desktop/build.bat` (או `python -m PyInstaller CommunityCompute.spec` עם ה-`.venv`).
- פלט: **`desktop/dist/CommunityCompute.exe`** (~51 MB, ללא קונסולה).
- מסכים: **הפעלה** (המתג הגדול + סטטוס חי) · **מפתחות** (3 שדות + הסכמה + פרוקסי) · **מידע**.
- רץ ברקע (מגש-מערכת) + הפעלה-אוטומטית-עם-הדלקה (HKCU Run, הפיך).

---

## אנדרואיד (APK) — קוד מלא, בנייה אצלך

Flutter לא מותקן בסביבת-הבנייה הזו, אז קוד ה-`lib/` המלא מוכן ואתה בונה את ה-APK:

```bash
cd community_compute/android
flutter create . --platforms=android --project-name community_compute   # מייצר את מארח-האנדרואיד
# הוסף את ההרשאות/השירות ל-android/app/src/main/AndroidManifest.xml (ראה למטה)
flutter pub get
flutter build apk --release            # → build/app/outputs/flutter-apk/app-release.apk
```

**הוספות ל-`AndroidManifest.xml`** (בתוך `<manifest>`, מעל `<application>`):
```xml
<uses-permission android:name="android.permission.INTERNET"/>
<uses-permission android:name="android.permission.WAKE_LOCK"/>
<uses-permission android:name="android.permission.POST_NOTIFICATIONS"/>
<uses-permission android:name="android.permission.FOREGROUND_SERVICE"/>
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC"/>
```
ובתוך `<application>` הוסף את `android:foregroundServiceType` לשירות של `flutter_foreground_task`
(ראה את ה-README של התוסף — הוא ממזג את הצהרת-השירות; רק צריך `dataSync` כסוג).

- מסכים זהים לדסקטופ: **הפעלה / מפתחות / מידע** בניווט-תחתון זכוכיתי.
- ריצת-רקע דרך foreground-service (`lib/fg_service.dart`, מבודד — אם גרסת התוסף דורשת התאמה,
  זה הקובץ היחיד שיושפע; האפליקציה עובדת מלא גם בלעדיו כשהיא פתוחה).

---

## מיפוי קבצים (דסקטופ ↔ אנדרואיד — אותו חוזה)

| תפקיד | דסקטופ | אנדרואיד |
|---|---|---|
| קבועים מוטמעים | `config.py` | `lib/config.dart` |
| אחסון-מפתחות מוצפן | `keystore.py` | `lib/keystore.dart` |
| מאגר-נתק (inbox/outbox) | `state.py` | `lib/state.dart` |
| מתאם 3-ספקים | `providers.py` | `lib/providers.dart` |
| לקוח control-plane | `client.py` | `lib/client.dart` |
| מנוע pull-loop | `engine.py` | `lib/engine.dart` |
| מתג גדול | `bigtoggle.py` | `lib/widgets/big_toggle.dart` |
| UI | `app.py` + `ui.py` | `lib/main.dart` + `lib/screens/*` + `lib/theme.dart` |
