# -*- coding: utf-8 -*-
"""Hand the 21-stream fleet from a FINISHED game to the next one — unattended, once.

The handover is the step that has always been manual, and it is the step where the fleet
silently rots: a finished game's workers keep running and keep spending the SAME provider
keys as whatever comes next (18 such zombies were found alive on 2026-08-07, and the only
symptom was more 429s on the live game), its scheduled tasks keep relaunching them, and the
dashboard keeps showing the retired game because a game only appears if it is in
fleet_config.json. So a handover is FIVE things, not one:

    1. stop the outgoing game everywhere   (kill its workers AND disable its tasks)
    2. deploy the incoming worker + shards to all 7 machines
    3. register + start the incoming tasks
    4. repoint the dashboard: fleet_config.json + the stream-id registry
    5. start the incoming pull + the website progress pusher

It is ONE-SHOT by construction: a stamp file is written before any destructive step, so a
5-minute cron that keeps firing can never run it twice.

    python fleet_handover.py                    # decide only, change nothing
    python fleet_handover.py --apply            # do it
    python fleet_handover.py --apply --force    # ignore the "is it finished" gate
"""
import argparse, glob, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
SSHO = ["-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes", "-o", "ConnectTimeout=30"]
KEY = os.path.expanduser("~/.ssh/id_ed25519")

MACHINES = [
    {"n": "desktop", "local": True},
    {"n": "laptop", "port": 22,   "user": "Nehoray_Cohen", "host": "10.0.0.49"},
    {"n": "vm4",    "port": 2225, "user": "vboxuser",      "host": "10.0.0.49"},
    {"n": "vm5",    "port": 2226, "user": "vboxuser",      "host": "10.0.0.49"},
    {"n": "vm",     "port": 2222, "user": "vboxuser",      "host": "127.0.0.1"},
    {"n": "vm2",    "port": 2223, "user": "vboxuser",      "host": "127.0.0.1"},
    {"n": "vm3",    "port": 2224, "user": "vboxuser",      "host": "127.0.0.1"},
]

# outgoing -> incoming. Everything the handover needs to know about a game lives here.
GAMES = {
    "skyrim": {
        "fleet": "games/skyrim/fleet", "worker": "skyrim_nim", "task": "Skyrim",
        "corpus": "corpus.json", "bank_glob": "out_*.json", "oversized": "oversized.json",
        # the pusher is a bare python process, not a task — a retired game's pusher otherwise
        # keeps publishing its progress to the website forever, next to the new game's
        "pusher_match": "skyrim_progress",
    },
    "spiderman2": {
        "fleet": "games/spiderman2/fleet", "worker": "sm2ne2_nim", "task": "Sm2",
        "corpus": "corpus.json", "bank_glob": "out_*.json", "oversized": None,
        "dir_vm": "C:/sm2w", "dir_laptop": "C:/Users/Nehoray_Cohen/Projects/sm2_worker",
        "title": "Marvel's Spider-Man 2 — ביקורת עידן חדש 2",
        "pull": "pull_sm2ne2.sh", "pusher": "sm2qa_progress.py", "pusher_match": "sm2qa_progress",
        "files": ["sm2ne2_nim.py", "fleet_providers.py", "brain_glossary.json"],
        "watchdog": "sm2ne2_watchdog.ps1",
    },
}
PROVS = ["groq", "sambanova", "nim"]


def sh(args, timeout=120):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def ps_remote(m, script, timeout=90):
    """Always base64 — fighting ssh quoting is how these steps silently do nothing."""
    import base64
    enc = base64.b64encode(script.encode("utf-16-le")).decode()
    if m.get("local"):
        return sh(["powershell", "-NoProfile", "-EncodedCommand", enc], timeout)
    return sh(["ssh", "-i", KEY] + SSHO + ["-p", str(m["port"]),
              f'{m["user"]}@{m["host"]}', f"powershell -NoProfile -EncodedCommand {enc}"], timeout)


def remaining(game):
    g = GAMES[game]; d = os.path.join(REPO, g["fleet"])
    corpus = json.load(open(os.path.join(d, g["corpus"]), encoding="utf-8"))
    done = set()
    for f in glob.glob(os.path.join(d, "banks", g["bank_glob"])):
        try:
            done |= set(json.load(open(f, encoding="utf-8")).keys())
        except Exception:
            pass
    over = set()
    if g.get("oversized"):
        try:
            over = set(json.load(open(os.path.join(d, g["oversized"]), encoding="utf-8")))
        except Exception:
            pass
    # a line PARKED as structurally impossible is out of scope, not outstanding work — leaving
    # it in the denominator pins a finished game below 100% forever and the handover never fires
    try:
        for f in glob.glob(os.path.join(d, "*skip*.json")):
            over |= set(json.load(open(f, encoding="utf-8")).get("skip", []))
    except Exception:
        pass
    left = [k for k in corpus if k not in done and k not in over]
    return len(corpus), len(done), len(left)


