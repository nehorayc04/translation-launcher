# -*- coding: utf-8 -*-
"""Extends fix_cpqa_suspects.py's dual-gender split with 11 more feminine-imperative pairs the
original curated 26-word list missed. Found by an independent audit (2026-07-31) of the ORIGINAL
55,259 CPQA fixes: any onscreens fix where the English source is a single-word UI action verb
(Buy/Leave/Drop/Drink/Scan/Examine/Wait/Reject/Unequip/Confess) and the fleet's "old"->"new" pair
is a feminine->masculine imperative flip. Cross-checked against localization_translated.json:
30 instances in onscreens.json + 16 in onscreens_final.json were left FLATTENED (femaleVariant ==
maleVariant == the masculine "new" word) — the feminine form the fleet itself supplied as "old" was
discarded instead of being kept as the female slot. Same root cause + same fix shape as
fix_cpqa_suspects.py's corpus-wide pass, just with a wider verified word list.

DETERMINISTIC, no LM, no new translation: both forms (feminine + masculine) were already produced
by the fleet review itself — this only re-attaches the feminine one to femaleVariant instead of
letting it be overwritten. Backs up both spines; atomic; reversible.

Run: python fix_cpqa_gender_gap2.py [--dry]
"""
import json, os, sys, shutil, time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
RES = os.path.join(ROOT, "תרגום_משחקים", "source", "resources")
BASE = os.path.join(RES, "localization_translated.json")
DLC = os.path.join(RES, "dlc_ep1_translated.json")
DRY = "--dry" in sys.argv

# feminine imperative -> masculine imperative, verified against the fleet's own old/new pairs
IMPERATIVE2 = {
    "קני": "קנה",        # Buy
    "עזבי": "עזוב",       # Leave
    "התוודי": "התוודה",   # Confess
    "השליכי": "השלך",    # Drop (variant A)
    "הפילי": "הפל",       # Drop (variant B)
    "שתי": "שתה",        # Drink
    "סרקי": "סרוק",       # Scan
    "בדקי": "בדוק",       # Examine
    "חכי": "חכה",        # Wait
    "דחי": "דחה",         # Reject
    "הסירי": "הסר",       # Unequip
}


def main():
    base = json.load(open(BASE, encoding="utf-8"))
    dlc = json.load(open(DLC, encoding="utf-8"))

    split = 0
    touched_subs = set()

    # reverse map: masculine word (what a flattened entry now holds in BOTH slots) -> feminine word
    masc_to_fem = {}
    for fem, masc in IMPERATIVE2.items():
        masc_to_fem.setdefault(masc, fem)

    for spine, is_dlc in ((base, False), (dlc, True)):
        for sec, items in spine.items():
            for it in items:
                fv = it.get("femaleVariant", "")
                mv = it.get("maleVariant", "")
                if not isinstance(fv, str) or not isinstance(mv, str):
                    continue
                if fv != mv:
                    continue
                masc_val = fv.strip()
                fem_val = masc_to_fem.get(masc_val)
                if not fem_val:
                    continue
                if not DRY:
                    it["femaleVariant"] = fem_val
                split += 1
                if "subtitles" in sec and "ep1" not in sec:
                    touched_subs.add(sec)

    print(f"restored femaleVariant on {split} flattened entries (base+DLC)")
    print(f"affected base-subtitle sections: {len(touched_subs)}")
    if touched_subs:
        for s in sorted(touched_subs):
            print(f"  {s}")

    if DRY:
        print("DRY — nothing written")
        return

    ts = time.strftime("%Y%m%d_%H%M%S")
    for path, obj in ((BASE, base), (DLC, dlc)):
        bak = f"{path}.bak.cpqa_gap2.{ts}"
        if not os.path.exists(bak):
            shutil.copy2(path, bak)
        tmp = path + ".tmp"
        json.dump(obj, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(tmp, path)
        print(f"  wrote {os.path.basename(path)}  (backup {os.path.basename(bak)})")

    secfile = os.path.join(os.path.dirname(__file__), "affected_cpqa_gap2_sections.txt")
    open(secfile, "w", encoding="utf-8").write("\n".join(sorted(touched_subs)))
    print(f"  wrote {secfile} ({len(touched_subs)} sections)")


if __name__ == "__main__":
    main()
