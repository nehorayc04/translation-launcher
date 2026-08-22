# -*- coding: utf-8 -*-
import os
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
EN_F = os.path.join(HERE, "english.json")
OUT_F = os.path.join(HERE, "hebrew.json")
PART1_F = os.path.join(HERE, "trans_8_part_1.json")
PART2_F = os.path.join(HERE, "trans_8_part_2.json")
PART3_F = os.path.join(HERE, "trans_8_part_3.json")
PART4_F = os.path.join(HERE, "trans_8_part_4.json")

TOK_RE = re.compile(
    r"\[\[S:[^\]]*\]\]|\[\[D:[^\]]*\]\]|\[/?style[^\]]*\]|\[/?i\]|\[Icons:[^\]]*\]|\[[A-Za-z][^\]]*Button\]|%d|%s|\\n|\\p"
)

def _load(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"Error loading {path}: {e}")
        return default

def validate(src, out):
    if not out or not out.strip():
        if src and src.strip() and src != "\\x{A0}":
            return "Empty translation"
        return None
    if re.search(r"[֑-ׇ]", out):  # niqqud
        return "Contains niqqud"
    if re.search(r"[؀-ۿЀ-ӿ一-鿿]", out):  # arabic/cyrillic/cjk
        return "Contains invalid unicode blocks"
    if "\\x{A0}" in out:
        return "Contains \\x{A0}"
    
    # Check tags
    src_tags = sorted(TOK_RE.findall(src))
    out_tags = sorted(TOK_RE.findall(out))
    if src_tags != out_tags:
        return f"Tag mismatch. Expected {src_tags}, got {out_tags}"
        
    return None

def main():
    en = _load(EN_F, {})
    heb = _load(OUT_F, {})
    part1 = _load(PART1_F, {})
    part2 = _load(PART2_F, {})
    part3 = _load(PART3_F, {})
    part4 = _load(PART4_F, {})
    
    new_translations = {}
    new_translations.update(part1)
    new_translations.update(part2)
    new_translations.update(part3)
    new_translations.update(part4)
    
    print(f"Loaded {len(new_translations)} new translations.")
    
    errors = 0
    validated_translations = {}
    for k, out in new_translations.items():
        src = en.get(k)
        if src is None:
            print(f"Error: Key {k} not found in english.json")
            errors += 1
            continue
            
        err = validate(src, out)
        if err:
            print(f"Error on key {k}: {err}")
            print(f"  English: {repr(src)}")
            print(f"  Hebrew:  {repr(out)}")
            errors += 1
        else:
            validated_translations[k] = out
            
    if errors > 0:
        print(f"Validation failed with {errors} errors. Aborting merge.")
        return 1
        
    # Merge and write atomically
    print("Validation passed. Merging and saving...")
    merged = {}
    merged.update(heb)
    merged.update(validated_translations)
    
    # Sort keys numerically to maintain order
    sorted_merged = {k: merged[k] for k in sorted(merged.keys(), key=int)}
    
    tmp = OUT_F + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(sorted_merged, f, ensure_ascii=False, indent=0)
    os.replace(tmp, OUT_F)
    
    print(f"Successfully merged. Total translations in hebrew.json now: {len(sorted_merged)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
