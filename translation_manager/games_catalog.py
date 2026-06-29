"""
Game catalog — mirrors the website's `src/data/games.ts` so the launcher's
library shows exactly the same titles, taglines, and descriptions as the
public site.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogGame:
    id: str                # matches /covers/{id}.jpg
    titleEn: str
    titleHe: str
    version: str
    theme_key: str         # cyberpunk / tsushima / rdr / hogwarts / default
    availability: str      # available · in-progress · coming-soon · planned
    tagline: str
    description: str
    progress: int | None = None


# ── Showcase (from games.ts `showcase` array) ─────────────────────────
SHOWCASE: list[CatalogGame] = [
    CatalogGame(
        "cyberpunk", "Cyberpunk 2077", "סייברפאנק 2077",
        "v2.12 Ultimate", "cyberpunk", "in-progress",
        "היכנסו לנעליו של V ברחובות נייט סיטי",
        "תרגום ענק המקיף מאות אלפי שורות דיאלוג, סלנג רחוב מחוספס ואווירה טכנולוגית בלתי נשכחת — עכשיו בעברית.",
        progress=72,
    ),
    CatalogGame(
        "tsushima", "Ghost of Tsushima", "גוסט אוף סושימה",
        "Director's Cut", "tsushima", "planned",
        'הפכו ל"רוח" והגנו על האי צושימה',
        "תרגום נאמן לרוח הסמוראים שמעניק כבוד לסיפורו הפואטי והוויזואלי של ג'ין סאקאי.",
    ),
    CatalogGame(
        "rdr1", "Red Dead Redemption", "רד דד רדמפשן",
        "PC Edition", "rdr", "planned",
        "סיפורו של ג'ון מרסטון בסוף עידן הקאובויים",
        "מסע של אבא, נקמה וגאולה בגבולות המערב הפרוע. כולל את הרחבת Undead Nightmare — גרסת ה-PC הסופית, קבצי הסיפור נעולים לתמיד.",
    ),
    CatalogGame(
        "rdr2", "Red Dead Redemption 2", "רד דד רדמפשן 2",
        "Complete Edition", "rdr", "planned",
        "האפוס הקולנועי של רוקסטאר",
        "ארתור מורגן וכנופיית ואן דר לינדה בסיפור על חברות, בגידה וגאולה בעולם פתוח עוצר נשימה. רוקסטאר לא נוגעת בקבצי הסינגל-פלייר.",
    ),
    CatalogGame(
        "gtav", "Grand Theft Auto V", "גרנד ת'פט אוטו V",
        "Story Mode", "default", "planned",
        "מייקל, פרנקלין וטרבור — שלוש דמויות, סיפור אחד גדול מהחיים",
        "לוס סנטוס במלוא הדרה — שודי בנקים, מרדפי משטרה ופארודיה אכזרית על המערב המודרני.",
    ),
    CatalogGame(
        "hogwarts", "Hogwarts Legacy", "הוגוורטס לגאסי",
        "Complete", "hogwarts", "planned",
        "הגיע הזמן לקבל את המכתב מהוגוורטס",
        "חוו את עולם הקוסמים של המאה ה-19 עם תרגום מלא לכל הלחשים, השיקויים והסודות של הטירה.",
    ),
]


# ── Planned (from games.ts `plannedSeeds`) ────────────────────────────
PLANNED: list[CatalogGame] = [
    CatalogGame("spiderman", "Marvel's Spider-Man Remastered", "מארוול ספיידר-מן רימאסטרד",
        "—", "default", "planned",
        "השכונה מעולם לא נראתה קרובה יותר",
        "הצטרפו לפיטר פארקר בסיפור אקשן סוחף ברחובות ניו יורק."),
    CatalogGame("spidermanmm", "Marvel's Spider-Man: Miles Morales", "מארוול ספיידר-מן: מיילס מוראלס",
        "—", "default", "planned",
        "מיילס מוראלס לוקח את הזירה",
        "ספיידר-מן חדש מגיע להארלם בעיצוב חורף קסום. סיפור עוצמתי על מציאת הקול הפנימי שלך — בתרגום מלא."),
    CatalogGame("spiderman2", "Marvel's Spider-Man 2", "מארוול ספיידר-מן 2",
        "בטא — ממשק", "default", "in-progress",
        "פיטר ומיילס יוצאים יחד נגד וונום",
        "תרגום עברית מלא לממשק המשחק — כל התפריטים, ההגדרות, התיאורים והכפתורים, עם כיווניות RTL תקינה. גרסת בטא: כתוביות ודיאלוג בתוך המשחק עדיין באנגלית (יתורגמו בהמשך). מותקן דרך Overstrike; במשחק יש לבחור שפה = ערבית.",
        progress=20),
    CatalogGame("witcher3", "The Witcher 3: Wild Hunt", "המכשף 3: ציד פראי",
        "—", "default", "planned",
        "צאו לציד מפלצות עם גראלט מריוויה",
        "עולם פנטזיה עמוק מלא בהחלטות גורליות, עכשיו בשפה שלנו."),
    CatalogGame("gow2018", "God of War (2018)", "גוד אוף וור (2018)",
        "—", "default", "planned",
        "ההתחלה של המסע הנורדי",
        "קרייטוס מלמד את בנו לשרוד בעולם של אלים ומפלצות."),
    CatalogGame("gowragnarok", "God of War Ragnarök", "גוד אוף וור ראגנארוק",
        "—", "default", "coming-soon",
        "המסע של קרייטוס ואטראוס אל סוף העולם",
        "חוו את הדרמה המשפחתית והקרבות האפיים מהמיתולוגיה הנורדית בתרגום עברי מרגש ועוצמתי."),
    CatalogGame("tlou1", "The Last of Us Part I", "דה לאסט אוף אס · חלק I",
        "—", "default", "planned",
        "סיפור הישרדות אנושי ומרגש",
        'ליווי של ג\'ואל ואלי במסע מסוכן ברחבי ארה"ב שאחרי המגפה.'),
    CatalogGame("horizonzd", "Horizon Zero Dawn", "הורייזון זירו דאון",
        "—", "default", "planned",
        "גלו את סודות העולם הישן",
        "עזרו לאלוי להילחם במכונות ענק ולחשוף את מקורותיה."),
    CatalogGame("horizonfw", "Horizon Forbidden West", "הורייזון פורבידן וסט",
        "—", "default", "planned",
        "המסע למערב האסור",
        "הרפתקה ויזואלית מרהיבה עם אויבים חדשים וטכנולוגיה עתיקה."),
    CatalogGame("watchdogs1", "Watch Dogs", "ווצ' דוגס",
        "—", "default", "planned",
        "הפכו את שיקגו לנשק שלכם",
        "מותחן טכנולוגי על נקמה, האקינג ושליטה בעיר חכמה."),
    CatalogGame("watchdogs2", "Watch Dogs 2", "ווצ' דוגס 2",
        "—", "default", "planned",
        "הצטרפו ל-DedSec בסן פרנסיסקו",
        "האקינג יצירתי ואווירה קלילה במלחמה נגד התאגידים."),
    CatalogGame("uncharted", "Uncharted: Legacy of Thieves", "אנצ'רטד: מורשת הגנבים",
        "—", "default", "planned",
        "צאו להרפתקה בעקבות אוצרות אבודים",
        "אקשן קולנועי עוצר נשימה עם ניית'ן דרייק וקלואי פרייזר."),
    # ── Assassin's Creed series ──
    CatalogGame("ac1", "Assassin's Creed", "אססינ'ס קריד",
        "—", "default", "planned",
        "איפה שהכל התחיל",
        "הצטרפו לאלטאיר בארץ הקודש במאבק העתיק בין המתנקשים לטמפלרים."),
    CatalogGame("ac2", "Assassin's Creed II", "אססינ'ס קריד II",
        "—", "default", "planned",
        "סיפורו של אציו אודיטורה ברנסנס האיטלקי",
        "מסע של נקמה שהופך למחויבות למסדר."),
    CatalogGame("acbrotherhood", "Assassin's Creed: Brotherhood", "אססינ'ס קריד: ברדרהוד",
        "—", "default", "planned",
        "הקימו את האחווה ברומא",
        "אציו מוביל את המאבק נגד משפחת בורג'ה המושחתת."),
    CatalogGame("acrevelations", "Assassin's Creed: Revelations", "אססינ'ס קריד: גילויים",
        "—", "default", "planned",
        "סגירת מעגל בקונסטנטינופול",
        "אציו הולך בעקבותיו של אלטאיר בחיפוש אחר תשובות."),
    CatalogGame("ac3", "Assassin's Creed III", "אססינ'ס קריד III",
        "—", "default", "planned",
        "המהפכה האמריקאית דרך עיניו של קונור",
        "קרב על חופש וצדק בעולם החדש."),
    CatalogGame("acblackflag", "Assassin's Creed IV: Black Flag", "אססינ'ס קריד IV: דגל שחור",
        "—", "default", "planned",
        "תור הזהב של הפיראטים",
        "הפליגו עם אדוארד קנוויי בים הקריבי בחיפוש אחר עושר ותהילה."),
    CatalogGame("acrogue", "Assassin's Creed: Rogue", "אססינ'ס קריד: רוג'",
        "—", "default", "planned",
        "הצד השני של המטבע",
        "חוו את סיפורו של מתנקש שהפך לצייד מתנקשים בשירות הטמפלרים."),
    CatalogGame("acunity", "Assassin's Creed: Unity", "אססינ'ס קריד: יוניטי",
        "—", "default", "planned",
        "המהפכה הצרפתית בפריז",
        "סיפור אהבה וקונספירציה בתוך הכאוס של המהפכה."),
    CatalogGame("acsyndicate", "Assassin's Creed Syndicate", "אססינ'ס קריד סינדיקייט",
        "—", "default", "planned",
        "המהפכה התעשייתית בלונדון",
        "הנהיגו כנופיות רחוב עם התאומים פריי כדי לשחרר את העיר."),
    CatalogGame("acorigins", "Assassin's Creed Origins", "אססינ'ס קריד אוריג'ינס",
        "—", "default", "planned",
        "גלו את מקור האחווה במצרים העתיקה",
        "מסעו של באייק בין פירמידות ומזימות פוליטיות."),
    CatalogGame("acodyssey", "Assassin's Creed Odyssey", "אססינ'ס קריד אודיסיאה",
        "—", "default", "planned",
        "כתבו את האודיסאה שלכם ביוון העתיקה",
        "בחרו את גורלכם כלוחמים ספרטנים בעולם מרהיב."),
    CatalogGame("acvalhalla", "Assassin's Creed Valhalla", "אססינ'ס קריד ולהאלה",
        "—", "default", "planned",
        "פלישת הוויקינגים לאנגליה",
        "הנהיגו את השבט שלכם בחיפוש אחר בית חדש ותהילה בוואלהלה."),
    CatalogGame("acmirage", "Assassin's Creed Mirage", "אססינ'ס קריד: מיראז'",
        "—", "default", "planned",
        "חזרה לשורשים בבגדאד",
        "עקבו אחר באסים בדרכו מנער רחוב למאסטר מתנקש."),
    # id matches the website/Supabase games row ("ac-shadows", hyphenated)
    # so the launcher's detection + the live catalog line up on the same id.
    CatalogGame("ac-shadows", "Assassin's Creed Shadows", "אססינ'ס קריד: שאדוס",
        "—", "default", "planned",
        "יפן הפיאודלית דרך עיניהם של נאואה ויאסקה",
        "הרפתקת התגנבות ולחימה ביפן של המאה ה-16 עם שתי דמויות משחק."),
    # ── Strategy / city-builder ──
    CatalogGame("anno1800", "Anno 1800", "אנו 1800",
        "—", "default", "planned",
        "בנו אימפריה תעשייתית במהפכה התעשייתית",
        "משחק אסטרטגיה ובניית ערים בעידן המהפכה התעשייתית — סחר ימי, ניהול תושבים "
        "ועיצוב מטרופולין משגשג. תרגום מלא לעברית של ממשק המשחק, מבנים ומשימות."),
]


ALL_GAMES: list[CatalogGame] = SHOWCASE + PLANNED


_AVAIL_RANK = {"available": 0, "in-progress": 1, "coming-soon": 2, "planned": 3}


def sorted_games() -> list[CatalogGame]:
    return sorted(ALL_GAMES, key=lambda g: (_AVAIL_RANK.get(g.availability, 99), g.titleEn))


def by_id(game_id: str) -> CatalogGame | None:
    for g in ALL_GAMES:
        if g.id == game_id:
            return g
    return None
