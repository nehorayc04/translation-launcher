# -*- coding: utf-8 -*-
"""Build a multi-language ONSCREENS reference panel for CP2077 (the New-Era meaning oracle).
Cheap: onscreens = 2 CR2W per language. Extracts+serializes every shipped language, then
builds panel[pk] = {lang: text}. Resumable. Read-only vs the game (extracts to TEMP).
Run: python build_onscreens_panel.py
"""
import json, os, subprocess, time
from pathlib import Path

GAME = r"C:\Game Lab\Cyberpunk 2077"
CLI = r"C:\Users\Nehoray_Cohen\AppData\Local\Programs\WolvenKit-CLI\WolvenKit.CLI.exe"
WORK = r"C:\Users\NEHORA~1\AppData\Local\Temp\cp2077_langpanel"
OUT = os.path.join(os.path.dirname(__file__), "onscreens_panel.json")
LANGS = ["en", "ar", "ru", "pl", "cs", "es-es", "es-mx", "fr", "it", "pt",
         "de", "ja", "ko", "zh-cn", "zh-tw", "tr", "th", "hu", "ua"]

def run(args, timeout=300):
    try:
        r = subprocess.run([CLI]+args, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return r.returncode == 0, (r.stdout or "")+(r.stderr or "")
    except Exception as e:
        return False, str(e)

def entries_of(txt_json):
    try:
        w = json.load(open(txt_json, encoding="utf-8"))
        return w["Data"]["RootChunk"]["root"]["Data"]["entries"]
    except Exception:
        return []

def lang_map(lang, scope):
    """Return {pk: femaleVariant} for a language's onscreens (base or ep1)."""
    arch = os.path.join(GAME, "archive", "pc", "content" if scope=="base" else "ep1",
                        f"lang_{lang}_text.archive")
    if not os.path.exists(arch):
        return {}
    ex = os.path.join(WORK, scope, lang)
    marker = os.path.join(ex, ".done")
    if not os.path.exists(marker):
        os.makedirs(ex, exist_ok=True)
        ok, out = run(["extract", arch, "-o", ex, "-w", "*onscreens*"], timeout=300)
        if not ok:
            print(f"    [{scope}/{lang}] extract FAIL: {out[-160:]}"); return {}
        Path(marker).touch()
    # loc-folder-agnostic: grab exactly the 2 CR2W resources by name (cz-cz, ar-ar, es-es ... all vary)
    cr2ws = [p for p in Path(ex).rglob("*.json")
             if p.name in ("onscreens.json", "onscreens_final.json")]
    out={}
    for cr2w in cr2ws:
        tj = str(cr2w)+".json"
        if not os.path.exists(tj):
            run(["convert","serialize",str(cr2w),"-o",str(cr2w.parent)],timeout=120)
        for e in entries_of(tj):
            pk = e.get("primaryKey") or e.get("stringId")
            if pk is None: continue
            fv = (e.get("femaleVariant") or "").strip()
            if fv: out[str(pk)] = fv
    return out

def main():
    os.makedirs(WORK, exist_ok=True)
    panel = {}   # pk -> {lang: text}   (base + dlc merged by pk; pk spaces are disjoint enough)
    for scope in ("base","ep1"):
        for lang in LANGS:
            t0=time.time()
            m = lang_map(lang, scope)
            for pk, txt in m.items():
                panel.setdefault(pk, {}).setdefault(lang, txt)
            print(f"  {scope}/{lang:6s}: {len(m):>6,} strings  ({time.time()-t0:.0f}s)")
    json.dump(panel, open(OUT,"w",encoding="utf-8"), ensure_ascii=False)
    langs_cov = {l: sum(1 for v in panel.values() if l in v) for l in LANGS}
    print(f"\npanel: {len(panel):,} unique pks -> {OUT}")
    print("coverage:", {k:v for k,v in langs_cov.items()})

if __name__ == "__main__": main()
