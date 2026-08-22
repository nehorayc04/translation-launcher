"""Switch every fleet machine from the SHARD worker to the POOL worker.

Per machine, in the order that matters:
  1. push cc_worker.py + the current cd_nim.py it imports for the prompt/guard,
  2. rewrite run3.bat so the scheduled task launches the pool worker,
  3. kill any shard worker still holding a slice (and its singleton lock),
  4. ENABLE then run the task - `schtasks /run` on a Disabled task does nothing
     and still exits 0, which reads as "restarted" while the machine sits idle,
  5. re-COUNT the processes and print what is actually running.

Step 5 is not decoration: a kill or a launch that reports success and changes
nothing is the failure mode this fleet has hit again and again.

Usage:  python switch_to_pool.py [--dry]
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import prep_machines as PM                        # noqa: E402  (machine map + ssh plumbing)

FILES = ["cc_worker.py", "cd_nim.py"]


def _sh(cmd, timeout):
    """scp/ssh with the stderr KEPT - swallowing it is how a 'pushed' line was
    printed for a transfer that never happened."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        class R:
            returncode, stdout, stderr = 1, "", str(e)
        return R()


def run3(d, py):
    lines = ["@echo off", f"cd /d {d}"]
    for p in PM.PROVS:
        lines.append(f'start "" /B "{py}" -u cc_worker.py {p} >> w_{p}.log 2>&1')
    return "\r\n".join(lines) + "\r\n"


def main():
    dry = "--dry" in sys.argv
    for m in PM.MACHINES:
        name, d, py = m["n"], m["dir"], m["py"]
        print(f"[{name}] {m['user']}@{m['host']}:{m['port']}  {d}")
        if dry:
            continue

        ok = True
        for f in FILES:
            r = _sh(["scp"] + PM.SSHO + ["-P", str(m["port"]), os.path.join(HERE, f),
                     f'{m["user"]}@{m["host"]}:{d}/{f}'], 240)
            if r.returncode:
                print(f"  scp {f} rc={r.returncode} {(r.stderr or '').strip()[:140]}")
                ok = False
        if not ok:
            print(f"  [{name}] SKIP restart - the files did not land")
            continue

        body = run3(d, py).replace("'", "''")
        scr = (f"Set-Content -Path '{d}\\run3.bat' -Encoding ASCII -Value '{body}';"
               "Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | "
               "Where-Object { $_.CommandLine -match 'cd_nim' } | "
               "ForEach-Object { Stop-Process -Id $_.ProcessId -Force };"
               f"Get-ChildItem -Path '{d}' -Filter 'worker*.lock' "
               "-ErrorAction SilentlyContinue | Remove-Item -Force;"
               "foreach ($t in 'CdMP','CdMPBoot') { Enable-ScheduledTask -TaskName $t "
               "-ErrorAction SilentlyContinue | Out-Null };"
               "schtasks /run /tn CdMP | Out-Null; Start-Sleep -Seconds 15;"
               "$n=@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | "
               "Where-Object { $_.CommandLine -match 'cc_worker' }).Count;"
               "$all=@(Get-Process python -ErrorAction SilentlyContinue).Count;"
               "Write-Output \"RESULT pool_workers=$n python_total=$all\"")
        r = PM.run(m, scr, 240)
        out = ((r.stdout or "").strip() or (r.stderr or "").strip())
        print("  " + (out[:200] if out else "(no output)"))


if __name__ == "__main__":
    main()
