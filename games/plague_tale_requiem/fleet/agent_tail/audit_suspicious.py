#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Flag entries an agent may have FORCE-translated to beat the has-Hebrew gate:
system placeholders (onom/EMPTY/mono...), URLs, special-key/glyph strings, language-name-in-native-
script. These should have been SKIPPED, not given invented Hebrew. Prints KEY | EN | HE for review."""
import json, os, re, glob

HERE  = os.path.dirname(os.path.abspath(__file__))
FLEET = os.path.dirname(HERE)

PLACEHOLDER = re.compile(r'^(?:onom|mono|empty|null|none|todo|test|xxx+|tbd|placeholder|loc|dummy)$', re.I)
URLISH      = re.compile(r'https?://|www\.|\^048|\.com|\.net|\.org|/eula|focus-')
KEYGLYPH    = re.compile(r'[↹⏎␣⇪⇞⇟⇧⌫←↑→↓⌦∞]')
FOREIGN     = re.compile(r'[؀-ۿЀ-ӿ一-鿿぀-ヿ가-힯฀-๿]')
HEB         = re.compile(r'[א-ת]')


def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def suspicious(en):
    core = en.strip()
    if PLACEHOLDER.match(core):
        return "placeholder"
    if URLISH.search(en):
        return "url"
    if KEYGLYPH.search(en):
        return "special-keys"
    if FOREIGN.search(en):
        return "native-name"
    # very short all-caps token like EMPTY / ONOM
    if re.fullmatch(r'[A-Z]{2,8}', core):
        return "caps-marker"
    return None


def main():
    total_flag = 0
    for k in (1, 2, 3):
        tt = load(os.path.join(HERE, f"agent_{k}", "to_translate.json"), {})
        bank = load(os.path.join(FLEET, "banks", f"out_agent{k}.json"), {})
        rows = []
        for key, he in bank.items():
            src = tt.get(key)
            if not src:
                continue
            en = src.get("en", "")
            why = suspicious(en)
            if why:
                # only flag if the agent CHANGED it to Hebrew (a verbatim copy is fine)
                changed = HEB.search(he) or he.strip() != en.strip()
                if changed:
                    rows.append((why, key, en, he))
        total_flag += len(rows)
        print(f"=== agent_{k}: {len(rows)} force-translated suspicious entries ===")
        by = {}
        for why, key, en, he in rows:
            by.setdefault(why, []).append((key, en, he))
        for why, items in sorted(by.items()):
            print(f"  [{why}] x{len(items)}")
            for key, en, he in items[:8]:
                print(f"      {key}  EN={en[:38]!r}  ->  HE={he[:38]!r}")
    print(f"=== TOTAL flagged across 3 agents: {total_flag}")


if __name__ == "__main__":
    main()
