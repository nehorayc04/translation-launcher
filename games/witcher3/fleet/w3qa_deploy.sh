#!/bin/bash
# Deploy the New-Era QA reviewer (w3qa_nim) to VM1 + VM2.
# Own dir C:\w3qa so it never collides with a w3_nim / w3ut_nim / pt_nim worker.
# scp worker + slice + selfheal, reuse the VM's existing NIM key, register the
# Scheduled Tasks (5-min heal + on-boot) and launch hidden.
set -u
KEY=~/.ssh/id_ed25519
FLEET="/c/Users/Nehoray_Cohen/Projects/Game translator/games/witcher3/fleet"
VPY='C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe'
U=vboxuser
H=127.0.0.1

deploy(){ # port slice_index
  local P=$1 N=$2
  echo "--- vm$((N+1)) ($H:$P) slice $N ---"
  ssh -i "$KEY" -p "$P" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=20 "$U@$H" \
    "powershell -NoProfile -Command \"New-Item -ItemType Directory -Force C:\\w3qa | Out-Null\"" >/dev/null 2>&1 \
    || { echo "  SSH FAILED — skip"; return 1; }
  scp -i "$KEY" -P "$P" -o StrictHostKeyChecking=no -o ConnectTimeout=20 \
      "$FLEET/w3qa_nim.py" "$U@$H:C:/w3qa/w3qa_nim.py" >/dev/null 2>&1 || { echo "  scp worker FAILED"; return 1; }
  scp -i "$KEY" -P "$P" -o StrictHostKeyChecking=no -o ConnectTimeout=60 \
      "$FLEET/qa_slice_$N.json" "$U@$H:C:/w3qa/corpus.json" || { echo "  scp corpus FAILED"; return 1; }
  scp -i "$KEY" -P "$P" -o StrictHostKeyChecking=no -o ConnectTimeout=20 \
      "$FLEET/selfheal_w3qa.ps1" "$U@$H:C:/w3qa/selfheal.ps1" >/dev/null 2>&1
  # reuse whichever NIM key this VM already has
  ssh -i "$KEY" -p "$P" -o StrictHostKeyChecking=no "$U@$H" \
    "powershell -NoProfile -Command \"foreach(\$s in 'C:\\w3w\\key.txt','C:\\w3ut\\key.txt','C:\\ptw\\key.txt','C:\\Users\\vboxuser\\Desktop\\key.txt'){ if(Test-Path \$s){ Copy-Item \$s C:\\w3qa\\key.txt -Force; break } }\"" >/dev/null 2>&1
  ssh -i "$KEY" -p "$P" -o StrictHostKeyChecking=no "$U@$H" \
    "powershell -NoProfile -Command \"if(Test-Path C:\\w3qa\\key.txt){'key OK'}else{'KEY MISSING'}\"" 2>/dev/null | tr -d '\r'
  ssh -i "$KEY" -p "$P" -o StrictHostKeyChecking=no "$U@$H" \
    "schtasks /Create /TN W3qaWorker /TR \"powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File C:\\w3qa\\selfheal.ps1\" /SC MINUTE /MO 5 /RU SYSTEM /RL HIGHEST /F & schtasks /Create /TN W3qaWorkerBoot /TR \"powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File C:\\w3qa\\selfheal.ps1\" /SC ONSTART /RU SYSTEM /RL HIGHEST /F" >/dev/null 2>&1
  local PID=$(ssh -i "$KEY" -p "$P" -o StrictHostKeyChecking=no "$U@$H" \
    "powershell -NoProfile -Command \"(Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='$VPY -u C:\\w3qa\\w3qa_nim.py'; CurrentDirectory='C:\\w3qa'}).ProcessId\"" 2>/dev/null | tr -d '\r')
  echo "  launched pid=$PID"
}

deploy 2222 0
deploy 2223 1
echo "=== w3qa deploy done ==="
