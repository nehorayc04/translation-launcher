# -*- coding: utf-8 -*-
"""Correctly resolve the 185 CPQA 'suspect' fixes, then scan the WHOLE corpus for the same
imperative-needs-a-split pattern. Everything here is DETERMINISTIC + reversible.

The suspect flag was mostly right to distrust the fleet's proposed fix:
  * 82 are FALSE POSITIVES — the engine already has a correct dual-gender split
    (femaleVariant feminine, maleVariant masculine). The fleet's fix would have made the
    femaleVariant masculine, breaking the female-V experience. -> REJECT (do nothing).
  * ~88 are backfilled (femaleVariant == maleVariant, both feminine). The RIGHT fix is a
    SPLIT: keep the feminine femaleVariant, set maleVariant to the masculine form. The fleet
    already handed us BOTH forms (old = feminine, new = masculine), so no inflector needed.
  * A curated handful of name/adjective corrections are genuine improvements -> ACCEPT.
  * The backwards over-corrections + common-word-collision names -> REJECT (keep current).

Then CORPUS-WIDE: any entry where femaleVariant == maleVariant and the value is exactly one of
the known feminine imperatives gets the same split (this is the "tip of the iceberg" the 88 hint at).

Backs up both spines; atomic. Emits affected_cpqa_fix2_sections.txt for a targeted re-bake.
Run: python fix_cpqa_suspects.py [--dry]
"""
import json, os, sys, time, collections, shutil

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
RES = os.path.join(ROOT, "תרגום_משחקים", "source", "resources")
BASE = os.path.join(RES, "localization_translated.json")
DLC = os.path.join(RES, "dlc_ep1_translated.json")
SUS = os.path.join(os.path.dirname(__file__), "cpqa_fixes_suspect.jsonl")
DRY = "--dry" in sys.argv

# Curated ACCEPT: genuine improvements (English is an adjective / a clean name-shortening).
ACCEPT = {
    ("באגסיי", "באגסי"),                     # Bagsy — consistent name shortening, no collision
    ("מיפוי מרחב", "מיפוי מרחבי"),           # Spatial Mapping
    ("לוח חשמל", "לוח חשמלי"),               # Electrical Panel
    ("שריון תת-עור", "שריון תת-עורי"),       # Subdermal Armor
    ("קולנוע בית", "קולנוע ביתי"),           # Home Cinema
    ("מצב בריאות", "מצב בריאותי"),           # Health Condition
    ("זיכרון שריר", "זיכרון שרירי"),         # Muscle Memory
    ("מסוף מרכז", "מסוף מרכזי"),             # Mainframe Terminal
    ("סיכון מקצוע", "סיכון מקצועי"),         # Occupational hazard
    ("חדר אחור", "חדר אחורי"),               # Back Room / Backroom
    ("רצח נציג תאגיד", "רצח נציג תאגידי"),   # Murder of a Corporate Rep.
    ("תקיפה על נציג תאגיד", "תקיפה על נציג תאגידי"),  # Battery of a Corporate Rep.
    ("מצלמה 16: עמוד דרום", "מצלמה 16: עמוד דרומי"),  # South Pillar
    ("מתקן תת-קרקע", "מתקן תת-קרקעי"),       # underground facility
}


def index(spine):
    idx = {}
    for sec, items in spine.items():
        for it in items:
            for kf in ("primaryKey", "stringId"):
                v = it.get(kf)
                if v is not None:
                    idx.setdefault((sec, str(v)), it)
    return idx


# EXPLICIT, controlled feminine->masculine imperative dictionary (verified from the suspects).
# Only real bare-verb UI imperatives — NEVER names/adjectives that merely end in a yod
# (a loose "old == new+'י'" rule pollutes this with אנדריי/אוטומטי/תאגידי and corrupts the corpus).
IMPERATIVE = {
    "שבי": "שב", "השתמשי": "השתמש", "דחפי": "דחף", "דברי": "דבר", "פתחי": "פתח",
    "חפשי": "חפש", "בחרי": "בחר", "נעלי": "נעל", "שלחי": "שלח", "קראי": "קרא",
    "אתרי": "אתר", "הפעלי": "הפעל", "התכופפי": "התכופף", "עצורי": "עצור",
    "התפללי": "התפלל", "נגני": "נגן", "הסתערי": "הסתער", "התחברי": "התחבר",
    "תפסי": "תפס", "רדי": "רד", "החזקי": "החזק", "בצעי": "בצע", "שחררי": "שחרר",
    "הרוגי": "הרוג", "הזיזי": "הזיז", "הממי": "המם",
}


