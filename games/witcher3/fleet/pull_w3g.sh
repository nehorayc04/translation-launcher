#!/usr/bin/env bash
# Collect the 3 W3 gender-review streams' out.json -> merge into w3_gender_reviewed.json.
cd "$(dirname "$0")" || exit 1
mkdir -p w3g_banks
pull() { # name host port user remote
  scp -P "$3" -o StrictHostKeyChecking=no -o ConnectTimeout=10 "$4@$2:$5" "w3g_banks/out_$1.json" >/dev/null 2>&1 \
    && python -c "import json;json.load(open('w3g_banks/out_$1.json'))" 2>/dev/null || rm -f "w3g_banks/out_$1.json"
}
pull vm  127.0.0.1 2222 vboxuser "C:/w3gw/out.json"
pull vm2 127.0.0.1 2223 vboxuser "C:/w3gw/out.json"
cp -f desktop_w3g/out.json w3g_banks/out_desktop.json 2>/dev/null
python - <<'PY'
import json, glob, os
he = {}
for f in glob.glob("w3g_banks/out_*.json"):
    try: he.update(json.load(open(f, encoding="utf-8")))
    except Exception: pass
json.dump(he, open("w3_gender_reviewed.json.tmp", "w", encoding="utf-8"), ensure_ascii=False)
os.replace("w3_gender_reviewed.json.tmp", "w3_gender_reviewed.json")
corpus = json.load(open("w3_gender_corpus.json", encoding="utf-8"))
changed = sum(1 for k, v in he.items() if k in corpus and v != corpus[k]["he"])
print(f"w3g reviewed: {len(he)}/{len(corpus)}  remaining {len(corpus)-len(he)}  (gender-changed so far {changed})")
PY
