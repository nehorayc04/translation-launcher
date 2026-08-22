"""apply_deterministic_fixes.py — NO-AI surgical fix of the deterministically
detected, deterministically fixable defects from deep_scan_deterministic.py:
  * foreign            -> strip_foreign() (remove foreign-script chars)
  * v_transliteration  -> replace standalone וי with Latin 'V'
'missing' / 'english_leak' are NOT touched here (they need translation = AI).

Safety: acquires the project QA write-lock, BACKS UP each spine file before
writing, writes atomically, then re-verifies the fixed fields are clean.
"""
import os, sys, json, re, time, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
UNIV = os.path.join(ROOT, "universal")
sys.path.insert(0, HERE); sys.path.insert(0, UNIV)
import cp2077_qa_defects as Q
import get_next_audit_batch as G
import audit_translations as A

DEFECTS = os.path.join(UNIV, "deterministic_defects.jsonl")
VI = re.compile(r"(?<![֐-׿])וי(?![֐-׿])")
TARGETS = {"base": G.BASE_TR, "dlc": G.DLC_TR}
FIXABLE = {"foreign", "v_transliteration"}


def _index(data):
    idx = {}
    for sec, rows in data.items():
        if not isinstance(rows, list):
            continue
        for e in rows:
            if not isinstance(e, dict):
                continue
            for k in ("primaryKey", "stringId"):
                v = e.get(k)
                if v not in (None, ""):
                    idx[(sec, str(v))] = e
    return idx


def _atomic(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def main():
    if not Q.acquire_lock("deterministic_fix"):
        sys.exit("[abort] QA lock held by another process — not safe to write.")
    try:
        defs = [json.loads(l) for l in open(DEFECTS, encoding="utf-8") if l.strip()]
        stamp = time.strftime("%Y%m%d_%H%M%S")
        applied = {"foreign": 0, "v_transliteration": 0}
        skipped = 0
        for proj, path in TARGETS.items():
            rows = [d for d in defs if d.get("project") == proj and d["kind"] in FIXABLE]
            if not rows:
                continue
            data = json.load(open(path, encoding="utf-8"))
            idx = _index(data)
            for d in rows:
                e = idx.get((d["section"], str(d["pk"])))
                if not e:
                    skipped += 1; continue
                fld = d["field"]
                old = e.get(fld) or ""
                if not old:
                    skipped += 1; continue
                if d["kind"] == "foreign":
                    new = Q.strip_foreign(old)
                elif old.strip() == "וי":
                    # GUARD: a whole-value "וי" is a SPEAKER/CHARACTER NAME (e.g.
                    # the player base record pk=48683). It must STAY Hebrew so the
                    # engine renders the subtitle speaker-label colon on the correct
                    # (RTL) side — Latin "V" breaks the colon. Only substring "וי"
                    # inside real dialogue should become "V". Never touch a bare name.
                    skipped += 1
                    continue
                else:
                    new = VI.sub("V", old)
                if new != old:
                    e[fld] = new
                    applied[d["kind"]] += 1
            bak = f"{path}.bak.detfix.{stamp}"
            shutil.copy2(path, bak)
            _atomic(path, data)
            print(f"[{proj}] backup -> {os.path.basename(bak)}")
        print(f"APPLIED: foreign={applied['foreign']}  v->V={applied['v_transliteration']}  "
              f"(skipped/not-found={skipped})")

        # ── re-verify the fixed fields are clean ──
        remain_foreign = remain_v = 0
        for proj, path in TARGETS.items():
            idx = _index(json.load(open(path, encoding="utf-8")))
            for d in defs:
                if d.get("project") != proj or d["kind"] not in FIXABLE:
                    continue
                e = idx.get((d["section"], str(d["pk"])))
                if not e:
                    continue
                val = e.get(d["field"]) or ""
                if d["kind"] == "foreign" and A.detect_scripts(val):
                    remain_foreign += 1
                if d["kind"] == "v_transliteration" and VI.search(val):
                    remain_v += 1
        print(f"VERIFY: residual foreign={remain_foreign}  residual V->וי={remain_v}  (expect ~0)")
    finally:
        Q.release_lock()


if __name__ == "__main__":
    main()
