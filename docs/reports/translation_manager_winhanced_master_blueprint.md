# 📘 דוח ארכיטקטורה ותוכנית אב: פלטפורמת העל המאוחדת
## TranslationManager × Winhanced (Master Blueprint)

> **תאריך:** 30 ביולי 2026  
> **מבוסס על:** ניתוח מעמיק של קובץ הפרויקט `CLAUDE.md` והקוד של **TranslationManager**, יחד עם יכולות **Winhanced**.

---

## 1. ניתוח מעמיק של TranslationManager (לפי CLAUDE.md)

מתוך ניתוח מעמיק של קובץ `CLAUDE.md`, **TranslationManager** היא אינה תוכנת תרגום רגילה, אלא **מערכת הנדסה לאחור (Reverse Engineering) והזרקת בינאריים מתקדמת ביותר למשחקי AAA**:

```mermaid
graph TD
    subgraph "TranslationManager Core Ecosystem (CLAUDE.md)"
        A1["🎮 Game Lab / Binary Injectors<br/>(Skyrim, AC Odyssey/Origins, FC5/6, RDR2, CP2077)"]
        A2["🌐 /translate Community Portal<br/>(99k+ Skyrim, 59k+ Odyssey, 28k+ Origins)"]
        A3["🚁 Multi-Provider Fleet Ops<br/>(Automated NIM / Llama-3.1-70b / OpenAI AI Engines)"]
        A4["🎨 Custom UI / Launcher Designer<br/>(React/Vite + Eel + 4-Level Glass/Anim)"]
        A5["🖥️ Fleet Dashboard & Android App<br/>(Live Telemetry, Worker Monitoring)"]
    end
```

### יכולות הליבה הקיימות ב-TranslationManager:
1. **מנועי הזרקה ייחודיים לפי מנועי משחק (Engine-Specific Binary Patchers):**
   * **Bethesda Creation Engine (Skyrim SE):** הזרקת גופנים (DefineFont3 SWF), תרגום קובצי `.STRINGS`/`.ILSTRINGS`/`.DLSTRINGS`, והזרקת `translate_english.txt` תוך טיפול ב-VISUAL Bidi וסנכרון תפריט ה-Launcher (`SkyrimSELauncher.exe`).
   * **Ubisoft AnvilNext 2.0 (AC Odyssey / Origins):** פענוח קובצי `.forge`, חילוץ וקידוד מחדש ב-Oodle (Mermaid/Kraken), הזרקת גופני Heebo לתוך DINPro/Friz Quadrata, pre-wrapping אוטומטי של שורות לפי רוחב פיקסלים (`text_em`), וזיהוי חבילות שפה (`LocalizationPackage_Arabic` / `ar-AR`).
   * **Ubisoft Dunia 2 (Far Cry 5 / 6):** פענוח קובצי `.fat`/`.dat`, קידוד Scheme-2/Zlib, והזרקת גופני `.ffd`+`.xbt`.
   * **Rockstar RAGE (RDR2/GTA) & CDPR REDengine (CP2077):** מנועי תרגום מורכבים למשחקי ענק.
2. **תשתית ה-Fleet Ops & Community Portal (`/translate`):**
   * צי תרגום אוטומטי מבוסס AI Multi-Provider (NIM, Llama-3.1-70b, OpenAI) שמריץ אלפי שורות במקביל.
   * אתר קהילתי (`/translate`) לניהול תיקונים, Gender Oracle (זיהוי מגדר דובר/פונה מרוסית/פולנית), ופתרון קונפליקטים.
3. **אוטומציה ובדיקות אוטונומיות (Autonomous In-Game Proofs):**
   * הרצת משחק אוטומטית ברקע (`autocheck.py`), לכידת מסך ב-DirectX (`dxcam`), זיהוי טקסט ואימות תקינות הפונטים וה-Bidi בלייב, וסגירה שקטה ללא חלונות קופצים.

---

## 2. חזון פלטפורמת העל (Master Unified Platform)

