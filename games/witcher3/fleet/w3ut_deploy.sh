#!/usr/bin/env bash
# Deploy the "New Era" TRANSLATE+multi-lang-gender worker to the FREE vm5 stream (its own dir C:\w3ut,
# so it never collides with a w3_nim / pt_nim worker). scp worker+corpus+key+selfheal, register the
# per-VM auto-resume tasks, launch. out.json is KEPT if it already exists (resumable).
set -u
KEY=~/.ssh/id_ed25519
FLEET="/c/Users/Nehoray_Cohen/Projects/Game translator/games/witcher3/fleet"
VPY='C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe'
H=""; P=2226; U=vboxuser
for cand in 10.0.0.49 100.116.78.88; do
  if ssh -i "$KEY" -p "$P" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=12 "$U@$cand" "echo ok" 2>/dev/null | grep -q ok; then H="$cand"; break; fi
done
[ -z "$H" ] && { echo "❌ vm5 unreachable on 10.0.0.49 and 100.116.78.88:2226"; exit 1; }
echo "--- vm5 reachable at $H:$P ---"
ssh -i "$KEY" -p "$P" -o StrictHostKeyChecking=no "$U@$H" "powershell -NoProfile -Command \"New-Item -ItemType Directory -Force C:\\w3ut | Out-Null\"" 2>/dev/null
# copy the worker + its slice (as corpus.json) + selfheal; key comes from the VM's existing C:\w3w\key.txt
scp -i "$KEY" -P "$P" -o StrictHostKeyChecking=no "$FLEET/w3ut_nim.py"       "$U@$H:C:/w3ut/w3ut_nim.py"
scp -i "$KEY" -P "$P" -o StrictHostKeyChecking=no "$FLEET/w3ut_corpus.json"  "$U@$H:C:/w3ut/corpus.json"
scp -i "$KEY" -P "$P" -o StrictHostKeyChecking=no "$FLEET/selfheal_w3ut.ps1" "$U@$H:C:/w3ut/selfheal.ps1"
# reuse the stream's existing NIM key (never printed): copy C:\w3w\key.txt -> C:\w3ut\key.txt
ssh -i "$KEY" -p "$P" -o StrictHostKeyChecking=no "$U@$H" "powershell -NoProfile -Command \"if (Test-Path C:\\w3w\\key.txt) { Copy-Item C:\\w3w\\key.txt C:\\w3ut\\key.txt -Force } elseif (Test-Path C:\\Users\\vboxuser\\Desktop\\key.txt) { Copy-Item C:\\Users\\vboxuser\\Desktop\\key.txt C:\\w3ut\\key.txt -Force }\"" 2>/dev/null
# register auto-resume tasks (SYSTEM) + launch now
ssh -i "$KEY" -p "$P" -o StrictHostKeyChecking=no "$U@$H" "schtasks /Create /TN W3utWorker /TR \"powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File C:\\w3ut\\selfheal.ps1\" /SC MINUTE /MO 5 /RU SYSTEM /RL HIGHEST /F & schtasks /Create /TN W3utWorkerBoot /TR \"powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File C:\\w3ut\\selfheal.ps1\" /SC ONSTART /RU SYSTEM /RL HIGHEST /F" 2>/dev/null
PID=$(ssh -i "$KEY" -p "$P" -o StrictHostKeyChecking=no "$U@$H" "powershell -NoProfile -Command \"(Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='$VPY -u C:\\w3ut\\w3ut_nim.py'; CurrentDirectory='C:\\w3ut'}).ProcessId\"" 2>/dev/null | tr -d '\r')
echo "  deployed + launched w3ut_nim on vm5 (pid=$PID)"
echo "=== vm5 w3ut deploy done ==="
