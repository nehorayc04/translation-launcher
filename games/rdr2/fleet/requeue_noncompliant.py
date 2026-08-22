# -*- coding: utf-8 -*-
"""Re-queue lines that were translated BEFORE the glossary existed (or that ignored it).

Why re-queue instead of string-patching: the model invents a DIFFERENT wrong word each time
("Gold Bar" came back as שרף זהב, סבאות זהב, סביבות זהב), so a wrong->right pair list can never
catch them all. Deleting the line from the banks costs one re-translation and the worker now has
the canonical term in its prompt, so the second attempt is right by construction.

Safe by design: it only removes lines that DEMONSTRABLY miss a canonical term whose English is
present, it never touches anything else, and the fleet re-does them automatically.

    py fleet/requeue_noncompliant.py            # report
    py fleet/requeue_noncompliant.py --apply    # remove them from banks + hebrew.json
"""
import glob
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
APPLY = "--apply" in sys.argv
corpus = json.load(io.open(os.path.join(HERE, "corpus.json"), encoding="utf-8"))
reg = json.load(io.open(os.path.join(HERE, "name_registry.json"), encoding="utf-8"))
terms = {}
for g in ("characters", "places", "factions", "systems", "gear"):
    terms.update({k: v for k, v in (reg.get(g) or {}).items() if k and v})

_PREFIX = "והבלמשכ"


def present(want, text):
    for w in want.split():
        stem = w[:-1] if len(w) > 3 and w[-1] in "הת" else w
        if stem in text or any(p + stem in text for p in _PREFIX):
            continue
        return False
    return True


def offending(en, he):
    for t, want in terms.items():
        if re.search(r"\b" + re.escape(t) + r"\b", en) and not present(want, he):
            return t
    return None


bad = {}
for f in glob.glob(os.path.join(HERE, "banks", "out_*.json")):
    try:
        d = json.load(io.open(f, encoding="utf-8"))
    except Exception:
        continue
    for k, v in d.items():
        if not isinstance(v, str):
            continue
        en = corpus.get(k, {}).get("en", "")
        t = offending(en, v)
        if t:
            bad.setdefault(f, []).append((k, t))

tot = sum(len(v) for v in bad.values())
print(f"non-compliant banked lines: {tot}")
for f, ks in bad.items():
    print(f"  {os.path.basename(f):28} {len(ks)}")
if not APPLY:
    print("\n(dry run — pass --apply to re-queue them)")
    raise SystemExit

for f, ks in bad.items():
    d = json.load(io.open(f, encoding="utf-8"))
    for k, _t in ks:
        d.pop(k, None)
    tmp = f + ".tmp"
    io.open(tmp, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False))
    os.replace(tmp, f)
hp = os.path.join(HERE, "hebrew.json")
if os.path.exists(hp):
    h = json.load(io.open(hp, encoding="utf-8"))
    for _f, ks in bad.items():
        for k, _t in ks:
            h.pop(k, None)
    tmp = hp + ".tmp"
    io.open(tmp, "w", encoding="utf-8").write(json.dumps(h, ensure_ascii=False))
    os.replace(tmp, hp)
print(f"\nre-queued {tot} lines — the fleet will redo them WITH the glossary")
