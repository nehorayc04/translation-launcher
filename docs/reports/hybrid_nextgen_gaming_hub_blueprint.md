# 🚀 ארכיטקטורה ותוכנית אב: הפלטפורמה המשולבת (Ultimate Gaming & Translation Hub)

> **תאריך:** 30 ביולי 2026  
> **חזון:** איחוד מוחלט בין היתרונות של **Winhanced** (ספרייה מאוחדת, חנות מחירים, מצב בקר, בקרת חומרה ו-Sleep/Wake) לבין היתרונות של **TranslationManager** (תרגום משחקים אוטומטי, התקנת מודים, מנוע AI ועיצוב מותאם אישית) לכדי **פלטפורמה אחת עוצמתית**.

---

## 1. חזון העל של הפלטפורמה המשולבת

הפלטפורמה החדשה לא רק מציגה משחקים או מנהלת תרגומים — היא תהיה **אקו-סיסטם גיימינג שלם**:

```mermaid
graph TD
    subgraph "🛒 1. Discovery & Buying"
        A1["השוואת מחירים (Steam/Epic/GOG)"]
        A2["חנות מובנית + Wishlist"]
    end

    subgraph "🎮 2. Unified Launcher & Handheld"
        B1["ספריית משחקים מאוחדת + אמולטורים"]
        B2["מצב בקר מלא (Console UI)"]
        B3["שליטת חומרה (TDP, מאווררים, RTSS)"]
    end

    subgraph "🌐 3. Translation & Modding Engine"
        C1["תרגום משחקים בלחיצה אחת (One-Click)"]
        C2["מנהל מודים ו-DLCs"]
        C3["תרגום מסך בזמן אמת (OCR/AI Overlay)"]
    end

    A1 --> B1
    A2 --> B1
    B1 --> C1
    B1 --> C2
    B1 --> C3
```

---

## 2. הארכיטקטורה הטכנית ההיברידית (The Hybrid Core)

כדי לקבל גם את הביצועים של C# וגם את הגמישות של Python/Web, המערכת תתבסס על **ארכיטקטורת מיקרו-שירותים מקומית (Local Microservices)**:

```mermaid
graph LR
    subgraph "Frontend Layer (UI)"
        UI["🎨 Web UI / WinUI 3 Host<br/>(Living Glass Design / Custom Themes)"]
    end

    subgraph "Core Service (C# .NET 8)"
        CS["⚡ Native Host Manager"]
        CS --> HW["🛠️ Hardware Controller (RyzenAdj / PawnIO)"]
        CS --> GP["🎮 Gamepad Engine (SDL3 / XInput)"]
        CS --> SL["🌊 Smart Launch Watcher"]
    end

    subgraph "Translation & Mod Engine (Python)"
        PY["🐍 Python Translation Microservice"]
        PY --> TR["🌐 AI Translation & OCR Engine"]
        PY --> MD["🧩 Mod & Patch Installer (Menyoo / Game Lab)"]
    end

    UI <--> CS
    CS <--> PY
```

### היכן כל לוגיקה תפעל?
1. **C# Core Host:**
   * ניהול תהליכים, Smart Launch Watcher (זיהוי UAC/AntiCheat).
   * ניטור חומרה בזמן אמת, שליטה ב-TDP ובמאווררים.
   * קריאת תשומת בקר (Gamepad Input) ברמה נמוכה (SDL3/XInput).
2. **Python Engine Service:**
   * מנועי התרגום (AI, Google Translate, DeepL, parsing של קובצי משחק).
   * התקנת מודים, חילוץ ארכיונים, ניהול DLCs ופלאגינים.
3. **Frontend UI Layer (Web/React או WinUI 3):**
   * תצוגת זכוכית שקופה (Living Glass), ערכות נושא מותאמות אישית, תמיכה במסך מגע ובקר.

---

## 3. מבנה הממשק והחוויה הויזואלית (UI/UX Design)

הממשק יכלול **שני מצבי תצוגה בלחיצת כפתור אחת**:

```mermaid
stateDiagram-v2
    [*] --> DesktopMode: אתחול ב-PC רגיל
    [*] --> ConsoleMode: אתחול ב-Handheld / בקר מחובר
    
    state DesktopMode {
        [*] --> ExpandedLibrary: תצוגה מורחבת (מקלדת/עכבר)
        ExpandedLibrary --> ModTranslationStudio: עריכת מודים ותרגומים
    }
    
    state ConsoleMode {
        [*] --> BigPictureUI: תצוגה מותאמת בקר (10ft Experience)
        BigPictureUI --> QuickGameLaunch: הפעלה מהירה + TDP + תרגום אוטומטי
    }
    
    DesktopMode --> ConsoleMode: לחיצה על כפתור Guide / Toggle
    ConsoleMode --> DesktopMode: יציאה למצב שולחן עבודה
```

### מסכי הליבה בממשק:

1. **Dashboard & Unified Library (ספרייה מאוחדת):**
   * כרטיס לכל משחק המציג:
     * **תמונת HD / Cover Art** מ-SteamGridDB.
     * **תג תרגום:** "בעברית" / "זמין לתרגום בלחיצה אחת" / "מודים מותקנים".
     * **תג ביצועים:** דירוג FPS צפוי במכשיר שלך.

2. **כרטיס משחק מורחב (Game Hub Detail):**
   * **כפתור "הפעל משחק"** (בצבע בולט).
   * **כפתור "תרגם משחק"** — בלחיצה אחת התוכנה מורידה ומתקינה את התרגום המתאים.
   * **כפתור "ניהול מודים"** — התקנת מודים מ-Game Lab.
   * **פאנל השוואת מחירים** — אם המשחק לא מותקן, מוצג המחיר הזול ביותר (Steam / Epic / GOG).

