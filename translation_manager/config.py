"""
Game definitions, paths to external projects, and all UI strings (Hebrew).
"""

from dataclasses import dataclass, field
from pathlib import Path


# ── External-project locations ───────────────────────────────
WEBSITE_PROJECT_DIR = Path(r"C:\Users\nc528\סקריפטים\אתר תרגום משחקים")
WEBSITE_DIST_DIR    = WEBSITE_PROJECT_DIR / "dist"
WEBSITE_GAMES_TS    = WEBSITE_PROJECT_DIR / "src" / "data" / "games.ts"
WEBSITE_PUBLIC_URL  = "https://hebrewgames.vercel.app"   # adjust if hosted elsewhere


@dataclass
class GameConfig:
    name: str                            # Display name
    internal_id: str                     # Internal ID (matches website games.ts id)
    cover_theme: str = "default"         # Key into theme.CARD_GRADIENTS
    mod_files: list[str] = field(default_factory=list)
    common_paths: list[str] = field(default_factory=list)
    disabled_suffix: str = ".disabled"
    validation_file: str = ""

    def is_valid_dir(self, base: Path) -> bool:
        return bool(self.validation_file) and (base / self.validation_file).exists()


# ── Supported titles ──────────────────────────────────────────
GAMES: dict[str, GameConfig] = {
    "Cyberpunk 2077": GameConfig(
        name="Cyberpunk 2077",
        internal_id="cyberpunk",
        cover_theme="cyberpunk",
        mod_files=[
            r"archive\pc\mod\z_hebrew_translation.archive",
        ],
        common_paths=[
            r"C:\Program Files (x86)\Steam\steamapps\common\Cyberpunk 2077",
            r"C:\Program Files\Epic Games\Cyberpunk2077",
            r"D:\SteamLibrary\steamapps\common\Cyberpunk 2077",
            r"D:\Games\Cyberpunk 2077",
            r"E:\SteamLibrary\steamapps\common\Cyberpunk 2077",
            r"E:\Games\Cyberpunk 2077",
            r"F:\SteamLibrary\steamapps\common\Cyberpunk 2077",
            r"C:\GOG Games\Cyberpunk 2077",
        ],
        validation_file=r"bin\x64\Cyberpunk2077.exe",
    ),
    "Ghost of Tsushima": GameConfig(
        name="Ghost of Tsushima",
        internal_id="tsushima",
        cover_theme="tsushima",
        common_paths=[
            r"C:\Program Files (x86)\Steam\steamapps\common\Ghost of Tsushima",
            r"D:\SteamLibrary\steamapps\common\Ghost of Tsushima",
        ],
        validation_file=r"GhostOfTsushima.exe",
    ),
    "Red Dead Redemption 2": GameConfig(
        name="Red Dead Redemption 2",
        internal_id="rdr2",   # matches /covers/rdr2.jpg
        cover_theme="rdr",
        common_paths=[
            r"C:\Program Files (x86)\Steam\steamapps\common\Red Dead Redemption 2",
            r"C:\Program Files\Rockstar Games\Red Dead Redemption 2",
            r"D:\SteamLibrary\steamapps\common\Red Dead Redemption 2",
        ],
        validation_file=r"RDR2.exe",
    ),
    "Grand Theft Auto V": GameConfig(
        name="Grand Theft Auto V",
        internal_id="gtav",
        cover_theme="gta",
        common_paths=[
            r"C:\Program Files\Rockstar Games\Grand Theft Auto V",
            r"C:\Program Files (x86)\Steam\steamapps\common\Grand Theft Auto V",
            r"D:\SteamLibrary\steamapps\common\Grand Theft Auto V",
        ],
        validation_file=r"GTA5.exe",
    ),
    "The Witcher 3": GameConfig(
        name="The Witcher 3",
        internal_id="witcher3",
        cover_theme="witcher",
        common_paths=[
            r"C:\Program Files (x86)\Steam\steamapps\common\The Witcher 3",
            r"C:\GOG Games\The Witcher 3 Wild Hunt GOTY",
            r"D:\SteamLibrary\steamapps\common\The Witcher 3",
        ],
        validation_file=r"bin\x64\witcher3.exe",
    ),
    "Baldur's Gate 3": GameConfig(
        name="Baldur's Gate 3",
        internal_id="bg3",
        cover_theme="bg3",
        common_paths=[
            r"C:\Program Files (x86)\Steam\steamapps\common\Baldurs Gate 3",
            r"D:\SteamLibrary\steamapps\common\Baldurs Gate 3",
        ],
        validation_file=r"bin\bg3.exe",
    ),
    "Elden Ring": GameConfig(
        name="Elden Ring",
        internal_id="elden_ring",
        cover_theme="elden",
        common_paths=[
            r"C:\Program Files (x86)\Steam\steamapps\common\ELDEN RING",
            r"D:\SteamLibrary\steamapps\common\ELDEN RING",
        ],
        validation_file=r"Game\eldenring.exe",
    ),
}


