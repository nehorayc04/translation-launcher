# 🎛 MISSION — לוח מצב תרגום המשחקים

_נוצר מ-`state.json` · עודכן: 2026-06-29T07:40:46_

**9 משחקים:** 🔨 בונה 1 · 🧱 קרקע 2 · 🛠 תחזוקה 1 · ✅ פורסם 5

> אל תערוך קובץ זה ידנית — נוצר ע"י `python orchestration/orchestrate.py board`.

## 🎮 משחקים

| משחק | שלב | התקדמות | סוכנים | גרסה | הצעד הבא |
|---|---|---:|---:|---|---|
| **godofwar_ragnarok**<br><sub>God of War Ragnarok</sub> | 🔨 בונה | 100% | — | — | אימות in-game של build delta>0 → פרסום (גייט) |
| **acshadows**<br><sub>Assassin's Creed Shadows</sub> | 🧱 קרקע | קריאה הושלמה | — | — | Part B: round-trip של repacker v42 (כלי חיצוני ATK) |
| **assassinscreed2**<br><sub>Assassin's Creed II (קלאסי 2009)</sub> | 🧱 קרקע | קריאה הושלמה | — | — | בחירת LTR slot + identity round-trip → font עברי |
| **cyberpunk2077**<br><sub>Cyberpunk 2077</sub> | 🛠 תחזוקה | 100% | — | 1.0.0-beta.3 | — |
| **anno1800**<br><sub>Anno 1800</sub> | ✅ פורסם | 100% | — | 1.0.0-beta.1 | wrangler deploy של slug anno1800-hebrew (אופציונלי) |
| **gtav**<br><sub>Grand Theft Auto V (Legacy)</sub> | ✅ פורסם | 100% | — | 1.0.0-beta.2 | לאנצ'ר שוגר עם תיקון ZLIB (in-place) + טקסט מתוקן (BUILD_ID 20260629034518, release id=52). ממתין: אימות in-game של התקנת ה-launcher; פרסום OIV לאתר (גייט) |
| **spiderman2**<br><sub>Marvel's Spider-Man 2</sub> | ✅ פורסם | 100% | — | 1.0.0-beta.6 | — |
| **steam**<br><sub>Steam UI</sub> | ✅ פורסם | 100% | — | 2026.05.20 | — |
| **watchdogs2**<br><sub>Watch Dogs 2</sub> | ✅ פורסם | 100% | — | 1.0.0-beta.3 | — |

## 🖥 לאנצ'ר

- שלב: 🧪 בטא · גרסה: 1.0.0-dev · הצעד הבא: User opens Settings->ביצועים, reports the GPU line (green=accelerated/red=software); if software -> Qt release-build/ANGLE fix.
- v1.0.0-dev.16 SHIPPED (BUILD_ID 20260629042940, row id=53, sha 1511afd7). FPS real-fix: removed ALL component backdrop-blur + GPU default-on flags + GPU diagnostic in Settings; mod-update clickable for SM2/WD2/GTAV; installed-version row. Website review-reply thread + guest-viewable /translate LIVE.

## 👉 הצעות לצעד הבא (ממתינות לאישורך)

- **godofwar_ragnarok**: אימות in-game של build delta>0 → פרסום (גייט)
- **acshadows**: Part B: round-trip של repacker v42 (כלי חיצוני ATK)
- **assassinscreed2**: בחירת LTR slot + identity round-trip → font עברי
- **anno1800**: wrangler deploy של slug anno1800-hebrew (אופציונלי)
- **gtav**: לאנצ'ר שוגר עם תיקון ZLIB (in-place) + טקסט מתוקן (BUILD_ID 20260629034518, release id=52). ממתין: אימות in-game של התקנת ה-launcher; פרסום OIV לאתר (גייט)
- **launcher**: User opens Settings->ביצועים, reports the GPU line (green=accelerated/red=software); if software -> Qt release-build/ANGLE fix.

---
_🔒 = דורש אישור מפורש לפני ביצוע (פרסום / שיגור לאנצ'ר / דריסת קבצי משחק)._