3. **In-Game Overlay (שכבת-על תוך כדי משחק):**
   * נפתחת בלחיצה על כפתור ה-Xbox/Guide בבקר:
     * **TDP & Fan Control:** שינוי צריכת חשמל בלייב.
     * **תרגום מסך בזמן אמת (Live OCR Translation):** תרגום דיאלוגים מוקפצים על המסך בלייב.
     * **FPS Overlay (RTSS):** תצוגת נתוני חומרה.

---

## 4. תרחישי שימוש מקצה לקצה (End-to-End User Scenarios)

### 🛒 תרחיש 1: גילוי, השוואת מחירים וקנייה

1. המשתמש נכנס לכרטיסייה **"Store"** בממשק.
2. המערכת מציגה משחק מוביל עם השוואת מחירים בזמן אמת:
   * Steam: $29.99 | Epic Games: $19.99 | GOG: $24.99
3. המשתמש לוחץ "קנה ב-Epic Games" והמערכת פותחת את תהליך הרכישה המאובטח.
4. לאחר ההורדה, המשחק מופיע **אוטומטית** בספרייה המאוחדת.

---

### 🌐 תרחיש 2: תרגום בלחיצה אחת (One-Click Game Translation)

```mermaid
sequenceDiagram
    actor User
    participant UI as 🎨 Frontend UI
    participant CS as ⚡ C# Core
    participant PY as 🐍 Python Engine
    participant Game as 🎮 Game Process

    User->>UI: לוחץ "תרגם לעברית" בכרטיס המשחק
    UI->>PY: בקשת תרגום למזהה המשחק
    PY->>PY: הורדת פאץ' התרגום / הפעלת מנוע AI
    PY->>PY: השתלת קובצי השפה בתיקיית המשחק
    PY-->>UI: תרגום הותקן בהצלחה!
    User->>UI: לוחץ "הפעל משחק"
    UI->>CS: הפעלת המשחק via Smart Launch
    CS->>Game: הרצת EXE + חסימת חלונות קופצים
```

---

### 🎮 תרחיש 3: משחק במכשיר Handheld בדרכים עם תרגום מסך בלייב

1. המשתמש מפעיל את מכשיר ה-ROG Ally / Legion Go.
2. התוכנה עולה ב-**Console Mode** במסך מלא עם סאונד פתיחה ואנימציה.
3. המשתמש בוחר משחק בעזרת הסטיק של הבקר ולוחץ A.
4. **Smart Launch Watcher** מטפל בחלונות UAC ו-AntiCheat ברקע.
5. תוך כדי משחק, המשתמש נתקל בטקסט באנגלית:
   * לוחץ על צירוף מקשים בבקר (למשל `LB + RB + D-Pad Down`).
   * שכבת-על (Overlay) מבצעת **OCR מתקדם ומציגה תרגום לעברית מעל המסך**.
   * המשתמש משנה TDP ל-15W כדי לחסוך בסוללה וחוזר לשחק.

---

## 5. מפת דרכים ליישום (Implementation Roadmap)

```mermaid
gantt
    title תוכנית עבודה לשילוב הפלטפורמות
    dateFormat  YYYY-MM-DD
    section שלב 1: תשתית
    בניית ה-Hybrid Host (C# + Python Service)   :active, a1, 2026-08-01, 30d
    שלוב ספריות ה-UI ועיצוב Living Glass       :a2, after a1, 20d
    section שלב 2: ספרייה וחנות
    ספרייה מאוחדת (Steam/Epic/GOG)              :b1, after a2, 25d
    מנוע השוואת מחירים וחנות                    :b2, after b1, 15d
    section שלב 3: תרגום ומודים
    שילוב מנוע התרגומים וה-AI מ-TranslationManager :c1, after b2, 25d
    מנהל מודים ו-Game Lab                         :c2, after c1, 20d
    section שלב 4: Handheld & Performance
    תמיכת בקר, TDP דינמי ו-Smart Launch Watcher  :d1, after c2, 25d
    בדיקות מקיפות ו-Release Candidate             :d2, after d1, 15d
```

---

## 6. סיכום ומטריצת יתרונות

| תחום | Winhanced לבד | TranslationManager לבד | **הפלטפורמה המשולבת** |
|---|---|---|---|
| **ממשק מוכוון בקר (Console UI)** | ✅ מצוין | ❌ אין | ✅ **מלא** |
| **תרגום משחקים אוטומטי** | ❌ אין | ✅ מצוין | ✅ **מלא (כולל OCR בלייב)** |
| **התקנת מודים ו-DLCs** | ❌ אין | ✅ מצוין | ✅ **מלא** |
| **השוואת מחירים וחנות** | ✅ כן | ❌ אין | ✅ **מלא** |
| **שליטה בחומרה (TDP/מאווררים)** | ✅ מצוין | ❌ אין | ✅ **מלא** |
| **עיצוב מותאם אישית (Custom Themes)** | ⚠️ מוגבל | ✅ מצוין | ✅ **מלא** |

> [!IMPORTANT]
> **השורה התחתונה:** השילוב בין שתי התוכנות יוצר את **משגר המשחקים (Launcher) המתקדם ביותר למשתמש הדובר עברית** — פלטפורמה שמציעה גם חנות וספרייה מאוחדת, גם שליטה מלאה בחומרה ובבקר, וגם יכולות תרגום והתקנת מודים בלחיצת כפתור אחת.
