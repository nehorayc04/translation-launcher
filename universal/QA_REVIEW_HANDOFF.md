# Universal translation-QA handoff (resumable across agents)

A fresh Google/Antigravity agent (empty history) reviews the Hebrew game translation
for correctness and fixes genuine errors. **The agent reviews and fixes the text
ITSELF — it must NOT connect to any local model / API / project translation script.**
It only uses the `qa_review.py` helper (pure file I/O, no network).

**Resumable:** every reviewed key is recorded in `qa_review_checkpoint.json`. If an
agent runs out of tokens mid-way, paste the SAME instruction to the next agent — its
first `get` returns the NEXT unreviewed batch automatically. Nothing is lost or redone.

The exact block to paste to each agent is below (and in the chat). Per game, only the
**working directory** changes (it holds that game's `qa_review_config.json`).

---

## The paste-ready instruction

> Working dir (SM2): `C:\Users\Nehoray_Cohen\Projects\Game translator\games\spiderman2\work`
> Helper: `C:\Users\Nehoray_Cohen\Projects\Game translator\universal\qa_review.py` (stdlib only — any `python` works)

```
משימה: עבור על תרגום עברית של משחק ובדוק אותו. אתה בודק ומתקן בעצמך — אסור להתחבר למודל מקומי,
ל-API, או להריץ סקריפט תרגום של הפרויקט. אתה משתמש רק בכלי qa_review.py (קריאה/כתיבת קבצים בלבד).

מקום עבודה (cd לשם): C:\Users\Nehoray_Cohen\Projects\Game translator\games\spiderman2\work
כלי:               C:\Users\Nehoray_Cohen\Projects\Game translator\universal\qa_review.py

הלולאה (חזור שוב ושוב עד "All done!"):
1) הרץ:  python "C:\Users\Nehoray_Cohen\Projects\Game translator\universal\qa_review.py" get 30
   זה כותב qa_review_batch.json = ‎{KEY: {"en": אנגלית, "he": עברית, "fix": ""}}‎.
2) קרא את qa_review_batch.json. לכל רשומה: השווה en מול he. **אם העברית תקינה — השאר fix="" (ברירת המחדל!).**
   **רק אם יש שגיאה אמיתית — כתוב את העברית המתוקנת בשדה "fix"** (שמור את כל המרקרים והטוקנים, ראה למטה).
3) שמור את qa_review_batch.json והרץ:  python "...\universal\qa_review.py" put
   זה מחיל את התיקונים (אחרי ולידציית מבנה), מסמן את כל ה-30 כ-reviewed (ה-checkpoint מתקדם),
   ורושם תיקונים שהוחלו / נדחו ל-qa_review_fixes.jsonl / qa_review_rejected.jsonl.
4) חזור ל-1 עד שמודפס "All done!".

מה לבדוק (קטגוריות הפגמים — תקן רק שגיאה אמיתית, לא טעם אישי):
1. תרגום שגוי / משמעות לא נכונה — העברית אומרת משהו אחר מהאנגלית.
2. אות זרה — תווים בערבית/רוסית/יוונית/תאית/סינית/קוריאנית שדלפו → תרגם מחדש לעברית.
3. ניקוד — נקודות תנועה עבריות → הסר אותן (עברית בלי ניקוד).
4. אנגלית לא מתורגמת בתוך עברית — מילים אנגליות אמיתיות שנשארו → תרגם. **חריג: שמות/מותגים/קודים
   נשארים אנגלית** (Spider-Man, Oscorp, F.E.A.S.T., NYPD, %d) — אל תתרגם אותם.
5. תעתיק שבור (עברית+לטינית מודבקות במילה אחת, כמו "גילherme" / "מטלFX") → תקן לכתב אחד.
6. ג'יבריש / עברית לא טבעית / רגיסטר שגוי → נסח מחדש בעברית טבעית.
7. עקביות שמות — שמות דמויות/מקומות לפי הגלוסר (מודפס ב-get). **רשומה שהיא שם-דובר בלבד חייבת להיות
   בעברית** (כדי שהנקודתיים יוצגו בצד הנכון ב-RTL).
8. מרקרים וטוקנים — ‎@@TS1@@‎ ‎@@TS2@@‎, ‎[TOKEN]‎, ‎{VALUE}‎, ‎%d/%s‎, ‎<br>‎, ‎&rlm;‎ — חייבים להישאר
   בדיוק כפי שהם בעברית. אל תכתוב ‎<ts=...>‎ בעצמך (זה ‎@@TSn@@‎). הכלי דוחה תיקון שמשנה/מוריד טוקן.

כללים נוקשים:
- ברירת המחדל היא OK. תקן רק שגיאות אמיתיות — אל תשכתב תרגום תקין לפי טעמך (תיקון-יתר = הכשל מס' 1).
- עברית + לטינית בלבד, בלי ניקוד.
- אם אתה לא בטוח אם זו שגיאה — השאר fix="" (אל תיגע).
- אל תיגע בשום קובץ אחר חוץ מ-qa_review_batch.json.
- אל תתחבר למודל/API. אתה המתרגם.

אם נגמרים הטוקנים: עצור. הסוכן הבא יקבל את אותה הנחיה בדיוק ו-get יחזיר אוטומטית את ה-30 הבאים
שלא נבדקו — שום דבר לא הולך לאיבוד.

בדיקת מצב בכל רגע:  python "C:\Users\Nehoray_Cohen\Projects\Game translator\universal\qa_review.py" status

סיכום בסוף (חובה):
--- AGENT SUMMARY ---
תאריך: [תאריך ושעה]
משימה: QA review — תרגום SM2
נבדקו (reviewed): [כמה reviewed כעת לפי status]
תוקנו (applied): [כמה]
מצב: [נגמרו הטוקנים / הסתיים "All done!"]
--- END SUMMARY ---
```

---

## For Claude (after an agent stops or finishes)

- The fixes are ALREADY written into the spine (`qa_review.py put` applied them, validated).
- `qa_review_fixes.jsonl` = every applied fix (`{key, old, new}`); `qa_review_rejected.jsonl` =
  fixes the structural gate rejected (inspect these — they may be real errors the agent phrased
  in a way that dropped a token).
- When the review pass is far enough (or `status` shows ~0 remaining): **rebake + redeploy +
  republish** per the game's chain (SM2: `10→91→94→95→96→97→15→80` under `.venv` → deploy 4
  targets → `pack_and_release.py <ver> --pack-only` → `gh release upload <stable-tag> --clobber`
  → `publish_version.py <game> <ver> --stage beta --apply`).
- **Adding QA to a NEW game:** drop a `qa_review_config.json` in that game's work dir
  (`en_file`, `spine_files` [later wins], optional `skip_keys_file`, `min_words`, `glossary`),
  and hand the agent the same block with the working dir swapped. The helper + loop are unchanged.
```
```

## מסמכים קשורים
- באותה תיקייה: [[universal/AGENT_TRANSLATION_HANDOFF_TEMPLATE|AGENT_TRANSLATION_HANDOFF_TEMPLATE]], [[universal/GENDER_ORACLE_ROLLOUT|GENDER_ORACLE_ROLLOUT]], [[universal/NEW_ERA_LANGUAGE_ROLES|NEW_ERA_LANGUAGE_ROLES]], [[universal/NEW_GAME_GROUNDWORK_PLAYBOOK|NEW_GAME_GROUNDWORK_PLAYBOOK]], [[universal/cross_audit_dashboard|cross_audit_dashboard]]
- פלייבוקים כלל-פרויקטיים: [[CLAUDE_INDEX#⚙️ סביבה / כלים / אורchestration|CLAUDE_INDEX]]
