import os, subprocess, base64, json, sys
HERE = os.path.dirname(os.path.abspath(__file__))
# --no-restart: stage the code+shards WITHOUT starting anything. Used to pre-deploy CD while
# Skyrim is still the live fleet — starting it early would put 42 workers on the same 30 API
# keys, which is the documented "more 429s, no other symptom" failure.
NO_RESTART = "--no-restart" in sys.argv


# 🔴 `expanduser("~")` is REDIRECTED under an Antigravity profile, so the ssh key resolved to
# ...\AntigravityProfiles\<p>\.ssh\id_ed25519 (nonexistent). scp then prints only a *Warning*
# ("Identity file ... not accessible"), falls back to another auth method, and a REMOTE machine
# fails rc=255 while the LOCAL VMs still succeed — an asymmetry that reads as "vm5 is down"
# instead of "the key path is wrong". Resolve the REAL profile. [[env-redirection-real-home]]
def _find_key():
    cands = []
    try:
        import ctypes
        buf = ctypes.c_wchar_p()
        # FOLDERID_Profile {5E6C858F-0E22-4760-9AFE-EA3317B67173} in GUID byte order
        # (Data1/2/3 little-endian, Data4 as-is) — get this wrong and the call just fails.
        guid = ctypes.create_string_buffer(bytes.fromhex("8f856c5e220e60479afeea3317b67173"))
        if ctypes.windll.shell32.SHGetKnownFolderPath(
                ctypes.byref(guid), 0, None, ctypes.byref(buf)) == 0 and buf.value:
            cands.append(os.path.join(buf.value, ".ssh", "id_ed25519"))
    except Exception:
        pass
    cands += [os.path.expanduser("~/.ssh/id_ed25519"),
              r"C:\Users\Nehoray_Cohen\.ssh\id_ed25519"]
    for c in cands:
        if c and os.path.exists(c):
            return c
    raise SystemExit("ssh key not found in: " + " | ".join(cands))


KEY = _find_key()
SSHO = ["-i", KEY, "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes",
        "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=12"]
machines = [
    {"name": "desktop", "dir": "C:/cdw", "ssh": None},
    {"name": "laptop", "dir": "C:/Users/Nehoray_Cohen/Projects/cd_worker", "ssh": "10.0.0.49", "port": 22, "user": "Nehoray_Cohen"},
    {"name": "vm4", "dir": "C:/cdw", "ssh": "10.0.0.49", "port": 2225, "user": "vboxuser"},
    {"name": "vm5", "dir": "C:/cdw", "ssh": "10.0.0.49", "port": 2226, "user": "vboxuser"},
    {"name": "vm", "dir": "C:/cdw", "ssh": "127.0.0.1", "port": 2222, "user": "vboxuser", "vm": True},
    {"name": "vm2", "dir": "C:/cdw", "ssh": "127.0.0.1", "port": 2223, "user": "vboxuser", "vm": True},
    {"name": "vm3", "dir": "C:/cdw", "ssh": "127.0.0.1", "port": 2224, "user": "vboxuser", "vm": True},
]
PROVS = ["groq", "sambanova", "nim"]
# only the machines this game OWNS (machines.json) — the other boxes are running the other
# game, and pushing a shard there would put two fleets on one machine's key set
_mf = os.path.join(HERE, "machines.json")
if os.path.exists(_mf):
    _own = set(json.load(open(_mf, encoding="utf-8")))
    machines = [m for m in machines if m["name"] in _own]

# 🔴 THE LAPTOP ROAMS. It hosts THREE of the streams (laptop + the vm4/vm5 guests behind its
# port-forwards), so when it leaves the LAN all 9 of those streams fail with
# "Connection timed out" — which reads as "3 machines are down" when the box is actually up
# and reachable on its Tailscale address. Probe once per host and switch the whole group.
ALT_HOST = {"10.0.0.49": "100.116.78.88"}          # LAN -> Tailscale (reachable on any network)


def _reachable(host, port, user):
    try:
        return subprocess.run(["ssh"] + SSHO + ["-p", str(port), f"{user}@{host}", "echo PONG"],
                              capture_output=True, text=True, timeout=25).returncode == 0
    except Exception:
        return False


_host_fix = {}
for _m in machines:
    h = _m.get("ssh")
    if not h or h in _host_fix or h not in ALT_HOST:
        continue
    if _reachable(h, _m["port"], _m["user"]):
        _host_fix[h] = h
    else:
        alt = ALT_HOST[h]
        _host_fix[h] = alt if _reachable(alt, _m["port"], _m["user"]) else h
        if _host_fix[h] != h:
            print(f"[host] {h} unreachable -> using {alt} (Tailscale)")
for _m in machines:
    if _m.get("ssh") in _host_fix:
        _m["ssh"] = _host_fix[_m["ssh"]]


def b64(s):
    return base64.b64encode(s.encode("utf-16-le")).decode()


# The worker + its support files travel WITH the shards. Pushing them separately by hand is
# how a machine ends up running last week's code against this week's shard (hit 2026-08-07:
# a shell where bare `scp` does not resolve reported "pushed" per line while transferring
# nothing, and 6 of 7 machines silently stayed on the previous worker). Python's subprocess
# resolves scp correctly, so keeping it in THIS script makes the deploy atomic and verifiable.
CODE = ["cd_nim.py", "fleet_providers.py", "brain_glossary.json"]


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
              "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'cd_nim' } | "
              "ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force } catch {} }; "
              f"Remove-Item '{mdir}/worker_*.lock' -ErrorAction SilentlyContinue; Start-Sleep 2; "
              # 🔴 prep_machines registers CdMP/CdMPBoot **Disabled** on purpose (so a staged
              # game can never start while another one owns the keys). `schtasks /run` on a
              # Disabled task does NOTHING and still exits 0 — every step would report success
              # and all 18 streams would sit idle. ENABLE first, always.
              "Enable-ScheduledTask -TaskName CdMP -ErrorAction SilentlyContinue | Out-Null; "
              "Enable-ScheduledTask -TaskName CdMPBoot -ErrorAction SilentlyContinue | Out-Null; "
              "schtasks /run /tn CdMP | Out-Null; Write-Output RESTARTED")
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
