"""
software_catalog.py - bundled offline fallback for the launcher's
"תוכנות" (Software) library.

Software rows live in the SAME catalog as games, flagged `isSoftware`, and
carry the FULL game shape - so the launcher renders them with the identical
GameCard / GameDetailPanel. This module only provides an offline seed for
when the live `/api/games` feed is unreachable.

IMPORTANT - only catalog METADATA is bundled. The translation FILES are NOT:
each entry's install action downloads its payload from the cloud (Cloudflare
Worker → GitHub release) via `mod_source` (VirtualDJ = `virtualdj-hebrew`).
"""
from __future__ import annotations

_COVERS = "https://mfudkftrluabqlrpkvtj.supabase.co/storage/v1/object/public/covers"


def sorted_software() -> list[dict]:
    """The bundled software catalog (game-shaped rows), in display order."""
    return [dict(s) for s in _SOFTWARE]


_SOFTWARE: list[dict] = [
    {
        "id":            "virtualdj",
        "titleEn":       "VirtualDJ 2026",
        "titleHe":       "וירטואל די-ג'יי 2026",
        "version":       "1.0.0-beta.1",
        "versionLabel":  "",
        "status":        "beta",
        "releaseStage":  "beta",
        "availability":  "available",
        "cover":         f"{_COVERS}/virtualdj.webp",
        "bannerUrl":     f"{_COVERS}/banners/virtualdj.webp",
        "logoUrl":       f"{_COVERS}/logos/virtualdj.png",
        "theme_key":     "default",
        "themeKey":      "default",
        "progress":      None,
        "downloadUrl":   "https://github.com/hebrew-translation-hub/virtualdj-hebrew-mods/releases/download/v1.0.0-beta.1/virtualdj_hebrew.zip",
        "tagline":       "תוכנת ה-DJ של Atomix - עכשיו בעברית מלאה",
        "description":   "תרגום מלא של VirtualDJ 2026 לעברית - כל התפריטים, ההגדרות והכלים, מימין לשמאל. ההתקנה מורידה את קובץ השפה מהענן ומחליפה את חריץ הערבית; בוחרים בהגדרות Language = Arabic ומקבלים עברית מלאה.",
        "changelog":     "גרסה ראשונה - תרגום מלא של הממשק (3,894 שורות), כיוון RTL מלא, קבצים בענן עם עדכון אוטומטי.",
        "priceCents":    1500,
        "featured":      False,
        "next":          False,
        "sortOrder":     1,
        "showOnWebsite": True,
        "showOnLauncher": True,
        "isSoftware":    True,
    },
    {
        "id":            "signalrgb",
        "titleEn":       "SignalRGB",
        "titleHe":       "SignalRGB",
        "version":       "1.0.0-beta.1",
        "versionLabel":  "",
        "status":        "beta",
        "releaseStage":  "beta",
        "availability":  "available",
        "cover":         f"{_COVERS}/signalrgb.webp",
        "bannerUrl":     f"{_COVERS}/banners/signalrgb.webp",
        "logoUrl":       f"{_COVERS}/logos/signalrgb.png",
        "theme_key":     "default",
        "themeKey":      "default",
        "progress":      None,
        "downloadUrl":   "https://github.com/hebrew-translation-hub/signalrgb-hebrew-mods/releases/download/v1.0.0-beta.1/signalrgb_hebrew.zip",
        "tagline":       "תוכנת ה-RGB האחת לכל ההתקנים - עכשיו בעברית מלאה",
        "description":   "תרגום מלא של SignalRGB לעברית - כל הממשק, עמוד המאקרו ועמודי ההגדרות של כל ההתקנים. ההתקנה מורידה את התרגום מהענן ומחילה אותו; השפה נקבעת אוטומטית.",
        "changelog":     "גרסה ראשונה - תרגום מלא של הממשק, עמוד המאקרו וכל עמודי ההתקנים; קבצים בענן עם עדכון אוטומטי.",
        "priceCents":    1500,
        "featured":      False,
        "next":          False,
        "sortOrder":     2,
        "showOnWebsite": True,
        "showOnLauncher": True,
        "isSoftware":    True,
    },
    {
        "id":            "borderless-gaming",
        "titleEn":       "Borderless Gaming",
        "titleHe":       "בורדרלס גיימינג",
        "version":       "1.0.0-beta.1",
        "versionLabel":  "",
        "status":        "beta",
        "releaseStage":  "beta",
        "availability":  "available",
        "cover":         f"{_COVERS}/borderless-gaming.webp",
        "bannerUrl":     f"{_COVERS}/banners/borderless-gaming.webp",
        "logoUrl":       f"{_COVERS}/logos/borderless-gaming.png",
        "theme_key":     "default",
        "themeKey":      "default",
        "progress":      None,
        "downloadUrl":   "https://github.com/hebrew-translation-hub/borderless-gaming-hebrew-mods/releases/download/v1.0.0-beta.1/borderless_gaming_hebrew.zip",
        "tagline":       "חלון ללא מסגרת ומסנני שדרוג תמונה - עכשיו בעברית מלאה",
        "description":   "תרגום מלא לעברית של Borderless Gaming - הכלי שהופך כל משחק לחלון ללא מסגרת ומוסיף מסנני שדרוג תמונה (FSR, Anime4K, CRT ועוד). מתורגמים גם ממשק התוכנה וגם עורך האפקטים כולו. ההתקנה כותבת רק לתיקיית המשתמש, ולכן אימות הקבצים של Steam לא מוחק את התרגום.",
        "changelog":     "גרסה ראשונה - 878 מחרוזות בעברית: ממשק התוכנה (343) ועורך האפקטים (535 מחרוזות ב-106 אפקטים).",
        "priceCents":    0,
        "featured":      False,
        "next":          False,
        "sortOrder":     2,
        "showOnWebsite": True,
        "showOnLauncher": True,
        "isSoftware":    True,
    },
]
