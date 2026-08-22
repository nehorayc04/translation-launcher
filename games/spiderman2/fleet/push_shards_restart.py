import os, subprocess, base64, json, sys
HERE = os.path.dirname(os.path.abspath(__file__))
# --no-restart: stage the code+shards WITHOUT starting anything. Used to pre-deploy SM2 while
# Skyrim is still the live fleet — starting it early would put 42 workers on the same 30 API
# keys, which is the documented "more 429s, no other symptom" failure.
NO_RESTART = "--no-restart" in sys.argv
KEY = os.path.expanduser("~/.ssh/id_ed25519")
SSHO = ["-i", KEY, "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes",
        "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=12"]
machines = [
    {"name": "desktop", "dir": "C:/sm2w", "ssh": None},
    {"name": "laptop", "dir": "C:/Users/Nehoray_Cohen/Projects/sm2_worker", "ssh": "10.0.0.49", "port": 22, "user": "Nehoray_Cohen"},
    {"name": "vm4", "dir": "C:/sm2w", "ssh": "10.0.0.49", "port": 2225, "user": "vboxuser"},
    {"name": "vm5", "dir": "C:/sm2w", "ssh": "10.0.0.49", "port": 2226, "user": "vboxuser"},
    {"name": "vm", "dir": "C:/sm2w", "ssh": "127.0.0.1", "port": 2222, "user": "vboxuser", "vm": True},
    {"name": "vm2", "dir": "C:/sm2w", "ssh": "127.0.0.1", "port": 2223, "user": "vboxuser", "vm": True},
    {"name": "vm3", "dir": "C:/sm2w", "ssh": "127.0.0.1", "port": 2224, "user": "vboxuser", "vm": True},
]
PROVS = ["groq", "sambanova", "nim"]
# only the machines this game OWNS (machines.json) — the other boxes are running the other
# game, and pushing a shard there would put two fleets on one machine's key set
_mf = os.path.join(HERE, "machines.json")
if os.path.exists(_mf):
    _own = set(json.load(open(_mf, encoding="utf-8")))
    machines = [m for m in machines if m["name"] in _own]


def b64(s):
    return base64.b64encode(s.encode("utf-16-le")).decode()


# The worker + its support files travel WITH the shards. Pushing them separately by hand is
# how a machine ends up running last week's code against this week's shard (hit 2026-08-07:
# a shell where bare `scp` does not resolve reported "pushed" per line while transferring
# nothing, and 6 of 7 machines silently stayed on the previous worker). Python's subprocess
# resolves scp correctly, so keeping it in THIS script makes the deploy atomic and verifiable.
CODE = ["sm2ne2_nim.py", "fleet_providers.py", "brain_glossary.json"]


for m in machines:
    name, mdir, is_local = m["name"], m["dir"], m["ssh"] is None
    ok = True
    # 0) push the worker code itself
    for f in CODE:
        src = os.path.join(HERE, f)
        if not os.path.exists(src):
            continue
        try:
            if is_local:
                import shutil; shutil.copy(src, os.path.join(mdir, f))
            else:
                r = subprocess.run(["scp"] + SSHO + ["-P", str(m["port"]), src,
                                    f'{m["user"]}@{m["ssh"]}:{mdir}/{f}'],
                                   capture_output=True, text=True, timeout=90)
                if r.returncode != 0:
                    print(f"  scp {name}/{f} rc={r.returncode} {(r.stderr or '').strip()[:120]}")
                    ok = False
        except Exception as e:
            print(f"  scp {name}/{f} FAIL: {e}"); ok = False
    # 1) push the 3 equal shards -> corpus_<prov>.json
    for prov in PROVS:
        src = os.path.join(HERE, "shards", f"corpus_{name}_{prov}.json")
        if not os.path.exists(src):
            print(f"  MISSING {src}"); ok = False; continue
        try:
            if is_local:
                import shutil; shutil.copy(src, os.path.join(mdir, f"corpus_{prov}.json"))
            else:
                # ⚠️ NOT DEVNULL: swallowing scp's stderr is exactly how "shards=ok" got
                # printed for a transfer that never happened. Check the return code.
                r = subprocess.run(["scp"] + SSHO + ["-P", str(m["port"]), src,
                                    f'{m["user"]}@{m["ssh"]}:{mdir}/corpus_{prov}.json'],
                                   capture_output=True, text=True, timeout=90)
                if r.returncode != 0:
                    print(f"  scp {name}/{prov} rc={r.returncode} {(r.stderr or '').strip()[:120]}")
                    ok = False
        except Exception as e:
            print(f"  scp {name}/{prov} FAIL: {e}"); ok = False
    # 2) VM: ensure IPv6 off; kill workers (they hold the lock + old shard); relaunch fresh
    if NO_RESTART:
        print(f"{name:<9} shards={'ok' if ok else 'PARTIAL'}  staged (no restart)")
        continue
    ipv6 = "Disable-NetAdapterBinding -Name '*' -ComponentID 'ms_tcpip6' -ErrorAction SilentlyContinue; " if m.get("vm") else ""
    script = (ipv6 +
              "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'sm2ne2_nim' } | "
              "ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force } catch {} }; "
              f"Remove-Item '{mdir}/worker_*.lock' -ErrorAction SilentlyContinue; Start-Sleep 2; "
              "schtasks /run /tn Sm2MP | Out-Null; Write-Output RESTARTED")
    try:
        if is_local:
            r = subprocess.run(["powershell", "-NoProfile", "-EncodedCommand", b64(script)],
                               capture_output=True, text=True, timeout=45)
        else:
            r = subprocess.run(["ssh"] + SSHO + ["-p", str(m["port"]), f'{m["user"]}@{m["ssh"]}',
                                f"powershell -NoProfile -EncodedCommand {b64(script)}"],
                               capture_output=True, text=True, timeout=45)
        st = "RESTARTED" if "RESTARTED" in (r.stdout or "") else "no-confirm"
    except Exception as e:
        st = f"restart FAIL: {e}"
    print(f"{name:<9} shards={'ok' if ok else 'PARTIAL'}  {st}")
print("done")
