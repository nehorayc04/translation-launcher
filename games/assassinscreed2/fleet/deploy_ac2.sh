#!/bin/bash
# Deploy the AC2 New-Era worker to the free streams (vm3 remote, desktop local) and launch them.
# Remote worker dir = C:\ac2w  (coexists with C:\w3w and C:\ptw; the self-heal only matches ac2_nim).
set -u
KEY=~/.ssh/id_ed25519
FLEET="/c/Users/Nehoray_Cohen/Projects/Game translator/games/assassinscreed2/fleet"
SSHOPT="-i $KEY -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=20"

deploy_vm(){ # name host port user
  local n=$1 h=$2 p=$3 u=$4
  echo "=== $n ($u@$h:$p) ==="
  ssh $SSHOPT -p "$p" "$u@$h" 'if not exist C:\ac2w mkdir C:\ac2w' 2>/dev/null
  scp $SSHOPT -P "$p" "$FLEET/ac2_nim.py"                    "$u@$h:C:/ac2w/ac2_nim.py"      || return 1
  scp $SSHOPT -P "$p" "$FLEET/splits/corpus_$n.json"         "$u@$h:C:/ac2w/corpus.json"     || return 1
  # reuse the NVIDIA key already on the box (w3w first, then ptw)
  ssh $SSHOPT -p "$p" "$u@$h" 'if exist C:\w3w\key.txt (copy /Y C:\w3w\key.txt C:\ac2w\key.txt) else (copy /Y C:\ptw\key.txt C:\ac2w\key.txt)' 2>/dev/null
  # launch hidden + register a self-resuming task
  ssh $SSHOPT -p "$p" "$u@$h" 'schtasks /Create /TN AC2Worker /TR "pythonw C:\ac2w\ac2_nim.py" /SC MINUTE /MO 5 /F >nul 2>&1 & schtasks /Create /TN AC2WorkerBoot /TR "pythonw C:\ac2w\ac2_nim.py" /SC ONSTART /RU SYSTEM /F >nul 2>&1 & start "" /B pythonw C:\ac2w\ac2_nim.py & echo LAUNCHED' 2>/dev/null
  ssh $SSHOPT -p "$p" "$u@$h" 'dir C:\ac2w' 2>/dev/null | tail -6
}

# ---- vm3 -------------------------------------------------------------------
deploy_vm vm3 127.0.0.1 2224 vboxuser

# ---- desktop (local) -------------------------------------------------------
echo "=== desktop (local) ==="
DW="$FLEET/desktop_worker"; mkdir -p "$DW"
cp -f "$FLEET/ac2_nim.py" "$DW/ac2_nim.py"
cp -f "$FLEET/splits/corpus_desktop.json" "$DW/corpus.json"
[ -f "$DW/key.txt" ] || cp -f /c/w3w/key.txt "$DW/key.txt" 2>/dev/null || true
ls -la "$DW"