הפלטפורמה המאוחדת תיקח את **כל יכולות ה-Reverse Engineering, ה-Fleet והתרגום מ-TranslationManager**, ותשלב אותן בתוך **מנוע הביצועים, חנות המחירים, מצב הבקר (Handheld) וה-Smart Launch מ-Winhanced**.

```mermaid
graph TD
    subgraph "🛒 1. Commerce & Discovery (Winhanced)"
        B1["השוואת מחירים (Steam / Epic / GOG / Xbox)"]
        B2["חנות מובנית (store_seed.db) + Wishlist"]
    end

    subgraph "🎮 2. Universal Library & Handheld (Winhanced + TM)"
        C1["ספריית משחקים מאוחדת + אמולטורים"]
        C2["מצב בקר קונסולי (10ft Living Glass UI)"]
        C3["שליטת חומרה (TDP, RyzenAdj, מאווררים, RTSS)"]
        C4["Smart Launch Watcher (חסימת UAC / EULA / AntiCheat)"]
    end

    subgraph "🌐 3. Translation, Modding & AI Engine (TranslationManager)"
        D1["Game Lab — תרגום משחקים בלחיצה אחת (BSA/Forge/SWF Injectors)"]
        D2["מנהל מודים, DLCs ופלאגינים"]
        D3["In-Game Live Overlay (OCR Real-Time Translation)"]
        D4["סנכרון צי תרגום (Fleet Ops) + אתר /translate"]
    end

    B1 --> C1
    B2 --> C1
    C1 --> D1
    C1 --> D2
    C1 --> D3
    D4 <--> D1
```

---

## 3. ארכיטקטורת המערכת ההיברידית (Hybrid Core Architecture)

כדי לאבד שום יכולת קיימת ולשמור על ביצועי שיא, המערכת תתבסס על **ארכיטקטורה משולבת של C# Host + Python Service**:

```mermaid
graph LR
    subgraph "Layer 1: Frontend UI"
        UI["🎨 Unified UI Host<br/>(React / Vite + WinUI 3 Shell)<br/>Custom Themes / Living Glass / Launcher Designer"]
    end

    subgraph "Layer 2: Native System Host (C# .NET 8 / C++)"
        CS["⚡ C# System & HW Controller"]
        CS --> HW["🛠️ Hardware Controller (RyzenAdj / PawnIO / RTSS)"]
        CS --> SL["🌊 Smart Launch Watcher (WinEventHook / Window Sweep)"]
        CS --> GP["🎮 Gamepad Engine (SDL3 / XInput Navigation)"]
    end

    subgraph "Layer 3: Game Lab & Translation Microservice (Python)"
        PY["🐍 Python Translation & Patch Engine"]
        PY --> INJ["🧩 Binary Injectors (bsa.py, forge.py, swf.py, oodle)"]
        PY --> FLT["🚁 Fleet Ops Push/Pull & /translate API"]
        PY --> OCR["👁️ In-Game Live OCR Engine"]
    end

    UI <--> CS
    CS <--> PY
```

---

## 4. הממשק והחוויה הויזואלית (UI/UX Design)

הממשק יציע **שני מצבי עבודה מותאמים מראש**:

### 💻 4.1 מצב דסקטופ (Desktop Mode)
הממשק הקיים והמוכר של **TranslationManager** (עם ה-Launcher Designer, Icon Manager, וניהול המשחקים), בתוספת:
* **טאב Store (חנות):** השוואת מחירים בזמן אמת בין Steam, Epic Games, GOG ו-Xbox.
* **פאנל Fleet Ops:** מעקב בלייב אחר התקדמות צי התרגום (כמו ב-`fleet_dashboard`).
* **Game Lab מורחב:** כלי דיאגנוסטיקה, בדיקת גופנים (Preview offline), וניהול מודים.

### 🎮 4.2 מצב קונסולה/בקר (Handheld Console Mode - 10ft UI)
מצב מסך מלא מותאם בקר (ROG Ally, Legion Go, Xbox Controller):
* **Living Glass UI:** רקעי זכוכית שקופים, אפקטי זוהר (Bloom), ואנימציות Lottie.
* **ניווט מלא בסטיק ובכפתורי Bumpers (LB/RB).**
* **כרטיס משחק חכם:** מציג תמונת Cover Art מ-SteamGridDB, מחיר עדכני, **וסטטוס תרגום בלחיצה אחת**.

