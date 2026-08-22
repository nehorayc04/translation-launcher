#!/usr/bin/env bash
# Collect the 3 W3-arabic streams' out.json -> merge into agent_arabic/hebrew.json.
cd "$(dirname "$0")" || exit 1
mkdir -p w3ar_banks
pull() { # name host port user remote
  scp -P "$3" -o StrictHostKeyChecking=no -o ConnectTimeout=10 "$4@$2:$5" "w3ar_banks/out_$1.json" >/dev/null 2>&1 \
    && python -c "import json;json.load(open('w3ar_banks/out_$1.json'))" 2>/dev/null || rm -f "w3ar_banks/out_$1.json"
}
pull vm  127.0.0.1 2222 vboxuser "C:/w3arw/out.json"
pull vm2 127.0.0.1 2223 vboxuser "C:/w3arw/out.json"
cp -f desktop_w3ar/out.json w3ar_banks/out_desktop.json 2>/dev/null
python - <<'PY'
import json, glob, os
he = {}
for f in glob.glob("w3ar_banks/out_*.json"):
    try: he.update(json.load(open(f, encoding="utf-8")))
    except Exception: pass
json.dump(he, open("agent_arabic/hebrew.json.tmp", "w", encoding="utf-8"), ensure_ascii=False)
os.replace("agent_arabic/hebrew.json.tmp", "agent_arabic/hebrew.json")
tt = json.load(open("agent_arabic/to_translate.json", encoding="utf-8"))
print(f"w3ar merged: {len(he)}/{len(tt)}  remaining {len(tt)-len(he)}")
PY
