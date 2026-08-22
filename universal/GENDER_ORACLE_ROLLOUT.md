# 🔑 Gender Oracle — gender/number from the game's OWN gendered localization, not English

**המטרה:** לתקן/למנוע שגיאות מגדר ומספר בעברית בלי לתרגם מחדש את המשמעות. אנגלית לא
מבחינה זכר/נקבה/רבים → תרגום מאנגלית **מנחש**. אבל המשחק כבר כולל תרגום מקצועי בשפות
ש**כן** מחלקות מגדר/מספר — ומהן גוזרים את התשובה. **ערבית = האורקל האידיאלי לעברית**
(שתיהן שמיות: أنتَ/أنتِ/أنتم = אתה/את/אתם, פעלים ממוגדרים, נקבה ـة). היא כבר בתוך המשחק
(החריץ שאנחנו חוטפים) → **בלי לשחק, בלי צילומי מסך**.

> **החוק החדש (RULES.md #12):** מקור המגדר לכל תרגום עברי = הלוקליזציה הממוגדרת של
> המשחק (ערבית קודם; אם אין — רוסית/ספרדית/צרפתית/גרמנית). אנגלית = מקור **המשמעות**
> בלבד. לא לתרגם מחדש תוכן — לתקן **רק** את המורפמה המגדרית.

---

## שלושת התרחישים — מה לעשות בכל צאט

### 1. תרגום שכבר הושלם (published / done)
פאס **תיקון-מגדר** דטרמיניסטי, אפס תרגום-מחדש:
1. **חלץ את המקור הממוגדר של המשחק** (החריץ הערבי המקורי/הפריסטין — לא ה-Hebrew שדרסנו).
2. הרץ `gender_oracle scan` על הספיין הקיים → `gender_oracle_suspects.jsonl` (אי-התאמות
   מגדר בביטחון גבוה + שורות תלויות-שחקן שנשארו שטוחות M==F).
3. **תקן רק את המורפמה** (`dualgender_inflect.py` — אתה↔את + הטיות פועל), משמעות לא נגעת.
   מה שלא ברור/דורש מבנה → האצל ([[delegate-all-translation]]).
4. rebuild + re-publish (אם הפער מצדיק — לפי שיקול המשתמש; לא מפרסמים בלי "פרסם").

### 2. תרגום שרץ עכשיו (in-progress)
א. **הזרם את איתות-המגדר להאנדוף** — לכל שורה, ספק למתרגם את הטקסט הממוגדר של המשחק
   (או לפחות "הנמען נקבה/זכר/רבים · הדובר נקבה/זכר" שנגזר ממנו) → המגדר נכון מהרגע הראשון.
ב. הרץ את פאס התיקון (#1) על מה שכבר תורגם עד כה.

### 3. תרגום עתידי (feasibility / not yet translated)
בהאנדוף העתידי: **אנגלית = משמעות, הלוקל הממוגדר = מגדר**. לכל שורה שהמתרגם מקבל, לצרף
את הטקסט הממוגדר המקביל (או תג המגדר הנגזר). ואז פאס QA של האורקל בסוף. כך אין בכלל חוב
מגדר להיווצר.

---

## הכלים (משותפים, ב-`universal/`)
- **`gender_oracle.py`** — פרסרים ערבית↔עברית (פנייה/מספר, דיוק>כיסוי: רק סימנים
  חד-משמעיים — أنتَ/أنتِ, סיומת פועל נקבה ـين, ـكِ/ـكَ, أنتم; לא פועל "עירום" تفعل כי
  הוא הומוגרף 2זכר/3נקבה). פקודות: `scan --arabic-dir <serialized> --spine <a> <b>
  --out suspects.jsonl` · `build_arabic_map(dir)` · `prove` · `selftest`.
  **הפרסרים כלליים לכל משחק** — רק המקור (מאיפה מגיע הטקסט הממוגדר) שונה פר-משחק.
  - **`ar_addressee_strict()` (נוסף 2026-07-04, hogwarts) — גרסת דיוק-מקסימלי ל-hint/QA:** רק
    כינויי גוף أنتِ/أنتَ + סיומת ـكِ/ـكَ **מנוקדת** + רבים أنتم/أنتما + **whitelist מונחה של
    פעלי 2nd-fem** (تريدين/تعرفين/…). **מפילה לגמרי את ה-heuristic הגנרי `ت…ين`** שנותן false
    positives על masdar תַפְעִיל (تحسين), ר"ר שבור/שלם (تنانين=דרקונים, تمارين), ופועל+כינוי-מושא
    (تسامحني=סלח **לי**). השתמש בזה כשהפלט נכתב חזרה כ-hint/auto-QA (`build_gender_source`,
    `gender_qa`) — כיסוי נמוך יותר אבל **אפס hint שגוי** (חוב-מגדר לא נוצר).
  - **הקשחת ה-parser המשותף (2026-07-04):** `_AR_YOU_F_VERB` דורש עכשיו `ت[..]{3,}ين` (מוציא
    masdar ת+2+ין); נזרק ענף ה-`ي` מ-`_AR_YOU_VERB_F2` (תפס ـني/הומוגרף 3rd-fem); `_AR_SUF_KF/KM`
    דורשים שאחרי ה-`كِ/كَ` **לא** תבוא אות (ה-`\b` אחרי ניקוד נכשל והצית בתוך الكَلب/ذكَر). כל
    המשחקים הערביים נהנים; selftest נשאר יציב (14/16 — 2 ה-MISS: masc-verb-via-particle + he-accusative, קדמו).
- **`dualgender_inflect.py`** — הטיה דטרמיניסטית fem→masc/masc→fem (אתה↔את + מפת סיומות),
  משמרת scaffold (כל תו לא-עברי זהה). לתיקון המורפמה בלבד.
- **`dualgender_verify_agents.py`** — verifier עצמאי (scaffold זהה + heb השתנה + בלי
  niqqud + בלי internal-edit) — לאמת כל תיקון, לא לסמוך על סוכן.

## מקור-המגדר לכל משחק
> לגזור **מגדר** בלבד; המשמעות נשארת מהתרגום הקיים/מאנגלית. המקור הערבי = הפריסטין
> המקורי של המשחק (re-extract מהארכיון, לא ה-mod שלנו).

| משחק | מקור ממוגדר | פורמט / כלי חילוץ | מפתח join | תרחיש |
|---|---|---|---|---|
| **cyberpunk2077** | ערבית (femaleVariant/maleVariant) | `lang_ar_text.archive` → WolvenKit extract+serialize | `primaryKey` (=`locstringId.ruid` בסצנות) | done → fix (בעבודה) |
| **spiderman2** | ערבית variant_18 | DAT1, `games/spiderman2/work/` extract (dat1lib) | `stringId` | done → fix |
| **watchdogs2** | `main_arabic.loc` המקורי | `tools/loctool/loctool.exe` decode | oasis id | done → fix |
| **godofwar_ragnarok** | `r_lang_ar.wad` המקורי | `work/gowr_wad.py extract` (MSGS_TXT) | numeric id | done → fix |
| **anno1800** | **אין ערבית** → `texts_russian.xml` (דובר) + `texts_spanish.xml` (רפרנט) | `work/rda_reader.py` על `data0.rda` | `<GUID>` | done → fix (פרסר רוסי/ספרדי) |
| **gtav** | **אין ערבית** → spanish/french/russian `.gxt2` | `work/gtav_gxt2.py read_gxt2` על `<lang>_rel.rpf` | `joaat(label)` | done → fix (פרסר רומאני/סלאבי) |
| **steam** | ערבית slot | `*_arabic-json.js` / VDF | key | done → fix |
| **hogwarts_legacy** | ערבית `arAE` (MAIN/SUB `.bin`) | `work/hl_bin.py decode arAE` | key (`MAIN:`/`SUB:` prefix) | future → **מקור מוכן ✅** (translate-with-gender) |
| **witcher3** | ערבית `ar.w3strings` (cleartext keyID0) | `work/w3strings.py decode` | `str_id` | future |
| **plague_tale_requiem** | ערבית `tt23.pc` המקורי (פריסטין `.he_backup`) | `work/pt_text.py` codec + NFKC (presentation→standard) | KEY | future → **מקור מוכן ✅** |
| **acshadows** | `LocalizationPackage_Arabic` | scimitar v42 forge, `games/acshadows/tools` | lineID/`0xFADE9F44` | future |
| **acunity** | `TLocalizationPackage_Arabic_Subtitles` | char-index, `games/acunity/work/acu_loc.py` | id | future |
| **assassinscreed2** | **אין ערבית** → Russian/Spanish `LocalizationPackage` | char-index, `games/assassinscreed2/tools/ac2_forge.py` | key | future |
| **tlou1** | **אין ערבית** → `text2/rus.subtitles` (דובר, עבר -л/-ла) + `text2/spa`/`fre`.subtitles (רפרנט) | `tools/psarc.py` + `tools/tlou_loc.py decode` על שפה ממוגדרת | **SID** (זהה בין שפות) | in-progress → translate-with-gender + fix |
| **tlou2** | **אין ערבית** → אותו מנוע ND: `text2/rus`/`spa`/`fre`.subtitles | `psarc` + `tlou_loc` (כמו tlou1) | **SID** | future (עדיין לא תורגם) |

## כללי בטיחות (חובה)
- **לא לתרגם מחדש משמעות.** נוגעים רק בשורות שהמקור-הממוגדר מוכיח שהמגדר בהן שגוי, ומשנים
  **רק** את אותיות/סיומות המגדר. משמעות זהה בייט-לבייט מלבד המורפמה.
- **גיבוי + qa.lock + כתיבה אטומית** לכל כתיבת ספיין (כמו `dualgender_fix/apply`).
- **guard פר-שורה:** כתוב רק אם הערך הנוכחי עדיין שווה למה שנסרק (לא לדרוס עבודה מקבילה).
- **passthrough לשמות/קודים** (RULES #5). **UTF-8 stdout** (RULES #8).
- **האורקל הוא ה-QA:** אחרי כל תיקון, `gender_oracle scan` מחדש + `dualgender_verify_agents`
  עצמאי. אף פעם לא לסמוך על "done" של סוכן (RULES #6/#7).
- **פר-שפה, לא-ערבית:** רוסית = מגדר-דובר חד-משמעי (עבר -л/-ла); ספרדית/צרפתית/איטלקית
  = רפרנט+תואר (-o/-a, -é/-ée); גרמנית = der/die/das + מין שם-עצם. להוסיף פרסר קטן פר-שפה
  לצד הפרסר הערבי הקיים.

## הרחבה למנוע (לסשן שמריץ)
הפרסר הערבי + `scan` כבר עובדים (הוכח על CP2077 q112: 70 שורות → 11 שגיאות אמת). למשחק
בלי ערבית, להוסיף ל-`gender_oracle.py` `ru_addressee/ru_speaker` (Cyrillic) או
`es_referent` (Latin) לצד `ar_addressee`, ולהזין ל-`scan` את המפה הנכונה. הפרסר העברי
(`he_addressee`) משותף.

**✅ בוצע ל-plague_tale_requiem (2026-07-03, מקור-מגדר מוכן ל-Phase-2):**
`games/plague_tale_requiem/work/build_gender_source.py` → `extract/gender_source.json` = לכל אחת מ-20,661
השורות `{en (משמעות), ar (מגדר), hint}`, join לפי **KEY**. מקור המגדר = **הערבית הפריסטין `tt23.pc.he_backup`**
(ה-live נדרס ע"י ה-proof; חילוץ דרך `pt_text` + **NFKC** presentation-forms→ערבית תקנית — חובה, אחרת הפרסר לא
תופס). 16,826 שורות עם אותיות ערביות; **508 שורות VO** קיבלו רמז-פנייה אוטומטי חד-משמעי (הרמז מוגבל ל-VO —
על שמות-עצם/קרדיטים ה-`ar_addressee` יורה false-positive על סיומת ـة). הערבית של המשחק מנוקדת רק ב-21% →
recall נמוך (מפספס ציוויי-נקבה כמו تتوقفي/تخفقي) אבל **הערבית הגולמית מצורפת לכל שורה** = המנגנון העיקרי;
המתרגם/סוכן קורא את המגדר ישירות. **QA לסוף Phase-2 מוכן:** `work/gender_qa.py <hebrew_KEY_to_text.json>`
(smoke-tested: עברית-זכר מול ערבית-נקבה → סומן; עברית-נקבה תואמת → לא סומן) → `extract/gender_suspects.jsonl`.
**Phase-2 handoff חייב לצרף לכל שורה את `ar`+`hint` מ-gender_source.json.** (multi-lang triangulation אפשרי —
המשחק כולל גם tt-קבצים צרפתית/ספרדית/איטלקית/גרמנית לרפרנט; לא נבנה, לא נדרש כרגע.)

**✅ בוצע ל-tlou1 (2026-07-06):** `ru_addressee`/`ru_speaker`/`es_referent` נוספו ל-`gender_oracle.py`
(selftest 8/8; תוקן באג הרחקת `-л` שהרג פעלים נפוצים вернул/видел/говорил) + `games/tlou1/work/gender_qa.py`
(scan רוסית↔עברית על האחצ' addressee) + **ההאנדוף הועשר: כל שורה נושאת את הטקסט הרוסי/ספרדי/צרפתי המקביל**
(`work/build_ct_strings.py` → `agent_handoff/gender_source.json`, join לפי SID; 3,623/32,881 עם רמז אוטומטי,
כולן עם הטקסט הגולמי). **dedup-by-EN נמדד בטוח-מגדרית** (6,376 ENs כפולים, ~6 קונפליקטים = רעש פרסר → אין צורך בפיצול).
18 קבצי שפה ממוגדרת נשמרו ב-`games/tlou1/extract/lang/`.

## מסמכים קשורים
- באותה תיקייה: [[universal/AGENT_TRANSLATION_HANDOFF_TEMPLATE|AGENT_TRANSLATION_HANDOFF_TEMPLATE]], [[universal/NEW_ERA_LANGUAGE_ROLES|NEW_ERA_LANGUAGE_ROLES]], [[universal/NEW_GAME_GROUNDWORK_PLAYBOOK|NEW_GAME_GROUNDWORK_PLAYBOOK]], [[universal/QA_REVIEW_HANDOFF|QA_REVIEW_HANDOFF]], [[universal/cross_audit_dashboard|cross_audit_dashboard]]
- פלייבוקים כלל-פרויקטיים: [[CLAUDE_INDEX#⚙️ סביבה / כלים / אורchestration|CLAUDE_INDEX]]