---

## 5. מפרט פיצ'רים מפורט (Feature Specification)

### 🛒 5.1 מנוע החנות והשוואת מחירים (Store & Price Aggregator)
* **קטלוג מקומי מהיר:** מבוסס על `store_seed.db` (167 MB, מתוך Winhanced) המאפשר עיון במשחקים גם ללא חיבור לרשת.
* **השוואת מחירים בזמן אמת:** שליפת מחירים מ-Steam Store API, Epic Games, GOG ו-Game Pass.
* **כפתור "קנה והתקן":** מעביר ישירות לחנות הזולה ביותר, ולאחר ההתקנה המשחק מזוהה אוטומטית בספרייה.

### 🎮 5.2 ספרייה מאוחדת ו-Smart Launch Watcher
* **זיהוי אוטומטי:** סריקת Steam, Epic, GOG, Xbox, אמולטורים (22+ פלטפורמות דרך `EmulatorRules.json`) ואפליקציות.
* **Smart Launch Watcher (חסימת חוסמים):** מעקב אחר חלונות UAC, התקנות DirectX/VC++, אישורי EULA, ומסכי התחברות של Launchers כדי לספק הפעלה חלקה.

### 🌐 5.3 מנוע התרגומים וההזרקות המתוחכם (Game Lab)
* **One-Click Hebrew Patching:** בלחיצת כפתור אחת (גם מהבקר), המערכת מפעילה את מנוע הפייתון הקיים ב-TranslationManager:
  * **Skyrim SE:** הזרקת `fonts_en.swf` (Heebo/Frank Ruhl), עדכון `translate_english.txt` וקובצי `.STRINGS`, וטיפול ב-VISUAL Bidi + תרגום ה-Launcher (`SkyrimSELauncher.exe`).
  * **AC Odyssey / Origins:** פענוח קובצי `.forge`, קידוד Oodle, pre-wrapping אוטומטי (`aor_rtl.to_visual_wrapped`), והזרקת גופנים.
  * **Far Cry 5 / 6:** הזרקת גופני `.ffd`/`.xbt` וקידוד Scheme-2.
* **אימות אוטונומי (Autonomous Proof):** הרצת בדיקה שקטה ברקע (`dxcam` capture) לאימות שהפונט וה-Bidi נראים מושלם במשחק לפני שהמשתמש משחק.

### 🤖 5.4 אינטגרציית Fleet Ops וסנכרון קהילה (`/translate`)
* **חיבור מלא לאתר הקהילה (`/translate`):** כרטיסי המשחקים מציגים את התקדמות התרגום הקהילתי בזמן אמת.
* **Gender Oracle:** שימוש בנתוני המגדר (מרוסית/פולנית) בעת הורדת התרגומים החדשים.
* **סנכרון צי (Fleet Push/Pull):** התוכנה יכולה לתרום כוח עיבוד מקומי (Community Compute) או למשוך את העדכונים האחרונים מצי ה-AI.

### ⚡ 5.5 שליטת חומרה (Hardware & TDP Control)
* **RyzenAdj Integration:** שליטה בזמן אמת ב-PPT Fast/Slow Limit, STAPM, וטמפרטורות מעבד.
* **עקומות מאווררים ופרופילים חכמים (Smart Profiles):** פרופיל מותאם לכל משחק שמחיל אוטומטית את צריכת החשמל האידיאלית.

### 👁️ 5.6 In-Game Live Overlay (שכבת-על תוך כדי משחק)
לחיצה על מקש קיצור או כפתור Guide בבקר פותחת שכבת-על:
1. **נתוני חומרה (RTSS):** תצוגת FPS, טמפרטורה, וניצול סוללה.
2. **TDP Quick Switch:** שינוי מצב חשמל (סוללה / ביצועים) תוך כדי משחק.
3. **Live OCR Translator:** זיהוי טקסט על המסך בזמן אמת ותרגומו לעברית בשכבה שקופה מעל המשחק.

