r"""
Validate + merge a filled batch into hebrew[_<slot>].json (anti-cheat gate).

  python merge_batch.py [slot]

Reads current_batch[_<slot>].json ({key:{en,refs,he}}), runs the structural
validator on each "he", and merges only the ones that PASS. Rejected lines are
listed with a reason and stay untranslated (re-served on the next get_batch).
The agent can NOT cheat by copying English, dropping a %-token, leaving niqqud,
or writing another script -> those are rejected.
"""
import sys
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _tokens import validate  # noqa: E402

slot = sys.argv[1] if len(sys.argv) > 1 else ""
sfx = f"_{slot}" if slot != "" else ""

batch = json.load(open(HERE / f"current_batch{sfx}.json", encoding="utf-8"))
heb_path = HERE / f"hebrew{sfx}.json"
done = json.load(open(heb_path, encoding="utf-8")) if heb_path.exists() else {}

added, rejected = 0, []
for key, rec in batch.items():
    en = rec.get("en", "")
    he = (rec.get("he") or "").strip()
    ok, reason = validate(en, he)
    if ok:
        done[key] = he
        added += 1
    else:
        rejected.append((key, reason, en[:40], he[:40]))

json.dump(done, open(heb_path, "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)

print(f"merged {added} / {len(batch)}  (total {len(done)})  rejected {len(rejected)}")
for key, reason, en, he in rejected[:40]:
    print(f"  REJECT [{reason}] {key}  en={en!r} he={he!r}")
if len(rejected) > 40:
    print(f"  ... +{len(rejected) - 40} more")
