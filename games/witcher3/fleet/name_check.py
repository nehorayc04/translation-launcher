# -*- coding: utf-8 -*-
import json, glob

he = json.load(open("hebrew.json", encoding="utf-8"))
vals = list(he.values())

# name -> plausible Hebrew transliteration variants
names = {
    "Geralt":     ["גראלט", "ג'ראלט", "ג'רלט", "גרלט", "גירלט"],
    "Ciri":       ["סירי", "צירי", "קירי"],
    "Yennefer":   ["יניפר", "ינפר", "ג'ניפר", "יאנפר", "יאניפר"],
    "Triss":      ["טריס", "טריז", "טרייס"],
    "Dandelion":  ["דנדליון", "יסקייר", "יאסקייר", "דנדיליון", "דנדלינה"],
    "Vesemir":    ["וסמיר", "ווסמיר", "וזמיר"],
    "Regis":      ["רגיס", "ריגיס", "רג'יס"],
    "Novigrad":   ["נוביגרד", "נוביגראד", "נובימרד"],
    "Velen":      ["ולן", "וולן", "וילן"],
    "Skellige":   ["סקליגה", "סקליג", "סקאליגה", "סקליגא", "סקלינה"],
    "Nilfgaard":  ["נילפגארד", "נילפגרד", "נילפגאארד", "נילפגארט"],
    "Toussaint":  ["טוסאן", "טוסן", "טוסאנט"],
    "Beauclair":  ["בוקלייר", "בוקלר", "בקלייר", "בוקלייה"],
    "Kaer Morhen":["קאר מורהן", "קר מורהן", "קאאר מורהן", "קאר מורן", "קר מורן"],
    "Emhyr":      ["אמהיר", "אמהייר", "אמהר"],
    "Redania":    ["רדניה", "רידניה", "ראדניה"],
}

for nm, variants in names.items():
    counts = {}
    for v in variants:
        c = sum(t.count(v) for t in vals)
        if c:
            counts[v] = c
    if not counts:
        print(f"{nm:12}: (none found)")
        continue
    total = sum(counts.values())
    top = max(counts.values())
    if len(counts) == 1:
        tag = "OK (1 form)"
    elif top / total >= 0.92:
        tag = "OK-dominant"
    else:
        tag = "*** INCONSISTENT ***"
    order = dict(sorted(counts.items(), key=lambda x: -x[1]))
    print(f"{nm:12}: {order}  -> {tag}")
