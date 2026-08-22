#!/bin/bash
# W3 fleet HOURLY health monitor (durable OS task, independent of any chat session).
# Heals everything (w3_heal.sh relaunches any dead of the 6 streams + the progress pusher), then logs
# ONE reliable health line. Read c:/tmp/w3_monitor.log for the last autonomous state.
# Reliability notes: banked/rate come from the pull log (no MSYS→native-python path issue); per-stream
# health = each bank file's line-count (a stream whose count doesn't grow hour-to-hour is stalled — the
# heal will have relaunched it); SSH aliveness is left to w3_heal.sh which owns the proven quoting.
FLEET="/c/Users/Nehoray_Cohen/Projects/Game translator/games/witcher3/fleet"
PY="/c/Users/Nehoray_Cohen/AppData/Local/Programs/Python/Python313/python.exe"
LOG=/c/tmp/w3_monitor.log
TS=$(date '+%Y-%m-%d %H:%M:%S')

# 1) heal (SSH-check + relaunch any dead stream / pusher — the real recovery)
bash "$FLEET/w3_heal.sh" 2>/dev/null

# 2) banked + rate + ETA from the PULL LOG (reliable, timestamped)
read banked rate eta pull_age <<<"$("$PY" - <<'PYEOF' 2>/dev/null
import re,os,time
from datetime import datetime
pts=[]
try:
    for ln in open(r'C:\tmp\w3_pull.log',encoding='utf-8').read().splitlines()[-80:]:
        m=re.match(r'(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\s+W3 banked (\d+)/',ln)
        if m: pts.append((datetime.strptime(m.group(1),'%Y-%m-%d %H:%M:%S').timestamp(),int(m.group(2))))
except Exception: pass
banked=pts[-1][1] if pts else 0
w=[p for p in pts if pts and pts[-1][0]-p[0]<=1800] or pts[-2:]
rate=int((w[-1][1]-w[0][1])/((w[-1][0]-w[0][0])/3600)) if len(w)>=2 and w[-1][0]>w[0][0] else 0
eta=f"{(92829-banked)/rate:.1f}h" if rate>0 else "—"
try: age=int((time.time()-os.path.getmtime(r'C:\tmp\w3_pull.log'))/60)
except Exception: age=-1
print(banked, rate, eta, age)
PYEOF
)"
pct=$("$PY" -c "print(f'{100*${banked:-0}/92829:.1f}')" 2>/dev/null || echo "?")

# 3) per-stream bank line-counts (which streams are contributing)
streams=$("$PY" - <<'PYEOF' 2>/dev/null
import json,glob,os
d=r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\witcher3\fleet\banks"
out=[]
for f in sorted(glob.glob(os.path.join(d,"out_*.json"))):
    n=os.path.basename(f)[4:-5]
    try: c=len(json.load(open(f,encoding="utf-8")))
    except Exception: c=-1
    out.append(f"{n}={c}")
print(" ".join(out))
PYEOF
)

# 4) disk + recent heals (last hour)
disk=$(MSYS_NO_PATHCONV=1 powershell.exe -NoProfile -Command "[math]::Round((Get-PSDrive C).Free/1GB,0)" 2>/dev/null | tr -d '\r ')
heals=$(tail -20 /c/tmp/w3_heal.log 2>/dev/null | grep -c "HEALED" || echo 0)

echo "$TS | banked ${banked:-0}/92829 (${pct}%) | rate ${rate:-0}/h | ETA ${eta:-—} | pull ${pull_age:-?}m ago | disk ${disk}GB | heals(recent)=${heals} | ${streams}" >> "$LOG"
