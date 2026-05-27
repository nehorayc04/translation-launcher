@echo off
:: מעבר לתיקייה שבה נמצא הסקריפט
cd /d "%~dp0"

:: הרצת הסקריפט (מומלץ להשתמש ב-pythonw אם אתה לא רוצה חלון CMD שחור)
python cp2077_fix_missing_translations.py

:: השהייה כדי לראות פלט/שגיאות לפני שהחלון נסגר
pause