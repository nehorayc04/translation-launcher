#!/usr/bin/env python3
"""audit_artifact.py — deterministic defect scan of the DEPLOYED RDR2 Hebrew mod.

🔴 THREE METHOD TRAPS THIS SCRIPT EXISTS TO AVOID (each one produced a large false-positive
count on the first draft, which is worse than no scan at all):

1. **Never token-check against `extract/game_text/american.json`.** That extraction is itself
   mis-aligned on a subset of keys (its English disagrees with fr/de/it AND with the Hebrew,
   and some "keys" decode as 4 bytes of ASCII text) — 5,124 "token mismatches" were almost
   entirely that. Engine tokens are LANGUAGE-INDEPENDENT, so the honest reference is the
   CONSENSUS of the game's OWN sibling languages at the same key.

2. **Never run a Hebrew word-shape regex on the deployed file.** The artifact stores VISUAL
   (pre-reversed) text, so "a lone prefix letter followed by a word" is meaningless there.
   Linguistic checks belong on the LOGICAL source; only structural ones belong here.

3. **Never hand-write the font's covered-codepoint set.** Read the real `glyphCode` table out
   of the font dump — a guessed set flagged «, », é and TAB, all of which the face ships.

    python audit_artifact.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
FLEET = os.path.join(HERE, "..", "fleet")
TEXT = os.path.join(HERE, "..", "extract", "game_text")
GAME = r"C:\Program Files (x86)\Steam\steamapps\common\Red Dead Redemption 2"
GXT2 = os.path.join(GAME, "lml", "tranar", "Ko Games Studio.gxt2")
GFX = os.path.join(GAME, "lml", "KGF", "asset_replace", "font_lib_efigs.gfx")
COVERED_JSON = os.path.join(HERE, "_fontinspect", "covered_codes.json")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

STRUCT = re.compile(r"~[^~]*~|\{[^}]*\}|%%|%[#0-9.*\-+]*[a-zA-Z]+")
HEB = re.compile(r"[\u05d0-\u05ea]")
NIQ = re.compile(r"[\u0591-\u05c7]")
FOREIGN = re.compile(r"[\u0400-\u04ff\u0600-\u06ff\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")
SIBLINGS = ("french", "german", "italian", "mexican", "brazilian", "spanish",
            "polish", "russian")
# A lone Hebrew prefix letter standing as its own word before another Hebrew word. Correct
# Hebrew always glues them, so this is the word-by-word signature — but ONLY on logical text.
WBW = re.compile(r"(?<![\u05d0-\u05ea])([\u05de\u05d4\u05dc\u05d5\u05d1\u05e9\u05db])\s+(?=[\u05d0-\u05ea])")


def load_deployed():
    rows, dup, noeq = {}, Counter(), []
    with open(GXT2, encoding="utf-8", errors="replace") as f:
        for i, ln in enumerate(f, 1):
            ln = ln.rstrip("\n")
            if not ln.strip() or ln.lstrip().startswith("#"):
                continue                                   # LML comment, not a record
            if " = " not in ln:
                noeq.append((str(i), ln[:60]))
                continue
            k, _, v = ln.partition(" = ")
            k = k.strip()
            dup[k] += 1
            rows[k] = v
    return rows, dup, noeq


def token_reference(langs, k):
    """The engine-token multiset every language at this key agrees on, or None.

    Requiring >=2 siblings to AGREE is what makes this independent of any one extraction: a
    single mis-parsed record cannot outvote the rest, and a key where the languages genuinely
    disagree is skipped rather than guessed at."""
    seen = Counter()
    best = None
    for L in langs:
        v = langs[L].get(k)
        if v is None:
            continue
        sig = tuple(sorted(STRUCT.findall(v)))
        seen[sig] += 1
    if not seen:
        return None
    sig, n = seen.most_common(1)[0]
    return sig if n >= 2 else None


def main():
    print(f"gxt2 {os.path.getsize(GXT2):,} B · font {os.path.getsize(GFX):,} B")
    rows, dup, noeq = load_deployed()
    print(f"parsed {len(rows):,} keys")

    covered = set(json.load(open(COVERED_JSON))) if os.path.exists(COVERED_JSON) else None
    langs = {}
    for L in SIBLINGS:
        p = os.path.join(TEXT, f"{L}.json")
        if os.path.exists(p):
            langs[L] = json.load(open(p, encoding="utf-8"))
    print(f"sibling languages for the token reference: {len(langs)}")

    logical = {}
    for p in ("hebrew.json", "hebrew_missing.json"):
        f = os.path.join(FLEET, p)
        if os.path.exists(f):
            logical.update({k: v for k, v in json.load(open(f, encoding="utf-8")).items()
                            if isinstance(v, str)})
    print(f"logical source lines: {len(logical):,}\n")

    hits = defaultdict(list)
    if noeq:
        hits["line without ' = ' (not a comment)"] = noeq
    for k, n in dup.items():
        if n > 1:
            hits["duplicate key"].append((k, f"x{n}"))

    # ---- structural, on the ARTIFACT (safe on VISUAL text) -------------------------------
    for k, v in rows.items():
        if "=" in v:
            hits["value contains '=' (LML parser truncates it)"].append((k, v[:48]))
        if "\u27e6" in v or "\u27e7" in v:
            hits["masked-drain marker leaked"].append((k, v[:48]))
        if not v.strip():
            hits["empty value"].append((k, ""))
        if NIQ.search(v):
            hits["niqqud"].append((k, v[:48]))
        if FOREIGN.search(v):
            hits["foreign script"].append((k, v[:48]))
        if covered:
            bad = {c for c in v if ord(c) not in covered}
            if bad:
                hits["codepoint absent from the FONT's own code table"].append(
                    (k, " ".join(f"U+{ord(c):04X}" for c in sorted(bad))[:50]))

    # ---- engine tokens, against the sibling-language CONSENSUS ---------------------------
    checked = 0
    for k, v in rows.items():
        ref = token_reference(langs, k)
        if ref is None:
            continue
        checked += 1
        if tuple(sorted(STRUCT.findall(v))) != ref:
            hits["engine tokens differ from the sibling-language consensus"].append(
                (k, f"{list(ref)[:3]} -> {sorted(STRUCT.findall(v))[:3]}"))

    # ---- linguistic, on the LOGICAL source only ------------------------------------------
    for k, v in logical.items():
        if len(WBW.findall(v)) >= 2:
            hits["word-by-word damage (logical source)"].append((k, v[:50]))
        if NIQ.search(v):
            hits["niqqud (logical source)"].append((k, v[:50]))

    print(f"token-checked against a >=2-language consensus: {checked:,}\n")
    print(f"{'defect':56} count")
    print("-" * 70)
    total = 0
    for name in sorted(hits, key=lambda x: -len(hits[x])):
        print(f"{name:56} {len(hits[name]):,}")
        total += len(hits[name])
    print(f"{'(none)' if not hits else '':56}")
    print(f"TOTAL {total:,}\n")
    for name in sorted(hits, key=lambda x: -len(hits[x])):
        print(f"--- {name} ---")
        for k, s in hits[name][:5]:
            print(f"   {k}  {s}")
        if len(hits[name]) > 5:
            print(f"   ... +{len(hits[name])-5} more")
    json.dump({k: v[:500] for k, v in hits.items()},
              open(os.path.join(HERE, "artifact_defects.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\n-> {os.path.join(HERE, 'artifact_defects.json')}")


if __name__ == "__main__":
    main()
