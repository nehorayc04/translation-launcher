# -*- coding: utf-8 -*-
"""Assemble the multi-language onscreens panel from ALREADY-serialized WolvenKit output.
Pure parse, no WolvenKit calls -> seconds, no timeout. Reads WORK/{base,ep1}/<lang>/**.
"""
import json, os
from pathlib import Path
WORK = Path(r"C:\Users\NEHORA~1\AppData\Local\Temp\cp2077_langpanel")
OUT = os.path.join(os.path.dirname(__file__), "onscreens_panel.json")
LANGS = ["en","ar","ru","pl","cs","es-es","es-mx","fr","it","pt","de","ja","ko",
         "zh-cn","zh-tw","tr","th","hu","ua"]

def entries_of(tj):
    try:
        w = json.load(open(tj, encoding="utf-8"))
        return w["Data"]["RootChunk"]["root"]["Data"]["entries"]
    except Exception:
        return []

panel = {}
for scope in ("base", "ep1"):
    for lang in LANGS:
        ex = WORK / scope / lang
        if not ex.exists():
            continue
        files = [p for p in ex.rglob("*.json.json")
                 if p.name in ("onscreens.json.json", "onscreens_final.json.json")]
        cnt = 0
        for tj in files:
            for e in entries_of(str(tj)):
                pk = e.get("primaryKey") or e.get("stringId")
                if pk is None:
                    continue
                fv = (e.get("femaleVariant") or "").strip()
                if fv:
                    panel.setdefault(str(pk), {}).setdefault(lang, fv)
                    cnt += 1
        if cnt:
            print(f"  {scope}/{lang:6s}: {cnt:>6,}")

json.dump(panel, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
cov = {l: sum(1 for v in panel.values() if l in v) for l in LANGS}
print(f"\npanel: {len(panel):,} pks -> {OUT}")
print("coverage:", {k: v for k, v in cov.items() if v})