def stop_game(game):
    g = GAMES[game]
    # the worker AND the pusher, plus every task of this game (MP / MPBoot / FleetPull /
    # Watchdog). Leaving the watchdog enabled is the sharpest trap: it re-enables the game's
    # own tasks and relaunches its workers within 5 minutes, so a handover that only kills
    # processes gets quietly undone and the two fleets then share one key pool.
    match = g["worker"] + ("|" + g["pusher_match"] if g.get("pusher_match") else "")
    scr = ("$ErrorActionPreference='SilentlyContinue';$k=0;"
           "Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | "
           f"Where-Object {{ $_.CommandLine -match '{match}' }} | "
           "ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force; $k++ } catch {} };$d=0;"
           f"Get-ScheduledTask | Where-Object {{ $_.TaskName -match '^{g['task']}' -and $_.State -ne 'Disabled' }} | "
           "ForEach-Object { Disable-ScheduledTask -TaskName $_.TaskName | Out-Null; $d++ };"
           "Write-Output \"stopped killed=$k tasks=$d\"")
    for m in MACHINES:
        r = ps_remote(m, scr)
        print(f"  {m['n']:<8} {(r.stdout or r.stderr or '').strip().splitlines()[-1:] or ['(no answer)']}")


def start_game(game):
    g = GAMES[game]; d = os.path.join(REPO, g["fleet"])
    # 1) shards
    r = sh([sys.executable, os.path.join(d, "reslice_equal.py")], 600)
    print("  " + (r.stdout or r.stderr).strip().replace("\n", "\n  "))
    # 2) code + shards + restart (that script asserts every scp's return code)
    r = sh([sys.executable, os.path.join(d, "push_shards_restart.py")], 900)
    print("  " + (r.stdout or r.stderr).strip().replace("\n", "\n  "))
    # 3) tasks. prep_machines.py already created them DISABLED (so the incoming fleet could be
    # staged without competing for the outgoing game's API keys), so the ONLY thing left is to
    # enable and fire them. 🔴 `schtasks /run` on a DISABLED task does nothing and still exits
    # 0 — enabling first is what makes this step real rather than a silent no-op. Creating the
    # task here as a fallback keeps the handover self-sufficient if prep was never run, but the
    # desktop is NOT elevated (no /ru SYSTEM, no /sc onstart) so it only ever enables+runs.
    for m in MACHINES:
        t = g["task"]
        if m.get("local"):
            scr = (f"Enable-ScheduledTask -TaskName {t}MP -EA SilentlyContinue | Out-Null;"
                   f"schtasks /run /tn {t}MP | Out-Null;"
                   f"$s=(Get-ScheduledTask -TaskName {t}MP -EA SilentlyContinue).State;"
                   f"Write-Output \"started state=$s\"")
        else:
            mdir = g["dir_laptop"] if m["n"] == "laptop" else g.get("dir_vm", "C:/sm2w")
            bat = f"{mdir}/run3.bat".replace("/", "\\")
            scr = (f"if (-not (Get-ScheduledTask -TaskName {t}MP -EA SilentlyContinue)) {{"
                   f"schtasks /create /tn {t}MP /tr 'cmd /c {bat}' /sc minute /mo 5 "
                   f"/ru SYSTEM /rl HIGHEST /f | Out-Null;"
                   f"schtasks /create /tn {t}MPBoot /tr 'cmd /c {bat}' /sc onstart "
                   f"/ru SYSTEM /rl HIGHEST /f | Out-Null }};"
                   f"Enable-ScheduledTask -TaskName {t}MP -EA SilentlyContinue | Out-Null;"
                   f"Enable-ScheduledTask -TaskName {t}MPBoot -EA SilentlyContinue | Out-Null;"
                   f"schtasks /run /tn {t}MP | Out-Null;"
                   f"$s=(Get-ScheduledTask -TaskName {t}MP -EA SilentlyContinue).State;"
                   f"Write-Output \"started state=$s\"")
        r = ps_remote(m, scr)
        print(f"  {m['n']:<8} {(r.stdout or r.stderr or '').strip().splitlines()[-1:] or ['(silent)']}")


