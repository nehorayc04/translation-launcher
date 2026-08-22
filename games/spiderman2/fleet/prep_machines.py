# -*- coding: utf-8 -*-
"""Make all 7 machines SM2-ready BEFORE the handover fires — idempotent, non-disruptive.

The handover script's start_game() assumes the incoming game's worker directory, its API keys
and its launcher already exist on every machine. They do not: a brand-new game has nothing on
the remotes. If that prerequisite is missing at handover time, the deploy half-succeeds (scp
into a non-existent directory fails, the task points at a run3.bat that isn't there) and the
21 streams sit idle with no error anywhere — the exact silent-stall shape this fleet keeps
producing. So the preparation is done NOW, while Skyrim is still running, and verified.

What it does per machine, all of it safe to run at any time:
  1. create the SM2 worker dir
  2. copy keys.json ACROSS FROM THE SKYRIM DIR ON THAT SAME MACHINE — never from here. Each
     machine holds a DIFFERENT key set (7 machines x 3 providers, and the rotation offset is
     per machine); pushing one keys.json to all of them would collapse the fleet onto one key
     and 429 everything.
  3. write run3.bat (VMs/laptop) and, on the non-elevated desktop, launch_workers.vbs — copied
     in SHAPE from the working Skyrim launchers, incl. `start "" /B` (a `/MIN` here breaks the
     `>> log 2>&1` redirect and every worker log stays 0 bytes)
  4. register Sm2MP + Sm2MPBoot **DISABLED**, so nothing can start before Skyrim finishes.
     The handover enables and runs them.

Run:  python prep_machines.py          # prepare + verify
      python prep_machines.py --check  # verify only, change nothing
"""
import base64, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
KEY = os.path.expanduser("~/.ssh/id_ed25519")
SSHO = ["-i", KEY, "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes",
        "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=20"]

# python.exe differs between the laptop/desktop (Programs\Python\Python313) and the VMs
# (Local\Python\pythoncore-3.14-64). Taking the wrong one is a silent no-op: the task runs,
# cmd cannot find the exe, and the log stays empty.
PY_HOST = r"C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe"
PY_VM = r"C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe"

MACHINES = [
    {"n": "desktop", "local": True, "dir": r"C:\sm2w", "src": r"C:\skyrimw", "py": PY_HOST},
    {"n": "laptop", "port": 22, "user": "Nehoray_Cohen", "host": "10.0.0.49", "py": PY_HOST,
     "dir": r"C:\Users\Nehoray_Cohen\Projects\sm2_worker",
     "src": r"C:\Users\Nehoray_Cohen\Projects\skyrim_worker"},
    {"n": "vm4", "port": 2225, "user": "vboxuser", "host": "10.0.0.49", "dir": r"C:\sm2w", "src": r"C:\skyrimw", "py": PY_VM},
    {"n": "vm5", "port": 2226, "user": "vboxuser", "host": "10.0.0.49", "dir": r"C:\sm2w", "src": r"C:\skyrimw", "py": PY_VM},
    {"n": "vm", "port": 2222, "user": "vboxuser", "host": "127.0.0.1", "dir": r"C:\sm2w", "src": r"C:\skyrimw", "py": PY_VM},
    {"n": "vm2", "port": 2223, "user": "vboxuser", "host": "127.0.0.1", "dir": r"C:\sm2w", "src": r"C:\skyrimw", "py": PY_VM},
    {"n": "vm3", "port": 2224, "user": "vboxuser", "host": "127.0.0.1", "dir": r"C:\sm2w", "src": r"C:\skyrimw", "py": PY_VM},
]
PROVS = ["groq", "sambanova", "nim"]
WORKER = "sm2ne2_nim.py"


def b64(s):
    return base64.b64encode(s.encode("utf-16-le")).decode()


def run(m, script, timeout=90):
    enc = b64(script)
    if m.get("local"):
        cmd = ["powershell", "-NoProfile", "-EncodedCommand", enc]
    else:
        cmd = ["ssh"] + SSHO + ["-p", str(m["port"]), f'{m["user"]}@{m["host"]}',
                                f"powershell -NoProfile -EncodedCommand {enc}"]
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        class R:
            returncode, stdout, stderr = 1, "", str(e)
        return R()


