# -*- coding: utf-8 -*-
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_F = os.path.join(HERE, "trans_part_1.json")

# Vocabulary for item names:
# Crest = סמל
# Sigil = חותם
# Inscribed = חרוט
# Etched = מגולף
# Polished = מלוטש
# Inlaid = משובץ
# Sharp = חד

QUALITY = {
    "Inscribed": "חרוט",
    "Etched": "מגולף",
    "Polished": "מלוטש",
    "Inlaid": "משובץ",
    "Sharp": "חד",
}

ITEM_TYPE = {
    "Crest": "סמל",
    "Sigil": "חותם",
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

# Load source
src = json.load(open(os.path.join(HERE, "batch_part1.json"), encoding="utf-8"))

data = {}
for k, v in src.items():
    translated = False
    # Try pattern: "Quality ItemType of Attribute"
    for q_en, q_he in QUALITY.items():
        for t_en, t_he in ITEM_TYPE.items():
            for a_en, a_he in ATTRIBUTE.items():
                pattern = f"{q_en} {t_en} of {a_en}"
                if v == pattern:
                    data[k] = f"{t_he} {q_he} של {a_he}"
                    translated = True
                    break
            if translated:
                break
        if translated:
            break

    if not translated:
        # Special items
        special = {
            "Design#Text Status#Needs Review": "Design#Text Status#Needs Review",
            "[OBSOLETE] Requires Bow Upgrade": "[OBSOLETE] דורש שדרוג קשת",
            "Enchantment Socket": "שקע קסם",
            "Switch Character": "החלף דמות",
            "Abilities": "יכולות",
            "Shield Combat": "לחימת מגן",
            "[OBSOLETE] Commander": "[OBSOLETE] מפקד",
            "[OBSOLETE] Ranged Combat": "[OBSOLETE] לחימה מרחוק",
            "[OBSOLETE] Berserker": "[OBSOLETE] ברסרקר",
            "[OBSOLETE] Elemental Combat": "[OBSOLETE] לחימה יסודית",
            "[OBSOLETE] Ranger": "[OBSOLETE] סייר",
            "[OBSOLETE] Magic Combat": "[OBSOLETE] לחימת קסם",
            "[OBSOLETE] Tactician": "[OBSOLETE] טקטיקאי",
            "[OBSOLETE] Expert Combat": "[OBSOLETE] לחימת מומחה",
            "Additional Bonus": "בונוס נוסף",
            "Rage Combat": "לחימת זעם",
        }
        if v in special:
            data[k] = special[v]
        else:
            # fallback - keep original
            data[k] = v
            print(f"WARNING: No translation for key {k}: {v}")

with open(OUT_F, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Saved trans_part_1.json with {len(data)} entries")
