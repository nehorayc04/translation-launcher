# Watch Dogs 2 — דוח היתכנות: תרגום עברית RTL

מקור: workflow מחקרי (4 צירים: format / tools / rtl / precedents → אימות יריב → סינתזה),
9 agents, ~1.24M tokens, 2026-06-16. נשען על סיור מקומי מאומת ב-`RECON.md`.

## 1. שורה תחתונה

**כן-עם-מגבלות — אבל רק כפרויקט מחקר חלוצי, לא replay של הפייפליין הקיים.**

שכבת ה-data פתורה ומוכחת: אפשר לחלץ טקסט, להזריק bytes עבריים (UTF-16LE), להזריק
גליפים עבריים לפונט, ולפרוס mod עובד (תרגומים מלאים LTR — אוקראינית, רוסית — כבר ב-Nexus).

**הבלוקר היחיד והגדול: ה-Disrupt engine כנראה לא מבצע bidi/RTL reordering, ואין שום
תקדים של תרגום RTL (עברית/ערבית/פרסית) על אף משחק Disrupt או Dunia אי-פעם.** כל
הניצחונות הקודמים (CP2077, Steam, SM2) נשענו על **Arabic-slot hijack** — ירושת ה-bidi
של המנוע "בחינם". **הטריק הזה לא זמין שמיש כאן.**

מסקנה: **אל תבטיח תוצאה נקייה. הרץ spike של יום אחד שמכריע את שאלת ה-RTL לפני שמתחייבים
לתרגום מלא.** עד אז — הפרויקט הימור, לא ודאות.

## 2. פורמט הנתונים

- **Container:** Disrupt `.fat` (index, magic `FAT5`/`0x46415435`, **version 11** = WD2) +
  `.dat` (blob). אומת byte-level מקומית: כל ה-`.fat` v11, platform 1 (Win64),
  CompressionVersion 6, NameHashVersion `0x70`. entry = 20B (name-hash 64-bit + packed
  sizes/offset/compression).
- שמות נשמרים רק כ-hashes → צריך `filelist` (gibbed/WatchDogs2-File-Lists). **לא לגזור
  hash מחדש — להשתמש ב-gibbed + filelists.**
- **Localization (Oasis), שתי צורות לכל שפה:**
  - `languages\<lang>\oasisstrings.rml` — string-id→text (CRC32 hex ids). **היעד המעשי לתרגום.**
  - `languages\main_<lang>.loc` — blob דחוס (magic `LS`, Huffman bit-packed → UTF-16LE).
    **קשה ל-rebuild** — היסטורית הסתמכו על runtime hook או על תרגום ה-`.rml`.
