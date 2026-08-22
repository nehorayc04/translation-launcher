"""Apply verified gender fixes to the spine (femaleVariant -> feminine; maleVariant keeps the
masculine so MALE V is unchanged). Safety: qa.lock + per-row GUARD (write only if the spine
still holds exactly he_female_current) + .bak.goracle backup + atomic write.
Dry-run by default; add --apply to write.  python apply_goracle.py [--apply]"""
import json, os, sys, time, shutil
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "universal"))
from dualgender_fix import acquire_lock, release_lock, atomic_write_json, _entry_key
RES = os.path.join(ROOT, "תרגום_משחקים", "source", "resources")
SPINE = {"base": os.path.join(RES, "localization_translated.json"),
         "dlc":  os.path.join(RES, "dlc_ep1_translated.json")}
DELEGATE = os.path.join(HERE, "..", "gender_oracle_delegate.jsonl")
APPLY = "--apply" in sys.argv

rows = {}
for l in open(DELEGATE, encoding="utf-8"):
    if l.strip():
        r = json.loads(l); rows[f'{r["src"]}|{r["section"]}|{r["pk"]}'] = r
verified = json.load(open(os.path.join(HERE, "verified_female.json"), encoding="utf-8"))
print(f"verified fixes to apply: {len(verified)}")

by_src = {}
for k, fixed in verified.items():
    r = rows.get(k)
    if r: by_src.setdefault(r["src"], []).append((r, fixed))
if APPLY and not acquire_lock("goracle_apply"):
    raise SystemExit("qa.lock held — abort")
st = Counter()
for src, items in by_src.items():
    path = SPINE.get(src)
    if not path: st["bad_src"] += len(items); continue
    spine = json.load(open(path, encoding="utf-8"))
    idx = {}
    for sec, lst in spine.items():
        if isinstance(lst, list):
            idx[sec] = {_entry_key(e): e for e in lst if isinstance(e, dict)}
    dirty = 0
    for r, fixed in items:
        e = idx.get(r["section"], {}).get(str(r["pk"]))
        if e is None: st["missing"] += 1; continue
        # GUARD: the spine must still hold exactly the masculine femaleVariant we scanned
        if (e.get("femaleVariant") or "") != r["he_female_current"]:
            st["guard_skip"] += 1; continue
        mv = e.get("maleVariant") or ""
        mv_new = mv if mv.strip() else r["he_female_current"]   # MALE V keeps masculine
        if APPLY:
            e["maleVariant"] = mv_new
            e["femaleVariant"] = fixed
        dirty += 1; st["ok"] += 1
    if dirty and APPLY:
        bak = f"{path}.bak.goracle.{time.strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(path, bak)
        atomic_write_json(path, spine)
        print(f"  wrote {os.path.basename(path)}: {dirty}  (backup {os.path.basename(bak)})")
    elif dirty:
        print(f"  [dry] {os.path.basename(path)}: would write {dirty}")
if APPLY:
    release_lock("goracle_apply")
print("stats:", dict(st))
print("DRY RUN — add --apply to write." if not APPLY else "APPLIED.")
