#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""INDEPENDENT verifier for the 3 parallel PT tail agents (trust nothing the merge said).
Re-checks every banked line against the source: token multiset, foreign/niqqud, no-English-prose,
Arabic-copy, and a gender spot-check vs the game's Arabic. Prints counts + suspects + samples.
Usage: python verify.py [N_samples]
"""
import json, os, re, sys, glob

HERE  = os.path.dirname(os.path.abspath(__file__))
FLEET = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(FLEET, "..", "..", "..", "universal"))
try:
    import gender_oracle as G
except Exception:
    G = None

STRUCT  = re.compile(r'\{[^}]*\}|\||%%|%[#0-9.*\-+]*[a-zA-Z]+')
FOREIGN = re.compile(r'[؀-ۿЀ-ӿ一-鿿぀-ヿ가-힯฀-๿]')   # incl. Arabic
ARABIC  = re.compile(r'[؀-ۿ]')
NIQ     = re.compile(r'[֑-ׇ]')
HEB     = re.compile(r'[א-ת]')
LOWERW  = re.compile(r'[a-z]{2,}')


def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def is_namey(en):
    core = STRUCT.sub(" ", en).strip()
    if not LOWERW.search(core):
        return True
    words = re.findall(r"[A-Za-z']+", core)
    return bool(words) and len(words) <= 4 and all(w[:1].isupper() for w in words)


def check(he, en):
    if not he or not he.strip():
        return "empty"
    if ARABIC.search(he):
        return "arabic-leak"
    if FOREIGN.search(he):
        return "foreign-script"
    if NIQ.search(he):
        return "niqqud"
    if sorted(STRUCT.findall(he)) != sorted(STRUCT.findall(en)):
        return "token-mismatch"
    if not HEB.search(he):
        if he.strip() == en.strip() and is_namey(en):
            return "ok-name"
        return "no-hebrew-prose"
    return "ok"


def main():
    nsamp = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    grand = {}
    gender_bad = []
    for k in (1, 2, 3):
        d = os.path.join(HERE, f"agent_{k}")
        tt = load(os.path.join(d, "to_translate.json"), {})
        bank = load(os.path.join(FLEET, "banks", f"out_agent{k}.json"), {})
        counts = {}
        bad = []
        samples = []
        for key, he in bank.items():
            src = tt.get(key)
            if not src:
                counts["not-in-slot"] = counts.get("not-in-slot", 0) + 1
                continue
            en = src.get("en", "")
            r = check(he, en)
            counts[r] = counts.get(r, 0) + 1
            if r not in ("ok", "ok-name"):
                bad.append((key, en, he, r))
            elif len(samples) < nsamp and HEB.search(he) and LOWERW.search(STRUCT.sub(" ", en)):
                samples.append((en, src.get("ar", ""), he))
            # gender spot-check
            if G and r in ("ok", "ok-name"):
                ar = src.get("ar", "")
                try:
                    res = G.check_line(he, ar)
                    if res.get("mismatch"):
                        gender_bad.append((k, key, en, ar, he, res.get("ar"), res.get("he")))
                except Exception:
                    pass
        for kk, vv in counts.items():
            grand[kk] = grand.get(kk, 0) + vv
        okc = counts.get("ok", 0) + counts.get("ok-name", 0)
        tot = sum(counts.values())
        print(f"=== agent_{k}: {tot} banked | OK {okc} | issues {tot-okc} | {counts}")
        for en, ar, he in samples:
            print(f"    EN {en[:44]!r}")
            print(f"    AR {ar[:44]}")
            print(f"    HE {he[:44]}")
            print()
        for key, en, he, r in bad[:6]:
            print(f"    ✗ [{r}] {key}  EN={en[:40]!r}  HE={he[:40]!r}")
    print("=== GRAND:", grand)
    print(f"=== gender suspects (AR vs HE addressee disagree): {len(gender_bad)}")
    for k, key, en, ar, he, ag, hg in gender_bad[:10]:
        print(f"    a{k} {key}: AR={ag} HE={hg} | EN={en[:34]!r} | HE={he[:30]} | AR={ar[:30]}")


if __name__ == "__main__":
    main()
