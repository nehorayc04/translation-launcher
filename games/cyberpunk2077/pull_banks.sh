#!/bin/bash
# Recurring pull of each VM/laptop NIM stream's out.json -> host bank (MSYS scp works; Windows scp can't parse C:/ colon).
KEY=~/.ssh/id_ed25519
BANK="/c/Users/Nehoray_Cohen/Projects/Game translator/games/cyberpunk2077/agent_handoff_qa"
LOG=/c/tmp/pull_banks.log
PY="/c/Users/Nehoray_Cohen/AppData/Local/Programs/Python/Python313/python.exe"
pull() {  # name host port user remotepath
  local dest="$BANK/retrans_agent_$1/retrans_corrections.json"
  local tmp="$dest.pull.tmp"
  rm -f "$tmp"
  scp -i "$KEY" -P "$3" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=10 "$4@$2:$5" "$tmp" 2>/dev/null
  if [ -s "$tmp" ] && "$PY" -c "import json,sys;json.load(open(sys.argv[1],encoding='utf-8'))" "$tmp" 2>/dev/null; then
    mv -f "$tmp" "$dest"
    echo "$(date +%H:%M:%S) $1 pulled ($(wc -c <"$dest") B)" >> "$LOG"
  else
    rm -f "$tmp"; echo "$(date +%H:%M:%S) $1 unreachable" >> "$LOG"
  fi
}
echo "$(date +%H:%M:%S) === pull loop start (pid $$) ===" >> "$LOG"
while true; do
  pull vm     127.0.0.1 2222 vboxuser "C:/vmw/out.json"
  pull vm2    127.0.0.1 2223 vboxuser "C:/vmw/out.json"
  pull vm4    10.0.0.49 2225 vboxuser "C:/vmw/out.json"
  pull vm5    10.0.0.49 2226 vboxuser "C:/vmw/out.json"
  pull laptop 10.0.0.49 22   Nehoray_Cohen "C:/Users/Nehoray_Cohen/Projects/cp2077_laptop_worker/out.json"
  sleep 180
done
