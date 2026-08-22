# -*- coding: utf-8 -*-
"""det_residual_fix.py — DETERMINISTIC (no LM) repair of the QA-battery residuals.

1. Bengali-glyph leak in two transliterated names (recurring):
     'ার্' (inside "Myers"  -> מאיירס)   'াক' (inside "Kitakyushu" -> קיטאקיושו)
   Pure script-repair; the rest of the line is already correct Hebrew.
2. Mirror-sync for pk 87615 + 92844: the Hebrew translation already EXISTS in
   onscreens_final.json's femaleVariant, but onscreens.json's FV (87615) and the
   maleVariant slots (both) still hold the old English. Propagate the good Hebrew
   FV -> the other file's FV and -> both maleVariants.
Backup + QA-lock + atomic write. Collects touched onscreens/subtitle sections."""
import os, sys, json, time, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "universal"))
import get_next_audit_batch as G
import cp2077_qa_defects as Q

BENGALI = {"מייার্ס": "מאיירס", "ার্": "אר", "াক": "אק"}
MIRROR_PKS = {"87615", "92844"}
ONS_SECS = ("onscreens/onscreens.json", "onscreens/onscreens_final.json")
import re
HEB = re.compile(r"[א-ת]")


def main():
    data = json.load(open(G.BASE_TR, encoding="utf-8"))
    touched_subs, onscreens_touched, n = set(), False, 0
    if not Q.acquire_lock("det_residual_fix"):
        sys.exit("[abort] lock")
    try:
        # 1) Bengali script-repair across the whole corpus
        for sec, rs in data.items():
            if not isinstance(rs, list):
                continue
            for e in rs:
                if not isinstance(e, dict):
                    continue
                for fld in ("femaleVariant", "maleVariant"):
                    v = e.get(fld) or ""
                    nv = v
                    for bad, good in BENGALI.items():
                        if bad in nv:
                            nv = nv.replace(bad, good)
                    if nv != v:
                        e[fld] = nv
                        n += 1
                        if sec.startswith("subtitles"):
                            touched_subs.add(sec)
                        elif sec.startswith("onscreens"):
                            onscreens_touched = True

        # 2) mirror-sync for the two English-leak pks
        # find the good Hebrew FV per pk (whichever onscreens file has Hebrew)
        good = {}
        for sec in ONS_SECS:
            for e in data.get(sec, []):
                if not isinstance(e, dict):
                    continue
                pk = str(e.get("primaryKey"))
                if pk in MIRROR_PKS:
                    fv = e.get("femaleVariant") or ""
                    if HEB.search(fv) and len(HEB.findall(fv)) > 5:
                        good[pk] = fv
        for sec in ONS_SECS:
            for e in data.get(sec, []):
                if not isinstance(e, dict):
                    continue
                pk = str(e.get("primaryKey"))
                if pk in good:
                    he = good[pk]
                    changed = False
                    if (e.get("femaleVariant") or "") != he:
                        e["femaleVariant"] = he; changed = True
                    # maleVariant: replace if empty OR not Hebrew (holds old English)
                    mv = e.get("maleVariant") or ""
                    if not mv or not HEB.search(mv):
                        e["maleVariant"] = he; changed = True
                    if changed:
                        n += 1
                        onscreens_touched = True

        bak = f"{G.BASE_TR}.bak.residfix.{time.strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(G.BASE_TR, bak)
        tmp = G.BASE_TR + ".tmp"
        json.dump(data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(tmp, G.BASE_TR)
        print(f"residual-fix applied {n} fields; backup {os.path.basename(bak)}", flush=True)
    finally:
        Q.release_lock()
    open(os.path.join(HERE, "residfix_subs.txt"), "w", encoding="utf-8").write("\n".join(sorted(touched_subs)))
    open(os.path.join(HERE, "residfix_onscreens.flag"), "w").write("1" if onscreens_touched else "0")
    print(f"onscreens_touched={onscreens_touched} touched_subs={len(touched_subs)}", flush=True)


if __name__ == "__main__":
    main()
