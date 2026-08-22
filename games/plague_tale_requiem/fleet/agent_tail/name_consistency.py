#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify character/place NAMES are transliterated CONSISTENTLY across ALL translated lines.
3 agents + the NIM fleet each transliterate independently -> the same English name can end up spelled
several ways in Hebrew (Lucas -> לוקא / לוקאס / לוקס). This auto-discovers proper nouns from the English
source, then for every line whose EN contains that name it tallies the distinct Hebrew renderings used,
and FLAGS any name rendered >1 way.

Reads ../hebrew.json (merged bank) + ../../extract/gender_source.json (en per key).
Usage: python name_consistency.py
"""
import json, os, re, collections

HERE   = os.path.dirname(os.path.abspath(__file__))
FLEET  = os.path.dirname(HERE)
BANK   = os.path.join(FLEET, "hebrew.json")
MASTER = os.path.join(FLEET, "..", "extract", "gender_source.json")

# common English words that are Capitalized only because they start a sentence / are not names
EN_STOP = set("""A An The And But Or So If When While As Of To In On At For With From By I You He She It We They
His Her My Your Our Their This That These Those What Who Why How Where Here There Now Then Yes No Not Do Don
Did Will Would Can Could Should May Might Must Have Has Had Are Is Was Were Be Been Being Get Got Go Come Came
Let Look Take Give Go Come Stay Wait Stop Run Hey Oh Ah Well Just Only More Most Very Too Also All Some Any
One Two Three Good Bad God Lord Sir Lady Mother Father Son Girl Boy Man Woman People Please Thank Thanks Okay
OK Right Left Down Up Out Over Under Again Still Even Never Always Something Nothing Everything Someone Anyone
Everyone Because About After Before Without Inside Outside Chapter Continue Loading Save Load Options Exit Back
Next Yes Maybe Nothing Us Them Me Him""".split())

# Hebrew function words that appear once-per-line and are NOT names (so they don't masquerade as a rendering)
HE_STOP = set("""של את לא אני זה אתה על כן מה אם גם יש אין הוא היא אנחנו הם כל רק אבל כי אז עוד לך לי לו לה שלי
שלך שלו שלה הזה הזאת הזו טוב רע כאן שם מי איך למה כדי אחרי לפני בלי עם או זו זאת הנה עכשיו תמיד מאוד יותר פה
כמו צריך צריכה יכול יכולה רוצה רוצָה בוא בואי תראה תראי הכל כלום משהו מישהו אנשים בבקשה תודה אמא אבא אדוני
גברתי בסדר נכון ימינה שמאלה למטה למעלה שוב עדיין אפילו לעולם תמיד היה היתה הייתי אתם אתן שלנו שלכם אותו אותה
אותי אותך הזמן פעם עכשָיו כאשר בזמן חייב חייבת צא צאי קדימה נו הא אה אוי טוב יופי הרבה קצת גדול קטן ראש יד""".split())

NAME = re.compile(r'(?<![A-Za-zÀ-ÿ])([A-ZÀ-Þ][a-zà-ÿ]{2,})')   # a Capitalised word
HEWORD = re.compile(r'[א-ת]{2,}')


def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def main():
    bank = load(BANK, {})
    master = load(MASTER, {})
    en = {k: (v.get("en") if isinstance(v, dict) else v) or "" for k, v in master.items()}

    # 1) discover proper-noun candidates: Capitalised, appears (capitalised, mid-sentence-ok) >=4 times
    freq = collections.Counter()
    for k in bank:
        for m in NAME.finditer(en.get(k, "")):
            w = m.group(1)
            if w not in EN_STOP:
                freq[w] += 1
    names = [w for w, c in freq.items() if c >= 4]
    # keep the ones that read like names (not ALL-common); sort by frequency
    names.sort(key=lambda w: -freq[w])

    print(f"bank={len(bank)}  proper-noun candidates (>=4 EN occurrences): {len(names)}")
    inconsistent = []
    for w in names:
        # lines where EN has this name (word-ish boundary) AND we have Hebrew
        pat = re.compile(r'(?<![A-Za-zÀ-ÿ])' + re.escape(w) + r'(?![A-Za-zÀ-ÿ])')
        he_tokens = collections.Counter()
        n_lines = 0
        for k, e in en.items():
            if k not in bank:
                continue
            if pat.search(e):
                n_lines += 1
                for t in set(HEWORD.findall(bank[k])):     # set(): count a rendering once per line
                    if t not in HE_STOP and len(t) >= 3:
                        he_tokens[t] += 1
        if n_lines < 4:
            continue
        # candidate renderings = Hebrew tokens present in a large fraction of the name's lines
        cand = [(t, c) for t, c in he_tokens.items() if c >= max(3, n_lines * 0.20)]
        cand.sort(key=lambda x: -x[1])
        # heuristic: renderings of THE SAME name share the first 2 Hebrew letters
        groups = collections.defaultdict(list)
        for t, c in cand:
            groups[t[:2]].append((t, c))
        variants = None
        for pre, items in groups.items():
            if len(items) > 1 and sum(c for _, c in items) >= n_lines * 0.4:
                variants = sorted(items, key=lambda x: -x[1])
                break
        top = ", ".join(f"{t}×{c}" for t, c in cand[:5]) or "(none dominant)"
        flag = ""
        if variants:
            flag = "  <<< INCONSISTENT: " + " / ".join(f"{t}×{c}" for t, c in variants)
            inconsistent.append((w, n_lines, variants))
        print(f"  {w:14s} EN×{freq[w]:<4d} lines={n_lines:<4d} -> {top}{flag}")

    print(f"\n=== {len(inconsistent)} names with >1 Hebrew rendering (same 2-letter prefix) ===")
    for w, n, variants in inconsistent:
        print(f"  {w}: " + " / ".join(f"{t}×{c}" for t, c in variants))


if __name__ == "__main__":
    main()
