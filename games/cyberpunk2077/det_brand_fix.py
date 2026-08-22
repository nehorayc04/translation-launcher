# -*- coding: utf-8 -*-
"""det_brand_fix.py — DETERMINISTIC (no LM) fix of the stubborn brand-name seams
gemma kept gluing. Each broken token -> its correct full form. Whole-value for
pure brands, substring for the one embedded case. Backup + QA-lock + atomic."""
import os, sys, json, time, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "universal"))
import get_next_audit_batch as G
import cp2077_qa_defects as Q

# broken substring -> correct replacement
REPL = {
    "4XדרYves": "4xDRIVE",
    "EZאסטייטס": "EZ Estates",
    "דוםלuncher": "Doomlauncher",
    "קריסטלCoat™": "CrystalCoat™",
    "מטלFX": "MetalFX",
    "בbastards": "בממזרים",
}


def main():
    data = json.load(open(G.BASE_TR, encoding="utf-8"))
    touched_subs, onscreens_touched, n = set(), False, 0
    if not Q.acquire_lock("det_brand_fix"):
        sys.exit("[abort] lock")
    try:
        for sec, rs in data.items():
            if not isinstance(rs, list):
                continue
            for e in rs:
                if not isinstance(e, dict):
                    continue
                for fld in ("femaleVariant", "maleVariant"):
                    v = e.get(fld) or ""
                    nv = v
                    for bad, good in REPL.items():
                        if bad in nv:
                            nv = nv.replace(bad, good)
                    if nv != v:
                        e[fld] = nv
                        n += 1
                        if sec.startswith("subtitles"):
                            touched_subs.add(sec)
                        elif sec.startswith("onscreens"):
                            onscreens_touched = True
        bak = f"{G.BASE_TR}.bak.brandfix.{time.strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(G.BASE_TR, bak)
        tmp = G.BASE_TR + ".tmp"
        json.dump(data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(tmp, G.BASE_TR)
        print(f"brand-fix applied {n} fields; backup {os.path.basename(bak)}", flush=True)
    finally:
        Q.release_lock()
    open(os.path.join(HERE, "brandfix_subs.txt"), "w", encoding="utf-8").write("\n".join(sorted(touched_subs)))
    open(os.path.join(HERE, "brandfix_onscreens.flag"), "w").write("1" if onscreens_touched else "0")
    print(f"onscreens_touched={onscreens_touched} touched_subs={len(touched_subs)}", flush=True)


if __name__ == "__main__":
    main()
