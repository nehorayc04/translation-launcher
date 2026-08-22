r"""
Serve the next batch of untranslated VirtualDJ lines (New-Era: each line carries
the source English + ALL other shipped languages as the meaning/gender oracle).

  python get_batch.py [N] [slot] [nslots]

Single agent:   python get_batch.py 40
Parallel (K agents), agent i of K:   python get_batch.py 40 i K
Partition is stable md5(key) % nslots so parallel agents never collide.

Writes current_batch[_<slot>].json = {key: {"en":.., "refs":{lang:..}, "he":""}}.
The agent fills each "he" (LOGICAL Hebrew), then runs merge_batch.py.
Prints "All done!" when nothing is left in this slot.
"""
import sys
import json
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
N = int(sys.argv[1]) if len(sys.argv) > 1 else 40
slot = sys.argv[2] if len(sys.argv) > 2 else ""
nslots = int(sys.argv[3]) if len(sys.argv) > 3 else 1

sfx = f"_{slot}" if slot != "" else ""
tt = json.load(open(HERE / "to_translate.json", encoding="utf-8"))
heb_path = HERE / f"hebrew{sfx}.json"
done = json.load(open(heb_path, encoding="utf-8")) if heb_path.exists() else {}


def mine(key):
    if nslots <= 1:
        return True
    h = int(hashlib.md5(key.encode()).hexdigest(), 16)
    return h % nslots == int(slot)


batch = {}
for key, rec in tt.items():
    if key in done:
        continue
    if not mine(key):
        continue
    batch[key] = {"en": rec["en"], "refs": rec["refs"], "he": ""}
    if len(batch) >= N:
        break

out = HERE / f"current_batch{sfx}.json"
if not batch:
    print(f"All done!  (translated {len(done)} / {sum(1 for k in tt if mine(k))} in slot '{slot}')")
    out.write_text("{}", encoding="utf-8")
else:
    json.dump(batch, open(out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"wrote {len(batch)} lines -> {out.name}  "
          f"(done {len(done)}, remaining ~{sum(1 for k in tt if mine(k) and k not in done)})")
