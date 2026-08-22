#!/usr/bin/env python3
"""Independent verification of the two candidate KCAP .xpps readers."""
import os, sys, json, struct, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.dirname(HERE)
EN = os.path.join(GAME, "extract", "lang_english_text.xpps")
AR = os.path.join(GAME, "extract", "lang_arabic_text.xpps")
TOOLS = os.path.join(GAME, "tools")

def load(mod, path):
    spec = importlib.util.spec_from_file_location(mod, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def is_ar(s):
    return any('؀' <= c <= 'ۿ' or 'ݐ' <= c <= 'ݿ' or
               'ﭐ' <= c <= '﷿' or 'ﹰ' <= c <= '﻿' for c in s)

def run_reader(name, path):
    try:
        m = load(name, path)
    except Exception as e:
        return None, f"load fail: {e}"
    try:
        en = m.read_pack(EN)
        ar = m.read_pack(AR)
        return (m, en, ar), None
    except Exception as e:
        import traceback
        return None, f"read fail: {traceback.format_exc()}"

report = {}
for name, fn in [("xpps", os.path.join(TOOLS,"xpps.py")),
                 ("xpps_alt", os.path.join(TOOLS,"xpps_alt.py"))]:
    print("="*70)
    print("READER:", name)
    res, err = run_reader(name, fn)
    if err:
        print("  ERROR:", err)
        report[name] = {"error": err}
        continue
    m, en, ar = res
    common = set(en) & set(ar)
    # translated pairs: EN has latin letters, AR value differs and is arabic
    trans = 0
    latin_en = 0
    for k in common:
        e, a = en[k], ar[k]
        if any('a'<=c.lower()<='z' for c in e):
            latin_en += 1
            if is_ar(a) and a != e:
                trans += 1
    rep = {
        "EN": len(en), "AR": len(ar), "overlap": len(common),
        "EN_only": len(en)-len(common), "AR_only": len(ar)-len(common),
        "common_with_latin_EN": latin_en,
        "common_EN_latin_AR_arabic_translated": trans,
        "translated_frac_of_latin_common": round(trans/latin_en,4) if latin_en else 0,
    }
    print("  ", json.dumps(rep, ensure_ascii=False))
    report[name] = rep

    # spot-check 10 pairs where EN is latin, AR is arabic, differ
    print("  --- 10 spot-check pairs (EN -> AR) ---")
    shown = []
    for k in sorted(common):
        e, a = en[k], ar[k]
        if any('a'<=c.lower()<='z' for c in e) and is_ar(a) and a != e and 2<len(e)<40:
            shown.append((k, e, a))
        if len(shown) >= 10:
            break
    for k,e,a in shown:
        print(f"    {k}  EN={e!r}  AR={a!r}")
    report[name]["spotcheck"] = [{"id":k,"en":e,"ar":a} for k,e,a in shown]

with open(os.path.join(HERE,"verify_out.json"),"w",encoding="utf-8") as f:
    json.dump(report,f,ensure_ascii=False,indent=1)
print("\nwrote verify_out.json")
