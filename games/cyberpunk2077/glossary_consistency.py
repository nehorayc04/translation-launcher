# -*- coding: utf-8 -*-
"""glossary_consistency.py — name-consistency report across the whole corpus.

For every glossary term (places, gangs, corps, people): find all rows whose
ENGLISH contains the term, and bucket the Hebrew rendering — which known
variant it uses, or OTHER (sample shown). The output exposes exactly the
"mission says X, map says Y" inconsistencies.

Output: glossary_report.txt (+ .jsonl). Read-only.
"""
import os, sys, json, re, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "universal"))
import get_next_audit_batch as G

# term -> list of known/expected Hebrew variants (first = preferred so far)
GLOSSARY = {
    "Night City":    ["נייט סיטי", "נייט-סיטי", "Night City", "סיטי הלילה", "עיר הלילה"],
    "Badlands":      ["באדלנדס", "בדלנדס", "Badlands", "ארצות החרבה"],
    "Watson":        ["ווטסון", "וואטסון", "וטסון", "Watson"],
    "Westbrook":     ["וסטברוק", "ווסטברוק", "Westbrook"],
    "Heywood":       ["הייווד", "היווד", "Heywood"],
    "Pacifica":      ["פסיפיקה", "פאסיפיקה", "Pacifica"],
    "Santo Domingo": ["סנטו דומינגו", "Santo Domingo"],
    "City Center":   ["סיטי סנטר", "מרכז העיר", "City Center"],
    "Japantown":     ["ג'פנטאון", "יפנטאון", "Japantown"],
    "Kabuki":        ["קאבוקי", "קבוקי", "Kabuki"],
    "Arasaka":       ["אראסאקה", "ארסאקה", "אראסקה", "Arasaka"],
    "Militech":      ["מיליטק", "מיליטך", "Militech"],
    "Biotechnica":   ["ביוטכניקה", "Biotechnica"],
    "Kang Tao":      ["קאנג טאו", "קאנג-טאו", "Kang Tao"],
    "Zetatech":      ["זטאטק", "זטהטק", "זטאטך", "Zetatech"],
    "Petrochem":     ["פטרוכם", "פטרוקם", "Petrochem"],
    "NetWatch":      ["נטווטש", "נטוואץ'", "NetWatch"],
    "Trauma Team":   ["טראומה טים", "צוות טראומה", "Trauma Team"],
    "NCPD":          ["משטרת נייט סיטי", "NCPD", "נ.ס.פ.ד"],
    "Maelstrom":     ["מאלסטרום", "מלסטרום", "Maelstrom"],
    "Wraiths":       ["רייתס", "ורייתס", "Wraiths", "רוחות"],
    "Tyger Claws":   ["טייגר קלוז", "טופרי הטיגריס", "Tyger Claws"],
    "Valentinos":    ["ולנטינוס", "וולנטינוס", "Valentinos"],
    "6th Street":    ["הרחוב השישי", "סיקסת' סטריט", "6th Street"],
    "Voodoo Boys":   ["וודו בויז", "נערי הוודו", "Voodoo Boys"],
    "Animals":       ["אנימלס", "החיות", "Animals"],
    "Moxes":         ["מוקסס", "מוקס", "Moxes"],
    "Scavengers":    ["סקאבנג'רס", "סקאבס", "נבלנים", "Scavengers"],
    "Afterlife":     ["אפטרלייף", "העולם הבא", "Afterlife"],
    "Totentanz":     ["טוטנטאנז", "טוטנטנץ", "Totentanz"],
    "Konpeki Plaza": ["קונפקי פלאזה", "קונפקי", "Konpeki"],
    "Lizzie":        ["ליזי", "Lizzie"],
    "Delamain":      ["דלאמיין", "דלמיין", "דלהמיין", "Delamain"],
    "Johnny":        ["ג'וני", "ג'וני סילברהנד", "Johnny"],
    "Silverhand":    ["סילברהנד", "סילבר-הנד", "Silverhand"],
    "Panam":         ["פאנם", "פאנאם", "פנאם", "Panam"],
    "Judy":          ["ג'ודי", "Judy"],
    "Jackie":        ["ג'קי", "Jackie"],
    "Rogue":         ["רוג", "רוג'", "Rogue"],
    "Takemura":      ["טאקמורה", "טקמורה", "Takemura"],
    "Yorinobu":      ["יורינובו", "Yorinobu"],
    "Saburo":        ["סאבורו", "סבורו", "Saburo"],
    "Evelyn":        ["אוולין", "אבלין", "Evelyn"],
    "Dexter":        ["דקסטר", "Dexter"],
    "DeShawn":       ["דה-שון", "דשון", "דה שון", "DeShawn"],
    "Alt Cunningham": ["אלט קנינגהם", "אלט"],
    "Kerry":         ["קרי", "Kerry"],
    "River":         ["ריבר", "River"],
    "Viktor":        ["ויקטור", "Viktor"],
    "Misty":         ["מיסטי", "Misty"],
    "Edgewood":      ["אדג'ווד", "Edgewood"],
    "Bellevue":      ["בלוויו", "בלוו", "Bellevue"],
}


def main():
    corpus, _, _ = G.build_corpus()
    report = []
    jl = []
    for term, variants in GLOSSARY.items():
        t_re = re.compile(rf"(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])", re.I)
        buckets = collections.Counter()
        other_samples = []
        total = 0
        for r in corpus:
            en, he = r.english or "", r.hebrew or ""
            if not he or not t_re.search(en):
                continue
            total += 1
            for v in variants:
                if v in he:
                    buckets[v] += 1
                    break
            else:
                buckets["OTHER/missing"] += 1
                if len(other_samples) < 5:
                    other_samples.append((r.section.split("/")[-1][:18], str(r.pk), he[:70]))
        if total == 0:
            continue
        distinct = [k for k in buckets if k != "OTHER/missing"]
        flag = "  <<< INCONSISTENT" if len(distinct) > 1 else ""
        report.append(f"### {term} — {total} rows{flag}")
        for v, n in buckets.most_common():
            report.append(f"    {v!r}: {n}")
        for s in other_samples:
            report.append(f"      other: [{s[0]}] pk={s[1]} :: {s[2]!r}")
        report.append("")
        jl.append({"term": term, "total": total,
                   "buckets": dict(buckets), "inconsistent": len(distinct) > 1})

    open(os.path.join(HERE, "glossary_report.txt"), "w", encoding="utf-8").write(
        "\n".join(["דוח עקביות שמות — וריאציות תרגום לכל שם", "=" * 50, ""] + report))
    with open(os.path.join(HERE, "glossary_report.jsonl"), "w", encoding="utf-8") as f:
        for x in jl:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    bad = [x["term"] for x in jl if x["inconsistent"]]
    print(f"terms checked: {len(jl)} | INCONSISTENT: {len(bad)}")
    print("  " + ", ".join(bad))
    print("-> glossary_report.txt")


if __name__ == "__main__":
    main()
