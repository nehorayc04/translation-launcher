# מנהל תרגומים — Translation Manager

ממשק שולחני קל לניהול מודים של תרגומים לעברית למשחקי PC.

## הפעלה מקוד מקור

```bat
pip install -r requirements.txt
python -m translation_manager.main
```

או דרך הסקריפט הישיר:

```bat
python translation_manager\run.py
```

## בניית קובץ EXE

הנח `icon.ico` ליד `build.bat` (אופציונלי) והרץ:

```bat
build.bat
```

הפלט יישמר ב-`dist\TranslationManager.exe` — קובץ יחיד, ללא חלון קונסולה.

### פקודת PyInstaller ידנית

```bat
pyinstaller ^
    --onefile ^
    --windowed ^
    --name "TranslationManager" ^
    --icon "icon.ico" ^
    --collect-all customtkinter ^
    --paths ".." ^
    run.py
```

## מבנה התיקיה

```
translation_manager/
├── __init__.py
├── main.py           # נקודת כניסה
├── run.py            # bootstrap ל-PyInstaller
├── config.py         # הגדרות משחקים + מחרוזות עברית
├── theme.py          # פלטת צבעים + פונטים
├── mod_logic.py      # לוגיקת זיהוי/הפעלה/השבתה/הסרה
├── ui/
│   ├── app.py        # חלון ראשי
│   └── components.py # רכיבים: כרטיס, כפתור ניאון, חיווי סטטוס
├── requirements.txt
├── build.bat
└── README.md
```

## הוספת משחק חדש

ערוך את `config.py` והוסף ערך ל-`GAMES`:

```python
"שם המשחק": GameConfig(
    name="Game Name",
    internal_id="my_game",
    mod_files=[r"path\to\mod.archive"],
    common_paths=[r"C:\Steam\...\GameName"],
    validation_file=r"bin\game.exe",
),
```

הממשק יזהה את הערך אוטומטית.

## תכונות

- **בחירת משחק** — תפריט נפתח, מוכן להרחבה.
- **זיהוי נתיב** — סריקה אוטומטית של נתיבי Steam/Epic/GOG ברקע, או בחירה ידנית.
- **מצב מקוון בטוח** — הפעלה והשבתה משנים את שם הקובץ ל-`.disabled` במקום למחוק, כך שאפשר לעבור למצב מקוון בלי חשש מחסימה.
- **הסרה מלאה** — מוחק את כל קבצי המוד באישור המשתמש.
- **חיווי סטטוס** — מציג בזמן אמת אם המוד `פעיל`, `מושבת` או `לא מותקן`, עם צבע מתאים.
- **חלון רגיל** — כפתורי מזעור / הגדלה / סגירה רגילים של Windows, ניתן לשנות גודל.
