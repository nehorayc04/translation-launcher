import json
import os

handoff = r"c:\Users\Nehoray_Cohen\Projects\Game translator\games\anno1800\agent_handoff"

# Load trans_part_1.json
out_path = os.path.join(handoff, "trans_part_1.json")
with open(out_path, "r", encoding="utf-8") as f:
    trans = json.load(f)

# The missing 70 translations
missing_trans = {
    "139697": "ענן רעיל",
    "139698": "ענן רעיל",
    "139707": "יאוסקה שמחה מהצעתך.",
    "139709": "יאוסקה שמחה מכך שהפתרון שלך עבד.",
    "139724": "נקודת ציון",
    "139739": "שריפה כימית",
    "139740": "שריפה כימית",
    "139741": "שריפה כימית",
    "139742": "שריפה כימית",
    "139756": "מודעות לשריפות",
    "139762": "מניעת שריפות",
    "139763": "מניעת שריפות",
    "139764": "רוויה מחדש",
    "139765": "רוויה מחדש",
    "139766": "תאונות עבודה",
    "139767": "תאונות עבודה",
    "139774": "ענן רעיל",
    "139797": "המטמון של איגנסיו",
    "139800": "דו-שיח",
    "139802": "דו-שיח",
    "139804": "הפעלת הסכר",
    "139814": "דו-שיח",
    "139815": "נקודת ציון",
    "139816": "רשתות דיג",
    "139817": "צב פצוע",
    "139868": "פיצוץ",
    "139871": "שריפה כימית",
    "139872": "שריפה כימית",
    "139873": "שריפה כימית",
    "139874": "ערימת חומרים",
    "139875": "ערימת חומרים",
    "139876": "ערימת חומרים",
    "139877": "ערימת חומרים",
    "139878": "ערימת חומרים",
    "139879": "ערימת חומרים",
    "139880": "ערימת חומרים",
    "139881": "ערימת חומרים",
    "139882": "ערימת חומרים",
    "139893": "ערימת חומרים",
    "139894": "ערימת חומרים",
    "139895": "ערימת חומרים",
    "139896": "ערימת חומרים",
    "139898": "גנרטור פירפוריאני",
    "139900": "צמחים ייחודיים",
    "139904": "כל המפעלים",
    "139911": "צמחים ייחודיים",
    "139912": "צמחים ייחודיים",
    "139913": "צמחים ייחודיים",
    "139914": "צמחים ייחודיים",
    "139915": "צמחים ייחודיים",
    "139916": "צמחים ייחודיים",
    "139917": "כל המפעלים",
    "139931": "שריפה כימית",
    "139933": "שריפה כימית",
    "139934": "כל מבני הייצור",
    "139935": "כל המפעלים",
    "139937": "אדים רעילים",
    "143027": "נקודת ציון",
    "143048": "הסכר",
    "143062": "נקודת ציון",
    "143063": "פוריות עצי דקל",
    "143106": "משפיע על [ItemAssetData(138583) ItemOrBuffEffectTargetsFormatted]",
    "143107": "משפיע על [ItemAssetData(138655) ItemOrBuffEffectTargetsFormatted]",
    "143108": "משפיע על [ItemAssetData(138582) ItemOrBuffEffectTargetsFormatted]",
    "143109": "משפיע על [ItemAssetData(138584) ItemOrBuffEffectTargetsFormatted]",
    "143135": "צמחים ייחודיים",
    "143136": "צמחים ייחודיים",
    "143137": "צמחים ייחודיים",
    "143140": "צמחים ייחודיים"
}

# Update trans dictionary
trans.update(missing_trans)

# Save trans_part_1.json
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(trans, f, ensure_ascii=False, indent=0)

# Load skip.json and append "139779"
skip_path = os.path.join(handoff, "skip.json")
if os.path.exists(skip_path):
    with open(skip_path, "r", encoding="utf-8") as f:
        skips = json.load(f)
else:
    skips = []

if "139779" not in skips:
    skips.append("139779")
    with open(skip_path, "w", encoding="utf-8") as f:
        json.dump(sorted(list(set(skips)), key=lambda x: int(x)), f, ensure_ascii=False, indent=0)

print("Updated trans_part_1.json and skip.json!")
