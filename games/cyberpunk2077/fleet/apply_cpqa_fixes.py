# -*- coding: utf-8 -*-
"""Apply the CP2077 line-by-line QA fixes (cpqa_fixes.jsonl) into the translation spine.

GUARDED + GENDER-AWARE + MONOTONIC:
  * A fix is applied ONLY if the current femaleVariant still equals the fix's `old`
    (a fix computed against a since-changed value is silently skipped — never clobbers).
  * `gender` fixes touch ONLY femaleVariant (the fix is specifically the feminine form;
    setting maleVariant too would make the male V read feminine).
  * non-gender fixes (phrasing/error/slang/foreign) also sync maleVariant IFF it == old
    (keeps the backfilled male copy in step for a gender-neutral text correction).
  * The 185 flagged suspects (cpqa_fixes_suspect.jsonl) are a SEPARATE file — never applied here.

Backs up each spine to <name>.bak.cpqa.<ts> before writing, atomically.
Also emits affected_cpqa_sections.txt (base subtitle sections) so the re-bake is targeted.
Run: python apply_cpqa_fixes.py [--dry]
"""
import json, os, sys, time, collections

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
RES = os.path.join(ROOT, "תרגום_משחקים", "source", "resources")
BASE = os.path.join(RES, "localization_translated.json")
DLC = os.path.join(RES, "dlc_ep1_translated.json")
FIXES = os.path.join(os.path.dirname(__file__), "cpqa_fixes.jsonl")
DRY = "--dry" in sys.argv


def load(p):
    return json.load(open(p, encoding="utf-8"))


def index(spine):
    """(sec, str(primaryKey)) -> entry, plus stringId if present."""
    idx = {}
    for sec, items in spine.items():
        for it in items:
            for kf in ("primaryKey", "stringId"):
                v = it.get(kf)
                if v is not None:
                    idx.setdefault((sec, str(v)), it)
    return idx


def main():
    base = load(BASE); dlc = load(DLC)
    bidx = index(base); didx = index(dlc)

    applied = skipped_stale = missing = 0
    male_synced = gender_only = 0
    by_iss = collections.Counter()
    touched_base_sub = set()

    for line in open(FIXES, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        fid = r["id"]; iss = r["iss"]; old = r.get("old", "") or ""; new = r.get("new", "") or ""
        parts = fid.split(":")
        pk = parts[-1]; sec = ":".join(parts[1:-1])
        is_dlc = "ep1" in sec
        it = (didx if is_dlc else bidx).get((sec, pk))
        if it is None:
            missing += 1
            continue
        if it.get("femaleVariant", "") != old:       # monotonic guard
            skipped_stale += 1
            continue
        it["femaleVariant"] = new
        if iss == "gender":
            gender_only += 1
        elif it.get("maleVariant", "") == old:
            it["maleVariant"] = new
            male_synced += 1
        applied += 1
        by_iss[iss] += 1
        if (not is_dlc) and "subtitles" in sec:
            touched_base_sub.add(sec)

    print(f"applied {applied}  | skipped-stale {skipped_stale}  | missing-in-spine {missing}")
    print(f"  gender-only (fV only): {gender_only}   maleVariant synced (neutral): {male_synced}")
    print("  by issue:", dict(by_iss))
    print(f"  affected base-subtitle sections: {len(touched_base_sub)}")

    if DRY:
        print("DRY — nothing written")
        return

    ts = time.strftime("%Y%m%d_%H%M%S")
    for path, obj in ((BASE, base), (DLC, dlc)):
        bak = f"{path}.bak.cpqa.{ts}"
        if not os.path.exists(bak):
            import shutil; shutil.copy2(path, bak)
        tmp = path + ".tmp"
        json.dump(obj, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(tmp, path)
        print(f"  wrote {os.path.basename(path)}  (backup {os.path.basename(bak)})")

    secfile = os.path.join(os.path.dirname(__file__), "affected_cpqa_sections.txt")
    open(secfile, "w", encoding="utf-8").write("\n".join(sorted(touched_base_sub)))
    print(f"  wrote {secfile} ({len(touched_base_sub)} sections)")


if __name__ == "__main__":
    main()