---

## 6. תרחישי שימוש מקצה לקצה (End-to-End Scenarios)

```mermaid
sequenceDiagram
    actor User as 👤 משתמש (בקר Handheld)
    participant UI as 🎨 Console Mode UI
    participant HW as ⚡ C# Hardware Engine
    participant PY as 🐍 Python Game Lab
    participant Net as 🌐 Store / Fleet API
    participant Game as 🎮 Game Process

    User->>UI: עורך עיון בחנות / בספרייה המאוחדת
    Net-->>UI: מציג מחיר זול ב-Epic + סטטוס: "תרגום עברית זמין (99.8%)"
    User->>UI: לוחץ "התקן ותרגם" (כפתור A בבקר)
    UI->>PY: הפעלת מנוע הזרקת הקבצים (BSA/Forge Injector)
    PY->>PY: השתלת פונטים, Bidi pre-wrapping וקובצי שפה
    PY-->>UI: תרגום הותקן בהצלחה!
    User->>UI: לוחץ "הפעל משחק"
    UI->>HW: הפעלת Smart Launch Watcher + פרופיל TDP (15W)
    HW->>Game: הרצת המשחק וחסימת חלונות קופצים
    User->>Game: משחק במשחק בעברית מלאה!
```

---

## 7. מטריצת יתרונות: המצב הקיים מול הפלטפורמה המשולבת

| רכיב / פיצ'ר | TranslationManager הקיים | Winhanced | **הפלטפורמה המאוחדת** |
|---|---|---|---|
| **מנועי הזרקה למשחקי AAA (BSA, Forge, FFD, SWF)** | ✅ **בעלת המנועים המתקדמים ביותר** | ❌ אין בכלל | ✅ **משולב ב-Game Lab** |
| **צי תרגום AI (Fleet Ops) ואתר `/translate`** | ✅ **מערכת לייב עובדת** | ❌ אין | ✅ **סנכרון מלא בלייב** |
| **מצב בקר מותאם (Handheld 10ft UI)** | ❌ אין (מיועד לעכבר/מקלדת) | ✅ מצוין | ✅ **תמיכה מלאה בבקר** |
| **שליטה בחומרה (TDP / RyzenAdj / מאווררים)** | ❌ אין | ✅ מצוין | ✅ **שליטה מלאה בחומרה** |
| **חנות והשוואת מחירים (Cross-Store)** | ❌ אין | ✅ מותקן (167MB DB) | ✅ **חנות השוואת מחירים** |
| **Smart Launch Watcher (חסימת חוסמים)** | ⚠️ חלקי (בדיקות שקטות) | ✅ מתקדם | ✅ **מלא** |
| **עיצוב מותאם (Launcher Designer / Icons)** | ✅ **מערכת מקיפה קיימת** | ⚠️ מוגבל | ✅ **גמישות עיצובית מלאה** |

---

## 8. סיכום והמלצה מעשית

השילוב בין **TranslationManager** ל-**Winhanced** יוצר מוצר שאין לו מתחרים בשוק הגיימינג:
* מחד, **העוצמה הטכנולוגית של TranslationManager** בפיצוח מנועי משחק, הזרקת גופנים, ניהול Bidi וצי ה-AI.
* מאידך, **חוויית המשתמש והביצועים של Winhanced** בספרייה מאוחדת, חנות מחירים, מצב בקר ובקרת חומרה.

### הצעד הראשון המומלץ:
להמשיך להשתמש ב-Python וב-Web Frontend הקיים של `TranslationManager` כבסיס, ולהוסיף לו **שירות C# קטן ברקע (C# Helper Service)** שיטפל ב-TDP (RyzenAdj), בקרת בקר (Gamepad Navigation) ו-Smart Launch Watcher. באופן הזה תקבל את **כל היתרונות של Winhanced** מבלי לשנות את קוד התרגומים וההזרקות העוצמתי שבנית!
