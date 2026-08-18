# 🚀 תוכנית-אב חזותית: השילוב המלא — TranslationManager × Winhanced

> **תאריך:** 31 ביולי 2026
> **חזון:** לשמור על ה-DNA של **TranslationManager** (העיצוב שלך + התקנת המודים שלך + הממשק שלך + קניית משחקים)
> ולצקת לתוכו את **כל** יתרונות **Winhanced** — ברמה הכי גבוהה, לא משנה כמה עבודה.
> **סגנון:** עברית קצרה וקולעת, הרבה תרחישים חזותיים עם חצים.

---

## 📋 תוכן

1. [ההבדל בבסיס הפיתוח (התוכנה שלך מול שלהם)](#1)
2. [עקרון השילוב — מה נשמר ומה מתווסף](#2)
3. [הארכיטקטורה המשולבת (שתי בסיסים + UI משותף)](#3)
4. [איך זה ייראה — מסך אחר מסך](#4)
5. [ביצועים — למה השילוב מהיר יותר](#5)
6. [13 תרחישים חזותיים עם חצים](#6)
7. [שיפורים חדשים שנולדים רק מהשילוב](#7)
8. [סיכום + טבלה מרכזית](#8)

---

<a id="1"></a>
## 1. ההבדל בבסיס הפיתוח — התוכנה שלך מול שלהם

`C:\Program Files\Translation Manager\TranslationManager.exe` בנויה אחרת לגמרי מ-Winhanced. זה בדיוק מה שקובע איך מחברים אותן:

```mermaid
graph TD
    subgraph "🐍 שלך — TranslationManager"
        A1["React Frontend<br/>(HTML/CSS/JS)"] <--> A2["QWebChannel Bridge<br/>(Qt WebEngine — production)"]
        A2 <--> A3["Python Core<br/>(מנוע תרגום/מודים/Fleet)"]
        A3 --> A4["Supabase + Cloudflare Worker<br/>+ community-compute"]
        A3 --> A5["PyInstaller + Inno Setup"]
    end
    subgraph "⚡ שלהם — Winhanced"
        B1["WinUI 3<br/>(XAML מקומפל .xbf)"] <--> B2["DirectX / Direct2D<br/>(רינדור נייטיב)"]
        B2 <--> B3["C# .NET 8 Core"]
        B3 --> B4["PawnIO / RyzenAdj<br/>(kernel driver)"]
        B3 --> B5["MSBuild + MSIX<br/>+ שרתים סגורים"]
    end
```

| רכיב | 🐍 שלך (TranslationManager) | ⚡ שלהם (Winhanced) | מה זה אומר לשילוב |
|---|---|---|---|
| **שפת ליבה** | Python 3 | C# (.NET 8) | שתי שפות → נחברן ב-IPC מקומי, לא מאחדים לשפה אחת |
| **ממשק (UI)** | React / Web (CSS גמיש) | WinUI 3 (XAML מקומפל) | ה-Web שלך **גמיש ונייד** → נשאר, מתארח מחדש |
| **מנוע רינדור** | Qt WebEngine (Chromium, GPU-compositing כבוי) | DirectX נייטיב | **פה החולשה** → מעבר ל-WebView2 מואץ-GPU |
| **גשר** | QWebChannel (prod) / Eel (dev) | in-process מנוהל | Python נשאר sidecar, מדבר עם מארח נייטיב |
| **חומרה** | ספריות עיליות (ctypes) | P/Invoke ל-kernel | חומרה נכנסת דרך מארח נייטיב (רק Handheld) |
| **אריזה** | PyInstaller + Inno | MSBuild + MSIX | אריזה משולבת: installer אחד שאורז את שניהם |
| **חוזק-על** | **מנוע הזרקה ל-AAA + Fleet + `/translate`** | **מעטפת נייטיב + חומרה + ספרייה** | כל אחד מביא את החוזק שלו — לא מתחרים |

> **השורה:** שתי התוכנות **משלימות מושלם** — שלך חזקה בעיבוד/תרגום/מודים/AI, שלהם חזקה בנייטיב/חומרה/בקר/ספרייה. אין חפיפה שמכריחה לוותר על משהו.

---

<a id="2"></a>
## 2. עקרון השילוב — מה נשמר ומה מתווסף

ה-DNA שלך נשאר **הבסיס**; יתרונות Winhanced נצקים מסביבו:

```mermaid
graph LR
    subgraph "🔒 נשמר ממך (ה-DNA)"
        K1["🎨 העיצוב שלך<br/>(Living Glass ב-CSS)"]
        K2["🧩 התקנת המודים שלך<br/>(BSA/Forge/SWF/Oodle)"]
        K3["🖥️ הממשק שלך<br/>(React + launcher-designer)"]
        K4["🛒 קניית משחקים<br/>(Supabase + PayPal + DRM)"]
    end
    subgraph "➕ מתווסף מ-Winhanced"
        W1["📚 ספרייה מאוחדת<br/>(Steam/Epic/GOG/Xbox/PS)"]
        W2["🎮 מצב בקר (10ft UI)"]
        W3["💰 השוואת מחירים (₪)"]
        W4["⚡ שליטת חומרה (TDP/מאווררים)"]
        W5["🌊 Smart Launch Watcher"]
    end
    subgraph "🌟 נולד מהשילוב"
        N1["👁️ תרגום-מסך חי (OCR)"]
        N2["🚁 סנכרון Fleet ↔ ספרייה"]
        N3["☁️ ענן PC↔Handheld"]
    end
    K1 --> N1
    K2 --> N2
    W1 --> N2
    W4 --> N3
```

**הכלל:** אף פיצ'ר של Winhanced לא דורש לוותר על משהו שלך. הכול **תוספת**.

---

<a id="3"></a>
## 3. הארכיטקטורה המשולבת — שתי בסיסים + UI משותף

```mermaid
graph TD
    subgraph "🎨 UI משותף (React — 100% שלך, ללא שינוי)"
        UI["העיצוב שלך + כרטיסי משחק + Play/תרגם/מודים/קנה"]
    end
    subgraph "🪟 בסיס 2 — מארח נייטיב דק (.NET / WebView2)"
        HOST["WebView2 מואץ-GPU<br/>(זכוכית + FPS אמיתיים)"]
        HW["חומרה/TDP/בקר/overlay (נייטיב)"]
        TRAY["Tray-daemon קליל (נשאר חי בזמן משחק)"]
        WATCH["Smart Launch Watcher"]
    end
    subgraph "🐍 בסיס 1 — מנוע Python (ה-moat, לא נוגעים)"
        PY["מנוע תרגום/מודים/Fleet/OCR + games/*"]
        STORE["ספרייה + השוואת-מחירים + Supabase"]
    end
    UI --> HOST
    HOST <-->|local IPC: named-pipe / JSON-RPC| PY
    HOST --> HW
    HOST --> WATCH
    PY --> STORE
```

* **בסיס 1 (Python):** כל מנוע התרגום, המודים, ה-Fleet, `/translate`, ה-community-compute — **אפס שינוי**.
* **בסיס 2 (.NET דק):** מארח את ה-React ב-WebView2 (מתקן את בעיית ה-FPS/זכוכית של Qt), ונותן חומרה/בקר/overlay/daemon.
* **UI (React):** נשאר שלך במלואו, רוכב בתוך WebView2. **לא WinUI 3.**

---

<a id="4"></a>
## 4. איך זה ייראה — מסך אחר מסך

### 4.1 מרכז + ספרייה מאוחדת
- כרטיס לכל משחק עם **תמונת HD** (SteamGridDB/IGDB), **תג תרגום** ("בעברית" / "זמין בלחיצה" / "מודים מותקנים"), **תג ביצועים** (דירוג FPS צפוי במכשירך).
- מקורות: Steam + Epic + GOG + Xbox + PS + אמולטורים — **מסך אחד**.

### 4.2 כרטיס משחק מורחב (Game Hub) — ה-DNA שלך
- **הפעל משחק** (בולט) · **תרגם לעברית** (בלחיצה — המנוע שלך) · **ניהול מודים** (Game Lab שלך) · **קנה** (השוואת-מחירים ₪ אם לא מותקן).

### 4.3 שני מצבי-תצוגה (זיהוי אוטומטי)

```mermaid
stateDiagram-v2
    [*] --> Desktop: מחשב + מקלדת/עכבר
    [*] --> Console: בקר / Handheld מחובר
    state Desktop {
        [*] --> Library: ספרייה מורחבת
        Library --> Studio: עריכת מודים ותרגומים (launcher-designer שלך)
    }
    state Console {
        [*] --> BigPicture: 10ft UI (סטיקים + זכוכית)
        BigPicture --> Quick: הפעלה מהירה + TDP + תרגום
    }
    Desktop --> Console: כפתור Guide
    Console --> Desktop: יציאה
```

> **בונוס:** Big Picture כבר בנוי אצלך (`BIG_PICTURE_ENABLED`) — רק כבוי בדגל. ההדלקה כמעט-חינם.

### 4.4 שכבת-על תוך משחק (In-Game Overlay)
- נפתחת בכפתור Guide/Xbox: **TDP + מאווררים בלייב**, **תרגום-מסך חי (OCR)**, **FPS/חומרה (RTSS)**.

### 4.5 הגדרות
- ההגדרות שלך (עיצוב/אנימציה/נתיבי-EXE) **+** לשוניות Winhanced: Controller, Performance (TDP), Integrations (Discord/Streaming), Update Center.

---

<a id="5"></a>
## 5. ביצועים — למה השילוב מהיר יותר (ומספרים אמיתיים)

```mermaid
graph TD
    P1["🪟 WebView2 מואץ-GPU<br/>(זכוכית חלקה — Qt לא נותן)"]
    P2["🌙 השהיה ל-Tray בזמן משחק<br/>(UI כבד מושהה, daemon קטן נשאר)"]
    P3["🏎️ Direct I/O להזרקה<br/>(מהיר ככל שהמוד מאפשר)"]
    P4["🧠 memoization + off-thread<br/>(אין קיפאון בממשק)"]
    P1 --- P2 --- P3 --- P4
```

| שיפור | מה זה נותן | **יעד ריאלי** (לא הייפ) |
|---|---|---|
| **WebView2 מואץ-GPU** | זכוכית + אנימציה חלקה | ה-`backdrop-filter` עובד באמת (Qt חסם אותו) — **מדיד ב-POC** |
| **השהיה ל-Tray בזמן משחק** | פחות RAM/CPU ברקע | ה-UI הכבד מושהה; נשאר daemon בעשרות-MB (לא "<20MB לכול") |
| **Direct I/O להזרקה** | התקנת תרגום מהירה | שניות עד דקות **לפי המוד** (W3 ~6 דק' — לא "3 שניות ל-100GB") |
| **off-thread + memoization** | ממשק לא קופא | פעולות כבדות ברקע (כבר קיים ב-`bridge.py`/`perf_manager`) |
| **overlay נייטיב** | תרגום-מסך תוך-משחק | "שמיש" — לא "0% FPS"; רק משחקים בלי אנטי-צ'יט |

---

<a id="6"></a>
## 6. תרחישים חזותיים עם חצים

### 🛒 תרחיש 1: גילוי → השוואת מחיר → קנייה → הופעה בספרייה
```mermaid
sequenceDiagram
    actor User as 👤 משתמש
    participant UI as 🎨 חנות/ספרייה
    participant PY as 🐍 מנוע Python
    participant Store as 🛒 חנות (Steam/Epic/GOG)
    User->>UI: מעיין בחנות
    UI->>PY: בקשת מחירים למשחק
    PY->>Store: שליפת מחיר (Steam API, ₪)
    Store-->>PY: Steam ₪120 · Epic ₪95 · GOG ₪110
    PY-->>UI: מציג "הזול ביותר: Epic ₪95"
    User->>UI: לוחץ "קנה ב-Epic"
    Store-->>UI: רכישה הושלמה → הופיע בספרייה אוטומטית
```

### 🌐 תרחיש 2: תרגום בלחיצה אחת (המנוע שלך)
```mermaid
sequenceDiagram
    actor User as 👤 משתמש
    participant UI as 🎨 כרטיס משחק
    participant PY as 🐍 Game Lab
    participant Game as 🎮 תיקיית המשחק
    User->>UI: "תרגם לעברית" (כפתור A)
    UI->>PY: מזהה משחק → הורדת פאץ' / הפעלת AI
    PY->>PY: זיהוי מנוע (Skyrim/Anvil/Dunia) → הזרקת Bidi+פונטים
    PY->>Game: השתלת קובצי שפה (Direct I/O)
    PY-->>UI: "התרגום הותקן!"
    User->>UI: "הפעל" → משחק בעברית מלאה
```

### 🎮 תרחיש 3: Handheld במצב בקר עם תרגום
```mermaid
sequenceDiagram
    actor User as 👤 (בקר)
    participant UI as 🎮 Console Mode
    participant Watch as 🌊 Smart Launch
    participant Game as 🎮 משחק
    User->>UI: מדליק Handheld → 10ft UI + סאונד פתיחה
    User->>UI: בוחר משחק בסטיק → A
    UI->>Watch: הפעלה
    Watch->>Watch: חוסם UAC/EULA/AntiCheat אוטומטית
    Watch->>Game: הרצה שקטה בעברית + TDP 15W (חיסכון סוללה)
```

### 👁️ תרחיש 4: תרגום-מסך חי תוך-משחק (ניסיוני)
```mermaid
sequenceDiagram
    actor User as 👤 (בקר)
    participant Game as 🎮 משחק AAA
    participant OV as 🖼️ Overlay נייטיב
    participant OCR as 🧠 OCR + MT
    User->>Game: נתקל בדיאלוג באנגלית
    User->>OV: לוחץ LB+RB+D-Pad
    OV->>OCR: לוכד פריים (dxcam) → OCR → תרגום לעברית
    OCR-->>OV: טקסט מתורגם
    OV->>Game: כתוביות עברית מעל המשחק (רק בלי אנטי-צ'יט)
```

### 🚁 תרחיש 5: סנכרון Fleet ↔ אתר `/translate`
```mermaid
sequenceDiagram
    participant Fleet as 🚁 Fleet AI (רב-ספקי)
    participant Site as 🌐 /translate
    participant Local as 🖥️ התוכנה שלך
    Fleet->>Site: תרגום 1,000 שורות חדשות + Gender-Oracle
    Local->>Site: בדיקת עדכונים קהילתיים
    Site-->>Local: הורדת הפאץ' המעודכן
    Local->>Local: הזרקת השורות החדשות למשחק
```

### 🧩 תרחיש 6: התקנת מוד + בדיקת קונפליקטים (Game Lab שלך)
```mermaid
sequenceDiagram
    actor User as 👤 משתמש
    participant Lab as 🧩 Game Lab
    participant Chk as 🔍 Conflict Checker
    participant Game as 🎮 תיקיית המשחק
    User->>Lab: בוחר מוד
    Lab->>Chk: בדיקת התנגשות ב-BSA/Forge
    Chk-->>Lab: אין קונפליקט
    Lab->>Game: התקנה (עם גיבוי אוטומטי לשחזור)
    Lab-->>User: "המוד הותקן!"
```

### 🧠 תרחיש 7: כניסה למשחק → השהיית UI ל-Tray
```mermaid
sequenceDiagram
    actor User as 👤 משתמש
    participant Watch as 🌊 Smart Launch
    participant UI as 🎨 UI (WebView2)
    participant Daemon as 🌙 Tray-daemon
    User->>UI: "הפעל משחק"
    UI->>Watch: המשחק נפתח
    Watch->>UI: השהיית ה-UI הכבד
    Watch->>Daemon: נשאר תהליך קטן בלבד (RAM נמוך)
    User->>Daemon: המשחק נסגר → התעוררות מהירה
```

### ☁️ תרחיש 8: סנכרון ענן PC ↔ Handheld
```mermaid
sequenceDiagram
    actor User as 👤 משתמש
    participant PC as 🖥️ מחשב
    participant Cloud as ☁️ ענן (Supabase שלך)
    participant HH as 🎮 Handheld
    User->>PC: מסיים שלב (Save + הגדרות תרגום)
    PC->>Cloud: העלאת שמירות + מודים
    User->>HH: מדליק בדרכים
    HH->>Cloud: משיכת השמירות
    HH-->>User: ממשיך בדיוק מאותה נקודה
```

### 🤖 תרחיש 9: אימות אוטונומי ברקע (dxcam) לפני משחק
```mermaid
sequenceDiagram
    participant PY as 🐍 Patcher
    participant Auto as 🤖 Autocheck
    participant DX as 📹 dxcam
    participant User as 👤 משתמש
    PY->>Auto: התרגום הותקן — בדוק
    Auto->>Auto: הרצת המשחק ברקע (ללא חלונות)
    Auto->>DX: לכידת פריים
    DX-->>Auto: תמונה
    Auto->>Auto: אימות פונטים + Bidi
    Auto-->>User: "מאומת 100% בעברית!"
```

### ⚡ תרחיש 10: פרופיל TDP חכם בהפעלה (Handheld)
```mermaid
sequenceDiagram
    actor User as 👤 משתמש
    participant Watch as 🌊 Smart Launch
    participant HW as ⚡ מארח נייטיב (RyzenAdj)
    User->>Watch: הפעלת משחק כבד
    Watch->>HW: החל פרופיל TDP למשחק זה
    HW->>HW: fast/slow limit + עקומת מאוורר
    HW-->>User: ביצועים אופטימליים + סוללה
```

### 🎁 תרחיש 11: משחק חינמי — התראה (בלי auto-claim מסוכן)
```mermaid
sequenceDiagram
    participant Cron as ⏰ שירות רקע
    participant Store as 🛒 Epic/GOG
    participant User as 👤 משתמש
    Cron->>Store: בדיקת חינמיים שבועיים
    Store-->>Cron: נמצא חינמי חדש!
    Cron-->>User: "🎁 משחק חינמי זמין — לחץ לתפיסה" (ידני, בטוח ל-ToS)
```

### 🕹️ תרחיש 12: ניווט מלא בבקר (Console Mode)
```mermaid
graph LR
    Stick["🕹️ סטיק/D-Pad"] --> Focus["מיקוד spatialNav"]
    Focus --> A["A = הפעל/בחר"]
    Focus --> B["B = חזרה"]
    Focus --> Guide["Guide = מעבר Desktop↔Console"]
    A --> Play["▶️ הפעל משחק / תרגם"]
```

### 🟣 תרחיש 13: נוכחות Discord + חברים
```mermaid
sequenceDiagram
    participant App as 🖥️ התוכנה
    participant RPC as 🟣 Discord RPC (pypresence)
    participant Friends as 👥 חברים
    App->>RPC: "משחק ב-Skyrim (עברית)"
    RPC-->>Friends: מציג נוכחות חיה
```

---

<a id="7"></a>
## 7. שיפורים חדשים שנולדים **רק** מהשילוב

דברים שאף אחת מהתוכנות לבד לא נותנת:

```mermaid
mindmap
  root((שילוב = 1+1>2))
    👁️ תרגום כפול
      Offline אפוי (איכות גבוהה — שלך)
      + OCR חי בזמן-אמת (Winhanced-style)
    🚁 ספרייה חכמה-תרגום
      כל משחק בספרייה מסומן: "יש תרגום עברי?"
      תפיסה: קונה → מזוהה → מוצע תרגום מיד
    🎮 מצב-בקר לתרגום
      "תרגם משחק" בכפתור A ב-10ft UI
    ⚡ TDP מודע-תרגום
      פרופיל TDP + פרופיל שפה יחד לכל משחק
    ☁️ ענן אחד
      שמירות + מודים + הגדרות-תרגום מסונכרנים
    🤖 אימות + התקנה
      dxcam מאמת שהתרגום עלה לפני שהמשתמש נכנס
```

- **תרגום דו-שכבתי:** האפוי-offline האיכותי שלך **+** OCR-חי כגיבוי לשורות שלא תורגמו. אף אחד בשוק לא נותן את שניהם.
- **ספרייה מודעת-תרגום:** כל משחק מסומן אם יש לו תרגום עברי — Winhanced אין את המידע הזה, לך יש.
- **פרופיל כפול לכל משחק:** TDP + שפה נשמרים יחד ומופעלים אוטומטית.
- **תפיסת-קנייה:** קונה משחק → מזוהה בספרייה → **מוצע תרגום עברי מיד**.

---

<a id="8"></a>
## 8. סיכום + טבלה מרכזית

### סיכום קצר
1. **הבסיס שונה לגמרי** — שלך Python+Web (גמיש, חזק בעיבוד/תרגום), שלהם C#+WinUI (נייטיב, חזק בחומרה/בקר). **משלימים, לא מתחרים.**
2. **השילוב הנכון = שתי בסיסים + UI שלך:** Python (מנוע) + מארח נייטיב דק (WebView2 → זכוכית+FPS אמיתיים) + React (העיצוב שלך, ללא שינוי). **לא rewrite ל-WinUI 3.**
3. **ה-DNA שלך נשאר הבסיס:** עיצוב + מודים + ממשק + קניית משחקים — ומסביבו נצקים כל יתרונות Winhanced.
4. **הרבה ערך מגיע בלי הבסיס השני בכלל** (ספרייה, מחירים, Console-Mode שכבר בנוי) — הנייטיב נכנס רק לזכוכית/overlay/חומרה.
5. **שיפורים חדשים** (תרגום דו-שכבתי, ספרייה מודעת-תרגום, פרופיל כפול) נולדים **רק** מהשילוב.

### טבלה מרכזית

| פיצ'ר | 🐍 שלך לבד | ⚡ Winhanced לבד | 🌟 **המשולב** |
|---|---|---|---|
| **מנוע הזרקה AAA (BSA/Forge/SWF/Oodle)** | ✅ מתקדם | ❌ | ✅ **מלא** |
| **צי AI + `/translate` + Gender-Oracle** | ✅ | ❌ | ✅ **מסונכרן** |
| **אימות אוטונומי (dxcam)** | ✅ | ❌ | ✅ |
| **העיצוב שלך (launcher-designer)** | ✅ | ⚠️ סגור | ✅ **נשמר** |
| **קניית משחקים + DRM (Supabase/PayPal)** | ✅ | ⚠️ | ✅ **נשמר** |
| **ספרייה מאוחדת (Steam/Epic/GOG/Xbox/PS)** | ⚠️ חלקי | ✅ | ✅ **מלא** |
| **מצב בקר (10ft UI)** | ⚠️ כבוי בדגל | ✅ | ✅ **מודלק+לוטש** |
| **השוואת מחירים (₪)** | ❌ | ✅ | ✅ **מלא** |
| **שליטת חומרה (TDP/מאווררים)** | ❌ | ✅ | ✅ **(Handheld)** |
| **Smart Launch Watcher** | ⚠️ גרעין | ✅ | ✅ **מלא** |
| **Discord Presence** | ❌ | ✅ | ✅ |
| **Streaming (Moonlight/Chiaki)** | ❌ | ✅ | ✅ **שיגור** |
| **זכוכית + FPS חלק (UI)** | ⚠️ Qt חוסם | ✅ נייטיב | ✅ **WebView2 מואץ-GPU** |
| **השהיה ל-Tray בזמן משחק** | ⚠️ | ⚠️ | ✅ **daemon קטן** |
| **תרגום-מסך חי (OCR)** | ❌ | ❌ | 🌟 **חדש (ניסיוני)** |
| **ספרייה מודעת-תרגום** | ❌ | ❌ | 🌟 **חדש** |
| **פרופיל TDP+שפה כפול** | ❌ | ⚠️ TDP בלבד | 🌟 **חדש** |
| **סנכרון ענן PC↔Handheld** | ⚠️ | ⚠️ | ✅ **מלא** |

> **השורה התחתונה:** אתה שומר על **כל** מה שמייחד אותך (העיצוב, המודים, הממשק, הקנייה, מנוע-התרגום), מקבל **את כל** יתרונות Winhanced (ספרייה, בקר, מחירים, חומרה, streaming), ומרוויח **פיצ'רים חדשים שאף אחד בשוק לא נותן** — הכול בפלטפורמה אחת, על שתי בסיסים שמשלימים זה את זה במקום להתנגש.
