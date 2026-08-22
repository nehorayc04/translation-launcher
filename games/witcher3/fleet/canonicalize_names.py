# -*- coding: utf-8 -*-
"""Deterministic name canonicalization for the W3 Hebrew corpus.

Folds every variant spelling of a name into its CANONICAL Hebrew form (verified
vs Hebrew Wikipedia + the Hebrew "המכשף" book translations). Word-boundary safe
and Hebrew-prefix aware (ב/ה/ו/כ/ל/מ/ש stays, e.g. בנוביגראד -> בנוביגרד).

This is spelling NORMALISATION of existing Hebrew (not translation) — matches
the SM2 names_apply / CP2077 deterministic-fix pattern.

Usage:  py canonicalize_names.py            # dry-run: counts + sample changed lines
        py canonicalize_names.py --apply    # backup + rewrite hebrew.json
"""
import json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
HE = os.path.join(HERE, "hebrew.json")

# canonical -> [variant spellings to fold in]  (canonical itself is left as-is)
CANON = {
    "גראלט":      ["ג'רלט", "גרלט", "ג'ראלט", "גירלט"],
    "סירי":       ["קירי", "צירי"],
    "ינפר":       ["יניפר", "יאנפר", "יאניפר"],
    "טריס":       ["טריז", "טרייס"],
    "וזמיר":      ["וסמיר", "ווסמיר"],
    "רגיס":       ["רג'יס", "ריגיס"],
    "נוביגרד":    ["נוביגראד", "נובימרד"],
    "סקליגה":     ["סקליג"],                       # bare -> full (boundary blocks סקליגה itself)
    "נילפגארד":   ["נילפגרד", "נילפגאארד", "נילפגארט"],
    "טוסאן":      ["טוסאנט"],                       # keep טוסן? no — fold to טוסאן
    "קאר מורהן":  ["קאר מורן", "קר מורן", "קר מורהן", "קאאר מורהן"],
    "אמהיר":      ["אמהייר", "אמהר"],
    "רדאניה":     ["רדניה", "רידניה", "ראדניה"],
    "בוקלייר":    ["בוקלר", "בקלייר", "בוקלייה"],
    "ולן":        ["וילן", "וולן"],                # Velen VEH-len -> ולן
}
# also fold single-token טוסן -> טוסאן (added separately to avoid it being a substring pitfall)
CANON["טוסאן"].append("טוסן")

PREFIX = "בהוכלמש"  # one optional Hebrew prefix letter may precede a name

def build_subs():
    subs = []  # (regex, canonical)
    for canon, variants in CANON.items():
        for v in variants:
            # optional single prefix, then the variant as a whole Hebrew token
            rx = re.compile(rf"(?<![א-ת])([{PREFIX}]?){re.escape(v)}(?![א-ת])")
            subs.append((rx, canon))
    # apply longer variants first so a short one never eats a longer match
    subs.sort(key=lambda s: -len(s[0].pattern))
    return subs

def apply_line(s, subs):
    changed = 0
    for rx, canon in subs:
        def repl(m):
            nonlocal changed
            changed += 1
            return m.group(1) + canon
        s = rx.sub(repl, s)
    return s, changed

def main():
    apply = "--apply" in sys.argv
    he = json.load(open(HE, encoding="utf-8"))
    subs = build_subs()
    total_changes = 0; changed_lines = 0; samples = []
    new = {}
    for k, v in he.items():
        nv, c = apply_line(v, subs)
        new[k] = nv
        if c:
            total_changes += c; changed_lines += 1
            if len(samples) < 12 and v != nv:
                samples.append((k, v[:55], nv[:55]))
    print(f"variants folded: {total_changes} replacements across {changed_lines} lines")
    for k, a, b in samples:
        print(f"  {k}: {a!r}\n       -> {b!r}")
    if apply:
        bak = HE + f".bak.names.{time.strftime('%Y%m%d_%H%M%S')}"
        json.dump(he, open(bak, "w", encoding="utf-8"), ensure_ascii=False)
        json.dump(new, open(HE + ".tmp", "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(HE + ".tmp", HE)
        print(f"\nAPPLIED. backup -> {os.path.basename(bak)}")
    else:
        print("\n(dry-run) nothing written. Re-run with --apply.")

if __name__ == "__main__":
    main()
