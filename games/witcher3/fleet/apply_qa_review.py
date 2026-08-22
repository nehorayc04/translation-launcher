# -*- coding: utf-8 -*-
"""Apply the approved New-Era QA review (qa_reviewed.json) into hebrew.json — for the 2ND update.

Run this ONLY when the audit has been eyeballed and you are building the next mod version.
Every write is guarded: a line is applied only if hebrew.json still holds exactly the "old"
value the reviewer saw, so a concurrent fleet/manual edit is never clobbered.

    py apply_qa_review.py                 # report + sample, writes nothing
    py apply_qa_review.py --iss gender    # limit to one issue class
    py apply_qa_review.py --apply
"""
import json, os, sys, time, collections, re

HERE = os.path.dirname(os.path.abspath(__file__))
HEB = os.path.join(HERE, "hebrew.json")
REV = os.path.join(HERE, "qa_reviewed.json")

STRUCT = re.compile(r"<[^>]*>|\{[^}]*\}|%%|%[#0-9.*\-+]*[a-zA-Z]+|&[a-zA-Z#0-9]+;")
FOREIGN = re.compile(r"[؀-ۿ぀-ヿ一-鿿가-힣Ѐ-ӿ]")
NIQ = re.compile(r"[֑-ֽֿׁׂ]")
HEBRE = re.compile(r"[֐-׿]")


def safe(old, new):
    """Re-verify the reviewer's guarantees on the HOST before touching the spine."""
    if not isinstance(new, str) or not new.strip():
        return False
    if FOREIGN.search(new) or NIQ.search(new) or not HEBRE.search(new):
        return False
    if sorted(STRUCT.findall(new)) != sorted(STRUCT.findall(old)):
        return False
    return True


def main():
    apply_it = "--apply" in sys.argv
    only = None
    if "--iss" in sys.argv:
        only = sys.argv[sys.argv.index("--iss") + 1]

    he = json.load(open(HEB, encoding="utf-8"))
    rev = json.load(open(REV, encoding="utf-8"))

    tags = collections.Counter()
    ok, stale, unsafe = {}, 0, 0
    for k, v in rev.items():
        iss = v.get("iss", "?")
        if only and iss != only:
            continue
        tags[iss] += 1
        cur = he.get(k)
        if not isinstance(cur, str) or cur.strip() != v.get("old", "").strip():
            stale += 1
            continue
        if not safe(cur, v.get("new", "")):
            unsafe += 1
            continue
        ok[k] = v["new"]

    print(f"audit entries       : {len(rev)}" + (f"  (filtered iss={only})" if only else ""))
    print("  by issue          : " + ", ".join(f"{t}:{n}" for t, n in tags.most_common()))
    print(f"  applicable        : {len(ok)}")
    print(f"  stale (spine moved): {stale}")
    print(f"  rejected by guard : {unsafe}")
    print("\n--- sample ---")
    for k in list(ok)[:10]:
        print(f"  EN : {rev[k].get('en','')[:70]}")
        print(f"  was: {rev[k]['old'][:80]}")
        print(f"  now: {rev[k]['new'][:80]}   [{rev[k]['iss']}]")
        print()

    if not apply_it:
        print("(dry-run) re-run with --apply")
        return
    bak = HEB + ".bak.qarev." + time.strftime("%Y%m%d_%H%M%S")
    json.dump(he, open(bak, "w", encoding="utf-8"), ensure_ascii=False)
    he.update(ok)
    tmp = HEB + ".tmp"
    json.dump(he, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, HEB)
    print(f"APPLIED {len(ok)} lines. backup: {os.path.basename(bak)}")
    print("Next: build_mod.py --deploy  ->  sync_release_data.py --apply  ->  pack_release.py")


if __name__ == "__main__":
    main()
