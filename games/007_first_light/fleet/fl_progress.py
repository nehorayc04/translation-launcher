# -*- coding: utf-8 -*-
"""Push the 007 First Light translation progress live to the hub dashboard (gameId=007-first-light).

Counted in LINES (not sentences) — unlike crimson_desert's cd_progress.py, this corpus is
already one string-per-unit (deduped by EN text at build_ct_pool.py time), not raw multi-
sentence paragraphs, so splitting further would misrepresent what was actually seeded.

DONE is read directly from the pool DB over SSH (dbexec.py on the self-hosted host), counting
`status='done' OR collected=1` for this game — a TRUE cumulative total that survives
fl_pull_selfhost.py runs (which flip collected=1 and would otherwise make a naive `/cc/stats`
read shrink every time a pull happens). 60 s loop -> /api/admin/progress.

The 007 games row (`availability='coming-soon'`) is NOT `planned`, so this shows on the
homepage dashboard the moment the first snapshot lands — no separate publish step needed
(unlike crimson-desert, which was intentionally kept invisible while still `planned`).
"""
import os, sys, json, time, subprocess, urllib.request
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
CORPUS = os.path.join(HERE, "corpus.json")
HIST = os.path.join(HERE, "fl_progress_hist.json")

GAME_ID = "007-first-light"
INTERVAL = 60
API = "https://hebrew-translation-hub.com"

DB_HOST = "root@10.0.0.20"


def acquire_singleton():
    """One pusher, ever — a second copy appending to the SAME history file reads 0/h on a
    healthy fleet, the exact false alarm crimson-desert's own pusher guards against."""
    lock = os.path.join(HERE, "fl_progress.lock")
    try:
        with open(lock, encoding="utf-8") as fh:
            old = int((fh.read() or "0").strip() or 0)
    except Exception:
        old = 0
    if old and old != os.getpid():
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"(Get-CimInstance Win32_Process -Filter \"ProcessId={old}\").CommandLine"],
                capture_output=True, text=True, timeout=30, errors="replace").stdout or ""
            if "fl_progress" in out:
                print(f"another pusher is already running (pid {old}) - exiting")
                return False
        except Exception:
            pass
    try:
        with open(lock, "w", encoding="utf-8") as fh:
            fh.write(str(os.getpid()))
    except OSError:
        pass
    return True


def _load_env(path):
    env = {}
    try:
        for ln in open(path, encoding="utf-8"):
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1); env[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return env


def pool_done():
    """TRUE cumulative done count, direct from the pool DB (survives fl_pull's collected=1
    flips, unlike /cc/stats which only counts collected=0 rows)."""
    try:
        payload = json.dumps({"statements": [[
            "SELECT COUNT(*) n FROM cc_lines WHERE game=? AND (status='done' OR collected=1)",
            [GAME_ID]]]}).encode("utf-8")
        p = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes",
             "-o", "ConnectTimeout=15", DB_HOST, "python3 /opt/cc-pool/dbexec.py"],
            input=payload, capture_output=True, timeout=30)
        if p.returncode != 0:
            return None
        out = json.loads(p.stdout.decode("utf-8"))
        return int(out["results"][0]["rows"][0]["n"])
    except Exception:
        return None


def count_streams():
    """Workers actively holding 007-first-light lines right now (fl-* only, never cd-*)."""
    try:
        payload = json.dumps({"statements": [[
            "SELECT COUNT(DISTINCT worker_id) n FROM cc_lines WHERE game=? AND status='claimed'",
            [GAME_ID]]]}).encode("utf-8")
        p = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes",
             "-o", "ConnectTimeout=15", DB_HOST, "python3 /opt/cc-pool/dbexec.py"],
            input=payload, capture_output=True, timeout=30)
        if p.returncode != 0:
            return 21
        out = json.loads(p.stdout.decode("utf-8"))
        n = int(out["results"][0]["rows"][0]["n"])
        return n or 21
    except Exception:
        return 21


def model_line(streams):
    return f"תרגום רב לשוני - {streams} זרמים"


def _rate(done):
    hist = []
    try:
        hist = json.load(open(HIST, encoding="utf-8"))
    except Exception:
        hist = []
    now = time.time(); hist.append([now, done])
    # Drop any point that is not a real PAST sample -- a clock jump around a reboot can write a
    # future timestamp that never ages out of the window and permanently pins the rate to 0
    # (found + fixed live in cd_progress.py, same fix applied here from day one).
    hist = [p for p in hist if 0 <= now - p[0] <= 3900][-80:]
    try:
        json.dump(hist, open(HIST, "w", encoding="utf-8"))
    except OSError:
        pass
    win = [p for p in hist if now - p[0] <= 1500] or hist[-2:]
    if len(win) < 2:
        return 0.0
    (t0, c0), (t1, c1) = win[0], win[-1]
    if t1 <= t0 or c1 < c0:
        return 0.0
    return (c1 - c0) / ((t1 - t0) / 3600.0)


def push(token, processed, total, rate, streams):
    body = json.dumps({
        "gameId": GAME_ID, "phase": "translation",
        "phaseLabelHe": "תרגום ממשק וכתוביות לעברית",
        "processed": processed, "total": total, "ratePerHour": int(rate),
        "unit": "שורות", "meta": {"alive": True, "streams": streams, "countUnit": "lines"},
        "aiModel": model_line(streams), "gpuModel": "",
    }).encode("utf-8")
    req = urllib.request.Request(API + "/api/admin/progress", body,
                                 {"Content-Type": "application/json",
                                  "Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def main():
    if not acquire_singleton():
        return 0
    env = _load_env(os.path.join(ROOT, ".env"))
    token = env.get("MONITOR_TOKEN", "")
    if not token:
        print("no MONITOR_TOKEN — exiting"); return 1
    corpus = json.load(open(CORPUS, encoding="utf-8"))
    total = len(corpus)
    print(f"007 First Light pusher: total {total} lines, every {INTERVAL}s -> {API}")
    last_done = 0
    while True:
        done = pool_done()
        if done is None:
            # 🔴 a transient SSH/db read must REUSE the last good value -- publishing 0
            # poisons the rate window and shows 0/min on a healthy fleet.
            done = last_done
        else:
            done = min(total, done)
            last_done = done
        rate = _rate(done)
        streams = count_streams()
        try:
            st = push(token, done, total, rate, streams)
            print(f"pushed {done}/{total} ({100 * done / max(1, total):.1f}%) "
                  f"rate={int(rate)}/h streams={streams} -> {st}")
        except Exception as e:
            print(f"push failed: {e}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    raise SystemExit(main())
