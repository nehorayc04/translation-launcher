# 📟 COMMANDS — אוצר הפקודות של המוח

דבר עם המוח (MAX chat) בפקודות קצרות. `<game>` = מזהה מהלוח (gtav, spiderman2,
watchdogs2, godofwar_ragnarok, anno1800, cyberpunk2077, acshadows, assassinscreed2).
`<N>` = כמה סוכני Google במקביל. עברית או אנגלית — שתיהן עובדות.

| פקודה | מה המוח עושה | שער? |
|---|---|---|
| `מצב` / `status` | מרענן ומראה את הלוח + מציע את הצעד הכי כדאי עכשיו. | — |
| `תרגם <game> <N>` / `translate` | מכין `N` סלוטים מקבילים (md5 partition + `SLOT_k.md` לכל סוכן), מעדכן הלוח, נותן `N` שורות מצביע. | — |
| `בקר <game> <N>` / `qa` | `prep_agents.py N` (חלוקת היתרה ל-`agent_K/` נפרדים), נותן `N` שורות מצביע לביקורת. | — |
| `מזג <game>` / `merge` | ממזג את פלט הסוכנים חזרה לספיין + בדיקות מבנה (token/foreign/niqqud) + עדכון אחוז בלוח. | — |
| `בנה <game>` / `build` | מריץ את שרשרת הבנייה של המשחק (encode/pack/deploy מקומי) — בלי פרסום. | 🔒 קבצי משחק |
| `פרסם <game>` / `publish` | build + GitHub release + Worker + Supabase + מצביע גרסה. | 🔒 פרסום |
| `שגר לאנצ'ר` / `ship launcher` | `build_exe.bat` → ISCC → `publish_release.py`. | 🔒 לאנצ'ר |
| `כלל "<טקסט>"` / `rule` | מסווג כללי/ספציפי, מוסיף ל-`RULES.md` (+ פלייבוק), יחיל על הנחיות עתידיות. | — |
| `חדש <game>` / `new` | מתחיל קרקע למשחק חדש לפי `universal/NEW_GAME_GROUNDWORK_PLAYBOOK.md`. | — |
| `המשך` / `continue` | (בפרופיל PRO) קורא `HANDOFF.md` וממשיך מאיפה ש-MAX עצר. | — |

## פורמט שורת המצביע (מה שאתה מדביק לכל סוכן)

```
קרא games/gtav/agent_handoff_full/SLOT_2.md ובצע לפי ההוראות עד 'All done'
```

המוח תמיד מייצר את הקובץ כך שהמצביע יישאר **שורה אחת**. למשל לתרגום מקבילי
הוא יוצר `SLOT_k.md` קטן שמכיל את מספר הסלוט + מפנה ל-`INSTRUCTIONS.md` המלא —
כדי שלא תצטרך להדביק את מספר הסלוט בנפרד.

## דוגמאות

- `תרגם gtav 5` → 5 שורות מצביע, סלוט לכל סוכן, אין התנגשות (md5 partition).
- `בקר watchdogs2 4` → 4 תיקיות `agent_K/` נפרדות, 4 שורות מצביע לביקורת.
- `מזג gtav` → מיזוג + בדיקות; הלוח מתעדכן; המוח מציע "מוכן לפרסם".
- `פרסם spiderman2` → המוח עוצר ומבקש אישור מפורש לפני release החוצה.
- `כלל "שם דמות בודד בכרטיס דובר חייב להישאר עברית לכיוון הנקודתיים"` → נוסף
  ל-`RULES.md` כללי-RTL ויחול על כל משחק בעתיד.

## שערי ביטחון (גם במצב אוטומטי מלא)

🔒 **פרסום מוד** · 🔒 **שיגור לאנצ'ר** · 🔒 **מחיקה/דריסה של קבצי משחק** —
המוח תמיד עוצר ומבקש אישור מפורש לפני ביצוע. כל השאר רץ אוטומטית.

## מאחורי הקלעים — ה-CLI שהמוח מריץ

| פקודה שלך | מה אני מריץ |
|---|---|
| `תרגם <game> <N>` | `python orchestration/orchestrate.py slots <game> <N>` (מייצר SLOT_k + מצביעים) |
| `בקר <game> <N>` | `python games/<game>/agent_handoff_qa/prep_agents.py <N>` + רישום dispatch |
| `מצב` | `orchestrate.py status` + `orchestrate.py next` |
| `מזג <game>` | merge_batch/loop_merge/qa_merge של המשחק → `orchestrate.py set <game> progress …` |
| כל שינוי מצב | `orchestrate.py set …` → `orchestrate.py board` |
| בדיקת תקינות | `orchestrate.py doctor` (state↔games↔דיסק) |

`orchestrate.py game <id>` מציג את כל הניתוב של משחק (handoff, slug, repo, build, publish).