def is_gender_pair(old, new):
    """old is a KNOWN single-word feminine imperative whose masculine == new."""
    return IMPERATIVE.get(old.strip()) == new.strip()


def main():
    base = json.load(open(BASE, encoding="utf-8"))
    dlc = json.load(open(DLC, encoding="utf-8"))
    bidx, didx = index(base), index(dlc)
    sus = [json.loads(l) for l in open(SUS, encoding="utf-8")]

    rej_split = split = accepted = rej_other = miss = 0
    fem2masc = {}                                  # known imperative dict for the corpus scan
    touched = set()

    def note(sec):
        if "subtitles" in sec and "ep1" not in sec:
            touched.add(sec)

    for r in sus:
        fid = r["id"]; parts = fid.split(":"); pk = parts[-1]; sec = ":".join(parts[1:-1])
        is_dlc = "ep1" in sec
        it = (didx if is_dlc else bidx).get((sec, pk))
        if it is None:
            miss += 1; continue
        fv = it.get("femaleVariant", ""); mv = it.get("maleVariant", "")
        old = r.get("old", ""); new = r.get("new", "")
        if fv == old and mv == new:                # already a correct split
            rej_split += 1; continue
        if fv == mv == old and is_gender_pair(old, new):   # backfilled -> real split
            if not DRY:
                it["maleVariant"] = new            # keep feminine fV, add masculine mV
            fem2masc[old.strip()] = new.strip()
            split += 1; note(sec)
        elif (old, new) in ACCEPT and fv == old:   # curated good name/adjective fix (guarded)
            if not DRY:
                it["femaleVariant"] = new
                if mv == old:
                    it["maleVariant"] = new
            accepted += 1; note(sec)
        else:
            rej_other += 1                          # backwards / collision / ambiguous -> keep current

    print(f"suspects: split(fixed) {split} | accepted {accepted} | reject-already-split {rej_split} "
          f"| reject-other {rej_other} | miss {miss}")
    print(f"known feminine imperatives for corpus scan: {sorted(fem2masc)}")

    # ---- corpus-wide: same split wherever fV==mV and fV is exactly a known imperative ----
    corp_split = 0
    for spine, idx in ((base, bidx), (dlc, didx)):
        for sec, items in spine.items():
            for it in items:
                fv = it.get("femaleVariant", ""); mv = it.get("maleVariant", "")
                key = fv.strip()
                if fv and fv == mv and key in IMPERATIVE:
                    if not DRY:
                        it["maleVariant"] = IMPERATIVE[key]
                    corp_split += 1
                    if "subtitles" in sec and "ep1" not in sec:
                        touched.add(sec)
    print(f"corpus-wide imperative splits (fV==mV, exact imperative): {corp_split}")
    print(f"affected base-subtitle sections: {len(touched)}")

    if DRY:
        print("DRY — nothing written"); return

    ts = time.strftime("%Y%m%d_%H%M%S")
    for path, obj in ((BASE, base), (DLC, dlc)):
        bak = f"{path}.bak.cpqa2.{ts}"
        if not os.path.exists(bak):
            shutil.copy2(path, bak)
        tmp = path + ".tmp"
        json.dump(obj, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(tmp, path)
        print(f"  wrote {os.path.basename(path)}  (backup {os.path.basename(bak)})")
    secfile = os.path.join(os.path.dirname(__file__), "affected_cpqa_fix2_sections.txt")
    open(secfile, "w", encoding="utf-8").write("\n".join(sorted(touched)))
    print(f"  wrote {secfile} ({len(touched)} sections)")


if __name__ == "__main__":
    main()