def repoint_dashboard(game):
    g = GAMES[game]; d = os.path.join(REPO, g["fleet"])
    total = len(json.load(open(os.path.join(d, g["corpus"]), encoding="utf-8")))
    cfgp = os.path.join(REPO, "tools", "fleet_dashboard", "fleet_config.json")
    cfg = json.load(open(cfgp, encoding="utf-8"))
    machines = []
    for m in MACHINES:
        if m.get("local"):
            machines.append({"name": "desktop", "kind": "local", "dir": g.get("dir_vm", "C:/sm2w")})
        else:
            machines.append({"name": m["n"], "kind": "ssh", "host": m["host"], "lan": m["host"],
                             "port": m["port"], "user": m["user"],
                             "dir": g["dir_laptop"] if m["n"] == "laptop" else "C:/sm2w"})
    cfg["games"] = [{
        "id": game, "title": g["title"], "corpus_total": total,
        "fleet_dir": g["fleet"], "bank_glob": g["bank_glob"],
        "shard_dir": g["fleet"] + "/shards",
        "pull_log": f"C:/tmp/{game}_pull.log", "pull_cadence_minutes": 5,
        "pusher_match": g["pusher_match"], "worker": g["worker"],
        "task": g["task"] + "MP", "pull_script": g["pull"], "machines": machines,
    }]
    json.dump(cfg, open(cfgp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    dist = os.path.join(REPO, "tools", "fleet_dashboard", "dist", "fleet_config.json")
    if os.path.exists(os.path.dirname(dist)):
        import shutil; shutil.copy(cfgp, dist)

    # 🔴 stream numbers are RENAMED, never re-allocated: an unknown key gets the next FREE
    # number, so appending would push the new game to #61+ while the retired one keeps 1-21.
    reg = os.path.join(os.environ.get("LOCALAPPDATA", ""), "FleetDash", "stream_ids.json")
    try:
        ids = json.load(open(reg, encoding="utf-8"))
        ids = {k: v for k, v in ids.items() if not k.startswith(tuple(f"{x}:" for x in GAMES))}
        i = 1
        for m in MACHINES:
            for p in PROVS:
                ids[f"{game}:{m['n']}:{p}"] = i; i += 1
        json.dump(ids, open(reg, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"  stream registry: {game} = #1-{i-1}")
    except Exception as e:
        print(f"  stream registry skipped: {e}")
    print(f"  fleet_config -> {game} ({total:,} lines)")


def start_pull_and_pusher(game):
    g = GAMES[game]; d = os.path.join(REPO, g["fleet"])
    bash = r"C:\Program Files\Git\bin\bash.exe"
    unix = "/" + d.replace("\\", "/").replace(":", "", 1).replace("C", "c", 1)
    sh(["powershell", "-NoProfile", "-Command",
        f"$a=New-ScheduledTaskAction -Execute '{bash}' -Argument '-lc \"cd \\\"{unix}\\\" && bash {g['pull']}\"';"
        "$t=New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5)"
        " -RepetitionDuration (New-TimeSpan -Days 3650);"
        f"Register-ScheduledTask -TaskName '{g['task']}FleetPull' -Action $a -Trigger $t -Force | Out-Null;"
        f"Start-ScheduledTask -TaskName '{g['task']}FleetPull'"], 120)
    sh(["powershell", "-NoProfile", "-Command",
        f"Start-Process -FilePath '{sys.executable}' -ArgumentList '-u {g['pusher']}' "
        f"-WorkingDirectory '{d}' -WindowStyle Hidden"], 60)
    # the incoming game needs its OWN self-healing layer — the outgoing game's watchdog was
    # just disabled, and without a replacement a hung guest or a dead worker sits silent
    if g.get("watchdog"):
        wd = os.path.join(d, g["watchdog"])
        sh(["powershell", "-NoProfile", "-Command",
            "$a=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "
            f"'-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File \"{wd}\"';"
            "$t=New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval "
            "(New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650);"
            "$s=New-ScheduledTaskSettingsSet -Hidden -MultipleInstances IgnoreNew "
            "-ExecutionTimeLimit (New-TimeSpan -Minutes 4);"
            f"Register-ScheduledTask -TaskName '{g['task']}Watchdog' -Action $a -Trigger $t "
            "-Settings $s -Force | Out-Null;"
            f"Start-ScheduledTask -TaskName '{g['task']}Watchdog'"], 120)
    print(f"  {g['task']}FleetPull + {g['task']}Watchdog registered; pusher launched")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", default="skyrim")
    ap.add_argument("--to", dest="dst", default="spiderman2")
    ap.add_argument("--threshold", type=int, default=25,
                    help="outgoing game counts as finished at <= this many real lines left")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    stamp = os.path.join(REPO, GAMES[a.dst]["fleet"], ".handover_done")
    tot, done, left = remaining(a.src)
    print(f"{a.src}: {done:,}/{tot:,}  real remaining {left:,}  (threshold {a.threshold})")
    if os.path.exists(stamp):
        print(f"handover already done ({stamp}) — nothing to do"); return 0
    if left > a.threshold and not a.force:
        print(f"not finished yet — no handover"); return 0
    if not a.apply:
        print("WOULD hand over (pass --apply)"); return 0

    # ONE-SHOT: stamp BEFORE the first destructive step, so a re-fire cannot repeat it.
    open(stamp, "w", encoding="utf-8").write(json.dumps({"from": a.src, "left": left}))
    print(f"\n[1/5] stopping {a.src}");            stop_game(a.src)
    print(f"[2/5+3/5] deploying + starting {a.dst}"); start_game(a.dst)
    print("[4/5] repointing the dashboard");        repoint_dashboard(a.dst)
    print("[5/5] pull + website pusher");           start_pull_and_pusher(a.dst)
    print(f"\nHANDOVER COMPLETE: {a.src} -> {a.dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