- EN text: `patch_english.dat` ≈ 8,594 entries, `installpackage_english.dat` ≈ 2,693
  (סה"כ strings כנראה עשרות אלפים — לא נמדד מדויק).
- **לשמר byte-exact:** `[CR]`/`[LF]`, `%s`/`%d`, `{VAR}`, `<tag>`, button-glyph codes.

## 3. כלים

| שכבה | כלי | URL | סטטוס |
|---|---|---|---|
| unpack/pack archive | **Gibbed.Disrupt** (`Gibbed.WatchDogs2.*`) | github.com/gibbed/Gibbed.Disrupt | מוכח לחילוץ. ⚠️ בונים מ-source (אין release). issue #3: המתחזק עצמו — "probably doesn't work out of the box" ל-WD2. **Pack לא מאומת.** |
| binaries מוכנים | DraxAris/gibbet | github.com/DraxAris/gibbet | ממותג WD1 — לא ה-FAT v11 של WD2. עדיף build מ-source. |
| file lists | **gibbed/WatchDogs2-File-Lists** | github.com/gibbed/WatchDogs2-File-Lists | מלא, חובה ל-Pack. |
| `.loc` → טקסט | ahmet-celik/watch-dogs-loc-tool | github.com/ahmet-celik/watch-dogs-loc-tool | מוכח WD1/2/Legion — **extract-only**. |
| repack `.loc` | community "loctool" | ZenHAX 14349 / ResHax 353 (gated) | ⚠️ **החוליה החלשה** — מוכח רק על Legion; "not tested for WD 1-2". **אין write-back מאומת ל-WD2.** |
| פונטים | eprilx/FFDConverter | github.com/eprilx/FFDConverter | תומך FFD WD1/2/Legion, glyph-agnostic. ⚠️ אפס שימוש מוכח RTL/עברית; metrics = סיכון. |
| merge mods | qotapac/WD2ModBundler | github.com/qotapac/WD2ModBundler | מאחד mods ל-Patch3. |

**Fallback — DLL hook** (proxy `dinput8.dll`): עוקף repack + locale, שליטה מלאה על RTL,
אבל הנדסה גדולה, שביר מול patches, **מתנגש ב-EAC**, ואין hook מאומת ל-WD2.

## 4. RTL — צוואר הבקבוק

**מחלוקת מתועדת בין ה-researchers על קיום Arabic slot:**
- `tools`/`format`: ה-`common.filelist` **כן** מכיל `languages\arabic\oasisstrings.rml` +
  `main_arabic.loc` (אומת בקריאת raw filelist) + subtitles ערביים רשמיים (PS Store בחריין).
- `rtl`/`precedents`: WD2 לא משלח Arabic, המנוע כנראה LTR-only.

**הפיוס:** קיום entry ב-build-list **לא מוכיח** ש-(1) ה-`.dat` הקמעונאי מכיל bytes ערביים
לא-ריקים (אולי artifact לצד pseudo-locale `fakelongenglish`); (2) ה-EXE חושף ערבית
כשפה ניתנת-לבחירה (regional gating; ה-`Support\Readme` המקומי חסר ערבית); (3) **המנוע
מרנדר RTL נכון** — אין תיעוד לכך בשום כיוון.

**ההסקה החזקה ל-no-bidi:** המשחק הראשון של Ubisoft עם ערבית מלאה (UI הפוך) =
**AC Mirage (2023)**, על **AnvilNext** שונה, ~3 שנים אחרי משחק ה-Disrupt האחרון.

**הגישה הריאליסטית (אם spike מאשר LTR-only):** **build-time visual pre-reversal
(logical→visual)** עם FriBidi/python-bidi (עברית לא צריכה joining כמו ערבית). caveats
בלתי-נמנעים: **line-wrap** (חייבים pre-wrap ידני לרוחב UI), **טקסט מעורב** (עברית+לטינית+
מספרים+`{VALUE}` runtime ינחתו לא נכון), **פיסוק/סוגריים** (mirroring ידני).
**מה שלא יעבוד:** Unicode bidi controls (RLM/RLE/PDF) — מנוע LTR מתעלם (לקח SM2/cohtml).

**ציפיות:** תפריטים סטטיים עברית-טהורה — בר-השגה. subtitles עם wrap דינמי + מעורב —
**לא יהיו מושלמים** ללא bidi ברמת המנוע.

## 5. אנטי-צ'יט + load order

- **EAC דלוק:** סורק זיכרון + files גם offline, **מסיר אוטומטית** קבצים מתוקנים, מזהיר על ban.
  swap נאיבי **ייהפך ב-launch**.
- **מעקף:** דגל **`-eac_launcher`** (Ubisoft Connect / shortcut) → EAC כבוי, online מנוטרל.
  "account-safe as long as offline" — אבל "no reported bans", לא מדיניות רשמית.
  → המשחק המתורגם **קבוע offline / ללא MP**.
- **Load order:** Disrupt טוען לפי מספר (`common`<`patch`<`patch2`<`patch3`, גבוה מנצח).
  **פורסים `patch3.dat`/`.fat` עם רק הקבצים שהשתנו** — בלי לגעת ב-`common.dat`. הסרה =
  מחיקת `patch3.*`. **reversible לחלוטין.** (חלופה: דריסת `patch_english.dat/.fat`, כמו ה-mod האוקראיני.)

## 6. השוואה לפייפליין הקיים

**עובר (reuse כמעט מלא):** ה-LM-translate trio (`sm2_translate/watchdog/progress`),
multi-agent frontier LQA (§11), structural QA (§7), publish+version-sync (4 surfaces),
השיעורים הקשים (UTF-8 stdout, reload-while-busy).

**לא עובר (השוני המהותי):** ❌ Arabic-slot hijack · ❌ ירושת bidi "בחינם" (חייבים reorder
בעצמנו ב-build) · ❌ font ready (להזריק גליפים עבריים מאפס + לכייל metrics) · ⚠️ repack
לא מאומת ל-WD2 · ⚠️ EAC שלב חובה.

**מסקנה:** הצד הלשוני = reuse כמעט מלא. הצד ה-engineering (RTL render + repack + font + EAC) = **R&D חדש**.

## 7. תוכנית "הכנת הקרקע" — 3 שערי go/no-go

**שלב 0 — תשתית (בטוח, reversible):**
1. הוסף `-eac_launcher` ל-launch args. reversible.
2. גבה `patch_english.dat/.fat` + `installpackage_english.dat/.fat`.
3. שלד `games/watchdogs2/work/` — העתק SM2 trio כ-template.

**שער 1 — round-trip של data (בטוח, מקומי):**
4. בנה Gibbed.Disrupt מ-source (`Gibbed.WatchDogs2.*`) + filelists.
5. smoke-test: unpack של `patch_english.dat` — לאמת שה-FAT v11 נפרס.
6. חלץ EN `.loc` עם `watch_dogs_loc.exe` (מצא min/max id ל-WD2 אמפירית).
7. **הקריטי:** repack **בלי תרגום** → `patch3.dat` → הרץ → ודא שאנגלית תקינה.
   **אם `.loc` repack נכשל ל-WD2 → DLL hook או הפרויקט לא שווה על המנוע.** reversible.

**שער 2 — להכריע RTL אמפירית (ה-spike המכריע, reversible):**
8. הזרק גליפים עבריים ל-`.ffd` + atlas `.xbt` עם FFDConverter.
9. **10-string Hebrew render test:** דרוס ~10 UI ids בשתי צורות — (a) logical, (b)
   visually pre-reversed (python-bidi). הרץ, צלם, קבע: גליפים מופיעים? באיזה כיוון?
   RLM משנה? **התוצאה מכריעה את כל הפרויקט.**
10. (במקביל) בדוק אם בחירת ערבית מ-ה-EXE אפשרית בכלל.

**רק אם שער 2 עבר:** 11. שכבת build-time bidi (pre-reverse + pre-wrap) + LM-translate על הקורפוס.
12. multi-agent LQA → bake → publish (Patch3 + GitHub + Worker + Supabase).

## 8. החלטות למשתמש

1. **להשקיע ב-spike של יום אחד?** ההחלטה המרכזית. ממליץ: כן — עלות נמוכה, מכריע הכל.
2. **אם Disrupt LTR-only (הצפי) — לקבל מגבלות?** תפריטים = בר-השגה; subtitles מעורבים +
   wrap דינמי = לא מושלמים לעולם. "מספיק טוב" או "מושלם או כלום"?
3. **offline-only מקובל?** ללא MP, EAC כבוי.
4. **אם `.loc` repack נכשל — ללכת ל-DLL hook?** עוקף הכל אבל הנדסה גדולה + מתנגש EAC.
5. **עדיפות מול SM2/AoT3** — ה-SM2 run פעיל (multi-week, אותו GPU). מתי להתחיל?

**הערה כנה:** ראיות חזקות על format+tools (byte-level + source). ראיות על RTL feasibility
**דקות מאוד** — אין תקדים, מחלוקת על ה-Arabic slot, ושתי הגרסאות מסכימות שזה לא הוכרע.
אל תתייחס ל-"Arabic-slot hijack viable on WD2" כמוכח. 4 שערים לא-מאומתים, נפתרים רק in-game.

---

## ספייק אמפירי — תוצאות (2026-06-16) ⛔ NO-GO ל"מושלם"

הרצנו את הספייק המכריע על ההתקנה החיה (`F:\Games\WATCH_DOGS2`).

### מה שהוכח חיובי (הדאטה והמנוע):
- **חריץ ערבי קיים בפועל בקבצים:** `common.filelist` כולל `languages\arabic\oasisstrings.rml`;
  חולץ ואומת שה-entry קיים ב-`common.dat` עם **5.06MB טקסט ערבי דחוס** (1.85MB LZ4LW).
- **פונט ערבי ייעודי נשלח:** `ui\fonts\helveticaneuelt_w1g_65_md_arabic.ffd` (+atlas) — לצד
  פונטים נפרדים לכל script (japanese/chinese/korean/default). **המנוע בוחר פונט+כיוון לפי
  שפה, לא לפי תוכן.**
- **קוד locale `ar-SA` קיים ב-`Disrupt_64.dll`** (0x353d790). enum השפות (לפי סדר ה-DLL,
  עוגן: english=3): arabic=22.
- כלים: Gibbed.WatchDogs2.Unpack/Pack נבנו (.NET 8 SDK + ref-assemblies); LZ4LW פוענח
  חלקית (block1 = LZ4 סטנדרטי 29,695→59,114, byte0=0x3a prefix; ה-block container המלא לא נסגר).

### ⛔ הבלוקר המכריע — ערבית חסומה ברמת ה-EXE ב-PC:
שלוש הרצות in-game (אומת בצילומי מסך + מצב הקבצים):
1. `TextLanguage2=20` ב-GamerProfile (דרך Connect) → המשחק **דרס ל-3**, אנגלית.
2. `TextLanguage2=22` + `HKLM\...\Installs\2688\Language=ar-SA` (דרך Connect) → **HKLM שרד ar-SA,
   אבל המשחק דרס את הקובץ ל-3**, אנגלית. → המשחק מקבל שפה מ-Connect IPC, מתעלם מהרישום.
3. אותו דבר + **הרצה ישירה** `WatchDogs2.exe -eac_launcher` (עוקף את Connect) → **שוב נדרס ל-3,
   אנגלית.** → ה-EXE עצמו כופה en-US ומתעלם גם מ-ar-SA ברישום וגם מ-22 בקובץ.

**מסקנה:** הדאטה+הפונט+ה-locale הערביים נשלחים, אבל **בורר השפה ב-EXE של גרסת ה-PC נעול
ל-SKU ללא ערבית** (כנראה גרסת קונסולה במזה"ת כן חשפה ערבית). אי אפשר להגיע למצב ערבית
ללא **patch בינארי ל-EXE/DLL** — שהוא שביר מול עדכונים **ומתנגש ב-EasyAntiCheat** (שמירת קבצים
מתוקנים), ולכן לא "מושלם/נקי/תחזוקתי".

### למה גם מסלול ה-mod (חריץ english) לא נותן "מושלם":
המנוע בוחר פונט+כיוון **לפי שפה** (ארכיטקטורת per-language fonts), לא לפי תוכן Unicode. לכן
עברית שנזריק לחריץ ה-english תרונדר **LTR** (ו/או ריבועים — לפונט ה-default אין גליפים עבריים).
content-based bidi מאוד לא סביר בארכיטקטורה הזו (לא נבדק אמפירית — דורש השלמת LZ4LW + repack +
הזרקת פונט, עם סיכוי נמוך מאוד).

### הוורדיקט תחת "מושלם בלי ויתור": **NO-GO.**
הצינור ה-RTL קיים במנוע אבל נעול מחוץ ל-EXE ב-PC. כל דרך להגיע אליו (exe-patch) או לזייף אותו
(visual pre-reversal בחריץ english) **מפֵרה את הרף**: הראשון שביר + EAC offline-only, השני
לא-RTL-אמיתי. תחת רף "מושלם" — WD2-PC לא מתאים לתרגום עברית נקי.

**אופציות שנותרו (כולן פוגעות ברף "מושלם"):**
- (a) exe/DLL patch לפתיחת arabic=22 → מצב ערבית RTL אמיתי, אבל שביר מול עדכונים + EAC כבוי
  (offline-only) + סיכון; R&D כבד.
- (b) visual pre-reversal בחריץ english (FriBidi + pre-wrap) → לא מושלם ב-wrap דינמי/טקסט מעורב.
- (c) לסיים LZ4LW ולבדוק content-bidi אמפירית — סיכוי נמוך מאוד (הארכיטקטורה language-gated).
- (d) **לעצור** — WD2-PC לא מתאים ל"מושלם". (מומלץ תחת הרף שנבחר.)

**ההתקנה שוחזרה:** HKLM Language→en-US, GamerProfile→en-US(3). גיבויים ב-`F:\WD2_lang_backup\`.

---

## עדכון — מבחן content-bidi + מצב LZ4LW (2026-06-16, המשך)

המשתמש ביקש לסיים LZ4LW + מבחן content-bidi (לסגירה 100%). מצב:

### כלים שנבנו ועובדים
- **Gibbed.WatchDogs2.Unpack/Pack** נבנו (`.NET 8 SDK`, ref-assemblies, submodules:
  Gibbed.IO/ProjectData/NDesk.Options/XCompression). filelists חוברו ל-`bin\projects\Watch Dogs 2\files`.
- ה-Unpack עובד מלא על entries **None (stored)** ו-**single-block LZ4LW** (מאומת: עשרות קבצי
  `.xbt`/`.xml`/`.console` חולצו נכון). census: **4,895 קבצי LZ4LW ב-common.dat**.

### LZ4LW — המבנה פוצח חלקית (פענוח מלא לא נסגר)
- decompressed rml **חייב להתחיל ב-`0x00`** (XmlResourceFile) — עוגן אימות.
- מבנה: **[varint header (high-bit continuation)][LZ4 block סטנדרטי]** — קבצי בלוק-יחיד
  מפענחים **נקי לחלוטין** (start אחרי ה-varint → unc מדויק, צריכת כל הקלט, סיום על literals).
  דוגמאות: `video.xbt` hdr=`fc 03`→684B; `square_32x32.xbt` hdr=`80 04`→684B.
- **מה שלא נסגר:** סמנטיקת ה-varint (לא תואמת ישירות גודל-דחוס/מפוענח), והתיחום של
  קבצים **רב-בלוקיים** (כמו oasisstrings: 1.85MB→5.06MB). נשללו ~8 השערות: whole-entry LZ4,
  zlib-style ushort[8] header, fixed-size blocks (reset+linked), chunked-by-size (H=1-4),
  large-window-offset-flag, varint=unc/comp chunk. ה-block הראשון מפענח 59,114B תקין מ-byte1
  ואז desync (גבול-בלוק/header). פענוח מלא ודאי דורש **disassembly של ה-decompressor
  ב-`Disrupt_64.dll`** (scheme byte 2, FAT5 v11) — משימת RE של שעות. סקריפטי הניתוח:
  `work/crack_lz4lw*.py`; raw samples ב-`extract/raw_oasis/`.

### מבחן content-bidi — חסום + צפוי שלילי
- המבחן (להזריק עברית+גליפים לחריץ english, לראות אם מרונדר RTL) **חסום על פענוח LZ4LW
  המלא** (צריך לחלץ+לערוך את oasisstrings).
- **צפוי שלילי בהסתברות גבוהה:** המנוע בוחר פונט+כיוון **לפי שפה** (ארכיטקטורת per-language
  fonts: arabic/japanese/chinese/korean/default), לא לפי תוכן Unicode — מאושש ע"י 3 הרצות-שפה
  כושלות + עיצוב ה-DLL. עברית בחריץ english צפויה LTR (+ריבועים, אין גליפים עבריים ב-default).

### מסקנה סופית (תחת "מושלם בלי ויתור"): **NO-GO נשאר.**
הראיות ל-NO-GO **אינן תלויות** בסגירת LZ4LW: ערבית נעולה ב-EXE (3 הרצות), וה-RTL
language-gated. סגירת LZ4LW + מבחן content-bidi הם **שעות RE נוספות לתוצאה צפויה-שלילית**.
הדרך היחידה ל-RTL אמיתי = exe/DLL patch (שביר + EAC) — מפר את הרף. מומלץ לעצור.

---

## ⛔→✅ היפוך הפסיקה ל-**GO** — RTL אמיתי הוכח אמפירית (2026-06-16, פריצת דרך)

**ה-NO-GO לעיל היה שגוי.** הוא נשען על 3 הרצות שבהן ניסיתי להחליף שפה דרך **הרישום/GamerProfile
ידנית** — הדרך הלא-נכונה. המשתמש גילה ש**ערבית כן ניתנת לבחירה מתוך המשחק** ("Settings → Written
Language → Arabic") ושאז **הכתוביות מרונדרות בערבית RTL מושלם** (אומת בצילום מסך תוך-משחקי:
"أهلا بك في متجر Plainstock. ستجد كل ما تحتاجه!..."). זה מפיל את הבלוקר המרכזי:

- **ה-Disrupt engine כן מבצע RTL/bidi reordering** לחריץ הערבי. צוואר הבקבוק היחיד שהיה מסומן
  "לא הוכרע" — **הוכרע חיובית.** אין צורך ב-pre-reversal/visual-bidi.
- **בורר השפה לא נעול ב-EXE** (טעות קודמת): `WD2_GamerProfile.xml` → `TextLanguage2="22"` =
  ערבית, מתקבל ומיושם. enum: english=3, arabic=22.

### היכן הטקסט באמת חי (מופה אמפירית ע"י דריסות מבוקרות + handle-probe)
המשחק (process `WatchDogs2`, בתיקיית `bin`) פותח בזמן ריצה את `common.dat`+`patch.dat`+
`patch2.dat` (אומת ב-probe של file-locks; `installpackage.dat` **לא** נטען ב-runtime).

| מערכת | מקור הטקסט בפועל | ניתן לעריכה? |
|---|---|---|
| **כתוביות / דיאלוג / נרטיב** (הגוף העיקרי) | **`languages\main_<lang>.loc`** (פורמט `SL`, Huffman) — נקרא לפי `TextLanguage2` (=22→`main_arabic.loc`) | כן, אבל דורש **encoder ל-.loc** |
| `oasisstrings.rml` (לכל שפה) | **לא נקרא ב-runtime כלל** — דריסת ה-rml האנגלי *וגם* הערבי (ל-Hebrew/arabic, stored תקין) **לא שינתה שום דבר**. ה-`.rml` הוא מקור build-time בלבד; ה-`.loc` מקומפל ממנו | לא רלוונטי |
| **תפריט ראשי / frontend** ("Continue/New Game", "ESC Skip") | **נעול-אנגלית** — לא עוקב אחרי `TextLanguage`, לא נקרא מ-`.loc` ולא מ-`.rml` (דריסת `main_english.loc`→`main_arabic.loc` לא שינתה את התפריט). כנראה מוטמע ב-`Disrupt_64.dll`/מקור frontend נפרד | לא (ללא DLL patch) |

**מנגנון פריסה הוכח:** fat-redirect — append ל-`.dat` + שכתוב ה-entry ב-`.fat` (stored, scheme=0,
ב-v11 חובה `UncompressedSize=0`; ראה `SanityCheckEntry`). גיבויים: `F:\WD2_lang_backup\*.fat.bak`
+ `*.dat.origsize`. ההתקנה **הוחזרה ל-pristine** אחרי הניסויים.

### פורמט ה-.loc (`main_arabic.loc`, 816,656B) — מובן מלא
מ-`ahmet-celik/watch-dogs-loc-tool` (C#, שוכפל ל-`c:\tmp\wd-loc-tool`, `Loc.cs`):
- header(12B): `magic"SL"=0x4C53`(2) · `version=1`(2) · `language=22`(2) · `table_length=82`(2) ·
  `tree_offset`(4, =647084).
- 82 `Table` (`first_id u32` + `offset_length u32`: 28b offset|4b subtable-count) → `SubTableMeta`
  (delta-id, size, escapes 0xF0/0xDC) → `SubTableIds` (בלוקים של 64 ids, offsets, pseudo-ids,
  `lo/hi` בביטים) → bitstream.
- Huffman ברוחב-ביט משתנה (8/10/12/14/16/24) לפי 12 ערכי `tree_meta`; עץ ב-`tree_offset`, nodes
  4B (leaf ≤0xFFFF = UTF-16; אחרת 2×16b מצביעי-ילד).

### מה שנותר לתרגום מלא (פרויקט רב-יומי, כמו CP2077/SM2)
1. **encoder/repacker ל-.loc** — ה-decoder קיים (פורט ל-`c:\tmp\wd-loc-tool`); אין repacker פומבי
   מאומת ל-WD2 (ה-recon אישר). זה ה-**gating task**: לבנות Huffman-encoder + לשחזר את הטבלאות/offsets
   ולאמת round-trip (decode∘encode = זהה) מול `main_arabic.loc`. אפשר ב-Python (offline, ללא המשחק).
2. **הזרקת גליפים עבריים** לפונט הערבי (`ui\fonts\helveticaneuelt_w1g_65_md_arabic.ffd`+atlas) דרך
   FFDConverter — בלי זה הטקסט = ריבועים.
3. **תרגום EN→עברית** של הקורפוס (pipeline ה-LM הסטנדרטי; ה-EN source = `main_english.loc`).
4. repack → fat-redirect deploy → `-eac_launcher` (offline) → אימות in-game.

### הוורדיקט המעודכן: **GO** (אפשרי, "פרפקט" בר-השגה לכתוביות+נרטיב)
תרגום עברי RTL נקי של **הכתוביות, הדיאלוג, ורוב הטקסט התוך-משחקי** — **בר-השגה ומושלם** (ה-RTL של
המנוע עובד; הערוץ זוהה). מגבלה ידועה אחת: **התפריט הראשי/frontend יישאר אנגלית** (נעול, דורש DLL
patch שמפר את רף ה"פרפקט" + מתנגש ב-EAC — לא שווה). זו מגבלה שולית (התפריט הוא חלק זעיר).
**ה"קרקע מוכנה": ההיתכנות הוכחה, הערוץ מופה, מנגנון הפריסה עובד, פורמט ה-.loc מובן.** המשימה הבאה
היחידה החוסמת = בניית ה-encoder ל-.loc.

## מסמכים קשורים
- באותה תיקייה: [[games/watchdogs2/PIPELINE|PIPELINE]], [[games/watchdogs2/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#watchdogs2|CLAUDE_INDEX_games]]
