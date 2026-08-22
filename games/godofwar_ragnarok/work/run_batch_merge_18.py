# -*- coding: utf-8 -*-
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
EN_F = os.path.join(HERE, "english.json")
HEB_F = os.path.join(HERE, "hebrew.json")

TOK_RE = r"\[\[S:[^\]]*\]\]|\[\[D:[^\]]*\]\]|\[/?style[^\]]*\]|\[/?i\]|\[Icons:[^\]]*\]|\[[A-Za-z][^\]]*Button\]|%d|%s|\\n|\\p"

def validate(en, heb):
    errors = []
    for k, v in heb.items():
        if k not in en:
            continue
        et = re.findall(TOK_RE, en[k])
        ht = re.findall(TOK_RE, v)
        if et != ht:
            errors.append((k, et, ht))
    return errors

def main():
    en = json.load(open(EN_F, encoding="utf-8"))
    heb = json.load(open(HEB_F, encoding="utf-8"))

    new = {}
    for i in range(1, 5):  # parts 1-4
        pf = os.path.join(HERE, f"trans_18_part_{i}.json")
        part = json.load(open(pf, encoding="utf-8"))
        new.update(part)

    print(f"Loaded {len(new)} new translations.")
    errs = validate(en, new)
    if errs:
        for k, et, ht in errs:
            print(f"  TAG MISMATCH {k}: expected {et}, got {ht}")
            print(f"  English: {en[k]}")
            print(f"  Hebrew : {new[k]}")
        print(f"VALIDATION FAILED — {len(errs)} errors. Aborting.")
        return

    print("Validation passed. Merging and saving...")
    heb.update(new)
    with open(HEB_F, "w", encoding="utf-8") as f:
        json.dump(heb, f, ensure_ascii=False, indent=2)
    print(f"Successfully merged. Total translations in hebrew.json now: {len(heb)}")

if __name__ == "__main__":
    main()