def run3_bat(d, py):
    lines = [f"@echo off", f"cd /d {d}"]
    for p in PROVS:
        lines.append(f'start "" /B "{py}" -u {WORKER} {p} >> w_{p}.log 2>&1')
    return "\r\n".join(lines) + "\r\n"


def vbs(d, py):
    out = ['Set sh = CreateObject("WScript.Shell")']
    for i, p in enumerate(PROVS):
        out.append(f'sh.Run "cmd /c cd /d {d} & start ""sm2_{p}"" /B ""{py}"" '
                   f'-u {WORKER} {p} >> w_{p}.log 2>&1", 0, False')
        if i < len(PROVS) - 1:
            out.append("WScript.Sleep 2000")
    return "\r\n".join(out) + "\r\n"


def prep(m, check_only):
    d, src, py = m["dir"], m["src"], m["py"]
    if check_only:
        scr = (f"$d='{d}';"
               "$r=@();"
               "$r+= if (Test-Path $d) {'dir=1'} else {'dir=0'};"
               "$r+= if (Test-Path \"$d\\keys.json\") {'keys=1'} else {'keys=0'};"
               "$r+= if (Test-Path \"$d\\run3.bat\") {'bat=1'} else {'bat=0'};"
               f"$r+= if (Test-Path \"$d\\{WORKER}\") {{'worker=1'}} else {{'worker=0'}};"
               "$t=Get-ScheduledTask -TaskName 'Sm2MP' -EA SilentlyContinue;"
               "$r+= 'task=' + $(if ($t) { $t.State } else { 'none' });"
               "Write-Output ($r -join ' ')")
        r = run(m, scr, 60)
        return (r.stdout or r.stderr or "no answer").strip().splitlines()[-1:] or ["(silent)"]

    body = run3_bat(d, py).replace("'", "''")
    extra = ""
    if m.get("local"):
        extra = (f"Set-Content -Path '{d}\\launch_workers.vbs' -Encoding ASCII -Value "
                 f"'{vbs(d, py).replace(chr(39), chr(39) * 2)}';")
        # the desktop shell is NOT elevated: /ru SYSTEM and /sc onstart both fail with
        # "Access is denied", so the desktop gets a user-level minute task + the Startup
        # folder for reboot resilience (exactly what Skyrim runs with).
        task = ("schtasks /create /tn Sm2MP /tr 'wscript.exe " + d + "\\launch_workers.vbs' "
                "/sc minute /mo 5 /f | Out-Null;"
                "Disable-ScheduledTask -TaskName Sm2MP | Out-Null;")
    else:
        task = ("schtasks /create /tn Sm2MP /tr 'cmd /c " + d + "\\run3.bat' /sc minute /mo 5 "
                "/ru SYSTEM /rl HIGHEST /f | Out-Null;"
                "schtasks /create /tn Sm2MPBoot /tr 'cmd /c " + d + "\\run3.bat' /sc onstart "
                "/ru SYSTEM /rl HIGHEST /f | Out-Null;"
                "Disable-ScheduledTask -TaskName Sm2MP | Out-Null;"
                "Disable-ScheduledTask -TaskName Sm2MPBoot | Out-Null;")

    scr = ("$ErrorActionPreference='SilentlyContinue';"
           f"New-Item -ItemType Directory -Force -Path '{d}' | Out-Null;"
           # keys.json comes from THIS machine's own skyrim dir — never pushed from the repo
           f"if (Test-Path '{src}\\keys.json') {{ Copy-Item '{src}\\keys.json' '{d}\\keys.json' -Force }};"
           f"Set-Content -Path '{d}\\run3.bat' -Encoding ASCII -Value '{body}';"
           + extra + task +
           f"$k = if (Test-Path '{d}\\keys.json') {{1}} else {{0}};"
           "$t = (Get-ScheduledTask -TaskName 'Sm2MP' -EA SilentlyContinue).State;"
           "Write-Output \"prepared keys=$k task=$t\"")
    r = run(m, scr, 120)
    return (r.stdout or r.stderr or "no answer").strip().splitlines()[-1:] or ["(silent)"]


def main():
    check = "--check" in sys.argv
    if not os.path.exists(os.path.join(HERE, WORKER)):
        sys.exit(f"missing {WORKER} — run make_worker.py first")
    print(("CHECK" if check else "PREPARE") + " SM2 machines")
    for m in MACHINES:
        print(f"  {m['n']:<8} {prep(m, check)[0]}")


if __name__ == "__main__":
    main()
