"""Add the entries the corpus filter had excluded, so the /translate pool holds EVERY line
of both LocalizationPackages with no filtering at all."""
import sys, os, json, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "games", "assassinscreed2", "tools"))
sys.path.insert(0, r"c:/Users/Nehoray_Cohen/Projects/Game translator/games/assassinscreed2/tools")
import ac2_forge, ac2_loc

GAME = r"D:/Games/Assassin's Creed II"
fg = ac2_forge.Forge(GAME + "/_HE_BACKUP/DataPC.forge")
IDX = {n: i for i, n in enumerate(fg.names) if n}


def load(name):
    slot, _, _ = fg.full_slot(IDX[name])
    _s, _p, strings = ac2_loc.decode_payload(ac2_loc.extract_payload(slot))
    return {int(k): v for k, v in strings}


CAT = {"ui": "ממשק ותפריטים", "sub": "כתוביות עלילה"}
existing = {r["string_key"] for r in json.load(
    open(os.path.join(HERE, "..", "extract", "ct_strings.json"), encoding="utf-8"))}

rows = []
order = 900000
for sec, nm in (("ui", "LocalizationPackage_English"), ("sub", "LocalizationPackage_English_Subtitles")):
    for k, v in load(nm).items():
        key = f"{sec}:{k}"
        if key in existing:
            continue
        order += 1
        rows.append({
            "string_key": key,
            "source_en": v if v is not None else "",
            "current_he": "",
            "context": CAT[sec] + " | קוד/מספר - בדרך כלל נשאר כפי שהוא",
            "section": CAT[sec],
            "order_index": order,
        })
out = os.path.join(HERE, "..", "extract", "ct_strings_extra.json")
json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False)
print(f"extra rows (previously filtered out): {len(rows)}")
for r in rows[:15]:
    print(f"   {r['string_key']:14} {r['source_en']!r}")
print("->", out)
