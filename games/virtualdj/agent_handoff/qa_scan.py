r"""
Full-corpus QA over the merged Hebrew (structural, no LM).

  python qa_scan.py

Merges hebrew.json + every hebrew_*.json (parallel slots), runs the validator
against to_translate.json, and reports coverage + failures by category.
"""
import sys
import json
import glob
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _tokens import validate  # noqa: E402

tt = json.load(open(HERE / "to_translate.json", encoding="utf-8"))
he = {}
for p in [HERE / "hebrew.json"] + [Path(x) for x in glob.glob(str(HERE / "hebrew_*.json"))]:
    if p.exists():
        he.update(json.load(open(p, encoding="utf-8")))

cats = {}
bad = []
for key, val in he.items():
    en = tt.get(key, {}).get("en", "")
    ok, reason = validate(en, val)
    if not ok:
        cats[reason] = cats.get(reason, 0) + 1
        bad.append((key, reason, en[:40], (val or "")[:40]))

print(f"coverage: {len(he)} / {len(tt)}  ({100*len(he)/max(1,len(tt)):.1f}%)")
print(f"missing:  {len(tt) - len(he)}")
print(f"defects:  {len(bad)}")
for c, n in sorted(cats.items(), key=lambda x: -x[1]):
    print(f"   {c:24s} {n}")
for key, reason, en, val in bad[:30]:
    print(f"  BAD [{reason}] {key}  en={en!r} he={val!r}")