# ── Hebrew UI strings ────────────────────────────────────────
class Strings:
    APP_TITLE       = "מנהל תרגומים לעברית"
    APP_BRAND       = "תרגומים"
    APP_SUBTITLE    = "פאנל בקרה למודי תרגום"

    NAV_HOME        = "דף הבית"
    NAV_LIBRARY     = "ספרייה"
    NAV_SETTINGS    = "הגדרות"

    HOME_TITLE      = "ברוך הבא"
    HOME_HERO_TITLE = "אתר תרגום משחקים"
    HOME_HERO_DESC  = "פרויקט פעיל — עשרות תרגומי עברית למשחקי PC, גלריית גרפיקה תלת-ממדית מרשימה ועדכונים שוטפים."
    HOME_HERO_OPEN  = "פתח באתר חי"
    HOME_HERO_LOCAL = "פתח גרסה מקומית"
    HOME_HERO_BUILD = "פתח תיקיית הפרויקט"
    HOME_FEATURED   = "תרגומים מובילים"
    HOME_QUICKLINKS = "קישורים מהירים"
    HOME_STATS      = "נתוני הפרויקט"

    LIB_TITLE       = "ספריית המשחקים"
    LIB_INSTALLED_M = "מותקנים עם מוד פעיל"
    LIB_INSTALLED_D = "מותקנים — מוד מושבת"
    LIB_INSTALLED   = "מותקנים ללא מוד"
    LIB_NOT_FOUND   = "לא נמצאו במחשב"
    LIB_SCANNING    = "סורק את המחשב לאיתור משחקים מותקנים..."
    LIB_REFRESH     = "סרוק שוב"

    SETTINGS_TITLE  = "הגדרות"
    SETTINGS_PATHS  = "נתיבי משחקים מותאמים"
    SETTINGS_WEBSITE= "נתיב פרויקט האתר"
    SETTINGS_THEME  = "מצב תצוגה"

    BTN_OPEN        = "פתח"
    BTN_BROWSE      = "עיון..."
    BTN_ENABLE      = "הפעל מוד"
    BTN_DISABLE     = "השבת מוד"
    BTN_UNINSTALL   = "הסר"
    BTN_INSTALL     = "התקן מוד"
    BTN_OPEN_FOLDER = "פתח תיקייה"
    BTN_CLOSE       = "סגור"
    BTN_SAVE        = "שמור"
    BTN_DETECT      = "זהה אוטומטית"

    STATUS_ACTIVE   = "פעיל"
    STATUS_DISABLED = "מושבת"
    STATUS_MISSING  = "לא מותקן"
    STATUS_UNKNOWN  = "—"

    UPDATE_TITLE    = "עדכוני מערכת"
    UPDATE_LATEST   = "גרסה אחרונה: v1.0.0"
    UPDATE_NEWS_1   = "תרגום Cyberpunk 2077 — 72% הושלמו"
    UPDATE_NEWS_2   = "פרויקט האתר עודכן עם 6 סצנות תלת-ממדיות"
    UPDATE_NEWS_3   = "תוספת תמיכה במשחקים: Witcher 3, BG3, Elden Ring"

    CONFIRM_TITLE   = "אישור"
    CONFIRM_UNINST  = "האם להסיר לצמיתות את כל קבצי המוד מתיקיית המשחק?"
    PICK_DIR        = "בחר תיקייה"

    MSG_NO_WEBSITE  = "פרויקט האתר לא נמצא בנתיב המוגדר."
    MSG_NO_DIST     = "תיקיית dist לא קיימת — יש להריץ 'npm run build' תחילה."
    MSG_SERVING     = "מגיש את האתר על http://localhost:{port}"
    MSG_OPENED      = "האתר נפתח בדפדפן."
    MSG_NO_PROJECT  = "פרויקט האתר לא נמצא."

    FOOTER          = "Translation Manager v1.0  •  © 2026 Nehoray"
