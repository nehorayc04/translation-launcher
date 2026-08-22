# -*- coding: utf-8 -*-
"""Add the ENGINE-level dimensions (variables, plural rules, char-limit, line-breaks, lore terms)
to the review corpus — the technical layer on top of the linguistic tags. Reads {kind}.tagged.jsonl,
writes {kind}.final.jsonl = the single fleet-ready corpus. Deterministic + reliable only; anything
error-prone stays evidence for the agent. Read-only.

engine tags per row:
  vars          : list of {…} tokens the engine injects (must survive verbatim)
  number_inject : bool — {int_0}/{float_0}/{stat_0}/%d present -> Hebrew counting/plural attention
  name_inject   : bool — {Name}/{Surname}/player -> phrase gender-neutral AROUND it (gender unknown)
  line_breaks   : count of forced \n (must be preserved exactly)
  overflow_risk : bool — Hebrew longer than the LONGEST other game language (char-limit proxy;
                  the UI slot was sized for all shipped languages, so exceeding the max = risk)
  lore_terms    : proper-noun / world terms kept identical across >=6 languages -> keep in Hebrew
"""
import json, os, re

HERE = os.path.dirname(__file__); OUT = os.path.join(HERE, "review_corpus")
VAR = re.compile(r'\{[^{}]*\}')
NL = re.compile(r'\\n|\n')
NUM = re.compile(r'\{(?:int|float|stat)_\d+\}|%[0-9.]*[di]')
NAME = re.compile(r'\{(?:Name|Surname|FirstName|LastName|nickname|playerName)\}', re.I)
CAPWORD = re.compile(r'\b[A-Z][A-Za-z][A-Za-z\'\-]{1,}\b')
STOP = {"The","This","That","You","Your","And","But","For","With","When","What","Where","How","Why","Not","Are","Was"}

def line_breaks(s): return len(NL.findall(s or ""))

def overflow(he, en, refs):
    hl = len(he or "")
    if hl < 15: return False
    others = [len(v[0]) for v in refs.values() if v and v[0]]
    ceiling = max(others + [len(en or "")]) if others else len(en or "")
    return hl > ceiling * 1.1

def lore_terms(en, refs):
    """Capitalized English words kept VERBATIM in >=6 language translations = proper noun / lore term."""
    out = []
    cands = [w for w in CAPWORD.findall(en or "") if w not in STOP]
    for w in dict.fromkeys(cands):
        kept = sum(1 for v in refs.values() if v and re.search(r'\b' + re.escape(w) + r'\b', v[0]))
        if kept >= 6:
            out.append(w)
    return out

def main():
    for kind in ("onscreens", "subtitles"):
        src = os.path.join(OUT, kind + ".tagged.jsonl")
        if not os.path.exists(src): continue
        dst = os.path.join(OUT, kind + ".final.jsonl")
        stats = {"vars": 0, "num": 0, "name": 0, "nl": 0, "ovf": 0, "lore": 0, "n": 0}
        with open(src, encoding="utf-8") as fi, open(dst, "w", encoding="utf-8") as fo:
            for line in fi:
                r = json.loads(line)
                en = r.get("en", "") or ""; he = r["he"][0]; refs = r.get("refs", {})
                vars_ = VAR.findall(en) + [v for v in VAR.findall(he) if v not in VAR.findall(en)]
                eng = {
                    "vars": sorted(set(vars_)),
                    "number_inject": bool(NUM.search(en) or NUM.search(he)),
                    "name_inject": bool(NAME.search(en) or NAME.search(he)),
                    "line_breaks": line_breaks(he),
                    "overflow_risk": overflow(he, en, refs),
                    "lore_terms": lore_terms(en, refs),
                }
                r["engine"] = eng
                fo.write(json.dumps(r, ensure_ascii=False) + "\n")
                stats["n"] += 1
                if eng["vars"]: stats["vars"] += 1
                if eng["number_inject"]: stats["num"] += 1
                if eng["name_inject"]: stats["name"] += 1
                if eng["line_breaks"]: stats["nl"] += 1
                if eng["overflow_risk"]: stats["ovf"] += 1
                if eng["lore_terms"]: stats["lore"] += 1
        print(f"  {kind}: -> {dst}")
        print(f"     vars {stats['vars']:,} | number {stats['num']:,} | name {stats['name']:,} "
              f"| line-breaks {stats['nl']:,} | overflow {stats['ovf']:,} | lore {stats['lore']:,}  (of {stats['n']:,})")

if __name__ == "__main__":
    import sys; sys.stdout.reconfigure(encoding="utf-8")
    main()
