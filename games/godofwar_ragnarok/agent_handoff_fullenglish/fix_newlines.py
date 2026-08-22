# -*- coding: utf-8 -*-
"""Restore each HE's newline encoding to match its EN exactly.
GoWR stores two kinds of break: literal backslash-n (2 chars) and real 0x0A.
The agent converted literal->real; here we rebuild HE with EN's exact break sequence."""
import json, os, re, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
src = json.load(open(os.path.join(HERE, "to_translate.json"), encoding="utf-8"))
done = json.load(open(os.path.join(HERE, "done_translate.json"), encoding="utf-8"))

LIT = "\\n"            # literal backslash-n (2 chars)
REAL = "\n"           # real newline (0x0A)
DELIM = re.compile(re.escape(LIT) + r"|" + REAL)   # literal first, then real

def breaks(s):
    return DELIM.findall(s)

fixed = flag = 0; flags = []
for k in src:
    en = src[k]["en"]; he = done[k]
    ed = breaks(en); hd = breaks(he)
    if len(ed) != len(hd):
        flag += 1; flags.append((k, len(ed), len(hd))); continue
    parts = DELIM.split(he)
    out = parts[0]
    for i, p in enumerate(parts[1:]):
        out += ed[i] + p
    if out != he:
        done[k] = out; fixed += 1

if len(sys.argv) > 1 and sys.argv[1] == "--apply" and flag == 0:
    tmp = os.path.join(HERE, "done_translate.json.tmp")
    json.dump(done, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(HERE, "done_translate.json"))
    print("APPLIED. reformatted %d" % fixed)
else:
    print("dry-run: would reformat %d | count-mismatch flags: %d" % (fixed, flag))
    for k, a, b in flags[:30]:
        print("   id=%s en_breaks=%d he_breaks=%d" % (k, a, b))
