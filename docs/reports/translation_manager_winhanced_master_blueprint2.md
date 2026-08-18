# 📘 תוכנית אב: הפלטפורמה המאוחדת (Master Blueprint)
## TranslationManager × Winhanced

> **שפה:** עברית קלה, קצרה וקולעת  
> **מטרה:** שילוב כל היתרונות של **TranslationManager** (תרגום משחקים, הזרקת קבצים, צי AI ו-Game Lab) יחד עם **Winhanced** (ספרייה מאוחדת, חנות מחירים, שליטת TDP ומצב בקר).

---

## 📋 תוכן העניינים

1. [קטגוריה 1: הארכיטקטורה בקצרה](#1-קטגוריה-1-הארכיטקטורה-בקצרה)
2. [קטגוריה 2: ביצועים ומהירות שיא (Extreme Performance)](#2-קטגוריה-2-ביצועים-ומהירות-שיא-extreme-performance)
3. [קטגוריה 3: שני מצבי תצוגה (Dual UI Modes)](#3-קטגוריה-3-שני-מצבי-תצוגה-dual-ui-modes)
4. [קטגוריה 4: חנות, מחירים וספרייה מאוחדת](#4-קטגוריה-4-חנות-מחירים-וספרייה-מאוחדת)
5. [קטגוריה 5: מנוע התרגומים והמודים (Game Lab)](#5-קטגוריה-5-מנוע-התרגומים-והמודים-game-lab)
6. [קטגוריה 6: תרגום בזמן אמת ובינה מלאכותית (NPU & Fleet)](#6-קטגוריה-6-תרגום-בזמן-אמת-ובינה-מלאכותית-npu--fleet)
7. [קטגוריה 7: שליטה בחומרה, סוללה ו-Smart Launch](#7-קטגוריה-7-שליטה-בחומרה-סוללה-ו-smart-launch)
8. [קטגוריה 8: 8 תרחישים ויזואליים עם חצים (Visual Scenarios)](#8-קטגוריה-8-8-תרחישים-ויזואליים-עם-חצים-visual-scenarios)
9. [קטגוריה 9: סיכום מנהלים קצר](#9-קטגוריה-9-סיכום-מנהלים-קצר)
10. [קטגוריה 10: טבלת השוואה מרכזית](#10-קטגוריה-10-טבלת-השוואה-מרכזית)

---

## 1. קטגוריה 1: הארכיטקטורה בקצרה

אנחנו מחברים 3 שכבות מנצחות למערכת אחת:

```mermaid
graph LR
    UI["🎨 שכבה 1: UI מעוצב<br/>(React / WinUI 3 / Living Glass)"] <--> CS["⚡ שכבה 2: C# System Host<br/>(חומרה, TDP, בקר, חסימת חלונות)"]
    CS <--> PY["🐍 שכבה 3: Python Game Lab<br/>(הזרקת תרגומים, מודים, צי AI)"]
```

* **C# Host (מערכת וחומרה):** אחראי על TDP, מאווררים, בקרים וחסימת חלונות קופצים.
* **Python Service (מנוע התרגום):** מריץ את כל מזרקי הקבצים של TranslationManager (`bsa.py`, `forge.py`, `swf.py`, Oodle) וצי ה-AI.
* **Frontend UI (ממשק זכוכית):** עיצוב מודרני (Living Glass) עם תמיכה מלאה בעכבר, מסך מגע ובקר.

---

## 2. קטגוריה 2: ביצועים ומהירות שיא (Extreme Performance)

```mermaid
graph TD
    RAM["🧠 1. הקפאת RAM בזמן משחק<br/>(ירידה ל-פחות מ-20MB RAM)"]
    IPC["⚡ 2. Shared Memory IPC<br/>(תקשורת מהירה מ-2ms)"]
    IO["🏎️ 3. Direct I/O Async Patcher<br/>(הזרקת תרגום ב-3 שניות)"]
    NPU["👁️ 4. Offline NPU OCR<br/>(תרגום מסך ללא ירידת FPS)"]

    RAM --- IPC --- IO --- NPU
```

1. **הקפאת RAM בזמן משחק:** כשהמשחק נפתח, התוכנה משחררת זיכרון ויורדת ל-**פחות מ-20MB RAM**. כשהמשחק נסגר, היא חוזרת ב-0.1 שניות!
2. **תקשורת מהירה (Shared Memory IPC):** מעבר נתונים בתוך ה-RAM בפחות מ-2 מילי-שניות.
3. **הזרקה ב-3 שניות (Direct I/O):** התקנת תרגום ענקי של 100GB מתקצרת מ-45 שניות ל-**3 שניות בלבד!**
4. **תרגום מסך ב-NPU:** תרגום בלייב על מאיץ ה-AI המקומי — **0% פגיעה ב-FPS ובכרטיס המסך!**

---

## 3. קטגוריה 3: שני מצבי תצוגה (Dual UI Modes)

```mermaid
graph TD
    App["🚀 הפעלת התוכנה"] --> Detect{"איזה מכשיר זה?"}
    Detect -- "🖥️ מחשב נייח" --> Desktop["💻 מצב דסקטופ<br/>(ספרייה מורחבת, ניהול מודים, Launcher Designer)"]
    Detect -- "🎮 Handheld / בקר" --> Console["🎮 מצב קונסולה (10ft UI)<br/>(ניווט סטיקים, אפקטי זכוכית, תרגום ב-A)"]
```

---

## 4. קטגוריה 4: חנות, מחירים וספרייה מאוחדת

```mermaid
graph LR
    Scan["🔍 סריקת משחקים<br/>(Steam / Epic / GOG / Xbox)"] --> Catalog["📚 ספרייה מאוחדת אחת"]
    Catalog --> Store["🛒 השוואת מחירים בזמן אמת"]
    Store --> Free["🎁 איסוף משחקים חינמיים אוטומטי"]
```

* **השוואת מחירים:** מציגה את המחיר הזול ביותר מכל החנויות.
* **איסוף משחקים חינמיים:** זיהוי ואיסוף בלחיצה אחת מ-Epic Games ו-GOG.

---

## 5. קטגוריה 5: מנוע התרגומים והמודים (Game Lab)

```mermaid
graph TD
    Select["🎯 בחירת משחק"] --> DetectEngine{"זיהוי מנוע המשחק"}
    DetectEngine -- "Skyrim SE" --> Creation["הזרקת SWF + STRINGS + Visual Bidi"]
    DetectEngine -- "AC Odyssey / Origins" --> Anvil["פענוח Forge + Oodle + text_em Pre-wrap"]
    DetectEngine -- "Far Cry 5 / 6" --> Dunia["הזרקת FFD/XBT + Scheme-2"]
    Creation & Anvil & Dunia --> Deploy["✅ התקנה בלחיצה אחת ב-3 שניות!"]
```

---

## 6. קטגוריה 6: תרגום בזמן אמת ובינה מלאכותית (NPU & Fleet)

```mermaid
graph LR
    User["🎮 משתמש במשחק"] --> Press["לחצן בבקר LB+RB"]
    Press --> OCR["👁️ NPU OCR (זיהוי טקסט)"]
    OCR --> AI["🤖 תרגום AI לעברית"]
    AI --> Overlay["🖼️ תצוגה שקופה מעל המשחק"]
```

---

## 7. קטגוריה 7: שליטה בחומרה, סוללה ו-Smart Launch

```mermaid
graph TD
    Launch["🚀 הרצת משחק"] --> Watcher["🌊 Smart Launch Watcher<br/>(חסימת חלונות UAC / EULA / AntiCheat)"]
    Watcher --> TDP["⚡ הפעלת פרופיל TDP מותאם (RyzenAdj)"]
    TDP --> Battery["🔋 חיסכון חכם בסוללה"]
```

---

## 8. קטגוריה 8: 8 תרחישים ויזואליים עם חצים (Visual Scenarios)

### 🛒 תרחיש 1: קניית משחק -> התקנה -> תרגום בלחיצה אחת
```mermaid
sequenceDiagram
    actor User as 👤 משתמש
    participant UI as 🎨 חנות / ספרייה
    participant Engine as 🐍 Python Game Lab
    participant Game as 🎮 משחק

    User->>UI: עורך עיון בחנות ומגלה משחק
    UI-->>User: מציג מחיר זול ב-Epic + "תרגום עברית זמין"
    User->>UI: לוחץ "קנה ותרגם" (כפתור A בבקר)
    UI->>Engine: הרצת Async Direct I/O Patcher
    Engine->>Engine: הזרקת פונטים, Bidi וקובצי שפה (3 שניות!)
    Engine-->>UI: התרגום הותקן!
    User->>UI: לוחץ "הפעל משחק"
    UI->>Game: הרצה שקטה בעברית מלאה!
```

---

### 🤖 תרחיש 2: בדיקה אוטונומית ברקע (`dxcam`) לפני המשחק
```mermaid
sequenceDiagram
    participant Patcher as 🐍 Python Patcher
    participant Auto as 🤖 Autocheck Engine
    participant DX as 📹 dxcam (DirectX Capture)
    participant User as 👤 משתמש

    Patcher->>Auto: התרגום הותקן, התחל בדיקה
    Auto->>Auto: הרצת המשחק ברקע ללא חלונות
    Auto->>DX: לכידת פריים מהמסך ב-DirectX
    DX-->>Auto: תמונת פריים התקבלה
    Auto->>Auto: אימות תקינות הפונטים וה-Bidi
    Auto-->>User: "המשחק מוכן ומוודא 100% בעברית!"
```

---

### 👁️ תרחיש 3: תרגום מסך בזמן אמת ב-NPU תוך כדי משחק
```mermaid
sequenceDiagram
    actor User as 👤 משתמש (בקר)
    participant Game as 🎮 משחק AAA
    participant Overlay as 🖼️ C# Overlay
    participant NPU as 🧠 NPU (ONNX Engine)

    User->>Game: נתקל בדיאלוג באנגלית
    User->>Overlay: לוחץ LB + RB + D-Pad Down
    Overlay->>NPU: העברת הפריים לתרגום
    NPU->>NPU: זיהוי OCR ותרגום לעברית (0% GPU Load)
    NPU-->>Overlay: טקסט מתורגם
    Overlay->>Game: הצגת כתוביות בעברית מעל המשחק!
```

---

### 🚁 תרחיש 4: סנכרון צי התרגום (Fleet Ops) ואתר `/translate`
```mermaid
sequenceDiagram
    participant Site as 🌐 אתר /translate
    participant Fleet as 🚁 Fleet AI (Multi-Provider)
    participant Local as 🖥️ תוכנה מקומית

    Fleet->>Site: תרגום אוטומטי של 1,000 שורות חדשות
    Site->>Site: הוספת נתוני Gender Oracle (זיהוי מגדר)
    Local->>Site: בדיקת עדכונים קהילתיים
    Site-->>Local: הורדת הפאץ' המעודכן
    Local->>Local: הזרקת השורות החדשות למשחק!
```

---

### 🧩 תרחיש 5: התקנת מודים ופתרון קונפליקטים ב-Game Lab
```mermaid
sequenceDiagram
    actor User as 👤 משתמש
    participant Lab as 🧩 Game Lab
    participant Checker as 🔍 Conflict Checker
    participant Game as 🎮 תיקיית המשחק

    User->>Lab: בוחר מוד להתקנה
    Lab->>Checker: בדיקת התנגשויות ב-BSA / Forge
    Checker-->>Lab: לא נמצאו קונפליקטים!
    Lab->>Game: התקנת קובצי המוד
    Lab-->>User: "המוד הותקן בהצלחה!"
```

---

### 🧠 תרחיש 6: כניסה למשחק והקפאת זיכרון RAM
```mermaid
sequenceDiagram
    actor User as 👤 משתמש
    participant Watcher as 🌊 Smart Launch Watcher
    participant UI as 🎨 React / Web UI
    participant Game as 🎮 משחק AAA

    User->>UI: לוחץ "הפעל משחק"
    UI->>Watcher: המשחק נפתח!
    Watcher->>UI: מעבר למצב RAM Suspend (<20MB RAM)
    Watcher->>Game: העברת 100% משאבי המחשב למשחק
    User->>Game: המשחק נסגר
    Watcher->>UI: התעוררות מיידית ב-0.1 שניות!
```

---

### ☁️ תרחיש 7: סנכרון ענן אוניברסלי (PC <-> Handheld)
```mermaid
sequenceDiagram
    actor User as 👤 משתמש
    participant PC as 🖥️ מחשב נייח
    participant Cloud as ☁️ Universal Cloud
    participant Handheld as 🎮 מכשיר נייד (ROG Ally)

    User->>PC: משחק ומסיים שלב (Save Game + מודים)
    PC->>Cloud: העלאת שמירות והגדרות תרגום
    User->>Handheld: מדליק את המכשיר בדרכים
    Handheld->>Cloud: משיכת השמירות וההגדרות
    Handheld-->>User: ממשיך לשחק exactement מהנקודה שעצר!
```

---

### 🎁 תרחיש 8: תפיסת משחקים חינמיים אוטומטית
```mermaid
sequenceDiagram
    participant Cron as ⏰ שירות רקע
    participant Store as 🛒 Epic Games / GOG
    participant User as 👤 משתמש

    Cron->>Store: בדיקת משחקים חינמיים שבועיים
    Store-->>Cron: נמצא משחק חינמי חדש!
    Cron->>Store: ביצוע Auto-Claim בחנות
    Cron-->>User: "המשחק נוסף בהצלחה לספרייה שלך!"
```

---

## 9. קטגוריה 9: סיכום מנהלים קצר

1. **אפס פשרות:** שומרים על **100% ממנועי התרגום וה-AI המתקדמים של TranslationManager**, ומרוויחים את **מצב הבקר, החנות וניהול החומרה של Winhanced**.
2. **מהירות שיא:** בזכות **הקפאת ה-RAM בזמן משחק (<20MB)** והזרקה ב-3 שניות, המשחקים רצים חלק ב-120 FPS.
3. **פלטפורמה אחת מושלמת:** פתרון מלא מקצה לקצה — מגילוי משחק ועד משחק בעברית מלאה בדרכים!

---

## 10. קטגוריה 10: טבלת השוואה מרכזית

| פיצ'ר / תכונה | TranslationManager | Winhanced | **הפלטפורמה המאוחדת** |
|---|---|---|---|
| **מנועי הזרקה למשחקי AAA (BSA, Forge, SWF, FFD)** | ✅ מתקדם ביותר | ❌ אין | ✅ **משולב מלא** |
| **צי תרגום AI (Fleet Ops) ואתר `/translate`** | ✅ קיים ופועל | ❌ אין | ✅ **סנכרון מלא** |
| **Gender Oracle (זיהוי מגדר)** | ✅ קיים | ❌ אין | ✅ **משולב אוטומטית** |
| **אימות אוטונומי ברקע (`dxcam`)** | ✅ קיים | ❌ אין | ✅ **בדיקה שקטה** |
| **מצב בקר מותאם (Handheld 10ft UI)** | ❌ אין | ✅ מצוין | ✅ **תמיכה מלאה בבקר** |
| **שליטה בחומרה (TDP / RyzenAdj / מאווררים)** | ❌ אין | ✅ מצוין | ✅ **שליטה מלאה בחומרה** |
| **חנות והשוואת מחירים (Cross-Store)** | ❌ אין | ✅ מותקן | ✅ **חנות השוואת מחירים** |
| **Smart Launch Watcher (חסימת חוסמים)** | ⚠️ חלקי | ✅ מתקדם | ✅ **מלא** |
| **חיסכון זיכרון בזמן משחק (RAM Suspend)** | ❌ אין | ⚠️ חלקי | ✅ **פחות מ-20MB RAM** |
| **תרגום מסך ב-NPU (Offline OCR)** | ❌ אין | ❌ אין | ✅ **0% ירידה ב-FPS** |
| **מהירות הזרקה (Async Direct I/O)** | ⚠️ רגיל | ❌ אין | ✅ **הזרקה ב-3 שניות** |
| **תקשורת מהירה (Shared Memory IPC)** | ⚠️ WebSockets | ❌ אין | ✅ **פחות מ-2ms** |
| **סנכרון ענן ושמירות (Cross-Cloud Sync)** | ⚠️ חלקי | ❌ אין | ✅ **סנכרון מלא** |
| **איסוף משחקים חינמיים אוטומטי** | ❌ אין | ❌ אין | ✅ **איסוף בלחיצה אחת** |

> [!IMPORTANT]
> **השורה התחתונה:** הפלטפורמה המאוחדת מעניקה לך את **המוצר המתקדם והמהיר ביותר בשוק**, המשלב את כל העוצמה ההנדסית של TranslationManager עם חוויית משתמש וביצועי קצה של Winhanced!
