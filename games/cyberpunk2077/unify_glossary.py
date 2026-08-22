# -*- coding: utf-8 -*-
"""unify_glossary.py — unify name variants to ONE canonical rendering.

Canonical = corpus majority + the user's precedents (Hebrew transliteration
for people/places/gangs/corps; English for product brands). Two replace
kinds:
  - Hebrew variants: plain substring replace (safe).
  - Latin variants: ONLY when the row's EN really contains the term AND the
    Latin token stands alone (not inside a larger English phrase / 's).
Deliberately SKIPPED (context-dependent, left to the model/human): NCPD vs
משטרת נייט סיטי (both valid), 6th Street, Animals, Afterlife's OTHER bucket,
Wraiths' 'רוחות' rows, Alt's short form.

Usage: python unify_glossary.py [--dry-run] [--dlc]
"""
import os, sys, json, re, time, shutil, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "universal"))
import get_next_audit_batch as G
import cp2077_qa_defects as Q

# canonical, [hebrew variants to replace], [latin variants to replace], en-term
RULES = [
    ("נייט סיטי",   ["נייט-סיטי"],                       ["Night City"],   "Night City"),
    ("באדלנדס",     ["בדלנדס"],                           ["Badlands"],     "Badlands"),
    ("ווטסון",      ["וואטסון"],                          ["Watson"],       "Watson"),
    ("וסטברוק",     ["ווסטברוק"],                         ["Westbrook"],    "Westbrook"),
    ("הייווד",      ["היווד"],                            ["Heywood"],      "Heywood"),
    ("פסיפיקה",     ["פאסיפיקה"],                         ["Pacifica"],     "Pacifica"),
    ("סנטו דומינגו", [],                                   ["Santo Domingo"],"Santo Domingo"),
    ("מרכז העיר",   ["סיטי סנטר"],                        [],               "City Center"),
    ("ג'פנטאון",    ["יפנטאון"],                          ["Japantown"],    "Japantown"),
    ("קבוקי",       ["קאבוקי"],                           [],               "Kabuki"),
    ("אראסאקה",     ["אראסקה", "ארסאקה", "אראסקא"],      ["Arasaka"],      "Arasaka"),
    ("מיליטק",      ["מיליטך"],                           ["Militech"],     "Militech"),
    ("ביוטכניקה",   [],                                    ["Biotechnica"],  "Biotechnica"),
    ("קאנג טאו",    ["קאנג-טאו"],                         ["Kang Tao"],     "Kang Tao"),
    ("פטרוכם",      ["פטרוקם"],                           ["Petrochem"],    "Petrochem"),
    ("נטווטש",      ["נטוואץ'"],                          ["NetWatch"],     "NetWatch"),
    ("צוות טראומה", ["טראומה טים"],                       ["Trauma Team"],  "Trauma Team"),
    ("מאלסטרום",    ["מלסטרום"],                          ["Maelstrom"],    "Maelstrom"),
    ("רייתס",       [],                                    ["Wraiths"],      "Wraiths"),
    ("טייגר קלוז",  [],                                    ["Tyger Claws"],  "Tyger Claws"),
    ("ולנטינוס",    ["וולנטינוס"],                        ["Valentinos"],   "Valentinos"),
    ("וודו בויז",   [],                                    ["Voodoo Boys"],  "Voodoo Boys"),
    ("טוטנטאנז",    ["טוטנטנז", "טוטנטנץ"],              ["Totentanz"],    "Totentanz"),
    ("קונפקי פלאזה", [],                                   ["Konpeki Plaza"],"Konpeki Plaza"),
    ("קונפקי",      [],                                    ["Konpeki"],      "Konpeki"),
    ("דלמיין",      ["דלאמיין", "דלהמיין"],               ["Delamain"],     "Delamain"),
    ("סילברהנד",    ["סילבר-הנד"],                        ["Silverhand"],   "Silverhand"),
    ("פאנם",        ["פאנאם", "פנאם"],                    ["Panam"],        "Panam"),
    ("ג'קי",        [],                                    ["Jackie"],       "Jackie"),
    ("סאבורו",      ["סבורו"],                            ["Saburo"],       "Saburo"),
    ("אוולין",      ["אבלין"],                            ["Evelyn"],       "Evelyn"),
    ("קרי",         [],                                    ["Kerry"],        "Kerry"),
    ("ויקטור",      [],                                    ["Viktor"],       "Viktor"),
    ("מיסטי",       [],                                    ["Misty"],        "Misty"),
    ("אדג'ווד",     [],                                    ["Edgewood"],     "Edgewood"),
    ("אפטרלייף",    [],                                    [],               "Afterlife"),
]

TAG = re.compile(r"(<[^>]*>|\{[^}]*\})")


def latin_re(v):
    # standalone Latin token: no Latin/apostrophe-s context around it
    return re.compile(rf"(?<![A-Za-z])({re.escape(v)})(?!['’]?s)(?![A-Za-z])")


def main():
    dry = "--dry-run" in sys.argv
    path = G.DLC_TR if "--dlc" in sys.argv else G.BASE_TR
    corpus, _, _ = G.build_corpus()
    en_by = {(r.section, str(r.pk), r.field): (r.english or "") for r in corpus}
    data = json.load(open(path, encoding="utf-8"))
    cnt = collections.Counter()
    changed = 0
    for sec, rows in data.items():
        if not isinstance(rows, list):
            continue
        for e in rows:
            if not isinstance(e, dict):
                continue
            pk = str(e.get("primaryKey") or e.get("stringId"))
            for fld in ("femaleVariant", "maleVariant"):
                v = e.get(fld)
                if not v:
                    continue
                en = en_by.get((sec, pk, fld), "")
                nv = v
                for canon, hebs, lats, term in RULES:
                    for h in hebs:
                        if h in nv:
                            nv = nv.replace(h, canon)
                            cnt[f"{h}->{canon}"] += 1
                    if lats and term.lower() in en.lower():
                        # replace only OUTSIDE tags
                        parts = TAG.split(nv)
                        out = []
                        for p in parts:
                            if TAG.fullmatch(p):
                                out.append(p)
                                continue
                            for lv in lats:
                                p2 = latin_re(lv).sub(canon, p)
                                if p2 != p:
                                    cnt[f"{lv}->{canon}"] += 1
                                    p = p2
                            out.append(p)
                        nv = "".join(out)
                if nv != v:
                    changed += 1
                    if not dry:
                        e[fld] = nv
    print(f"{'DRY-RUN ' if dry else ''}values changed: {changed}")
    for k, n in cnt.most_common(20):
        print(f"  {k}: {n}")
    if dry or not changed:
        return
    if not Q.acquire_lock("unify_glossary"):
        sys.exit("[abort] QA lock held")
    try:
        bak = f"{path}.bak.glossary.{time.strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(path, bak)
        tmp = path + ".tmp"
        json.dump(data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(tmp, path)
        print(f"saved; backup {os.path.basename(bak)}")
    finally:
        Q.release_lock()


if __name__ == "__main__":
    main()
