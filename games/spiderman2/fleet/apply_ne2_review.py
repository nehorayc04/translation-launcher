# -*- coding: utf-8 -*-
"""דור 3 (New-Era-2) REVIEW -> merge the fleet's reviewed Hebrew back into the build spine.

hebrew.json is {id:{"he":<hebrew>,"iss":<ok|gender|phrasing|slang|error|foreign>}} where
id = "<kind>:<key>", kind in {subtitles, dialogue}, key = the exact key in
work/subtitles_he.json / work/dialogue_he.json (see build_multilang.py -- that IS how the
corpus was built, so the mapping back is exact by construction).

Independent, DEFENSE-IN-DEPTH verification before writing anything (the worker's own
review_ok()/gender_ok() already gated every accepted change server-side -- this is a second,
local check so a merge can never ship a token/newline regression even if a bank file were
hand-edited or corrupted in transit):
  * STRUCT token multiset (<ts=..>, &rlm;, <tag>, {VAR}, [TOKEN], %spec) must match the
    CURRENT spine value exactly -- the build depends on these byte-for-byte.
  * newline count must match the current spine value.
A line failing either check is REJECTED (spine kept as-is, reported), never silently applied.

Run:  python apply_ne2_review.py [--dry]
"""
import json, os, re, shutil, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
WORK = os.path.join(ROOT, "games", "spiderman2", "work")

# 🔴 [NAME ICON] must be widened alongside sm2ne2_nim.py's STRUCT (same rationale/history
# recorded there) — a space-containing engine token the plain [A-Z0-9_]{1,40} alternative
# below never matches, which let a review pass silently corrupt "[PETE ICON]"->"[פיט ICON]".
# Scoped to " ICON]" only; do NOT widen to any all-caps bracket ("[FOR PICKUP]" is ordinary
# translatable prose, not a protected token).
STRUCT = re.compile(r'<[^<>]{1,120}>|&[a-zA-Z]{2,8};|\{[^{}]{0,80}\}'
                    r'|\[[A-Z][A-Z0-9_]* ICON\]|\[[A-Z0-9_]{1,40}\]|%[#0-9.*+-]*[a-zA-Z]')

SPINE_FILES = {"subtitles": "subtitles_he.json", "dialogue": "dialogue_he.json"}


def load(name):
    return json.load(open(os.path.join(WORK, name), encoding="utf-8"))


def main():
    dry = "--dry" in sys.argv

    hebrew = json.load(open(os.path.join(HERE, "hebrew.json"), encoding="utf-8"))
    spines = {k: load(fn) for k, fn in SPINE_FILES.items()}

    applied = {"subtitles": 0, "dialogue": 0}
    applied_by_iss = {}
    unchanged = 0
    rejected = []
    orphan = 0

    for pid, v in hebrew.items():
        if ":" not in pid:
            orphan += 1
            continue
        kind, key = pid.split(":", 1)
        spine = spines.get(kind)
        if spine is None or key not in spine:
            orphan += 1
            continue
        cur = spine[key]
        new = (v.get("he") or "").strip() if isinstance(v, dict) else str(v or "").strip()
        iss = v.get("iss", "?") if isinstance(v, dict) else "?"
        if not new or new == cur:
            unchanged += 1
            continue
        if sorted(STRUCT.findall(new)) != sorted(STRUCT.findall(cur)):
            rejected.append((pid, "token-mismatch", cur, new))
            continue
        if cur.count("\n") != new.count("\n"):
            rejected.append((pid, "newline-count", cur, new))
            continue
        spine[key] = new
        applied[kind] += 1
        applied_by_iss[iss] = applied_by_iss.get(iss, 0) + 1

    total_applied = sum(applied.values())
    print(f"reviewed rows        : {len(hebrew):,}")
    print(f"unchanged (iss=ok)   : {unchanged:,}")
    print(f"applied total        : {total_applied:,}  (subtitles {applied['subtitles']:,} / "
          f"dialogue {applied['dialogue']:,})")
    print("applied by iss        :", dict(sorted(applied_by_iss.items(), key=lambda kv: -kv[1])))
    print(f"orphan (no spine key) : {orphan:,}")
    print(f"REJECTED (guard)      : {len(rejected):,}")
    for pid, why, cur, new in rejected[:20]:
        print(f"  {why:15s} {pid}\n    cur={cur!r:.120}\n    new={new!r:.120}")

    if dry:
        print("\n[--dry] not written")
        return

    if total_applied == 0:
        print("\nnothing to apply")
        return

    ts = time.strftime("%Y%m%d_%H%M%S")
    for kind, fn in SPINE_FILES.items():
        if applied[kind] == 0:
            continue
        path = os.path.join(WORK, fn)
        bak = path + f".bak.ne2review.{ts}"
        shutil.copy2(path, bak)
        tmp = path + ".tmp"
        json.dump(spines[kind], open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.replace(tmp, path)
        print(f"wrote {fn}  (+{applied[kind]:,} changed)  backup -> {os.path.basename(bak)}")


if __name__ == "__main__":
    main()
