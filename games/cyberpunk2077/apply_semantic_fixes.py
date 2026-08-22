# -*- coding: utf-8 -*-
"""apply_semantic_fixes.py — apply the workflow-confirmed semantic QA fixes.

Each fix carries a verified final_hebrew. We apply it to the flagged field,
mirror it to the sibling gender variant when that variant still holds the same
bad value, and (for onscreens) to the onscreens.json <-> onscreens_final.json
mirror. A light gate rejects any suggestion that is empty / lacks Hebrew /
introduces a foreign script or niqqud. Backup + QA-lock + atomic write."""
import os, sys, json, re, time, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "universal"))
import get_next_audit_batch as G
import cp2077_qa_defects as Q

HEB = re.compile(r"[א-ת]")
BAD = re.compile(r"[؀-ۿͰ-ϿЀ-ӿঀ-৿ऀ-ॿ"
                 r"฀-๿぀-ヿ一-鿿가-힯]")
NIQQUD = re.compile(r"[֑-ׇ]")
ONS = ("onscreens/onscreens.json", "onscreens/onscreens_final.json")


def gate(he):
    return bool(he) and HEB.search(he) and not BAD.search(he) and not NIQQUD.search(he)


def main():
    infile = sys.argv[1] if len(sys.argv) > 1 else "semantic_fixes.json"
    fixes = json.load(open(os.path.join(HERE, infile), encoding="utf-8"))
    data = json.load(open(G.BASE_TR, encoding="utf-8"))

    def entries(sec, pk):
        out = []
        for e in data.get(sec, []):
            if isinstance(e, dict) and str(e.get("primaryKey") or e.get("stringId")) == str(pk):
                out.append(e)
        return out

    touched_subs, onscreens_touched, applied, rejected = set(), False, 0, []
    if not Q.acquire_lock("apply_semantic"):
        sys.exit("[abort] lock")
    try:
        for c in fixes:
            sec, pk, fld, fin = c["section"], c["pk"], c["field"], c["final_hebrew"]
            if not gate(fin):
                rejected.append((pk, "gate")); continue
            # which sections to touch: the flagged one + its onscreens mirror
            secs = [sec]
            if sec in ONS:
                secs = list(ONS)
            hit = False
            for s in secs:
                for e in entries(s, pk):
                    old = e.get(fld) or ""
                    # apply to the flagged field
                    if e.get(fld) != fin:
                        e[fld] = fin
                        hit = True
                    # sync sibling variant if it holds the same bad text
                    other = "maleVariant" if fld == "femaleVariant" else "femaleVariant"
                    ov = e.get(other) or ""
                    if ov and (ov == old or ov == c.get("hebrew")):
                        e[other] = fin
                    if s.startswith("subtitles"):
                        touched_subs.add(s)
                    elif s.startswith("onscreens"):
                        onscreens_touched = True
            if hit:
                applied += 1
            else:
                rejected.append((pk, "not-found-or-nochange"))

        bak = f"{G.BASE_TR}.bak.semantic.{time.strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(G.BASE_TR, bak)
        tmp = G.BASE_TR + ".tmp"
        json.dump(data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(tmp, G.BASE_TR)
        print(f"applied {applied}/{len(fixes)}; rejected {len(rejected)} {rejected}; backup {os.path.basename(bak)}", flush=True)
    finally:
        Q.release_lock()
    open(os.path.join(HERE, "semantic_subs.txt"), "w", encoding="utf-8").write("\n".join(sorted(touched_subs)))
    open(os.path.join(HERE, "semantic_onscreens.flag"), "w").write("1" if onscreens_touched else "0")
    print(f"onscreens_touched={onscreens_touched} touched_subs={len(touched_subs)}", flush=True)


if __name__ == "__main__":
    main()
