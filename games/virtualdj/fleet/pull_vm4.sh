#!/bin/bash
# Pull vm4's out.json (Actions slice) and fold VALID entries into the main
# agent_handoff/hebrew.json. Safe: only adds keys not already present, and
# re-validates each with the same _tokens gate.
set -u
KEY=~/.ssh/id_ed25519
H=10.0.0.49; P=2225; U=vboxuser
GAME="/c/Users/Nehoray_Cohen/Projects/Game translator/games/virtualdj"
FLEET="$GAME/fleet"
PY="$GAME/../../.venv/Scripts/python"

scp -i "$KEY" -P $P -o StrictHostKeyChecking=no -o ConnectTimeout=20 \
  "$U@$H:C:/vdjw/out.json" "$FLEET/out_vm4.json" 2>/dev/null \
  || { echo "no out.json yet"; exit 0; }

"$PY" - <<'PY'
import json, sys
sys.path.insert(0, r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\virtualdj\agent_handoff")
from _tokens import validate
G = r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\virtualdj"
tt = json.load(open(G + r"\agent_handoff\to_translate.json", encoding="utf-8"))
he = json.load(open(G + r"\agent_handoff\hebrew.json", encoding="utf-8"))
vm = json.load(open(G + r"\fleet\out_vm4.json", encoding="utf-8"))
add = 0; bad = 0
for k, v in vm.items():
    if k in he or k not in tt:
        continue
    ok, _ = validate(tt[k]["en"], v)
    if ok:
        he[k] = v; add += 1
    else:
        bad += 1
json.dump(he, open(G + r"\agent_handoff\hebrew.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
print(f"folded vm4: +{add}  rejected {bad}  total {len(he)}/{len(tt)}")
PY
