# -*- coding: utf-8 -*-
"""Rolling restart of the pool workers, so a pushed cc_worker.py actually takes effect.

A worker reads its code ONCE, at start: pushing a new cc_worker.py changes nothing until
the process is replaced. This kills the running ones, clears the singleton locks they hold
(a lock left behind makes the relaunch exit instantly and look like a silent no-op), starts
them again through the machine's OWN launcher, and then RE-COUNTS - a `schtasks /run` that
exits 0 is not evidence that anything is running.

Killed mid-claim, a worker's lines simply return to the queue when its lease expires, so a
restart costs nothing but the batches in flight. That is the whole point of the pool.

Run:  python restart_pool_workers.py            # every machine
      python restart_pool_workers.py vm3 vm4    # only these
"""
import subprocess
import sys

import prep_machines as P

PROVS = ("groq", "sambanova", "nim")


def remote(m):
    d = m["dir"].replace("\\", "/")
    ps = (
        "$p=@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | "
        "Where-Object { $_.CommandLine -match 'cc_worker\\.py' });"
        "$k=$p.Count; $p | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue };"
        f"Get-ChildItem -Path '{d}' -Filter '*.lock' -EA SilentlyContinue | Remove-Item -Force -EA SilentlyContinue;"
        "Start-Sleep -Seconds 2;"
        "schtasks /change /tn CdMP /enable | Out-Null;"
        "schtasks /run /tn CdMP | Out-Null;"
        "Start-Sleep -Seconds 20;"
        "$n=@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | "
        "Where-Object { $_.CommandLine -match 'cc_worker\\.py' }).Count;"
        "Write-Output \"killed=$k now=$n\""
    )
    r = P.run(m, ps, timeout=150)
    out = (getattr(r, "stdout", None) or "").strip().splitlines()
    return out[-1].strip() if out else "no output"


def local():
    """The desktop is not elevated, so it has no SYSTEM task - it uses its own VBS launcher."""
    ps = (
        "$p=@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | "
        "Where-Object { $_.CommandLine -match 'cc_worker\\.py' });"
        "$k=$p.Count; $p | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue };"
        "Get-ChildItem -Path 'C:/cdw' -Filter '*.lock' -EA SilentlyContinue | Remove-Item -Force -EA SilentlyContinue;"
        "Start-Sleep -Seconds 2;"
        "wscript.exe 'C:\\cdw\\launch_workers.vbs';"
        "Start-Sleep -Seconds 20;"
        "$n=@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | "
        "Where-Object { $_.CommandLine -match 'cc_worker\\.py' }).Count;"
        "Write-Output \"killed=$k now=$n\""
    )
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True, timeout=180, errors="replace")
    out = (r.stdout or "").strip().splitlines()
    return out[-1].strip() if out else "no output"


def main():
    want = set(a.lower() for a in sys.argv[1:])
    if not want or "desktop" in want:
        print(f"{'desktop':8} {local()}")
    for m in P.MACHINES:
        if want and m["n"].lower() not in want:
            continue
        print(f"{m['n']:8} {remote(m)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
