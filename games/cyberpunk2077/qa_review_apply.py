"""qa_review_apply.py — apply the accumulated Opus-QA line fixes
(universal/opus_qa_fixes.jsonl) to the base spine. Each fix is applied ONLY
when the current value still equals the recorded `old` (so nothing is
clobbered if the line changed since review). For onscreens fixes the same pk
in the SIBLING onscreens section is also corrected when it holds the identical
old value (the two onscreens files mirror each other).

Validates each new value: must parse cleanly (mk.parse_slots) so a fix can
never introduce broken markup. Standard discipline: QA write-lock, spine
backup, atomic write. Applied fixes are moved to opus_qa_fixes.applied.jsonl.

Usage: python qa_review_apply.py
"""
import json, os, sys, time, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
UNIV = os.path.join(os.path.dirname(os.path.dirname(HERE)), "universal")
sys.path.insert(0, HERE); sys.path.insert(0, UNIV)
import cp2077_markup_translate as mk
import cp2077_qa_defects as Q
import get_next_audit_batch as G

SPINE = G.BASE_TR
FIXES = os.path.join(UNIV, "opus_qa_fixes.jsonl")
APPLIED = os.path.join(UNIV, "opus_qa_fixes.applied.jsonl")
ONSCREENS = ("onscreens/onscreens.json", "onscreens/onscreens_final.json")


def _index(rows):
    return {str(e.get("primaryKey")): e for e in rows if isinstance(e, dict)}


def main():
    if not os.path.exists(FIXES):
        print("no fixes file — nothing to apply."); return
    fixes = [json.loads(l) for l in open(FIXES, encoding="utf-8") if l.strip()]
    if not fixes:
        print("fixes file empty."); return
    if not Q.acquire_lock("qa_review_apply"):
        sys.exit("[abort] QA lock held by another process — retry later.")
    try:
        spine = json.load(open(SPINE, encoding="utf-8"))
        idx = {sec: _index(spine.get(sec, [])) for sec in spine if isinstance(spine.get(sec), list)}
        applied = skipped = sibling = 0
        for fx in fixes:
            sec, pk, fld = fx["sec"], str(fx["pk"]), fx.get("field", "femaleVariant")
            old, new = fx["old"], fx["new"]
            if mk.parse_slots(new) is None:                 # never write broken markup
                print(f"  [skip-invalid] {sec}|{pk}: new value fails parse"); skipped += 1; continue
            e = idx.get(sec, {}).get(pk)
            if not e or (e.get(fld) or "") != old:
                skipped += 1; continue
            e[fld] = new
            applied += 1
            # propagate to sibling onscreens section if it mirrors the old value
            if sec in ONSCREENS:
                other = ONSCREENS[1] if sec == ONSCREENS[0] else ONSCREENS[0]
                oe = idx.get(other, {}).get(pk)
                if oe and (oe.get(fld) or "") == old:
                    oe[fld] = new
                    sibling += 1
        stamp = time.strftime("%Y%m%d_%H%M%S")
        bak = f"{SPINE}.bak.opusqa.{stamp}"
        shutil.copy2(SPINE, bak)
        tmp = SPINE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(spine, f, ensure_ascii=False)
        os.replace(tmp, SPINE)
        with open(APPLIED, "a", encoding="utf-8") as f:
            for fx in fixes:
                fx["_applied_at"] = stamp
                f.write(json.dumps(fx, ensure_ascii=False) + "\n")
        os.remove(FIXES)
        # keep only the 3 newest opusqa spine backups (each ~44 MB)
        import glob
        baks = sorted(glob.glob(f"{SPINE}.bak.opusqa.*"))
        for old in baks[:-3]:
            try:
                os.remove(old)
            except OSError:
                pass
        print(f"backup -> {os.path.basename(bak)}")
        print(f"APPLIED {applied} fixes (+{sibling} sibling-mirrored), skipped {skipped}.")
    finally:
        Q.release_lock()


if __name__ == "__main__":
    main()
