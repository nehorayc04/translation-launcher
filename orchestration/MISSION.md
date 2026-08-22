# 🎛 MISSION — לוח מצב תרגום המשחקים

_נוצר מ-`state.json` · עודכן: 2026-07-21T10:33:39_

**9 משחקים:** 🔨 בונה 1 · 🧱 קרקע 2 · 🛠 תחזוקה 1 · ✅ פורסם 5

> אל תערוך קובץ זה ידנית — נוצר ע"י `python orchestration/orchestrate.py board`.

## 🎮 משחקים

| משחק | שלב | התקדמות | סוכנים | גרסה | הצעד הבא |
|---|---|---:|---:|---|---|
| **godofwar_ragnarok**<br><sub>God of War Ragnarok</sub> | 🔨 בונה | 100% | — | — | אימות in-game של build delta>0 → פרסום (גייט) |
| **acshadows**<br><sub>Assassin's Creed Shadows</sub> | 🧱 קרקע | קריאה הושלמה | — | — | Part B: round-trip של repacker v42 (כלי חיצוני ATK) |
| **assassinscreed2**<br><sub>Assassin's Creed II (קלאסי 2009)</sub> | 🧱 קרקע | קריאה הושלמה | — | — | בחירת LTR slot + identity round-trip → font עברי |
| **cyberpunk2077**<br><sub>Cyberpunk 2077</sub> | 🛠 תחזוקה | 100% | 4 | 1.0.0-beta.3 | דרגה-2 דו-מגדרי: ~1,770 נבנקו (checkpoint 15,020). תוקן באג נתיב-checkpoint ב-prep (סבבים לא התקדמו). סבב-2 מוכן (1,600 חדשות), נותרו 8,574. guards: copy-EN+batch-size. bake(🔒) כשנצבר |
| **anno1800**<br><sub>Anno 1800</sub> | ✅ פורסם | 100% | — | 1.0.0-beta.1 | wrangler deploy של slug anno1800-hebrew (אופציונלי) |
| **gtav**<br><sub>Grand Theft Auto V (Legacy)</sub> | ✅ פורסם | 100% | — | 1.0.0-beta.2 | מאגר /translate עלה (141,212 שורות, 3 קטגוריות עברית). פתוח: אימות in-game של התקנת הלאנצ'ר; שער #2 = פרסום OIV מעודכן לאתר |
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
- **cyberpunk2077**: דרגה-2 דו-מגדרי: ~1,770 נבנקו (checkpoint 15,020). תוקן באג נתיב-checkpoint ב-prep (סבבים לא התקדמו). סבב-2 מוכן (1,600 חדשות), נותרו 8,574. guards: copy-EN+batch-size. bake(🔒) כשנצבר
- **anno1800**: wrangler deploy של slug anno1800-hebrew (אופציונלי)
- **gtav**: מאגר /translate עלה (141,212 שורות, 3 קטגוריות עברית). פתוח: אימות in-game של התקנת הלאנצ'ר; שער #2 = פרסום OIV מעודכן לאתר
- **launcher**: User opens Settings->ביצועים, reports the GPU line (green=accelerated/red=software); if software -> Qt release-build/ANGLE fix.

---
_🔒 = דורש אישור מפורש לפני ביצוע (פרסום / שיגור לאנצ'ר / דריסת קבצי משחק)._

## מסמכים קשורים
- באותה תיקייה: [[orchestration/BOOT|BOOT]], [[orchestration/COMMANDS|COMMANDS]], [[orchestration/DOCTRINE|DOCTRINE]], [[orchestration/FLEET|FLEET]], [[orchestration/HANDOFF|HANDOFF]], [[orchestration/README|README]], [[orchestration/RULES|RULES]]
- מפת הבקרה: [[CLAUDE_INDEX#⚙️ סביבה / כלים / אורchestration|CLAUDE_INDEX]]
