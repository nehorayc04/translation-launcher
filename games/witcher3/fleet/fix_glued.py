# -*- coding: utf-8 -*-
"""Fix the SYSTEMATIC untranslated-English fragments the fleet glued into Hebrew words.
Only unambiguous, canonical single words (Geralt / vampire / crystal / legendary / laughter).
Regexes preserve the Hebrew prefix/suffix around the Latin fragment. --apply writes (backup);
default dry-run prints before/after samples + a total count."""
import json, os, re, sys, time, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
BANK = os.path.join(HERE, "hebrew.json")

# (regex, replacement) — applied in order, case-insensitive on the Latin part.
RULES = [
    # Geralt: "גרALT" / "לגרALT" / "כשג'רaltı" -> גראלט  (keep the Hebrew prefix before גר / ג'ר)
    (re.compile(r"(ג'?)ר\s?alt[ıiİI]?", re.I), r"\1ראלט"),
    # vampire: "וampire" / "וampireים" -> ערפד / ערפדים  (the ו is the transliterated v)
    (re.compile(r"ו?ampire", re.I), "ערפד"),
    # crystal: "kristל" / "krist" -> קריסטל
    (re.compile(r"krist(?:al)?ל?", re.I), "קריסטל"),
    # legendary (item rarity) -> אגדי/אגדית/אגדיים/אגדיות by the Hebrew suffix the model kept
    (re.compile(r"א?legend(?:ary)?ר?יות", re.I), "אגדיות"),
    (re.compile(r"א?legend(?:ary)?ר?יים", re.I), "אגדיים"),
    (re.compile(r"א?legend(?:ary)?ר?י[תה]", re.I), "אגדית"),
    (re.compile(r"א?legend(?:ary)?ר?י", re.I), "אגדי"),
    (re.compile(r"א?legendary", re.I), "אגדי"),
    # laughter: "הahaha" / "אהahaha" -> האהאהא (consume the model's leading ה = the first 'ha')
    (re.compile(r"ה?(?:ah)+aha", re.I), "האהאהא"),
]


def fix(s):
    for rx, rep in RULES:
        s = rx.sub(rep, s)
    return s


def main(apply=False):
    heb = json.load(open(BANK, encoding="utf-8"))
    changed = {}
    for sid, s in heb.items():
        ns = fix(s)
        if ns != s:
            changed[sid] = (s, ns)
    print(f"strings changed: {len(changed)}")
    for sid, (o, n) in list(changed.items())[:16]:
        # show the first differing word region
        print(f"  [{sid}] {o[:46]!r}\n         -> {n[:46]!r}")
    if apply and changed:
        shutil.copy2(BANK, f"{BANK}.bak.glued.{int(time.time())}")
        for sid, (o, n) in changed.items():
            heb[sid] = n
        json.dump(heb, open(BANK + ".tmp", "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(BANK + ".tmp", BANK)
        print(f"APPLIED to {len(changed)} strings (backup saved).")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
