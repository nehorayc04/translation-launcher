# -*- coding: utf-8 -*-
"""Batch 52 unified translator for Parts 2-4 (item names + armor)."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))

QUALITY = {
    "Inscribed": "חרוט",
    "Etched": "מגולף",
    "Polished": "מלוטש",
    "Inlaid": "משובץ",
    "Sharp": "חד",
    "Sturdy": "יציב",
    "Jagged": "משונן",
}

ITEM_TYPE = {
    "Crest": "סמל",
    "Sigil": "חותם",
    "Relic": "שריד",
    "Sign": "אות",
    "Brand": "מותג",
}

ATTRIBUTE = {
    "Courage": "אומץ",
    "Truth": "אמת",
    "Heart": "לב",
    "Frenzy": "טירוף",
    "Fortitude": "עוצמה",
    "Triumph": "ניצחון",
    "Cunning": "ערמה",
    "Determination": "נחישות",
    "Fervor": "להט",
    "Concentration": "ריכוז",
    "Bounty": "שפע",
    "Perseverance": "התמדה",
    "Survival": "הישרדות",
    "Consideration": "תבונה",
    "Providence": "השגחה",
    "Menace": "איום",
    "Tenacity": "עקשנות",
    "Resilience": "חוסן",
    "Defiance": "מרי",
    "Fortune": "מזל",
    "Shadows": "צללים",
}

# "Symbol of X" (no quality prefix)
SYMBOL_MAP = {f"Symbol of {a_en}": f"סמל של {a_he}" for a_en, a_he in ATTRIBUTE.items()}

def translate_item(v):
    # Pattern: Quality ItemType of Attribute
    for q_en, q_he in QUALITY.items():
        for t_en, t_he in ITEM_TYPE.items():
            for a_en, a_he in ATTRIBUTE.items():
                if v == f"{q_en} {t_en} of {a_en}":
                    return f"{t_he} {q_he} של {a_he}"
    # Pattern: Symbol of Attribute
    if v in SYMBOL_MAP:
        return SYMBOL_MAP[v]
    # Armor patterns with "of"
    armor_of = {
        "Gauntlets of the Undying Flame": "כפפות הלהבה שאינה דועכת",
        "Pauldron of Undying Light": "מגן כתף של אור נצחי",
    }
    if v in armor_of:
        return armor_of[v]
    return None

# Manual translations for non-pattern items
MANUAL = {
    "Jotunn Trinket": "תכשיט יוטן",
    "Wolf Trinket": "תכשיט זאב",
    "Boar Hide Shoulder Guard": "מגן כתף מעור חזיר",
    "Boar Hide Bracers": "מגיני זרוע מעור חזיר",
    "Boar Hide Belt": "חגורת עור חזיר",
    "Traveler Trinket": "תכשיט נוסע",
    "Tattered armor.": "שריון בלוי.",
    "Enhances defense": "משפר הגנה",
    "Built to increase damage": "בנוי להגברת נזק",
    "Worn armor.": "שריון שחוק.",
    "Higher quality trinket": "תכשיט באיכות גבוהה יותר",
    "Basic armor.": "שריון בסיסי.",
    "Nearly perfect trinket": "תכשיט כמעט מושלם",
    "Improved armor.": "שריון משופר.",
    "Exceptional trinket": "תכשיט יוצא דופן",
    "Bonus to Strength.": "בונוס לכוח.",
    "Viken Tunic": "גלימת ויקן",
    "Defender's Cuirass": "שריון חזה של מגן",
    "Plated Völunder Cuirass": "שריון חזה וולונדר מצופה",
    "Runic Wyrmskin Pauldrons": "מגיני כתף רוניים מעור תנין",
    "Wolfskin Shoulder Guard": "מגן כתף מעור זאב",
    "Metal-Plated Shoulder Guard": "מגן כתף מצופה מתכת",
    "Dwarven Runic Pauldron": "מגן כתף גמדי רוני",
    "Viken Waist Guard": "מגן מותן ויקן",
    "Defender's Waist Guard": "מגן מותן של מגן",
    "Plated Völunder Waist Guard": "מגן מותן וולונדר מצופה",
    "Runeweaver War Belt": "חגורת מלחמה של אורג רונות",
    "Wolfskin Waist Guard": "מגן מותן מעור זאב",
    "Metal-Plated Waist Guard": "מגן מותן מצופה מתכת",
    "Dwarven Runic War Belt": "חגורת מלחמה גמדית רונית",
    "Viken Bracers": "מגיני זרוע ויקן",
    "Defender's Arm Guards": "מגיני זרוע של מגן",
    "Plated Völunder Gauntlets": "כפפות וולונדר מצופות",
    "Plated Runeweaver Bracers": "מגיני זרוע אורג רונות מצופים",
    "Wolfskin Bracers": "מגיני זרוע מעור זאב",
    "Metal-Plated Bracers": "מגיני זרוע מצופי מתכת",
    "Dwarven Runic Gauntlets": "כפפות גמדיות רוניות",
    # Armor with "of" patterns
    "Mythic Pauldron of the Bear": "מגן כתף אגדי של הדוב",
    "Mythic War Belt of the Bear": "חגורת מלחמה אגדית של הדוב",
    "Mythic Bracers of the Bear": "מגיני זרוע אגדיים של הדוב",
    "Mythic Pauldrons of the Raven": "מגיני כתף אגדיים של העורב",
    "Mythic Gauntlets of the Raven": "כפפות אגדיות של העורב",
    "Ornate Bracers of the Raven": "מגיני זרוע מקושטים של העורב",
    "Scaled Bracers of the Dragon": "מגיני זרוע קשקשים של הדרקון",
    "Scaled Waist Guard of the Dragon": "מגן מותן קשקשי של הדרקון",
    "Plated Pauldrons of Undying Light": "מגיני כתף מצופים של אור נצחי",
    "Plated Waist Guard of Undying Light": "מגן מותן מצופה של אור נצחי",
    "Waist Guard of the Undying Flame": "מגן מותן של הלהבה שאינה דועכת",
    "Defender’s Cuirass": "שריון חזה של מגן",
    "Defender’s Waist Guard": "מגן מותן של מגן",
    "Defender’s Arm Guards": "מגיני זרוע של מגן",
    "Plated Pauldrons of Focus": "מגיני כתף מצופים של מיקוד",
    "Scaled Waist Guard of Focus": "מגן מותן קשקשי של מיקוד",
    "Scaled Bracers of Focus": "מגיני זרוע קשקשיים של מיקוד",
    "Pauldron of the True Warrior": "מגן כתף של הלוחם האמיתי",
    "Gauntlets of the True Warrior": "כפפות של הלוחם האמיתי",
    "Waist Guard of the True Warrior": "מגן מותן של הלוחם האמיתי",
    "Mythic Pauldrons of Clarity": "מגיני כתף אגדיים של בהירות",
    "Mythic Bracers of Clarity": "מגיני זרוע אגדיים של בהירות",
    "Mythic War Belt of Clarity": "חגורת מלחמה אגדית של בהירות",
    "Mythic Pauldrons of Protection": "מגיני כתף אגדיים של הגנה",
    "Ornate Bracers of Protection": "מגיני זרוע מקושטים של הגנה",
    "Plated Waist Guard of Protection": "מגן מותן מצופה של הגנה",
    "Mythic Pauldron of Arcane Might": "מגן כתף אגדי של כוח מסתורי",
    "Mythic Gauntlets of Arcane Might": "כפפות אגדיות של כוח מסתורי",
    "Mythic War Belt of Arcane Might": "חגורת מלחמה אגדית של כוח מסתורי",
}

# Style-tag descriptions
STYLE = {
    "Cheaply made, but sturdy. Commonly used within Reaver clans. Favors [style=Highlight][Icons:DEFENSE] DEFENSE[/style].":
        "מיוצר בזול, אבל חסון. נפוץ בקרב שבטי הבוזזים. מעדיף [style=Highlight][Icons:DEFENSE] הגנה[/style].",
    "Reinforced, boiled leather armor. Not very comfortable, but slightly increases [style=Highlight][Icons:STRENGTH] STRENGTH[/style].":
        "שריון עור מחוזק ומבושל. לא נוח במיוחד, אבל מגביר מעט את [style=Highlight][Icons:STRENGTH] הכוח[/style].",
    "Basic defensive armor that increases [style=Highlight][Icons:VITALITY] VITALITY[/style].":
        "שריון הגנה בסיסי שמגביר [style=Highlight][Icons:VITALITY] חיוניות[/style].",
    "Sturdy defensive armor favoring [style=Highlight][Icons:DEFENSE] DEFENSE[/style].":
        "שריון הגנה חסון המעדיף [style=Highlight][Icons:DEFENSE] הגנה[/style].",
    "Sturdy defensive armor favoring [style=Highlight][Icons:VITALITY] VITALITY[/style].":
        "שריון הגנה חסון המעדיף [style=Highlight][Icons:VITALITY] חיוניות[/style].",
    "Sturdy armor favoring [style=Highlight][Icons:COOLDOWN] COOLDOWN[/style].":
        "שריון חסון המעדיף [style=Highlight][Icons:COOLDOWN] זמן מנוחה[/style].",
    "Girded defensive armor favoring [style=Highlight][Icons:RUNIC] RUNIC[/style].":
        "שריון הגנה מחוזק המעדיף [style=Highlight][Icons:RUNIC] רוני[/style].",
    "Sturdy offensive armor that increases [style=Highlight][Icons:STRENGTH] STRENGTH[/style].":
        "שריון התקפה חסון שמגביר [style=Highlight][Icons:STRENGTH] כוח[/style].",
    "Armor reinforced with Dwarven metal favoring [style=Highlight][Icons:RUNIC] RUNIC and [style=Highlight][Icons:STRENGTH] STRENGTH[/style].":
        "שריון מחוזק במתכת גמדית המעדיף [style=Highlight][Icons:RUNIC] רוני ו[style=Highlight][Icons:STRENGTH] כוח[/style].",
    "Dwarven-forged metal embedded with Ogre teeth, favoring [style=Highlight][Icons:STRENGTH] STRENGTH[/style].":
        "מתכת מחושלת גמדית משובצת בשיני עוג, המעדיפה [style=Highlight][Icons:STRENGTH] כוח[/style].",
    "Heavily reinforced armor favoring [style=Highlight][Icons:DEFENSE] DEFENSE[/style].":
        "שריון מחוזק מאוד המעדיף [style=Highlight][Icons:DEFENSE] הגנה[/style].",
    "Fortified steel from a Dwarven forge imbues this offensive armor with increases to [style=Highlight][Icons:RUNIC] RUNIC[/style] and [style=Highlight][Icons:STRENGTH] STRENGTH[/style].":
        "פלדה מבוצרת ממחשלה גמדית מעניקה לשריון ההתקפה הזה תוספת ל[style=Highlight][Icons:RUNIC] רוני[/style] ול[style=Highlight][Icons:STRENGTH] כוח[/style].",
    # Additional patterns found in parts 3-4
    "Belt reinforced with Ogre teeth, favoring [style=Highlight][Icons:STRENGTH] STRENGTH[/style].":
        "חגורה מחוזקת בשיני עוג, המעדיפה [style=Highlight][Icons:STRENGTH] כוח[/style].",
    "Bracers reinforced with Ogre teeth, favoring [style=Highlight][Icons:STRENGTH] STRENGTH[/style].":
        "מגיני זרוע מחוזקים בשיני עוג, המעדיפים [style=Highlight][Icons:STRENGTH] כוח[/style].",
    "Pauldrons reinforced with Ogre teeth, favoring [style=Highlight][Icons:STRENGTH] STRENGTH[/style].":
        "מגיני כתף מחוזקים בשיני עוג, המעדיפים [style=Highlight][Icons:STRENGTH] כוח[/style].",
    "Hardened leather armor that increases [style=Highlight][Icons:COOLDOWN] COOLDOWN[/style].":
        "שריון עור מוקשח שמגביר [style=Highlight][Icons:COOLDOWN] זמן מנוחה[/style].",
    "Reinforced offensive armor that increases [style=Highlight][Icons:STRENGTH] STRENGTH[/style].":
        "שריון התקפה מחוזק שמגביר [style=Highlight][Icons:STRENGTH] כוח[/style].",
    "Hardened leather armor designed for a large range of movement. Favors [style=Highlight][Icons:RUNIC] RUNIC[/style] and [style=Highlight][Icons:STRENGTH] STRENGTH[/style].":
        "שריון עור מוקשח המעוצב לטווח תנועה גדול. מעדיף [style=Highlight][Icons:RUNIC] רוני[/style] ו[style=Highlight][Icons:STRENGTH] כוח[/style].",
    "Reinforced offensive armor of Dwarven-forged steel, favoring [style=Highlight][Icons:STRENGTH] STRENGTH[/style].":
        "שריון התקפה מחוזק מפלדה מחושלת גמדית, המעדיף [style=Highlight][Icons:STRENGTH] כוח[/style].",
    "Pauldrons reinforced with layered steel of unknown origin, favoring [style=Highlight][Icons:COOLDOWN] COOLDOWN[/style].":
        "מגיני כתף מחוזקים בפלדה שכבתית ממקור לא ידוע, המעדיפים [style=Highlight][Icons:COOLDOWN] זמן מנוחה[/style].",
    "Bracers reinforced with layered steel of unknown origin, favoring [style=Highlight][Icons:COOLDOWN] COOLDOWN[/style].":
        "מגיני זרוע מחוזקים בפלדה שכבתית ממקור לא ידוע, המעדיפים [style=Highlight][Icons:COOLDOWN] זמן מנוחה[/style].",
    "Belt reinforced with layered steel of unknown origin, favoring [style=Highlight][Icons:COOLDOWN] COOLDOWN[/style].":
        "חגורה מחוזקת בפלדה שכבתית ממקור לא ידוע, המעדיפה [style=Highlight][Icons:COOLDOWN] זמן מנוחה[/style].",
}

for part_num in [2, 3, 4]:
    src_path = os.path.join(HERE, f"batch_part{part_num}.json")
    out_path = os.path.join(HERE, f"trans_part_{part_num}.json")
    src = json.load(open(src_path, encoding="utf-8"))
    data = {}
    warnings = []

    for k, v in src.items():
        result = translate_item(v)
        if result:
            data[k] = result
            continue
        if v in MANUAL:
            data[k] = MANUAL[v]
            continue
        if v in STYLE:
            data[k] = STYLE[v]
            continue
        # Fallback
        data[k] = v
        warnings.append(f"  key {k}: {v[:80]}")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Part {part_num}: {len(data)} entries, {len(warnings)} untranslated")
    if warnings:
        for w in warnings[:5]:
            print(w)
        if len(warnings) > 5:
            print(f"  ... and {len(warnings) - 5} more")
