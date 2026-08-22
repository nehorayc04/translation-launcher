"""Hourly QA check across all translation streams' banked output.
Validates each stream's {key:{f,m}} against the EN source: Hebrew present, dual-gender,
tokens preserved, no foreign script / niqqud. Reports per-stream health + issue rate."""
import json, re, os, glob
HERE = os.path.dirname(os.path.abspath(__file__))
BANK = os.path.join(HERE, "agent_handoff_qa")
POOL = json.load(open(os.path.join(BANK, "_pool", "full_pool.json"), encoding="utf-8"))

FOREIGN = re.compile(r'[؀-ۿ぀-ヿ一-鿿가-힣Ѐ-ӿ]'); NIQ = re.compile(r'[֑-ֽֿׁׂ]'); HEB = re.compile(r'[֐-׿]')
STRUCT = re.compile(r'<[^>]*>|\{[^}]*\}|%%|%[#0-9.*\-+]*[a-zA-Z]+|&[a-zA-Z#0-9]+;'); LOWER = re.compile(r'[a-z]{2,}')
_NAMEWORD = re.compile(r"^[A-Z0-9][\w.\-'/]*$"); _CTRL = "".join(chr(c) for c in range(0x20))

def is_namey(en):
    en = (en or "").strip(); ws = en.split()
    return bool(ws) and len(ws) <= 4 and all(_NAMEWORD.match(w) for w in ws)

def check(he, en):
    """Mirrors vm_nim.py validate() — incl. the name/code passthrough (a no-Hebrew
    result is OK when the source is a proper-noun/code left Latin)."""
    p = []
    if not he or not str(he).strip(): return ["empty"]
    if FOREIGN.search(he): p.append("foreign")
    if NIQ.search(he): p.append("niqqud")
    if sorted(STRUCT.findall(he)) != sorted(STRUCT.findall(en)): p.append("token")
    core = STRUCT.sub(" ", en); bare = he.lstrip(_CTRL).strip()
    if LOWER.search(core) and not HEB.search(he):
        if not (bare == en.strip() and is_namey(en)): p.append("no_heb")
    return p

grand = {"entries": 0, "cells": 0, "bad": 0}
for folder in sorted(glob.glob(os.path.join(BANK, "retrans_agent_*"))):
    f = os.path.join(folder, "retrans_corrections.json")
    if not os.path.exists(f): continue
    try:
        d = json.load(open(f, encoding="utf-8"))
    except Exception as e:
        print(f"{os.path.basename(folder):22} LOAD-FAIL {e}"); continue
    if not isinstance(d, dict): continue
    cells = 0; bad = 0; iss = {}
    for k, v in d.items():
        en = POOL.get(k, "")
        if not isinstance(v, dict):
            bad += 1; cells += 1; iss["shape"] = iss.get("shape", 0) + 1; continue
        for g in ("f", "m"):
            cells += 1
            for pr in check(v.get(g, ""), en):
                bad += 1; iss[pr] = iss.get(pr, 0) + 1
    rate = 100.0 * (cells - bad) / cells if cells else 0
    tag = "OK " if rate >= 98 else ("WARN" if rate >= 90 else "BAD ")
    print(f"{tag} {os.path.basename(folder):22} entries={len(d):6} valid={rate:5.1f}%  issues={iss}")
    grand["entries"] += len(d); grand["cells"] += cells; grand["bad"] += bad
r = 100.0 * (grand["cells"] - grand["bad"]) / grand["cells"] if grand["cells"] else 0
print(f"--- TOTAL entries={grand['entries']} cells={grand['cells']} valid={r:.2f}% ---")
